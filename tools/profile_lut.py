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
