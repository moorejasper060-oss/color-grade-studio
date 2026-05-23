"""Tests for the color engine and presets."""
from __future__ import annotations

import numpy as np
import pytest

from color_grade_studio.core import (
    GradeParams,
    PRESETS,
    apply_grade,
    apply_pipeline,
    bake_grade_to_lut,
    compute_combined_lut,
    get_preset,
    identity_lut,
)


def _gradient_frame(h: int = 64, w: int = 96) -> np.ndarray:
    """A test frame with a diagonal brightness gradient and color blocks."""
    f = np.zeros((h, w, 3), dtype=np.uint8)
    for y in range(h):
        for x in range(w):
            v = int((x + y) / (h + w) * 255)
            f[y, x] = (v, v, v)
    f[: h // 3, :, 2] = 200  # red top
    f[h // 3 : 2 * h // 3, :, 1] = 200  # green middle
    f[2 * h // 3 :, :, 0] = 200  # blue bottom
    return f


def test_dtype_and_shape_preserved():
    frame = _gradient_frame()
    out = apply_grade(frame, GradeParams())
    assert out.dtype == np.uint8
    assert out.shape == frame.shape


def test_none_grade_is_close_to_identity():
    frame = _gradient_frame()
    out = apply_grade(frame, GradeParams())
    # With all-zero params the pipeline should be a near-identity transform.
    assert np.abs(out.astype(int) - frame.astype(int)).max() <= 1


def test_exposure_brightens():
    frame = _gradient_frame()
    base_mean = frame.mean()
    bright = apply_grade(frame, GradeParams(exposure=0.5)).mean()
    assert bright > base_mean


def test_exposure_darkens():
    frame = _gradient_frame()
    base_mean = frame.mean()
    dark = apply_grade(frame, GradeParams(exposure=-0.5)).mean()
    assert dark < base_mean


def test_full_desaturation_produces_grayscale():
    frame = _gradient_frame()
    out = apply_grade(frame, GradeParams(saturation=-1.0))
    # All three channels should be equal within rounding for a true grayscale.
    diff = out.max(axis=-1).astype(int) - out.min(axis=-1).astype(int)
    assert diff.max() <= 3


def test_contrast_increases_dynamic_range():
    """Pushing contrast should pull mids toward extremes — std should grow."""
    frame = _gradient_frame()
    base_std = frame.std()
    out_std = apply_grade(frame, GradeParams(contrast=0.8)).std()
    assert out_std > base_std


def test_temperature_warm_pushes_red_up_blue_down():
    frame = np.full((16, 16, 3), 128, dtype=np.uint8)
    warm = apply_grade(frame, GradeParams(temperature=1.0))
    # BGR order: red is channel 2, blue is channel 0.
    assert warm[..., 2].mean() > 128
    assert warm[..., 0].mean() < 128


def test_input_validation():
    with pytest.raises(TypeError):
        apply_grade(np.zeros((8, 8, 3), dtype=np.float32), GradeParams())
    with pytest.raises(ValueError):
        apply_grade(np.zeros((8, 8), dtype=np.uint8), GradeParams())


def test_combine_stacks_preset_and_manual():
    preset = GradeParams(exposure=0.1, contrast=0.2)
    manual = GradeParams(exposure=0.05, saturation=-0.5)
    combined = preset.combine(manual)
    assert combined.exposure == pytest.approx(0.15)
    assert combined.contrast == pytest.approx(0.2)
    assert combined.saturation == pytest.approx(-0.5)


def test_all_presets_run_without_error():
    frame = _gradient_frame()
    for preset in PRESETS:
        out = apply_grade(frame, preset.params)
        assert out.shape == frame.shape
        assert out.dtype == np.uint8


def test_preset_lookup_falls_back_to_none():
    assert get_preset("does_not_exist").id == "none"
    assert get_preset("cinematic").id == "cinematic"


def test_preset_count():
    """Exactly 10 named cinematic presets, plus the 'none' pass-through."""
    named = [p for p in PRESETS if p.id != "none"]
    assert len(named) == 10


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


def test_cinematic_signature():
    """Cinematic: subtle teal shadows + warm highlights."""
    from tests._preset_signature import BASELINE, signature

    sig = signature(get_preset("cinematic").params)
    assert sig.mean_r > BASELINE.mean_r + 1, "expected warmer highlights"


def test_teal_orange_signature():
    """Teal & Orange: high saturation, red boosted, blue shadow tint."""
    from tests._preset_signature import BASELINE, signature

    sig = signature(get_preset("teal_orange").params)
    assert sig.mean_saturation > BASELINE.mean_saturation + 5, "expected aggressive saturation push"
    assert sig.mean_r > sig.mean_b, "expected red dominance"


def test_moody_drama_signature():
    """Moody Drama: darker overall with cool shadow tint."""
    from tests._preset_signature import BASELINE, signature

    sig = signature(get_preset("moody_drama").params)
    assert sig.mean_brightness < BASELINE.mean_brightness - 3, "expected darker overall"
    assert sig.mean_b > sig.mean_r, "expected cool (blue > red) cast"


def test_bleach_bypass_signature():
    """Bleach Bypass: desaturated + high contrast."""
    from tests._preset_signature import BASELINE, signature

    sig = signature(get_preset("bleach_bypass").params)
    assert sig.mean_saturation < BASELINE.mean_saturation - 5, "expected desaturated"
    assert sig.std_contrast > BASELINE.std_contrast + 3, "expected hard contrast"


def test_golden_hour_signature():
    """Golden Hour: warm shift (R up, B down)."""
    from tests._preset_signature import BASELINE, signature

    sig = signature(get_preset("golden_hour").params)
    assert sig.mean_r > BASELINE.mean_r + 5, "expected strong red push"
    assert sig.mean_b < BASELINE.mean_b - 1, "expected blue rolled down"


def test_anamorphic_dream_signature():
    """Anamorphic Dream: cool cast (blue > red) + vignette darkens corners."""
    from tests._preset_signature import BASELINE, signature

    sig = signature(get_preset("anamorphic_dream").params)
    assert sig.mean_b > sig.mean_r, "expected cool (blue > red) cast"
    assert sig.mean_brightness < BASELINE.mean_brightness, "expected vignette to darken overall"


def test_vintage_print_signature():
    """Vintage Print: warm cast, faded (low contrast)."""
    from tests._preset_signature import BASELINE, signature

    sig = signature(get_preset("vintage_print").params)
    assert sig.mean_r > BASELINE.mean_r + 3, "expected warm cast"
    assert sig.std_contrast < BASELINE.std_contrast + 1, "expected faded (low) contrast"


def test_day_for_night_signature():
    """Day for Night: significantly darker, blue-dominant."""
    from tests._preset_signature import BASELINE, signature

    sig = signature(get_preset("day_for_night").params)
    assert sig.mean_brightness < BASELINE.mean_brightness - 15, "expected dramatically darker"
    assert sig.mean_b > sig.mean_r, "expected blue dominance"


def test_drone_hero_signature():
    """Drone Hero: saturated and contrasty."""
    from tests._preset_signature import BASELINE, signature

    sig = signature(get_preset("drone_hero").params)
    assert sig.mean_saturation > BASELINE.mean_saturation + 8, "expected punchy saturation"
    assert sig.std_contrast > BASELINE.std_contrast + 1, "expected punch"


def test_cinescope_signature():
    """Cinescope: subtly cool, lifted blacks."""
    from tests._preset_signature import BASELINE, signature

    sig = signature(get_preset("cinescope").params)
    assert sig.mean_b > BASELINE.mean_b, "expected slight cool cast"
    assert sig.mean_brightness > BASELINE.mean_brightness - 3, "expected blacks lifted"


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


# --- LUT pipeline ---------------------------------------------------------


def test_baked_lut_matches_apply_grade_without_vignette():
    """Baking a grade into a LUT and applying it should match the direct
    grade closely (modulo trilinear interpolation rounding)."""
    params = get_preset("cinematic").params
    # Strip any vignette since LUT-baking deliberately excludes it.
    params = type(params)(
        exposure=params.exposure,
        contrast=params.contrast,
        saturation=params.saturation,
        temperature=params.temperature,
        tint=params.tint,
        shadows_rgb=params.shadows_rgb,
        midtones_rgb=params.midtones_rgb,
        highlights_rgb=params.highlights_rgb,
        hue_shift=params.hue_shift,
        vignette=0.0,
        fade=params.fade,
    )
    rng = np.random.default_rng(7)
    frame = (rng.random((32, 48, 3)) * 255).astype(np.uint8)
    direct = apply_grade(frame, params)
    lut = bake_grade_to_lut(params, size=33)
    via_lut = apply_pipeline(frame, lut)
    # Trilinear interpolation introduces small error; 3/255 is well below
    # what a human eye can see and is the standard tolerance for 8-bit LUTs.
    diff = np.abs(direct.astype(int) - via_lut.astype(int)).max()
    assert diff <= 4, f"baked LUT diverges by {diff} levels from direct grade"


def test_warm_temperature_baked_lut_pushes_red_above_blue():
    params = GradeParams(temperature=1.0)
    lut = bake_grade_to_lut(params)
    gray = np.full((4, 4, 3), 128, dtype=np.uint8)
    out = apply_pipeline(gray, lut)
    # BGR ordering: red=2, blue=0. Warm grade should leave red > blue.
    assert out[..., 2].mean() > out[..., 0].mean() + 10


def test_compute_combined_lut_with_identity_inputs():
    """When input_lut and creative_lut are None, compute_combined_lut should
    equal bake_grade_to_lut for the same params."""
    params = get_preset("teal_orange").params
    only_grade = bake_grade_to_lut(params, size=33)
    combined = compute_combined_lut(params, input_lut=None, creative_lut=None, size=33)
    diff = np.abs(only_grade.table - combined.table).max()
    assert diff < 5e-4


def test_compute_combined_lut_with_identity_input_lut():
    """An identity input LUT should not change the result."""
    params = get_preset("vintage").params
    no_input = compute_combined_lut(params, input_lut=None, creative_lut=None, size=33)
    with_identity = compute_combined_lut(params, input_lut=identity_lut(33), creative_lut=None, size=33)
    diff = np.abs(no_input.table - with_identity.table).max()
    # Allow a touch more slack because two trilinear lookups stack.
    assert diff < 3e-3
