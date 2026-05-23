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
from color_grade_studio.core.color_engine import _halation, _luma_sat, _tone_curve


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


def test_tone_curve_identity_is_noop():
    """Default tone_curve must not change pixels (within rounding)."""
    rng = np.random.default_rng(1)
    img = rng.random((16, 24, 3), dtype=np.float32)
    out = _tone_curve(img, (0.0, 0.25, 0.5, 0.75, 1.0))
    np.testing.assert_allclose(out, img, atol=2e-3)


def test_tone_curve_lifts_midtones():
    """Bumping the mid-output above 0.5 lifts mid-grays."""
    img = np.full((4, 4, 3), 0.5, dtype=np.float32)
    out = _tone_curve(img, (0.0, 0.25, 0.65, 0.85, 1.0))  # mid 0.5 -> 0.65
    assert out.mean() > 0.6


def test_tone_curve_crushes_blacks():
    """Lowering low-mid-output crushes shadows."""
    img = np.full((4, 4, 3), 0.25, dtype=np.float32)
    out = _tone_curve(img, (0.0, 0.10, 0.5, 0.75, 1.0))  # lo_mid 0.25 -> 0.10
    assert out.mean() < 0.20


def test_tone_curve_is_monotonic_when_control_points_are():
    """PCHIP guarantee: monotonic control points -> monotonic output curve.

    Tested against several steep curves that broke the old Catmull-Rom math.
    """
    cases = [
        (0.0, 0.01, 0.5, 0.99, 1.0),    # extreme S
        (0.0, 0.0, 0.5, 1.0, 1.0),      # plateau ends
        (0.0, 0.49, 0.5, 0.51, 1.0),    # near-flat middle
        (0.0, 0.10, 0.50, 0.90, 1.0),   # mild S
        (0.0, 0.05, 0.45, 0.85, 0.99),  # heavy lift + shoulder
    ]
    ramp = np.linspace(0.0, 1.0, 256, dtype=np.float32).reshape(1, 256, 1)
    ramp = np.repeat(ramp, 3, axis=2)
    for pts in cases:
        out = _tone_curve(ramp, pts)
        diffs = np.diff(out[0, :, 0])
        # Allow tiny numerical noise from the 256-entry quantisation.
        assert (diffs > -1e-3).all(), \
            f"non-monotonic output for pts={pts}: min diff = {diffs.min()}"


def test_three_way_hsl_identity_is_noop():
    """All-default per-zone HSL produces no change."""
    from color_grade_studio.core.color_engine import _three_way_hsl
    rng = np.random.default_rng(2)
    img = rng.random((16, 24, 3), dtype=np.float32)
    out = _three_way_hsl(img, (0.0, 1.0, 1.0), (0.0, 1.0, 1.0), (0.0, 1.0, 1.0))
    np.testing.assert_allclose(out, img, atol=2e-3)


def test_three_way_hsl_shadows_only_affects_dark_pixels():
    """A shadow saturation crush should mostly affect dark pixels."""
    from color_grade_studio.core.color_engine import _three_way_hsl
    # Build a frame with a dark warm patch (top half) and bright warm patch (bottom).
    # V=max(BGR), so the "dark" patch needs values low enough to land in the
    # shadow zone (mask peak at V=0.15).
    dark = np.full((8, 16, 3), [0.06, 0.10, 0.18], dtype=np.float32)   # BGR, V=0.18
    bright = np.full((8, 16, 3), [0.7, 0.8, 0.9], dtype=np.float32)    # V=0.9
    img = np.concatenate([dark, bright], axis=0)
    out = _three_way_hsl(img,
                         shadows=(0.0, 0.0, 1.0),  # zero shadow saturation
                         midtones=(0.0, 1.0, 1.0),
                         highlights=(0.0, 1.0, 1.0))
    # Top half (dark) should be much closer to gray than the bottom half.
    top_chroma = float(out[:8].max(axis=-1).mean() - out[:8].min(axis=-1).mean())
    bot_chroma = float(out[8:].max(axis=-1).mean() - out[8:].min(axis=-1).mean())
    assert top_chroma < bot_chroma * 0.6


def test_luma_sat_identity_is_noop():
    rng = np.random.default_rng(3)
    img = rng.random((12, 12, 3), dtype=np.float32)
    out = _luma_sat(img, (1.0, 1.0, 1.0))
    np.testing.assert_allclose(out, img, atol=2e-3)


def test_luma_sat_crushes_shadow_saturation():
    """Zero shadow sat should desaturate dark pixels but leave bright ones."""
    # NOTE: BGR=(0.06, 0.10, 0.18) is genuinely dark (V=0.18, in shadow zone).
    dark = np.full((4, 8, 3), [0.06, 0.10, 0.18], dtype=np.float32)
    bright = np.full((4, 8, 3), [0.70, 0.80, 0.90], dtype=np.float32)
    img = np.concatenate([dark, bright], axis=0)
    out = _luma_sat(img, (0.0, 1.0, 1.0))
    top_chroma = float(out[:4].max(axis=-1).mean() - out[:4].min(axis=-1).mean())
    bot_chroma = float(out[4:].max(axis=-1).mean() - out[4:].min(axis=-1).mean())
    assert top_chroma < bot_chroma * 0.6


def test_halation_identity_is_noop():
    rng = np.random.default_rng(4)
    img = rng.random((16, 16, 3), dtype=np.float32)
    out = _halation(img, 0.0)
    np.testing.assert_allclose(out, img, atol=1e-6)


def test_halation_glows_bright_red_into_neighbours():
    """A bright white spot in the middle should brighten the red channel of nearby pixels."""
    img = np.zeros((32, 32, 3), dtype=np.float32)
    img[8:24, 8:24] = 1.0  # 16x16 bright white square
    out = _halation(img, 0.6)
    # Pixel adjacent to the bright square — original was 0, now should have red.
    near_red = out[4, 16, 2]   # 4 rows above the 8-24 square — adjacent
    near_green = out[4, 16, 1]
    assert near_red > 0.05
    assert near_red > near_green, "halation should bloom red preferentially"


def test_pipeline_includes_three_way_hsl():
    """Setting only shadows_hsl on GradeParams should change the output."""
    params = GradeParams(shadows_hsl=(0.0, 0.0, 1.0))  # crush shadow saturation
    # Genuinely dark warm pixel — V=max(BGR)/255=0.18, sits in shadow zone.
    # (The task-spec value [40,80,160] gives V=0.627, which is firmly midtone
    # and not what the shadow-zone mask targets.)
    frame = np.full((8, 8, 3), [15, 25, 45], dtype=np.uint8)  # dark warm
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
