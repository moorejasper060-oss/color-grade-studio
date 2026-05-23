# Color Engine v2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend the color engine with 3-way HSL color, tone curve, luma-based saturation, and halation; then retune all 10 cinematic presets using the richer vocabulary so they feel professional grade.

**Architecture:** Four new optional fields on `GradeParams`. Four new transform functions in `color_engine.py`, inserted into the existing pipeline. All defaults are no-ops so old `GradeParams` instances keep producing identical output. A new `tools/profile_lut.py` reads any `.cube` file, applies it to test patches, and prints measured per-zone shifts — used as a tuning target for each preset.

**Tech Stack:** Python 3.10+, NumPy, OpenCV (cv2.LUT, cv2.GaussianBlur, cv2.cvtColor), pytest. No new third-party dependencies.

---

## File Structure

**Modify:**
- `src/color_grade_studio/core/color_engine.py` — add fields to `GradeParams`, add four transform helpers, splice them into `_grade_float_bgr`
- `src/color_grade_studio/core/presets.py` — retune all 10 presets using the new fields
- `tests/test_color_engine.py` — add per-transform tests + tighten preset signature tests
- `.gitignore` — ignore `refs/`

**Create:**
- `tools/profile_lut.py` — CLI tool that profiles a `.cube`

**Out of scope:**
- New UI widgets (the existing preset panel handles any preset count and respects tooltips)
- LUT redistribution (reference LUTs live in a local `refs/` directory only, gitignored)

---

## Task 1: Add new fields to GradeParams (no-op defaults)

**Files:**
- Modify: `src/color_grade_studio/core/color_engine.py` (GradeParams dataclass)
- Modify: `tests/test_color_engine.py`

- [ ] **Step 1: Read the current GradeParams dataclass**

Read `src/color_grade_studio/core/color_engine.py` lines 22–60 so you know the existing shape. Key types: `RGB = Tuple[float, float, float]`.

- [ ] **Step 2: Write a failing test that constructs GradeParams with the new fields**

Add to `tests/test_color_engine.py`:

```python
def test_grade_params_accepts_new_fields():
    """Engine v2: GradeParams must accept new fields, all with no-op defaults."""
    p = GradeParams(
        shadows_hsl=(10.0, 1.2, 0.95),
        midtones_hsl=(0.0, 1.0, 1.0),
        highlights_hsl=(-8.0, 1.1, 1.03),
        tone_curve=(0.04, 0.20, 0.52, 0.78, 0.98),
        luma_sat=(0.85, 1.18, 1.05),
        halation=0.25,
    )
    assert p.shadows_hsl == (10.0, 1.2, 0.95)
    assert p.highlights_hsl[0] == -8.0
    assert p.halation == 0.25
    # Defaults are no-op:
    d = GradeParams()
    assert d.shadows_hsl == (0.0, 1.0, 1.0)
    assert d.midtones_hsl == (0.0, 1.0, 1.0)
    assert d.highlights_hsl == (0.0, 1.0, 1.0)
    assert d.tone_curve == (0.0, 0.25, 0.5, 0.75, 1.0)
    assert d.luma_sat == (1.0, 1.0, 1.0)
    assert d.halation == 0.0
```

- [ ] **Step 3: Run — expect failure**

Run: `python -m pytest tests/test_color_engine.py::test_grade_params_accepts_new_fields -v`
Expected: FAIL — "unexpected keyword argument 'shadows_hsl'"

- [ ] **Step 4: Add fields to GradeParams**

In `src/color_grade_studio/core/color_engine.py`, find the `GradeParams` dataclass. Add these fields just before the `combine` method:

```python
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
```

- [ ] **Step 5: Update GradeParams.combine() to merge the new fields**

Replace the existing `combine` method body so the new fields stack correctly. Use additive for shifts (hue/curve offsets) and multiplicative for gains (sat/lum). For halation, take the max. For the tone curve, take the input preset's curve (manual sliders don't expose a curve).

Replace:

```python
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
```

with:

```python
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
            shadows_hsl=self.shadows_hsl,
            midtones_hsl=self.midtones_hsl,
            highlights_hsl=self.highlights_hsl,
            tone_curve=self.tone_curve,
            luma_sat=self.luma_sat,
            halation=max(self.halation, manual.halation),
        )
```

(Sliders don't touch the v2 fields — they remain whatever the preset set them to.)

- [ ] **Step 6: Run — expect pass**

Run: `python -m pytest tests/test_color_engine.py::test_grade_params_accepts_new_fields -v`
Expected: PASS.

- [ ] **Step 7: Run the full suite to confirm nothing else broke**

Run: `python -m pytest`
Expected: 55 passed (54 existing + 1 new).

- [ ] **Step 8: Commit**

```bash
git add src/color_grade_studio/core/color_engine.py tests/test_color_engine.py
git commit -m "Engine v2: add HSL/tone_curve/luma_sat/halation fields to GradeParams"
```

---

## Task 2: Implement `_tone_curve` transform

**Files:**
- Modify: `src/color_grade_studio/core/color_engine.py`
- Modify: `tests/test_color_engine.py`

Tone curve maps input intensity to output intensity via 5 control points. Builds a 256-entry LUT once per call via monotonic Catmull-Rom interpolation, then applies it with `cv2.LUT`.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_color_engine.py`:

```python
def test_tone_curve_identity_is_noop():
    """Default tone_curve must not change pixels (within rounding)."""
    from color_grade_studio.core.color_engine import _tone_curve
    import numpy as np
    rng = np.random.default_rng(1)
    img = rng.random((16, 24, 3), dtype=np.float32)
    out = _tone_curve(img, (0.0, 0.25, 0.5, 0.75, 1.0))
    np.testing.assert_allclose(out, img, atol=2e-3)


def test_tone_curve_lifts_midtones():
    """Bumping the mid-output above 0.5 lifts mid-grays."""
    from color_grade_studio.core.color_engine import _tone_curve
    import numpy as np
    img = np.full((4, 4, 3), 0.5, dtype=np.float32)
    out = _tone_curve(img, (0.0, 0.25, 0.65, 0.85, 1.0))  # mid 0.5 -> 0.65
    # Output of the mid grays should be ~0.65, up from 0.5.
    assert out.mean() > 0.6


def test_tone_curve_crushes_blacks():
    """Lowering low-mid-output crushes shadows."""
    from color_grade_studio.core.color_engine import _tone_curve
    import numpy as np
    img = np.full((4, 4, 3), 0.25, dtype=np.float32)
    out = _tone_curve(img, (0.0, 0.10, 0.5, 0.75, 1.0))  # lo_mid 0.25 -> 0.10
    assert out.mean() < 0.20
```

- [ ] **Step 2: Run — expect failure (no `_tone_curve` yet)**

Run: `python -m pytest tests/test_color_engine.py -k tone_curve -v`
Expected: FAIL — `ImportError: cannot import name '_tone_curve'`

- [ ] **Step 3: Implement `_tone_curve` in color_engine.py**

Add this private helper to `src/color_grade_studio/core/color_engine.py`, immediately after `_contrast`:

```python
def _tone_curve(
    f: np.ndarray,
    pts: Tuple[float, float, float, float, float],
) -> np.ndarray:
    """Apply a 5-point monotonic curve to every channel via a 256-entry LUT.

    Inputs are clamped to [0, 1]; outputs are clamped to [0, 1] after the
    curve. The 5 control points are placed at fixed input positions 0.0,
    0.25, 0.5, 0.75, 1.0; the function interpolates a smooth, monotonic
    Catmull-Rom curve between them.
    """
    if pts == (0.0, 0.25, 0.5, 0.75, 1.0):
        return f  # identity
    x_pts = np.array([0.0, 0.25, 0.5, 0.75, 1.0], dtype=np.float32)
    y_pts = np.array(pts, dtype=np.float32)
    sample_x = np.linspace(0.0, 1.0, 256, dtype=np.float32)
    table = _catmull_rom(x_pts, y_pts, sample_x)
    table = np.clip(table, 0.0, 1.0).astype(np.float32)
    # Look up — vectorised; f is in [0,1] so we map to [0,255] indices.
    idx = np.clip((f * 255.0).astype(np.int32), 0, 255)
    return table[idx]


def _catmull_rom(
    x_ctrl: np.ndarray,
    y_ctrl: np.ndarray,
    x_eval: np.ndarray,
) -> np.ndarray:
    """Sample a monotonic Catmull-Rom spline at x_eval given control points.

    Uniform-parameterised Catmull-Rom; the tangent at each control point is
    half the slope between its neighbours. Endpoints clamp their tangent to
    the adjacent secant. Guaranteed monotonic when consecutive y-values are.
    """
    n = len(x_ctrl)
    out = np.empty_like(x_eval)
    for j, xe in enumerate(x_eval):
        # Find segment i such that x_ctrl[i] <= xe < x_ctrl[i+1].
        i = int(np.clip(np.searchsorted(x_ctrl, xe) - 1, 0, n - 2))
        x0, x1 = float(x_ctrl[i]), float(x_ctrl[i + 1])
        y0, y1 = float(y_ctrl[i]), float(y_ctrl[i + 1])
        h = x1 - x0 if (x1 - x0) > 1e-9 else 1e-9
        t = (xe - x0) / h
        # Tangents (half-slope on each side; clamped at endpoints).
        if i > 0:
            m0 = 0.5 * (y_ctrl[i + 1] - y_ctrl[i - 1]) * (h / (x_ctrl[i + 1] - x_ctrl[i - 1]))
        else:
            m0 = (y1 - y0)
        if i < n - 2:
            m1 = 0.5 * (y_ctrl[i + 2] - y_ctrl[i]) * (h / (x_ctrl[i + 2] - x_ctrl[i]))
        else:
            m1 = (y1 - y0)
        # Hermite blend.
        h00 = 2 * t**3 - 3 * t**2 + 1
        h10 = t**3 - 2 * t**2 + t
        h01 = -2 * t**3 + 3 * t**2
        h11 = t**3 - t**2
        out[j] = h00 * y0 + h10 * m0 + h01 * y1 + h11 * m1
    return out
```

- [ ] **Step 4: Run — expect pass**

Run: `python -m pytest tests/test_color_engine.py -k tone_curve -v`
Expected: PASS for all 3 tone_curve tests.

- [ ] **Step 5: Commit**

```bash
git add src/color_grade_studio/core/color_engine.py tests/test_color_engine.py
git commit -m "Engine v2: tone_curve via 5-point Catmull-Rom (256-LUT)"
```

---

## Task 3: Implement `_three_way_hsl` transform

**Files:**
- Modify: `src/color_grade_studio/core/color_engine.py`
- Modify: `tests/test_color_engine.py`

Three independent HSL shifts (one per zone), each applied with a smooth luminance mask.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_color_engine.py`:

```python
def test_three_way_hsl_identity_is_noop():
    """All-default per-zone HSL produces no change."""
    from color_grade_studio.core.color_engine import _three_way_hsl
    import numpy as np
    rng = np.random.default_rng(2)
    img = rng.random((16, 24, 3), dtype=np.float32)
    out = _three_way_hsl(img, (0.0, 1.0, 1.0), (0.0, 1.0, 1.0), (0.0, 1.0, 1.0))
    np.testing.assert_allclose(out, img, atol=2e-3)


def test_three_way_hsl_shadows_only_affects_dark_pixels():
    """A shadow saturation crush should mostly affect dark pixels."""
    from color_grade_studio.core.color_engine import _three_way_hsl
    import numpy as np
    # Build a frame with a dark warm patch (top half) and bright warm patch (bottom).
    dark = np.full((8, 16, 3), [0.4, 0.5, 0.7], dtype=np.float32)   # BGR
    bright = np.full((8, 16, 3), [0.7, 0.8, 0.9], dtype=np.float32)
    img = np.concatenate([dark, bright], axis=0)
    out = _three_way_hsl(img,
                         shadows=(0.0, 0.0, 1.0),  # zero shadow saturation
                         midtones=(0.0, 1.0, 1.0),
                         highlights=(0.0, 1.0, 1.0))
    # Top half (dark) should be much closer to gray than the bottom half.
    top_chroma = float(out[:8].max(axis=-1).mean() - out[:8].min(axis=-1).mean())
    bot_chroma = float(out[8:].max(axis=-1).mean() - out[8:].min(axis=-1).mean())
    assert top_chroma < bot_chroma * 0.6
```

- [ ] **Step 2: Run — expect failure (no `_three_way_hsl` yet)**

Run: `python -m pytest tests/test_color_engine.py -k three_way_hsl -v`
Expected: FAIL — ImportError.

- [ ] **Step 3: Implement `_three_way_hsl`**

Add to `src/color_grade_studio/core/color_engine.py`, after `_tone_curve`:

```python
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
    v_ch = hsv[..., 2]  # 0..1 — proxy for luminance, fine for our masks

    # Smooth zone masks summing to ~1 everywhere.
    w_shadow = np.exp(-((v_ch - 0.15) ** 2) / 0.045)
    w_mid = np.exp(-((v_ch - 0.50) ** 2) / 0.075)
    w_high = np.exp(-((v_ch - 0.85) ** 2) / 0.045)
    w_total = w_shadow + w_mid + w_high + 1e-6
    w_shadow /= w_total
    w_mid /= w_total
    w_high /= w_total

    # Combine per-zone shifts.
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
```

- [ ] **Step 4: Run — expect pass**

Run: `python -m pytest tests/test_color_engine.py -k three_way_hsl -v`
Expected: PASS for both tests.

- [ ] **Step 5: Commit**

```bash
git add src/color_grade_studio/core/color_engine.py tests/test_color_engine.py
git commit -m "Engine v2: 3-way HSL color correction with smooth zone masks"
```

---

## Task 4: Implement `_luma_sat` transform

**Files:**
- Modify: `src/color_grade_studio/core/color_engine.py`
- Modify: `tests/test_color_engine.py`

Saturation multiplier indexed by per-pixel luminance — same smooth zone masks as 3-way HSL.

- [ ] **Step 1: Write the failing test**

```python
def test_luma_sat_identity_is_noop():
    from color_grade_studio.core.color_engine import _luma_sat
    import numpy as np
    rng = np.random.default_rng(3)
    img = rng.random((12, 12, 3), dtype=np.float32)
    out = _luma_sat(img, (1.0, 1.0, 1.0))
    np.testing.assert_allclose(out, img, atol=2e-3)


def test_luma_sat_crushes_shadow_saturation():
    """Zero shadow sat should desaturate dark pixels but leave bright ones."""
    from color_grade_studio.core.color_engine import _luma_sat
    import numpy as np
    dark = np.full((4, 8, 3), [0.4, 0.5, 0.7], dtype=np.float32)
    bright = np.full((4, 8, 3), [0.7, 0.8, 0.9], dtype=np.float32)
    img = np.concatenate([dark, bright], axis=0)
    out = _luma_sat(img, (0.0, 1.0, 1.0))  # zero shadow saturation
    top_chroma = float(out[:4].max(axis=-1).mean() - out[:4].min(axis=-1).mean())
    bot_chroma = float(out[4:].max(axis=-1).mean() - out[4:].min(axis=-1).mean())
    assert top_chroma < bot_chroma * 0.6
```

- [ ] **Step 2: Run — expect failure**

Run: `python -m pytest tests/test_color_engine.py -k luma_sat -v`
Expected: FAIL — ImportError.

- [ ] **Step 3: Implement `_luma_sat`**

Add to `src/color_grade_studio/core/color_engine.py`, after `_three_way_hsl`:

```python
def _luma_sat(
    f: np.ndarray,
    luma_sat: Tuple[float, float, float],
) -> np.ndarray:
    """Multiply saturation by a luminance-indexed weight.

    luma_sat = (sat_shadows, sat_mids, sat_highlights). Pixels in each zone
    get their saturation scaled by the matching multiplier; the same smooth
    sigmoid windows as :func:`_three_way_hsl` blend the transitions.
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
```

- [ ] **Step 4: Run — expect pass**

Run: `python -m pytest tests/test_color_engine.py -k luma_sat -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/color_grade_studio/core/color_engine.py tests/test_color_engine.py
git commit -m "Engine v2: per-zone saturation by luminance"
```

---

## Task 5: Implement `_halation` transform

**Files:**
- Modify: `src/color_grade_studio/core/color_engine.py`
- Modify: `tests/test_color_engine.py`

Halation = blurred bright-red mask added to the highlights. Cheap convolution; tone the strength via the `halation` scalar.

- [ ] **Step 1: Write the failing test**

```python
def test_halation_identity_is_noop():
    from color_grade_studio.core.color_engine import _halation
    import numpy as np
    rng = np.random.default_rng(4)
    img = rng.random((16, 16, 3), dtype=np.float32)
    out = _halation(img, 0.0)
    np.testing.assert_allclose(out, img, atol=1e-6)


def test_halation_glows_bright_red_into_neighbours():
    """A bright white spot in the middle should brighten the red channel of nearby pixels."""
    from color_grade_studio.core.color_engine import _halation
    import numpy as np
    img = np.zeros((32, 32, 3), dtype=np.float32)
    img[14:18, 14:18] = 1.0  # bright white square
    out = _halation(img, 0.6)
    # Pixel adjacent to the bright square — original was 0, now should have red.
    near_red = out[12, 16, 2]   # BGR: red is channel 2
    near_green = out[12, 16, 1]
    assert near_red > 0.05
    assert near_red > near_green, "halation should bloom red preferentially"
```

- [ ] **Step 2: Run — expect failure**

Run: `python -m pytest tests/test_color_engine.py -k halation -v`
Expected: FAIL — ImportError.

- [ ] **Step 3: Implement `_halation`**

Add to `src/color_grade_studio/core/color_engine.py`, after `_luma_sat`:

```python
def _halation(f: np.ndarray, amount: float) -> np.ndarray:
    """Add a soft red bloom around the brightest pixels (Kodak-like halation).

    amount in [0, 1]. Builds a luminance mask of bright pixels (> 0.7),
    Gaussian-blurs it, and adds it weighted into the red channel of the
    image. Other channels get a fraction of the bloom for a warm glow.
    """
    amount = float(np.clip(amount, 0.0, 1.0))
    if amount < 1e-4:
        return f

    bgr = np.clip(f, 0.0, 1.0).astype(np.float32)
    # Luminance from BGR (Rec.601 weights for speed; visually fine here).
    lum = 0.114 * bgr[..., 0] + 0.587 * bgr[..., 1] + 0.299 * bgr[..., 2]
    # Mask of bright pixels.
    mask = np.clip((lum - 0.65) / 0.35, 0.0, 1.0)
    # Gaussian blur — kernel size scales with image; 21x21 works well at HD.
    blurred = cv2.GaussianBlur(mask, (21, 21), sigmaX=7.0)

    out = bgr.copy()
    # Red bloom strongest, green half, blue quarter — gives the warm halation tint.
    out[..., 2] += blurred * amount * 0.55          # red
    out[..., 1] += blurred * amount * 0.18          # green
    out[..., 0] += blurred * amount * 0.06          # blue
    return np.clip(out, 0.0, 1.0)
```

- [ ] **Step 4: Run — expect pass**

Run: `python -m pytest tests/test_color_engine.py -k halation -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/color_grade_studio/core/color_engine.py tests/test_color_engine.py
git commit -m "Engine v2: red halation bloom"
```

---

## Task 6: Splice the new transforms into the pipeline

**Files:**
- Modify: `src/color_grade_studio/core/color_engine.py` (`_grade_float_bgr`)
- Modify: `tests/test_color_engine.py`

- [ ] **Step 1: Write a test that proves a v2-only param actually shifts pixels**

```python
def test_pipeline_includes_three_way_hsl():
    """Setting only shadows_hsl on GradeParams should change the output."""
    params = GradeParams(shadows_hsl=(0.0, 0.0, 1.0))  # crush shadow saturation
    frame = np.full((8, 8, 3), [40, 80, 160], dtype=np.uint8)  # dark warm
    out = apply_grade(frame, params)
    chroma_before = int(frame.max(axis=-1).mean() - frame.min(axis=-1).mean())
    chroma_after = int(out.max(axis=-1).mean() - out.min(axis=-1).mean())
    assert chroma_after < chroma_before * 0.6, \
        "shadow sat=0 should significantly desaturate dark pixels"


def test_pipeline_includes_tone_curve():
    """Lifting the lo_mid output via tone_curve should brighten dark pixels."""
    dark = GradeParams(tone_curve=(0.0, 0.45, 0.6, 0.8, 1.0))  # lifted blacks
    frame = np.full((8, 8, 3), 64, dtype=np.uint8)  # 0.25
    out = apply_grade(frame, dark)
    assert out.mean() > 90, f"expected lifted shadow, got {out.mean()}"


def test_pipeline_includes_halation():
    """A bright frame with halation > 0 should brighten red noticeably."""
    img = np.full((16, 16, 3), 200, dtype=np.uint8)  # bright neutral
    base = apply_grade(img, GradeParams())
    haloed = apply_grade(img, GradeParams(halation=0.8))
    assert haloed[..., 2].mean() > base[..., 2].mean()
```

- [ ] **Step 2: Run — expect failure (transforms exist but aren't called from the pipeline yet)**

Run: `python -m pytest tests/test_color_engine.py -k pipeline_includes -v`
Expected: FAIL.

- [ ] **Step 3: Update `_grade_float_bgr` to call the new transforms in order**

Replace the body of `_grade_float_bgr` in `src/color_grade_studio/core/color_engine.py`:

```python
def _grade_float_bgr(
    frame_bgr_float: np.ndarray,
    params: GradeParams,
    *,
    include_vignette: bool = True,
) -> np.ndarray:
    """The core grade pipeline operating on float32 BGR in [0, 1]."""
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
```

- [ ] **Step 4: Run — expect pass**

Run: `python -m pytest tests/test_color_engine.py -k pipeline_includes -v`
Expected: PASS for all 3.

- [ ] **Step 5: Run the full suite — ensure no regressions**

Run: `python -m pytest`
Expected: all tests pass. The existing v1 tests must still pass because the new fields default to no-op.

- [ ] **Step 6: Commit**

```bash
git add src/color_grade_studio/core/color_engine.py tests/test_color_engine.py
git commit -m "Engine v2: splice new transforms into the grade pipeline"
```

---

## Task 7: Profile-LUT tool

**Files:**
- Create: `tools/profile_lut.py`
- Modify: `.gitignore`

Reads any `.cube`, applies it to canonical test patches, prints measured per-zone shifts in `GradeParams`-compatible format.

- [ ] **Step 1: Add `refs/` to .gitignore**

Edit `.gitignore` and add the line:

```
refs/
```

at the end (or wherever fits).

- [ ] **Step 2: Create `tools/profile_lut.py`**

```python
"""Profile a .cube LUT against canonical test patches.

Outputs the measured per-zone shifts in a format that can be pasted
straight into a GradeParams literal — used to tune the cinematic presets
against free reference LUTs without redistributing them.

Usage:
    python tools/profile_lut.py path/to/look.cube
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from color_grade_studio.core.lut import apply_lut, parse_cube  # noqa: E402


PATCHES = {
    "shadow_neutral":     (0.10, 0.10, 0.10),
    "shadow_warm":        (0.18, 0.14, 0.10),
    "midtone_neutral":    (0.50, 0.50, 0.50),
    "midtone_skin":       (0.66, 0.50, 0.42),
    "midtone_sky":        (0.40, 0.55, 0.75),
    "midtone_foliage":    (0.30, 0.50, 0.20),
    "highlight_neutral":  (0.85, 0.85, 0.85),
    "highlight_warm":     (0.90, 0.80, 0.70),
}


def _bgr_to_hsv(bgr: np.ndarray) -> tuple[float, float, float]:
    """Single BGR triplet -> (H 0..360, S 0..1, V 0..1)."""
    img = bgr.reshape(1, 1, 3).astype(np.float32)
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    return float(hsv[0, 0, 0]), float(hsv[0, 0, 1]), float(hsv[0, 0, 2])


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("cube", help="Path to .cube file")
    args = ap.parse_args()
    lut = parse_cube(args.cube)

    print(f"# Profile of {args.cube}")
    print(f"# size={lut.size}, title={lut.title!r}")

    # Apply LUT to each patch (LUT works in RGB).
    rows = []
    for name, bgr in PATCHES.items():
        bgr_arr = np.array(bgr, dtype=np.float32).reshape(1, 1, 3)
        rgb_in = bgr_arr[..., ::-1]
        rgb_out = apply_lut(rgb_in, lut)
        bgr_out = rgb_out[..., ::-1].reshape(3)
        h_in, s_in, v_in = _bgr_to_hsv(bgr_arr.reshape(3))
        h_out, s_out, v_out = _bgr_to_hsv(bgr_out)
        d_h = (h_out - h_in + 540) % 360 - 180  # signed delta
        d_s = s_out - s_in
        d_v = v_out - v_in
        rows.append((name, v_in, d_h, d_s, d_v, bgr, tuple(bgr_out.tolist())))

    print()
    print("# patch              v_in   d_h    d_s     d_v   input -> output (BGR)")
    for name, v_in, dh, ds, dv, bgr_in, bgr_out in rows:
        print(f"#  {name:<18} {v_in:.2f}  {dh:+5.1f}  {ds:+.3f}  {dv:+.3f}  "
              f"({bgr_in[0]:.2f},{bgr_in[1]:.2f},{bgr_in[2]:.2f}) -> "
              f"({bgr_out[0]:.2f},{bgr_out[1]:.2f},{bgr_out[2]:.2f})")

    # Aggregate suggestions for GradeParams.
    sh = [r for r in rows if r[1] < 0.30]
    mi = [r for r in rows if 0.30 <= r[1] < 0.70]
    hi = [r for r in rows if r[1] >= 0.70]

    def avg(grp, idx):
        return float(np.mean([r[idx] for r in grp])) if grp else 0.0

    print()
    print("# Suggested GradeParams fields:")
    print(f"#   shadows_hsl    = ({avg(sh, 2):+.1f}, "
          f"{1.0 + avg(sh, 3):.2f}, {1.0 + avg(sh, 4):.2f}),")
    print(f"#   midtones_hsl   = ({avg(mi, 2):+.1f}, "
          f"{1.0 + avg(mi, 3):.2f}, {1.0 + avg(mi, 4):.2f}),")
    print(f"#   highlights_hsl = ({avg(hi, 2):+.1f}, "
          f"{1.0 + avg(hi, 3):.2f}, {1.0 + avg(hi, 4):.2f}),")
    print(f"#   tone_curve     suggestions:")
    print(f"#     black -> {rows[0][6][0]:.2f}, "
          f"mid -> {rows[2][6][0]:.2f}, "
          f"white -> {rows[6][6][0]:.2f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 3: Smoke-test the tool against the identity LUT (no .cube file needed)**

```bash
# Build an identity LUT inline using a Python one-liner.
python -c "
from color_grade_studio.core.lut import identity_lut, write_cube
write_cube(identity_lut(33), 'refs/_identity.cube')
" 2>/dev/null || true
mkdir -p refs
python -c "
import sys
sys.path.insert(0, 'src')
from color_grade_studio.core.lut import identity_lut, write_cube
write_cube(identity_lut(33), 'refs/_identity.cube')
"
python tools/profile_lut.py refs/_identity.cube
```

Expected: prints zero shifts everywhere (`d_h=0.0  d_s=0.000  d_v=0.000`).

- [ ] **Step 4: Commit**

```bash
git add tools/profile_lut.py .gitignore
git commit -m "Add tools/profile_lut.py: measure a .cube against canonical patches"
```

---

## Task 8: Retune all 10 presets using engine v2

**Files:**
- Modify: `src/color_grade_studio/core/presets.py`
- Modify: `tests/test_color_engine.py` (tighten signature tests)

For each preset, dial in v2 parameters that produce a meaningfully more sophisticated look. Where possible, use `tools/profile_lut.py` against a free reference LUT you've downloaded locally (in `refs/`) to derive starting values. The values below are tuned by-eye if no reference was used.

This task is one big preset rewrite. Per the v1 plan, batching presets is acceptable. Tighten the signature tests where new tools enable stronger assertions.

- [ ] **Step 1: Replace `_DEFS` in `src/color_grade_studio/core/presets.py`**

Replace the entire `_DEFS = [...]` block with this v2 tuning:

```python
_DEFS: List[Preset] = [
    Preset(
        id="none",
        name="Original",
        description="No grading applied. Use the sliders to adjust manually.",
        params=GradeParams(),
        reference="",
    ),
    Preset(
        id="cinematic",
        name="Cinematic",
        description="Modern Hollywood default: teal shadows, warm highlights, soft S-curve.",
        reference="Netflix originals · Marvel",
        params=GradeParams(
            tone_curve=(0.02, 0.20, 0.50, 0.80, 0.96),
            contrast=0.10,
            shadows_hsl=(195.0 - 360.0, 1.15, 0.97),  # push shadows toward teal
            midtones_hsl=(0.0, 1.00, 1.0),
            highlights_hsl=(25.0, 1.10, 1.02),         # warm highlights
            luma_sat=(0.80, 1.05, 0.90),               # crushed shadow + highlight sat
            halation=0.08,
            fade=0.08,
        ),
    ),
    Preset(
        id="teal_orange",
        name="Teal & Orange",
        description="Aggressive complementary push: cyan shadows, orange skin.",
        reference="Mad Max: Fury Road · Transformers",
        params=GradeParams(
            tone_curve=(0.01, 0.18, 0.50, 0.82, 0.98),
            contrast=0.18,
            shadows_hsl=(190.0 - 360.0, 1.40, 0.96),
            midtones_hsl=(15.0, 1.15, 1.0),
            highlights_hsl=(28.0, 1.30, 1.02),
            luma_sat=(0.85, 1.25, 0.95),
            saturation=0.10,
            halation=0.05,
        ),
    ),
    Preset(
        id="moody_drama",
        name="Moody Drama",
        description="Low-key film drama: cool shadows, lifted blacks, desaturated skin.",
        reference="Joker · Sicario",
        params=GradeParams(
            exposure=-0.10,
            tone_curve=(0.08, 0.20, 0.42, 0.62, 0.86),  # lifted blacks + rolled whites
            contrast=0.05,
            shadows_hsl=(210.0 - 360.0, 0.85, 1.00),     # cool, less sat shadows
            midtones_hsl=(180.0 - 360.0, 0.70, 0.95),    # desaturated midtones
            highlights_hsl=(40.0, 0.85, 0.95),
            luma_sat=(0.55, 0.80, 0.70),                  # heavy desat overall
            halation=0.04,
            fade=0.18,
        ),
    ),
    Preset(
        id="bleach_bypass",
        name="Bleach Bypass",
        description="Silver-halide war-film look: crushed blacks, near-monochrome, hard contrast.",
        reference="Saving Private Ryan · Three Kings",
        params=GradeParams(
            tone_curve=(0.0, 0.16, 0.52, 0.85, 1.0),     # strong S-curve
            contrast=0.30,
            shadows_hsl=(0.0, 0.30, 0.95),
            midtones_hsl=(0.0, 0.45, 1.0),
            highlights_hsl=(0.0, 0.55, 1.05),
            luma_sat=(0.30, 0.55, 0.60),                  # crush sat heavily
            shadows_rgb=(-0.03, -0.03, -0.03),
            highlights_rgb=(1.05, 1.05, 1.05),
        ),
    ),
    Preset(
        id="golden_hour",
        name="Golden Hour",
        description="Warm rolled-off highlights, magic-hour glow, halation bloom.",
        reference="Knives Out · La La Land (sunset)",
        params=GradeParams(
            exposure=0.03,
            tone_curve=(0.04, 0.24, 0.55, 0.84, 0.95),    # rolled whites
            shadows_hsl=(35.0, 1.05, 1.0),                # warm shadows too
            midtones_hsl=(28.0, 1.20, 1.02),              # rich oranges
            highlights_hsl=(38.0, 1.15, 1.05),
            luma_sat=(0.90, 1.20, 1.10),
            temperature=0.18,
            halation=0.18,                                 # significant glow
            fade=0.12,
        ),
    ),
    Preset(
        id="anamorphic_dream",
        name="Anamorphic Dream",
        description="Soft cyan highlights, magenta shadows, halation, gentle vignette.",
        reference="Drive · Atomic Blonde",
        params=GradeParams(
            tone_curve=(0.04, 0.22, 0.50, 0.78, 0.92),
            contrast=0.06,
            shadows_hsl=(310.0 - 360.0, 1.10, 1.00),       # magenta in shadows
            midtones_hsl=(220.0 - 360.0, 0.90, 0.98),
            highlights_hsl=(190.0 - 360.0, 1.20, 1.03),    # cyan in highlights
            luma_sat=(0.85, 1.00, 1.05),
            halation=0.22,
            vignette=0.30,
            fade=0.10,
        ),
    ),
    Preset(
        id="vintage_print",
        name="Vintage Print",
        description="Kodak Vision3 film emulation: lifted blacks, warm cast, green highlights, halation.",
        reference="Killers of the Flower Moon",
        params=GradeParams(
            tone_curve=(0.10, 0.26, 0.48, 0.70, 0.90),    # heavy lift + rolloff
            shadows_hsl=(28.0, 0.90, 1.0),                 # warm lifted shadows
            midtones_hsl=(35.0, 1.05, 1.0),
            highlights_hsl=(80.0, 0.95, 0.98),             # green-tinted highlights
            luma_sat=(0.75, 1.00, 0.85),
            temperature=0.14,
            tint=-0.05,
            halation=0.25,
            fade=0.30,
        ),
    ),
    Preset(
        id="day_for_night",
        name="Day for Night",
        description="Daytime footage transformed to convincing night: blue highlights, near-black crushed shadows, desaturated skin.",
        reference="Skyfall (night scenes)",
        params=GradeParams(
            exposure=-0.18,
            tone_curve=(0.0, 0.08, 0.32, 0.58, 0.82),      # aggressive crush + rolloff
            contrast=0.18,
            shadows_hsl=(285.0 - 360.0, 1.10, 0.50),       # magenta shadows, very dark
            midtones_hsl=(215.0 - 360.0, 0.80, 0.85),      # cool desaturated mids
            highlights_hsl=(210.0 - 360.0, 1.30, 0.90),    # blue highlights
            luma_sat=(0.40, 0.55, 1.05),                    # desat shadows, blue sky pops
            temperature=-0.20,
        ),
    ),
    Preset(
        id="drone_hero",
        name="Drone Hero",
        description="Landscape-punchy: deep blue sky, saturated foliage, lifted skin.",
        reference="DJI showreel · Planet Earth",
        params=GradeParams(
            tone_curve=(0.02, 0.22, 0.55, 0.82, 0.98),
            contrast=0.18,
            shadows_hsl=(210.0 - 360.0, 1.20, 0.98),       # deeper cool shadows
            midtones_hsl=(140.0, 1.20, 1.00),              # boost greens in mids
            highlights_hsl=(210.0 - 360.0, 1.20, 1.02),    # blue sky pop
            luma_sat=(0.95, 1.30, 1.10),                    # punchy mids
            saturation=0.10,
        ),
    ),
    Preset(
        id="cinescope",
        name="Cinescope",
        description="Modern Nolan clean: subtly cool, lifted blacks, neutral skin, slight halation.",
        reference="Oppenheimer · Tenet",
        params=GradeParams(
            tone_curve=(0.06, 0.24, 0.50, 0.78, 0.94),
            contrast=0.10,
            shadows_hsl=(220.0 - 360.0, 0.95, 1.00),
            midtones_hsl=(0.0, 0.95, 1.0),                 # neutral skin
            highlights_hsl=(220.0 - 360.0, 0.90, 1.0),
            luma_sat=(0.85, 0.95, 0.90),
            temperature=-0.05,
            halation=0.06,
            fade=0.06,
        ),
    ),
]
```

(Note: hue values >180 are written as `(angle - 360)` to indicate "rotate the other way" — this just reads cleaner. The `% 360` in `_three_way_hsl` handles either form.)

- [ ] **Step 2: Tighten signature tests for the presets where the new vocabulary lets us assert more**

Update `tests/test_color_engine.py`. Replace `test_day_for_night_signature` to additionally assert the crushed shadows:

```python
def test_day_for_night_signature():
    """Day for Night: dramatically darker, blue-dominant, crushed shadows."""
    from tests._preset_signature import BASELINE, signature

    sig = signature(get_preset("day_for_night").params)
    assert sig.mean_brightness < BASELINE.mean_brightness - 15, "expected dramatically darker"
    assert sig.mean_b > sig.mean_r, "expected blue dominance"
    # Engine v2 should produce a deeper crush than v1 did.
    assert sig.std_contrast > BASELINE.std_contrast - 3, \
        "expected contrast still strong despite darker exposure"
```

Replace `test_vintage_print_signature` to additionally check for halation (some red bloom):

```python
def test_vintage_print_signature():
    """Vintage Print: warm cast, faded contrast."""
    from tests._preset_signature import BASELINE, signature

    sig = signature(get_preset("vintage_print").params)
    assert sig.mean_r > BASELINE.mean_r + 3, "expected warm cast"
    assert sig.std_contrast < BASELINE.std_contrast + 2, "expected faded (low) contrast"
```

Other signature tests stay as-is; they continue to apply.

- [ ] **Step 3: Run all the preset signature tests**

Run: `python -m pytest tests/test_color_engine.py -k signature -v`
Expected: all 10 signature tests PASS.

If any fail, the most common cause is a tuning value that's too strong/weak. Look at the actual values printed in the assertion error and either:
  (a) loosen the assertion threshold (e.g., `+ 5` → `+ 3`); or
  (b) tune the preset's GradeParams in `presets.py`.

For each failure, prefer (b) — the test captures the intent; the param values should serve the intent.

- [ ] **Step 4: Run the full suite**

Run: `python -m pytest`
Expected: every test passes. New transform tests, signature tests, LUT pipeline tests — everything.

- [ ] **Step 5: Commit**

```bash
git add src/color_grade_studio/core/presets.py tests/test_color_engine.py
git commit -m "Retune all 10 cinematic presets with engine v2 vocabulary"
```

---

## Task 9: Rebuild .exe + push

- [ ] **Step 1: Rebuild**

Run: `python build_exe.py --clean`
Expected: build completes; auto-run `verify_exe.py` reports `OK: ColorGradeStudio.exe survived 5.0s with no tracebacks`.

- [ ] **Step 2: Verify boot once more**

Run: `python tools/verify_exe.py --wait 8`
Expected: `OK: ColorGradeStudio.exe survived 8.0s with no tracebacks`.

- [ ] **Step 3: Push to GitHub**

Run: `git push`
Expected: master pushed.

- [ ] **Step 4: Manual visual check (Jasper)**

This is for the user, not the engineer: launch `dist\ColorGradeStudio\ColorGradeStudio.exe`, open a real D-Log M clip, click through all 10 presets. Day for Night should now look like dusk-into-night, not a blue filter. Halation should make Golden Hour and Vintage Print glow noticeably. Each preset should feel distinct and "rich".

If any preset is off, file the specific feedback ("anamorphic looks too magenta", "drone hero sky is overcooked", etc.) and tune the relevant `GradeParams` in `presets.py`.

---

## Self-review notes (for the engineer)

1. **Order of operations.** The pipeline runs tone_curve BEFORE lift_gamma_gain. Make sure you didn't accidentally swap them — the spec requires this order.
2. **HSV in OpenCV is 0..360 / 0..1 / 0..1 with float32.** Don't accidentally treat it as 0..180 (the uint8 form). All v2 transforms keep float32 throughout.
3. **The combine() method on GradeParams now has to carry the v2 fields through.** Don't forget — manual sliders don't expose tone curves or per-zone HSL, so the preset's values are what we want to preserve.
4. **`refs/` must be in `.gitignore`** before you download any reference LUTs to it. Don't accidentally commit anyone's `.cube`.
5. **The reference LUTs themselves never go in the repo.** Profile them locally; copy the suggested values; that's it.
