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
    """Apply ``params`` to the test frame and return a Signature."""
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
