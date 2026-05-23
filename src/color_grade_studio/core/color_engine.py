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

from dataclasses import dataclass, field, replace
from typing import Tuple

import cv2
import numpy as np


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

    f = _exposure(f, params.exposure)
    f = _white_balance(f, params.temperature, params.tint)
    f = _lift_gamma_gain(
        f,
        params.shadows_rgb,
        params.midtones_rgb,
        params.highlights_rgb,
    )
    f = _contrast(f, params.contrast)
    f = _saturation(f, params.saturation)
    if abs(params.hue_shift) > 1e-4:
        f = _hue_shift(f, params.hue_shift)
    if params.fade > 1e-4:
        f = _fade(f, params.fade)
    if params.vignette > 1e-4:
        f = _vignette(f, params.vignette)

    f = np.clip(f, 0.0, 1.0)
    return (f * 255.0 + 0.5).astype(np.uint8)


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
