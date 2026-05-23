# Cinematic Presets Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the 20 generic presets with exactly 10 awesome cinematic looks, each tuned for a recognisable film reference.

**Architecture:** No changes to the LUT pipeline, export, or UI shell. Only `core/presets.py` is rewritten; one new optional field (`reference`) is added to the `Preset` dataclass; tooltips in `ui/preset_panel.py` display it. Each preset is verified by a "signature" test that asserts the preset moves pixels the way its name suggests (e.g., *Day for Night* darkens & blues, *Bleach Bypass* desaturates & contrasts).

**Tech Stack:** Python 3.10+, NumPy, OpenCV, PySide6, pytest. The same `GradeParams` shape and the `compute_combined_lut`/`apply_pipeline` pipeline built in the prior pass.

---

## File Structure

**Modify:**
- `src/color_grade_studio/core/presets.py` — drop 20 presets, add 10, add `reference` field
- `src/color_grade_studio/ui/preset_panel.py` — show `reference` in tooltips
- `tests/test_color_engine.py` — update `test_preset_count`, add `test_preset_ids_are_stable`, add `test_each_preset_is_non_trivial`
- `tests/test_color_engine.py` — add one signature test per preset (10 new)

**Add:**
- `tests/_preset_signature.py` — helper module with `signature(params) -> dict` used by every per-preset test

**Out of scope:** No new pipeline code, no new UI widgets, no .cube bundling.

---

## Task 1: Add `reference` field to Preset dataclass + signature helper + count test update

**Files:**
- Modify: `src/color_grade_studio/core/presets.py` (Preset dataclass)
- Modify: `src/color_grade_studio/core/__init__.py` (no change — re-export unchanged)
- Create: `tests/_preset_signature.py`
- Modify: `tests/test_color_engine.py::test_preset_count`

- [ ] **Step 1: Read the current Preset dataclass**

Read `src/color_grade_studio/core/presets.py` lines 1–25 so you know the existing shape:

```python
@dataclass
class Preset:
    id: str
    name: str
    description: str
    params: GradeParams
```

- [ ] **Step 2: Add the optional `reference` field**

Edit `src/color_grade_studio/core/presets.py`:

```python
@dataclass
class Preset:
    id: str
    name: str
    description: str
    params: GradeParams
    reference: str = ""  # film reference shown in UI tooltip; "" = none
```

- [ ] **Step 3: Create the signature helper**

Create `tests/_preset_signature.py`:

```python
"""Test helper: measurable per-preset 'signature' of an applied grade.

Each cinematic preset has a recognisable signature on a synthetic
log-like test frame — average brightness, saturation, channel skew.
The per-preset tests in test_color_engine.py call signature() on a
preset's params and assert the relevant axes moved in the expected
direction. This guards against accidental preset swaps and silently
broken presets.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple

import cv2
import numpy as np

from color_grade_studio.core import GradeParams, apply_grade


@dataclass
class Signature:
    mean_b: float
    mean_g: float
    mean_r: float
    mean_brightness: float
    std_contrast: float
    mean_saturation: float


def _test_frame() -> np.ndarray:
    """A repeatable BGR uint8 test frame: gray ramp + warm patch + cool patch."""
    h, w = 64, 96
    f = np.zeros((h, w, 3), dtype=np.uint8)
    # Diagonal gray ramp.
    for y in range(h):
        for x in range(w):
            v = int((x + y) / (h + w) * 220) + 16
            f[y, x] = (v, v, v)
    # Warm patch (skin-tone-ish), top-right.
    f[0:h // 3, 2 * w // 3:w] = (110, 150, 200)
    # Cool patch (sky-ish), bottom-left.
    f[2 * h // 3:h, 0:w // 3] = (180, 130, 100)
    return f


def signature(params: GradeParams) -> Signature:
    """Apply `params` to the test frame and return a Signature."""
    frame = _test_frame()
    out = apply_grade(frame, params)
    hsv = cv2.cvtColor(out, cv2.COLOR_BGR2HSV).astype(np.float32)
    return Signature(
        mean_b=float(out[..., 0].mean()),
        mean_g=float(out[..., 1].mean()),
        mean_r=float(out[..., 2].mean()),
        mean_brightness=float(out.mean()),
        std_contrast=float(out.std()),
        mean_saturation=float(hsv[..., 1].mean()),
    )


BASELINE = signature(GradeParams())
```

- [ ] **Step 4: Update `test_preset_count`**

Open `tests/test_color_engine.py` and find `test_preset_count`. Replace it with:

```python
def test_preset_count():
    """Exactly 10 named cinematic presets, plus the 'none' pass-through."""
    named = [p for p in PRESETS if p.id != "none"]
    assert len(named) == 10
```

- [ ] **Step 5: Add `test_preset_ids_are_stable`**

Add to `tests/test_color_engine.py`:

```python
def test_preset_ids_are_stable():
    """Pin the preset IDs so accidental renames don't sneak in."""
    expected_ids = {
        "none",
        "cinematic",
        "teal_orange",
        "moody_drama",
        "bleach_bypass",
        "golden_hour",
        "anamorphic_dream",
        "vintage_print",
        "day_for_night",
        "drone_hero",
        "cinescope",
    }
    actual_ids = {p.id for p in PRESETS}
    assert actual_ids == expected_ids
```

- [ ] **Step 6: Add `test_each_preset_is_non_trivial`**

Add to `tests/test_color_engine.py`:

```python
def test_each_preset_is_non_trivial():
    """Every named preset must move at least one pixel — guards against
    shipping a preset that does nothing."""
    from tests._preset_signature import BASELINE, signature

    for preset in PRESETS:
        if preset.id == "none":
            continue
        sig = signature(preset.params)
        moved = (
            abs(sig.mean_brightness - BASELINE.mean_brightness) > 1
            or abs(sig.mean_saturation - BASELINE.mean_saturation) > 1
            or abs(sig.std_contrast - BASELINE.std_contrast) > 1
        )
        assert moved, f"preset {preset.id} produces no visible change"
```

- [ ] **Step 7: Run the existing tests (most will fail because we haven't rewritten presets yet)**

Run: `python -m pytest tests/test_color_engine.py -v`
Expected: `test_preset_count` FAILS (still 20 presets), `test_preset_ids_are_stable` FAILS (old IDs don't match new set), other tests still pass.

This is the "red" state for TDD. Subsequent tasks turn each failing assertion green.

- [ ] **Step 8: Commit**

```bash
git add src/color_grade_studio/core/presets.py tests/_preset_signature.py tests/test_color_engine.py
git commit -m "Add reference field to Preset; lock 10-cinematic-preset test contract"
```

---

## Task 2: Preset — Cinematic

**Files:**
- Modify: `src/color_grade_studio/core/presets.py` (the `_DEFS` list)
- Modify: `tests/test_color_engine.py` (add one signature test)

Reference look: Netflix originals / modern Marvel. Slight teal in shadows, warm highlights, soft S-curve contrast, lifted blacks.

- [ ] **Step 1: Write the failing signature test**

Add to `tests/test_color_engine.py`:

```python
def test_cinematic_signature():
    """Cinematic: subtle teal shadows + warm highlights, slight contrast bump.

    Signature: red channel up, blue channel slightly lifted in shadows
    (visible as overall blue staying close to baseline despite warm shift),
    contrast slightly higher than baseline.
    """
    from tests._preset_signature import BASELINE, signature

    sig = signature(get_preset("cinematic").params)
    assert sig.mean_r > BASELINE.mean_r + 1, "expected warmer highlights"
    assert sig.std_contrast > BASELINE.std_contrast - 1, "expected mild contrast"
```

- [ ] **Step 2: Run — expect failure**

Run: `python -m pytest tests/test_color_engine.py::test_cinematic_signature -v`
Expected: FAIL — the cinematic preset's current params don't satisfy these criteria, or the preset doesn't exist after the cleanup.

- [ ] **Step 3: Rewrite `presets.py` _DEFS list opening with `none` + `cinematic`**

Open `src/color_grade_studio/core/presets.py` and rewrite the `_DEFS` list. For this task, you only need to include `none` and `cinematic`. Subsequent tasks append the rest. Replace the existing list with:

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
        description="Modern Hollywood default: teal shadows, warm highlights, lifted blacks.",
        reference="Netflix originals · Marvel",
        params=GradeParams(
            contrast=0.18,
            saturation=-0.05,
            temperature=0.06,
            shadows_rgb=(0.05, 0.01, -0.02),   # teal lift
            highlights_rgb=(0.95, 1.00, 1.07),  # warm gain
            fade=0.12,
        ),
    ),
]
```

- [ ] **Step 4: Run the cinematic test**

Run: `python -m pytest tests/test_color_engine.py::test_cinematic_signature -v`
Expected: PASS.

- [ ] **Step 5: Note: other preset/ids tests will still fail until later tasks add the rest. That's OK — verify nothing unrelated broke.**

Run: `python -m pytest tests/test_color_engine.py -v -k 'not preset_count and not preset_ids and not non_trivial and not test_baked_lut and not test_warm_temperature_baked and not test_compute_combined and not preset_lookup_falls_back and not all_presets'`

Expected: only "cinematic" + the engine-math tests pass; the count/ids/non-trivial tests still fail because we only added 1 of 10 presets. That's expected and fixed by later tasks.

- [ ] **Step 6: Commit**

```bash
git add src/color_grade_studio/core/presets.py tests/test_color_engine.py
git commit -m "Preset: Cinematic — Netflix/Marvel default"
```

---

## Task 3: Preset — Teal & Orange

**Files:**
- Modify: `src/color_grade_studio/core/presets.py`
- Modify: `tests/test_color_engine.py`

Reference look: Mad Max: Fury Road. Aggressive complementary push.

- [ ] **Step 1: Write the failing signature test**

Add to `tests/test_color_engine.py`:

```python
def test_teal_orange_signature():
    """Teal & Orange: high saturation, red boosted, blue shadow tint."""
    from tests._preset_signature import BASELINE, signature

    sig = signature(get_preset("teal_orange").params)
    assert sig.mean_saturation > BASELINE.mean_saturation + 5, \
        "expected aggressive saturation push"
    assert sig.mean_r > sig.mean_b, "expected red dominance"
```

- [ ] **Step 2: Run — expect failure**

Run: `python -m pytest tests/test_color_engine.py::test_teal_orange_signature -v`
Expected: FAIL — preset not in list yet.

- [ ] **Step 3: Append `teal_orange` to `_DEFS`**

Open `src/color_grade_studio/core/presets.py`. Add this entry to the `_DEFS` list (before the closing `]`):

```python
    Preset(
        id="teal_orange",
        name="Teal & Orange",
        description="Aggressive complementary push: cyan shadows, orange skin.",
        reference="Mad Max: Fury Road · Transformers",
        params=GradeParams(
            contrast=0.25,
            saturation=0.25,
            temperature=0.12,
            shadows_rgb=(0.09, 0.02, -0.04),   # strong cyan lift
            highlights_rgb=(0.85, 1.00, 1.15),  # strong orange in highlights
        ),
    ),
```

- [ ] **Step 4: Run the test**

Run: `python -m pytest tests/test_color_engine.py::test_teal_orange_signature -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/color_grade_studio/core/presets.py tests/test_color_engine.py
git commit -m "Preset: Teal & Orange — Mad Max signature"
```

---

## Task 4: Preset — Moody Drama

**Files:**
- Modify: `src/color_grade_studio/core/presets.py`
- Modify: `tests/test_color_engine.py`

Reference look: Joker, Sicario. Low-key, desaturated, cool shadow tint, pulled-down highlights.

- [ ] **Step 1: Write the failing signature test**

```python
def test_moody_drama_signature():
    """Moody Drama: darker overall, lower saturation, cool shadow tint."""
    from tests._preset_signature import BASELINE, signature

    sig = signature(get_preset("moody_drama").params)
    assert sig.mean_brightness < BASELINE.mean_brightness - 3, "expected darker overall"
    assert sig.mean_saturation < BASELINE.mean_saturation - 5, "expected desaturated"
```

- [ ] **Step 2: Run — expect failure**

Run: `python -m pytest tests/test_color_engine.py::test_moody_drama_signature -v`
Expected: FAIL.

- [ ] **Step 3: Append `moody_drama` to `_DEFS`**

```python
    Preset(
        id="moody_drama",
        name="Moody Drama",
        description="Low-key desaturated drama with cool shadows.",
        reference="Joker · Sicario",
        params=GradeParams(
            exposure=-0.12,
            contrast=0.12,
            saturation=-0.25,
            temperature=-0.10,
            shadows_rgb=(0.06, 0.02, -0.01),  # cool, lifted
            highlights_rgb=(0.97, 0.97, 0.97), # pulled-down whites
            fade=0.10,
        ),
    ),
```

- [ ] **Step 4: Run**

Run: `python -m pytest tests/test_color_engine.py::test_moody_drama_signature -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/color_grade_studio/core/presets.py tests/test_color_engine.py
git commit -m "Preset: Moody Drama — Joker/Sicario low-key"
```

---

## Task 5: Preset — Bleach Bypass

**Files:**
- Modify: `src/color_grade_studio/core/presets.py`
- Modify: `tests/test_color_engine.py`

Reference: Saving Private Ryan, Three Kings. Silver-halide. Crushed blacks, low saturation, hard contrast.

- [ ] **Step 1: Write the failing signature test**

```python
def test_bleach_bypass_signature():
    """Bleach Bypass: very desaturated + high contrast."""
    from tests._preset_signature import BASELINE, signature

    sig = signature(get_preset("bleach_bypass").params)
    assert sig.mean_saturation < BASELINE.mean_saturation - 25, \
        "expected near-monochrome"
    assert sig.std_contrast > BASELINE.std_contrast + 3, "expected hard contrast"
```

- [ ] **Step 2: Run — expect failure**

Run: `python -m pytest tests/test_color_engine.py::test_bleach_bypass_signature -v`
Expected: FAIL.

- [ ] **Step 3: Append `bleach_bypass` to `_DEFS`**

```python
    Preset(
        id="bleach_bypass",
        name="Bleach Bypass",
        description="Silver-halide look: crushed blacks, low saturation, hard contrast.",
        reference="Saving Private Ryan · Three Kings",
        params=GradeParams(
            contrast=0.40,
            saturation=-0.50,
            temperature=-0.05,
            shadows_rgb=(-0.03, -0.03, -0.03),  # crush blacks
            highlights_rgb=(1.06, 1.06, 1.06),   # lift whites
        ),
    ),
```

- [ ] **Step 4: Run**

Run: `python -m pytest tests/test_color_engine.py::test_bleach_bypass_signature -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/color_grade_studio/core/presets.py tests/test_color_engine.py
git commit -m "Preset: Bleach Bypass — silver-halide war-film look"
```

---

## Task 6: Preset — Golden Hour

**Files:**
- Modify: `src/color_grade_studio/core/presets.py`
- Modify: `tests/test_color_engine.py`

Reference: Knives Out, La La Land sunset. Warm rolled-off highlights, magic-hour glow.

- [ ] **Step 1: Write the failing signature test**

```python
def test_golden_hour_signature():
    """Golden Hour: warm shift (R up, B down), slight overall brightness up."""
    from tests._preset_signature import BASELINE, signature

    sig = signature(get_preset("golden_hour").params)
    assert sig.mean_r > BASELINE.mean_r + 5, "expected strong red push"
    assert sig.mean_b < BASELINE.mean_b - 1, "expected blue rolled down"
```

- [ ] **Step 2: Run — expect failure**

Run: `python -m pytest tests/test_color_engine.py::test_golden_hour_signature -v`
Expected: FAIL.

- [ ] **Step 3: Append `golden_hour` to `_DEFS`**

```python
    Preset(
        id="golden_hour",
        name="Golden Hour",
        description="Warm rolled-off highlights with magic-hour glow.",
        reference="Knives Out · La La Land (sunset scenes)",
        params=GradeParams(
            exposure=0.04,
            contrast=0.06,
            saturation=0.08,
            temperature=0.32,
            highlights_rgb=(0.88, 0.97, 1.10),  # roll off blue in highlights
            fade=0.12,
        ),
    ),
```

- [ ] **Step 4: Run**

Run: `python -m pytest tests/test_color_engine.py::test_golden_hour_signature -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/color_grade_studio/core/presets.py tests/test_color_engine.py
git commit -m "Preset: Golden Hour — Knives Out warm magic"
```

---

## Task 7: Preset — Anamorphic Dream

**Files:**
- Modify: `src/color_grade_studio/core/presets.py`
- Modify: `tests/test_color_engine.py`

Reference: Drive, Atomic Blonde. Soft cyan highlights, slight magenta shadows, gentle vignette.

- [ ] **Step 1: Write the failing signature test**

```python
def test_anamorphic_dream_signature():
    """Anamorphic Dream: blue-shifted, mild vignette (mean brightness slightly down)."""
    from tests._preset_signature import BASELINE, signature

    sig = signature(get_preset("anamorphic_dream").params)
    assert sig.mean_b > BASELINE.mean_b + 1, "expected cool highlights"
    # Vignette should pull average brightness slightly down at the corners.
    assert sig.mean_brightness < BASELINE.mean_brightness + 1, \
        "expected vignette to keep brightness in check"
```

- [ ] **Step 2: Run — expect failure**

Run: `python -m pytest tests/test_color_engine.py::test_anamorphic_dream_signature -v`
Expected: FAIL.

- [ ] **Step 3: Append `anamorphic_dream` to `_DEFS`**

```python
    Preset(
        id="anamorphic_dream",
        name="Anamorphic Dream",
        description="Soft cyan highlights with magenta shadows and gentle vignette.",
        reference="Drive · Atomic Blonde",
        params=GradeParams(
            contrast=0.10,
            saturation=-0.05,
            temperature=-0.10,
            shadows_rgb=(-0.02, -0.02, 0.04),   # slight magenta lift
            highlights_rgb=(1.08, 1.02, 0.95),  # cyan in highlights
            vignette=0.28,
        ),
    ),
```

- [ ] **Step 4: Run**

Run: `python -m pytest tests/test_color_engine.py::test_anamorphic_dream_signature -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/color_grade_studio/core/presets.py tests/test_color_engine.py
git commit -m "Preset: Anamorphic Dream — Drive/Atomic Blonde neon"
```

---

## Task 8: Preset — Vintage Print

**Files:**
- Modify: `src/color_grade_studio/core/presets.py`
- Modify: `tests/test_color_engine.py`

Reference: Killers of the Flower Moon. Kodak Vision3 emulation. Lifted blacks, warm cast, slight green in highlights.

- [ ] **Step 1: Write the failing signature test**

```python
def test_vintage_print_signature():
    """Vintage Print: lifted blacks (overall brighter shadows), warm cast, low contrast."""
    from tests._preset_signature import BASELINE, signature

    sig = signature(get_preset("vintage_print").params)
    assert sig.mean_r > BASELINE.mean_r + 3, "expected warm cast"
    # Faded look reduces dynamic range -> std should drop.
    assert sig.std_contrast < BASELINE.std_contrast + 1, \
        "expected faded (low) contrast"
```

- [ ] **Step 2: Run — expect failure**

Run: `python -m pytest tests/test_color_engine.py::test_vintage_print_signature -v`
Expected: FAIL.

- [ ] **Step 3: Append `vintage_print` to `_DEFS`**

```python
    Preset(
        id="vintage_print",
        name="Vintage Print",
        description="Kodak Vision3 film emulation: lifted blacks, warm cast, green highlights.",
        reference="Killers of the Flower Moon",
        params=GradeParams(
            contrast=-0.08,
            saturation=-0.18,
            temperature=0.20,
            tint=-0.06,
            shadows_rgb=(-0.01, 0.00, 0.05),   # warm shadow lift
            highlights_rgb=(0.95, 1.03, 1.00), # slight green tint highlights
            fade=0.35,
        ),
    ),
```

- [ ] **Step 4: Run**

Run: `python -m pytest tests/test_color_engine.py::test_vintage_print_signature -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/color_grade_studio/core/presets.py tests/test_color_engine.py
git commit -m "Preset: Vintage Print — Kodak Vision3 film stock"
```

---

## Task 9: Preset — Day for Night

**Files:**
- Modify: `src/color_grade_studio/core/presets.py`
- Modify: `tests/test_color_engine.py`

Reference: Skyfall night scenes. Blue shift + darker exposure, transforming daytime footage into a night-time look.

- [ ] **Step 1: Write the failing signature test**

```python
def test_day_for_night_signature():
    """Day for Night: significantly darker, blue-dominant."""
    from tests._preset_signature import BASELINE, signature

    sig = signature(get_preset("day_for_night").params)
    assert sig.mean_brightness < BASELINE.mean_brightness - 15, \
        "expected dramatically darker"
    assert sig.mean_b > sig.mean_r, "expected blue dominance"
```

- [ ] **Step 2: Run — expect failure**

Run: `python -m pytest tests/test_color_engine.py::test_day_for_night_signature -v`
Expected: FAIL.

- [ ] **Step 3: Append `day_for_night` to `_DEFS`**

```python
    Preset(
        id="day_for_night",
        name="Day for Night",
        description="Daytime footage shifted to a cool night-time look.",
        reference="Skyfall (night scenes)",
        params=GradeParams(
            exposure=-0.30,
            contrast=0.22,
            saturation=-0.25,
            temperature=-0.40,
            shadows_rgb=(0.08, 0.00, -0.05),    # cool, lifted
            highlights_rgb=(1.12, 0.95, 0.82),  # cool whites
        ),
    ),
```

- [ ] **Step 4: Run**

Run: `python -m pytest tests/test_color_engine.py::test_day_for_night_signature -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/color_grade_studio/core/presets.py tests/test_color_engine.py
git commit -m "Preset: Day for Night — Skyfall night-from-day trick"
```

---

## Task 10: Preset — Drone Hero

**Files:**
- Modify: `src/color_grade_studio/core/presets.py`
- Modify: `tests/test_color_engine.py`

Reference: DJI showreel, Planet Earth. Landscape-punchy with boosted sky/earth contrast, skintones preserved.

- [ ] **Step 1: Write the failing signature test**

```python
def test_drone_hero_signature():
    """Drone Hero: saturated and contrasty, slight warm bias."""
    from tests._preset_signature import BASELINE, signature

    sig = signature(get_preset("drone_hero").params)
    assert sig.mean_saturation > BASELINE.mean_saturation + 8, \
        "expected punchy saturation"
    assert sig.std_contrast > BASELINE.std_contrast + 1, "expected punch"
```

- [ ] **Step 2: Run — expect failure**

Run: `python -m pytest tests/test_color_engine.py::test_drone_hero_signature -v`
Expected: FAIL.

- [ ] **Step 3: Append `drone_hero` to `_DEFS`**

```python
    Preset(
        id="drone_hero",
        name="Drone Hero",
        description="Landscape-punchy: boosted sky/earth contrast, skin-tones preserved.",
        reference="DJI showreel · Planet Earth",
        params=GradeParams(
            contrast=0.25,
            saturation=0.32,
            temperature=0.05,
            shadows_rgb=(0.02, 0.00, -0.01),    # subtle teal earth
            highlights_rgb=(0.97, 1.00, 1.05),  # slight warm sky highlight
        ),
    ),
```

- [ ] **Step 4: Run**

Run: `python -m pytest tests/test_color_engine.py::test_drone_hero_signature -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/color_grade_studio/core/presets.py tests/test_color_engine.py
git commit -m "Preset: Drone Hero — DJI showreel landscape punch"
```

---

## Task 11: Preset — Cinescope

**Files:**
- Modify: `src/color_grade_studio/core/presets.py`
- Modify: `tests/test_color_engine.py`

Reference: Oppenheimer, Tenet. Modern Nolan clean look. Slight cool cast, lifted blacks, neutral skin tones.

- [ ] **Step 1: Write the failing signature test**

```python
def test_cinescope_signature():
    """Cinescope: subtly cool, lifted blacks, neutral skin."""
    from tests._preset_signature import BASELINE, signature

    sig = signature(get_preset("cinescope").params)
    assert sig.mean_b > BASELINE.mean_b, "expected slight cool cast"
    assert sig.mean_brightness > BASELINE.mean_brightness - 3, \
        "expected blacks lifted (overall brightness not dropping)"
```

- [ ] **Step 2: Run — expect failure**

Run: `python -m pytest tests/test_color_engine.py::test_cinescope_signature -v`
Expected: FAIL.

- [ ] **Step 3: Append `cinescope` to `_DEFS`**

```python
    Preset(
        id="cinescope",
        name="Cinescope",
        description="Modern Nolan clean look: slight cool cast, lifted blacks, neutral skin.",
        reference="Oppenheimer · Tenet",
        params=GradeParams(
            contrast=0.15,
            saturation=-0.10,
            temperature=-0.05,
            shadows_rgb=(0.04, 0.02, 0.00),   # gentle blue lift
            highlights_rgb=(1.00, 1.00, 0.98), # neutral highlights, mild cool
            fade=0.08,
        ),
    ),
```

- [ ] **Step 4: Run**

Run: `python -m pytest tests/test_color_engine.py::test_cinescope_signature -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/color_grade_studio/core/presets.py tests/test_color_engine.py
git commit -m "Preset: Cinescope — modern Nolan clean look"
```

---

## Task 12: Verify ALL preset tests pass + UI tooltip shows reference

**Files:**
- Modify: `src/color_grade_studio/ui/preset_panel.py`
- (Re-)Run: full test suite

- [ ] **Step 1: Run the full preset test suite**

Run: `python -m pytest tests/test_color_engine.py -v -k 'preset_count or preset_ids or non_trivial or signature or baked_lut or test_all_presets'`
Expected: PASS — all preset tests now green.

If any fail, do not proceed; fix the underlying preset's `GradeParams` until the assertion passes. Tweak conservatively (small deltas to `temperature`, `shadows_rgb`, etc.). Re-commit with `git commit --amend` only if the fix is to the most-recent preset task; otherwise create a fresh commit titled `"tweak: <preset_id> — <one-line reason>"`.

- [ ] **Step 2: Read the current preset_panel.py**

Read `src/color_grade_studio/ui/preset_panel.py`. Find the line `item.setToolTip(preset.description)` (around line 50).

- [ ] **Step 3: Update the tooltip to include the film reference**

Replace the line:

```python
item.setToolTip(preset.description)
```

with:

```python
tooltip = preset.description
if preset.reference:
    tooltip += f"\n\nLook: {preset.reference}"
item.setToolTip(tooltip)
```

- [ ] **Step 4: Run UI smoke test**

Run: `PYTHONPATH=src python tests/smoke_ui.py`
Expected: `smoke OK` — the window constructs without exception.

- [ ] **Step 5: Run the entire test suite**

Run: `python -m pytest`
Expected: all tests PASS — total count should be approximately previous + 13 (10 signature + 1 ids + 1 count + 1 non-trivial), but `test_preset_count` replaced an existing test so net +12 or so.

- [ ] **Step 6: Commit**

```bash
git add src/color_grade_studio/ui/preset_panel.py
git commit -m "UI: show preset's film reference in tooltip"
```

---

## Task 13: Rebuild .exe + manual visual check

**Files:** none (build + manual verification)

- [ ] **Step 1: Run the post-build self-verification**

Run: `python build_exe.py --clean`
Expected: build completes; the auto-run `tools/verify_exe.py` reports `OK: ColorGradeStudio.exe survived 5.0s with no tracebacks`.

- [ ] **Step 2: Launch the built .exe and eyeball the preset list**

Run: `cmd /c start "" "dist\ColorGradeStudio\ColorGradeStudio.exe"`
(or double-click the desktop shortcut)

Open a real video clip. Click through the 10 presets and confirm each one looks visibly different from the others and matches its claimed look. If any look indistinguishable from another, note it and tune that preset's `params` in `presets.py`; re-run the engine tests after each tweak; re-build.

This is a MANUAL CHECK — there's no automated assertion. The goal is that a knowledgeable viewer would recognise each preset's intent on real footage. Spend ~30 seconds per preset.

- [ ] **Step 3: Push to GitHub**

```bash
git push
```

- [ ] **Step 4: Commit any tuning tweaks discovered in step 2**

If step 2 surfaced any preset that needed a tweak:

```bash
git add src/color_grade_studio/core/presets.py
git commit -m "tweak: <preset_id> — <one-line reason>"
git push
```

---

## Self-review notes (for the engineer)

Before stopping:

1. **Did every preset task add exactly one signature test that names the preset in its assertion?** If a test only checks a generic property without naming the preset, that's a bug — accidental swaps won't be caught.
2. **Are all film references plausible?** They appear in tooltips, so if they're wrong the user notices.
3. **Did Task 1's `_preset_signature.py` cover the channels you actually used in later assertions?** If you wrote a test that checks `sig.mean_g` and the helper doesn't expose `mean_g`, that's a broken test.
4. **Are old preset IDs (vibrant, punch, pastel, warm, cool, sepia, bw, etc.) completely gone from `presets.py`?** The `test_preset_ids_are_stable` test should catch this, but eyeball the final `_DEFS` list anyway.
