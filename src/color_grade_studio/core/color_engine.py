"""Color grading engine.

Pure-function transforms on BGR uint8 numpy arrays. All operations are vectorised
and can run on a full-resolution frame in tens of ms on a modern CPU.

Parameter convention:
    All inputs are normalised. Tonal sliders (exposure, contrast, saturation,
    temperature, tint, hue_shift, vignette, fade) accept -1.0 .. 1.0 except
    where noted. RGB triplets are absolute multipliers: lift defaults to 0,
    gamma to 1, gain to 1.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple

import cv2
import numpy as np

from .lut import Lut3D, apply_lut, compose, identity_lut


RGB = Tuple[float, float, float]


@dataclass
class GradeParams:
    """All parameters that define a final grade.

    A preset contributes its baseline values; manual sliders on top add or
    multiply with the preset (see :func:`combine`).
    """
    exposure: float = 0.0
    contrast: float = 0.0
    saturation: float = 0.0
    temperature: float = 0.0
    tint: float = 0.0
    shadows_rgb: RGB = (0.0, 0.0, 0.0)
    midtones_rgb: RGB = (1.0, 1.0, 1.0)
    highlights_rgb: RGB = (1.0, 1.0, 1.0)
    hue_shift: float = 0.0
    vignette: float = 0.0
    fade: float = 0.0

    # --- Engine v2 fields (additive; defaults are no-ops) -----------
    # Per-zone HSL: (hue_shift_deg, sat_mult, lum_mult).
    shadows_hsl: Tuple[float, float, float] = (0.0, 1.0, 1.0)
    midtones_hsl: Tuple[float, float, float] = (0.0, 1.0, 1.0)
    highlights_hsl: Tuple[float, float, float] = (0.0, 1.0, 1.0)
    # 5-point tone curve outputs at fixed inputs (0.0, 0.25, 0.5, 0.75, 1.0).
    tone_curve: Tuple[float, float, float, float, float] = (0.0, 0.25, 0.5, 0.75, 1.0)
    # Saturation multiplier per luminance zone: (shadows, mids, highlights).
    luma_sat: Tuple[float, float, float] = (1.0, 1.0, 1.0)
    # Red halation bloom strength (0..1).
    halation: float = 0.0

    def combine(self, manual: "GradeParams") -> "GradeParams":
        """Stack a manual adjustment on top of this (preset) baseline."""
        return GradeParams(
            exposure=self.exposure + manual.exposure,
            contrast=self.contrast + manual.contrast,
            saturation=self.saturation + manual.saturation,
            temperature=self.temperature + manual.temperature,
            tint=self.tint + manual.tint,
            shadows_rgb=_add3(self.shadows_rgb, manual.shadows_rgb),
            midtones_rgb=_mul3(self.midtones_rgb, manual.midtones_rgb),
            highlights_rgb=_mul3(self.highlights_rgb, manual.highlights_rgb),
            hue_shift=self.hue_shift + manual.hue_shift,
            vignette=max(self.vignette, manual.vignette),
            fade=max(self.fade, manual.fade),
            # v2 fields: not exposed via manual sliders, so the preset's values
            # pass through unchanged. Halation alone takes a max so a future
            # slider can only enhance — never reduce — the preset's bloom.
            shadows_hsl=self.shadows_hsl,
            midtones_hsl=self.midtones_hsl,
            highlights_hsl=self.highlights_hsl,
            tone_curve=self.tone_curve,
            luma_sat=self.luma_sat,
            halation=max(self.halation, manual.halation),
        )


def _add3(a: RGB, b: RGB) -> RGB:
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def _mul3(a: RGB, b: RGB) -> RGB:
    return (a[0] * b[0], a[1] * b[1], a[2] * b[2])


def apply_grade(frame_bgr: np.ndarray, params: GradeParams) -> np.ndarray:
    """Apply a full grade to a BGR uint8 frame and return a new BGR uint8 frame.

    The transform pipeline is deliberately fixed:
        exposure -> white balance -> lift/gamma/gain -> contrast ->
        saturation -> hue shift -> fade -> vignette

    Order matters: exposure first so later steps see a normalised brightness;
    contrast after L/G/G so the s-curve sits on the toned image; saturation
    after color shifts so the punch reflects the new palette.
    """
    if frame_bgr.dtype != np.uint8:
        raise TypeError(f"expected uint8 BGR frame, got {frame_bgr.dtype}")
    if frame_bgr.ndim != 3 or frame_bgr.shape[2] != 3:
        raise ValueError(f"expected HxWx3 frame, got shape {frame_bgr.shape}")

    f = frame_bgr.astype(np.float32) / 255.0
    f = _grade_float_bgr(f, params, include_vignette=True)
    return (f * 255.0 + 0.5).astype(np.uint8)


def _grade_float_bgr(
    frame_bgr_float: np.ndarray,
    params: GradeParams,
    *,
    include_vignette: bool = True,
) -> np.ndarray:
    """The core grade pipeline operating on float32 BGR in [0, 1].

    Vignette is position-dependent and cannot be expressed as a 3D LUT, so
    LUT-baking calls this with ``include_vignette=False`` and applies the
    vignette as a separate post-LUT step on the actual frame.
    """
    f = frame_bgr_float
    f = _exposure(f, params.exposure)
    f = _white_balance(f, params.temperature, params.tint)
    f = _tone_curve(f, params.tone_curve)
    f = _lift_gamma_gain(
        f,
        params.shadows_rgb,
        params.midtones_rgb,
        params.highlights_rgb,
    )
    f = _contrast(f, params.contrast)
    f = _three_way_hsl(
        f, params.shadows_hsl, params.midtones_hsl, params.highlights_hsl,
    )
    f = _luma_sat(f, params.luma_sat)
    f = _saturation(f, params.saturation)
    if abs(params.hue_shift) > 1e-4:
        f = _hue_shift(f, params.hue_shift)
    f = _halation(f, params.halation)
    if params.fade > 1e-4:
        f = _fade(f, params.fade)
    if include_vignette and params.vignette > 1e-4:
        f = _vignette(f, params.vignette)
    return np.clip(f, 0.0, 1.0)


def bake_grade_to_lut(params: GradeParams, size: int = 33) -> Lut3D:
    """Bake the color-only portion of a grade into a 3D LUT.

    Vignette is excluded because it depends on pixel position, not color.
    """
    ident = identity_lut(size)
    rgb_samples = ident.table.reshape(-1, 3)  # (N, 3) in RGB order
    bgr_samples = rgb_samples[:, ::-1].copy().reshape(-1, 1, 3)  # to BGR
    graded_bgr = _grade_float_bgr(bgr_samples, params, include_vignette=False)
    graded_rgb = graded_bgr.reshape(-1, 3)[:, ::-1].copy()
    table = graded_rgb.reshape(size, size, size, 3).astype(np.float32)
    return Lut3D(size=size, table=table, title="grade")


def compute_combined_lut(
    params: GradeParams,
    input_lut: Optional[Lut3D] = None,
    creative_lut: Optional[Lut3D] = None,
    size: int = 33,
) -> Lut3D:
    """Build one LUT that = input_lut ∘ creative_lut ∘ grade_params.

    The result can be applied to a frame to produce the same output as
    walking through each step in turn — but in a single trilinear lookup.
    This keeps preview and export pixel-perfect identical: preview calls
    :func:`apply_pipeline`, export writes the LUT to .cube and lets ffmpeg
    apply it via the ``lut3d`` filter.
    """
    work = identity_lut(size)
    if input_lut is not None:
        work = compose(work, input_lut, size=size)
    if creative_lut is not None:
        work = compose(work, creative_lut, size=size)
    # Now bake the programmatic grade on top.
    rgb_samples = work.table.reshape(-1, 3)
    bgr_samples = rgb_samples[:, ::-1].copy().reshape(-1, 1, 3)
    graded_bgr = _grade_float_bgr(bgr_samples, params, include_vignette=False)
    graded_rgb = graded_bgr.reshape(-1, 3)[:, ::-1].copy()
    return Lut3D(
        size=size,
        table=graded_rgb.reshape(size, size, size, 3).astype(np.float32),
        title="combined",
    )


def apply_pipeline(
    frame_bgr: np.ndarray,
    combined_lut: Lut3D,
    vignette: float = 0.0,
) -> np.ndarray:
    """Apply a pre-computed combined LUT (+ optional vignette) to a BGR uint8 frame."""
    if frame_bgr.dtype != np.uint8:
        raise TypeError(f"expected uint8 BGR frame, got {frame_bgr.dtype}")
    if frame_bgr.ndim != 3 or frame_bgr.shape[2] != 3:
        raise ValueError(f"expected HxWx3 frame, got shape {frame_bgr.shape}")
    f = frame_bgr.astype(np.float32) / 255.0
    rgb = f[..., ::-1]  # BGR -> RGB for LUT lookup
    rgb_out = apply_lut(rgb, combined_lut)
    bgr_out = rgb_out[..., ::-1]
    if vignette > 1e-4:
        bgr_out = _vignette(bgr_out, vignette)
    bgr_out = np.clip(bgr_out, 0.0, 1.0)
    return (bgr_out * 255.0 + 0.5).astype(np.uint8)


def _exposure(f: np.ndarray, ev: float) -> np.ndarray:
    if abs(ev) < 1e-4:
        return f
    # ev in [-1, 1] mapped to roughly +/-1.5 stops
    factor = 2.0 ** (ev * 1.5)
    return f * factor


def _white_balance(f: np.ndarray, temperature: float, tint: float) -> np.ndarray:
    # OpenCV BGR ordering.
    if abs(temperature) < 1e-4 and abs(tint) < 1e-4:
        return f
    b_gain = 1.0 - 0.30 * temperature
    r_gain = 1.0 + 0.30 * temperature
    g_gain = 1.0 - 0.20 * tint
    rb_correction = 1.0 + 0.10 * tint
    out = f.copy()
    out[..., 0] *= b_gain * rb_correction
    out[..., 1] *= g_gain
    out[..., 2] *= r_gain * rb_correction
    return out


def _lift_gamma_gain(
    f: np.ndarray,
    lift_bgr: RGB,
    gamma_bgr: RGB,
    gain_bgr: RGB,
) -> np.ndarray:
    """Lift/Gamma/Gain in BGR order.

    Lift raises the black point (added before gamma), gamma reshapes midtones,
    gain scales the white point.
    """
    if (
        lift_bgr == (0.0, 0.0, 0.0)
        and gamma_bgr == (1.0, 1.0, 1.0)
        and gain_bgr == (1.0, 1.0, 1.0)
    ):
        return f
    out = f.copy()
    for i in range(3):
        ch = out[..., i]
        lift = lift_bgr[i]
        gamma = max(gamma_bgr[i], 0.05)
        gain = gain_bgr[i]
        ch = (ch + lift) * gain
        ch = np.clip(ch, 0.0, None)
        ch = np.power(ch, 1.0 / gamma)
        out[..., i] = ch
    return out


def _contrast(f: np.ndarray, amount: float) -> np.ndarray:
    if abs(amount) < 1e-4:
        return f
    # amount in [-1, 1]; sigmoid-like s-curve around 0.5
    if amount >= 0:
        k = 1.0 + amount * 3.0
        s = 1.0 / (1.0 + np.exp(-k * (f - 0.5)))
        s_min = 1.0 / (1.0 + np.exp(0.5 * k))
        s_max = 1.0 / (1.0 + np.exp(-0.5 * k))
        return (s - s_min) / max(s_max - s_min, 1e-6)
    # negative amount = pull contrast down (flatten)
    flat = 0.5 + (f - 0.5) * (1.0 + amount * 0.8)
    return flat


def _catmull_rom(
    x_ctrl: np.ndarray,
    y_ctrl: np.ndarray,
    x_eval: np.ndarray,
) -> np.ndarray:
    """Sample a monotonic cubic spline at x_eval given control points.

    Fritsch-Carlson PCHIP tangent rule: at each interior point the tangent
    is the harmonic mean of the adjacent secants, clipped to zero where the
    secants change sign. This guarantees the interpolated curve is
    monotonic on every segment where consecutive y-values are monotonic.
    Endpoints fall back to the adjacent secant.
    """
    n = len(x_ctrl)
    out = np.empty_like(x_eval)
    for j, xe in enumerate(x_eval):
        i = int(np.clip(np.searchsorted(x_ctrl, xe) - 1, 0, n - 2))
        x0, x1 = float(x_ctrl[i]), float(x_ctrl[i + 1])
        y0, y1 = float(y_ctrl[i]), float(y_ctrl[i + 1])
        h = x1 - x0 if (x1 - x0) > 1e-9 else 1e-9
        t = (xe - x0) / h
        # Fritsch-Carlson PCHIP tangents — preserve monotonicity by clipping
        # tangent magnitude where adjacent secants change sign or differ a lot.
        d_curr = (y1 - y0) / h  # secant of current segment, per-unit-x
        # Endpoint tangents fall back to the adjacent secant.
        if i == 0:
            m0 = d_curr
        else:
            d_prev = (y_ctrl[i] - y_ctrl[i - 1]) / (x_ctrl[i] - x_ctrl[i - 1])
            if d_prev * d_curr <= 0:
                m0 = 0.0  # extremum at the control point
            else:
                m0 = 3 * d_prev * d_curr / (2 * d_curr + d_prev)
        m0 *= h  # rescale to Hermite basis convention (per-segment units)
        if i == n - 2:
            m1 = d_curr
        else:
            d_next = (y_ctrl[i + 2] - y_ctrl[i + 1]) / (x_ctrl[i + 2] - x_ctrl[i + 1])
            if d_curr * d_next <= 0:
                m1 = 0.0
            else:
                m1 = 3 * d_curr * d_next / (2 * d_next + d_curr)
        m1 *= h
        h00 = 2 * t**3 - 3 * t**2 + 1
        h10 = t**3 - 2 * t**2 + t
        h01 = -2 * t**3 + 3 * t**2
        h11 = t**3 - t**2
        out[j] = h00 * y0 + h10 * m0 + h01 * y1 + h11 * m1
    return out


def _tone_curve(
    f: np.ndarray,
    pts: Tuple[float, float, float, float, float],
) -> np.ndarray:
    """Apply a 5-point monotonic curve to every channel via a 256-entry LUT.

    Inputs are clamped to [0, 1]; outputs are clamped to [0, 1] after the
    curve. The 5 control points are placed at fixed input positions 0.0,
    0.25, 0.5, 0.75, 1.0; the function interpolates a smooth, monotonic
    PCHIP cubic curve between them.
    """
    if pts == (0.0, 0.25, 0.5, 0.75, 1.0):
        return f  # identity
    x_pts = np.array([0.0, 0.25, 0.5, 0.75, 1.0], dtype=np.float32)
    y_pts = np.array(pts, dtype=np.float32)
    sample_x = np.linspace(0.0, 1.0, 256, dtype=np.float32)
    table = _catmull_rom(x_pts, y_pts, sample_x)
    table = np.clip(table, 0.0, 1.0).astype(np.float32)
    idx = np.clip(np.round(f * 255.0).astype(np.int32), 0, 255)
    return table[idx]


def _three_way_hsl(
    f: np.ndarray,
    shadows: Tuple[float, float, float],
    midtones: Tuple[float, float, float],
    highlights: Tuple[float, float, float],
) -> np.ndarray:
    """Independent HSL (hue_shift_deg, sat_mult, lum_mult) for each zone.

    Zone masks are smooth sigmoid-style windows over luminance:
      shadows:    weight peaks near L=0.15, falls off by L=0.45
      midtones:   weight peaks near L=0.50, falls off at both ends
      highlights: weight peaks near L=0.85, falls off below L=0.55

    A pixel's contribution from each zone is its mask weight; the per-zone
    HSL shifts are blended additively (for hue/sat in HSV space) then
    re-composited.
    """
    if (shadows == (0.0, 1.0, 1.0)
            and midtones == (0.0, 1.0, 1.0)
            and highlights == (0.0, 1.0, 1.0)):
        return f

    bgr = np.clip(f, 0.0, 1.0).astype(np.float32)
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
    h_ch = hsv[..., 0]  # 0..360
    s_ch = hsv[..., 1]  # 0..1
    v_ch = hsv[..., 2]  # 0..1 - proxy for luminance, fine for our masks

    # Smooth zone masks summing to ~1 everywhere.
    w_shadow = np.exp(-((v_ch - 0.15) ** 2) / 0.045)
    w_mid = np.exp(-((v_ch - 0.50) ** 2) / 0.075)
    w_high = np.exp(-((v_ch - 0.85) ** 2) / 0.045)
    w_total = w_shadow + w_mid + w_high + 1e-6
    w_shadow /= w_total
    w_mid /= w_total
    w_high /= w_total

    hue_shift = (
        w_shadow * shadows[0] + w_mid * midtones[0] + w_high * highlights[0]
    )
    sat_mult = (
        w_shadow * shadows[1] + w_mid * midtones[1] + w_high * highlights[1]
    )
    lum_mult = (
        w_shadow * shadows[2] + w_mid * midtones[2] + w_high * highlights[2]
    )

    h_out = (h_ch + hue_shift) % 360.0
    s_out = np.clip(s_ch * sat_mult, 0.0, 1.0)
    v_out = np.clip(v_ch * lum_mult, 0.0, 1.0)

    hsv_out = np.stack([h_out, s_out, v_out], axis=-1).astype(np.float32)
    return cv2.cvtColor(hsv_out, cv2.COLOR_HSV2BGR)


def _luma_sat(
    f: np.ndarray,
    luma_sat: Tuple[float, float, float],
) -> np.ndarray:
    """Multiply saturation by a luminance-indexed weight.

    luma_sat = (sat_shadows, sat_mids, sat_highlights). Same smooth Gaussian
    zone masks as :func:`_three_way_hsl` blend the transitions.
    """
    if luma_sat == (1.0, 1.0, 1.0):
        return f

    bgr = np.clip(f, 0.0, 1.0).astype(np.float32)
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
    v = hsv[..., 2]

    w_s = np.exp(-((v - 0.15) ** 2) / 0.045)
    w_m = np.exp(-((v - 0.50) ** 2) / 0.075)
    w_h = np.exp(-((v - 0.85) ** 2) / 0.045)
    w_total = w_s + w_m + w_h + 1e-6
    sat_mult = (
        w_s * luma_sat[0] + w_m * luma_sat[1] + w_h * luma_sat[2]
    ) / w_total
    hsv[..., 1] = np.clip(hsv[..., 1] * sat_mult, 0.0, 1.0)
    return cv2.cvtColor(hsv, cv2.COLOR_HSV2BGR)


def _halation(f: np.ndarray, amount: float) -> np.ndarray:
    """Add a soft red bloom around the brightest pixels (Kodak-like halation).

    amount in [0, 1]. Builds a luminance mask of bright pixels (> 0.65),
    Gaussian-blurs it, and adds it weighted into the red channel. Other
    channels get a fraction of the bloom for a warm glow.
    """
    amount = float(np.clip(amount, 0.0, 1.0))
    if amount < 1e-4:
        return f

    bgr = np.clip(f, 0.0, 1.0).astype(np.float32)
    # Luminance from BGR (Rec.601 weights for speed; visually fine here).
    lum = 0.114 * bgr[..., 0] + 0.587 * bgr[..., 1] + 0.299 * bgr[..., 2]
    mask = np.clip((lum - 0.65) / 0.35, 0.0, 1.0)
    # Gaussian blur — kernel scales with image; 21x21 works well at HD.
    blurred = cv2.GaussianBlur(mask, (21, 21), sigmaX=7.0)

    out = bgr.copy()
    out[..., 2] += blurred * amount * 0.55   # red (strongest)
    out[..., 1] += blurred * amount * 0.18   # green
    out[..., 0] += blurred * amount * 0.06   # blue
    return np.clip(out, 0.0, 1.0)


def _saturation(f: np.ndarray, amount: float) -> np.ndarray:
    if abs(amount) < 1e-4:
        return f
    bgr = np.clip(f, 0.0, 1.0)
    hsv = cv2.cvtColor(bgr.astype(np.float32), cv2.COLOR_BGR2HSV)
    factor = 1.0 + amount  # -1 = monochrome, +1 = double saturation
    hsv[..., 1] = np.clip(hsv[..., 1] * factor, 0.0, 1.0)
    return cv2.cvtColor(hsv, cv2.COLOR_HSV2BGR)


def _hue_shift(f: np.ndarray, amount: float) -> np.ndarray:
    bgr = np.clip(f, 0.0, 1.0)
    hsv = cv2.cvtColor(bgr.astype(np.float32), cv2.COLOR_BGR2HSV)
    # OpenCV HSV hue is 0..360 in float32. amount in [-1,1] mapped to +/-30 deg.
    hsv[..., 0] = (hsv[..., 0] + amount * 30.0) % 360.0
    return cv2.cvtColor(hsv, cv2.COLOR_HSV2BGR)


def _fade(f: np.ndarray, amount: float) -> np.ndarray:
    # Lift blacks, pull whites down a touch -> classic faded film look.
    amount = float(np.clip(amount, 0.0, 1.0))
    low = 0.08 * amount
    high = 1.0 - 0.04 * amount
    return f * (high - low) + low


_VIGNETTE_CACHE: dict = {}


def _vignette(f: np.ndarray, amount: float) -> np.ndarray:
    amount = float(np.clip(amount, 0.0, 1.0))
    h, w = f.shape[:2]
    key = (h, w)
    mask = _VIGNETTE_CACHE.get(key)
    if mask is None:
        yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
        cx, cy = w / 2.0, h / 2.0
        d = np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2)
        d_norm = d / np.sqrt(cx * cx + cy * cy)
        mask = np.clip(1.0 - d_norm ** 2 * 1.1, 0.0, 1.0)
        _VIGNETTE_CACHE[key] = mask
    # blend between 1.0 (no darkening) and the mask
    blend = 1.0 - amount + amount * mask
    return f * blend[..., None]
