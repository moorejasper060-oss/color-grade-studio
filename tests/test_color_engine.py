"""Tests for the color engine and presets."""
from __future__ import annotations

import numpy as np
import pytest

from color_grade_studio.core import (
    GradeParams,
    PRESETS,
    apply_grade,
    get_preset,
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
    # We promised 20+ named presets in the spec.
    named = [p for p in PRESETS if p.id != "none"]
    assert len(named) >= 20
