"""Tests for the LUT module: parse, apply, compose, round-trip."""
from __future__ import annotations

from pathlib import Path
from textwrap import dedent

import numpy as np
import pytest

from color_grade_studio.core.lut import (
    Lut3D,
    apply_lut,
    compose,
    identity_lut,
    lut_from_function,
    parse_cube,
    write_cube,
)


def test_identity_lut_passes_image_through():
    rng = np.random.default_rng(42)
    img = rng.random((8, 12, 3), dtype=np.float32)
    out = apply_lut(img, identity_lut(33))
    # Identity should preserve every pixel within tight tolerance (trilinear
    # interpolation on identity grid is exact).
    np.testing.assert_allclose(out, img, atol=2e-3)


def test_identity_lut_at_corners_is_exact():
    """Corner samples land exactly on grid points — no interpolation needed."""
    img = np.array([
        [[0.0, 0.0, 0.0], [1.0, 1.0, 1.0]],
        [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]],
    ], dtype=np.float32)
    out = apply_lut(img, identity_lut(33))
    np.testing.assert_allclose(out, img, atol=1e-6)


def test_write_cube_round_trip(tmp_path: Path):
    """A LUT serialised then re-parsed should be byte-equal in effect."""
    rng = np.random.default_rng(0)
    size = 17
    table = rng.random((size, size, size, 3), dtype=np.float32)
    lut = Lut3D(size=size, table=table, title="Random")

    out_path = tmp_path / "rand.cube"
    write_cube(lut, out_path)
    re_loaded = parse_cube(out_path)

    assert re_loaded.size == size
    np.testing.assert_allclose(re_loaded.table, table, atol=1e-5)


def test_parse_cube_known_content(tmp_path: Path):
    """Hand-written tiny .cube parses into the expected table."""
    # 2x2x2 LUT that inverts each channel (RGB).
    cube_text = dedent("""\
        TITLE "Invert"
        LUT_3D_SIZE 2
        DOMAIN_MIN 0.0 0.0 0.0
        DOMAIN_MAX 1.0 1.0 1.0
        # R fastest, then G, then B
        1.0 1.0 1.0
        0.0 1.0 1.0
        1.0 0.0 1.0
        0.0 0.0 1.0
        1.0 1.0 0.0
        0.0 1.0 0.0
        1.0 0.0 0.0
        0.0 0.0 0.0
    """)
    p = tmp_path / "invert.cube"
    p.write_text(cube_text)
    lut = parse_cube(p)
    assert lut.size == 2
    assert lut.title == "Invert"
    # Inverting (0,0,0) should give (1,1,1), and vice versa.
    img = np.array([[[0.0, 0.0, 0.0], [1.0, 1.0, 1.0]]], dtype=np.float32)
    out = apply_lut(img, lut)
    np.testing.assert_allclose(out[0, 0], [1.0, 1.0, 1.0], atol=1e-6)
    np.testing.assert_allclose(out[0, 1], [0.0, 0.0, 0.0], atol=1e-6)


def test_parse_rejects_1d_lut(tmp_path: Path):
    p = tmp_path / "bad.cube"
    p.write_text("LUT_1D_SIZE 4\n0 0 0\n1 1 1\n")
    with pytest.raises(ValueError):
        parse_cube(p)


def test_parse_rejects_truncated_table(tmp_path: Path):
    p = tmp_path / "trunc.cube"
    p.write_text("LUT_3D_SIZE 3\n0 0 0\n1 1 1\n")
    with pytest.raises(ValueError):
        parse_cube(p)


def test_compose_two_identities_is_identity():
    composed = compose(identity_lut(33), identity_lut(33))
    rng = np.random.default_rng(1)
    img = rng.random((4, 6, 3), dtype=np.float32)
    out = apply_lut(img, composed)
    np.testing.assert_allclose(out, img, atol=3e-3)


def test_compose_with_identity_preserves_lut():
    """compose(A, identity) should behave like A."""
    rng = np.random.default_rng(2)
    table = rng.random((33, 33, 33, 3), dtype=np.float32)
    lut_a = Lut3D(size=33, table=table, title="A")
    composed = compose(lut_a, identity_lut(33))

    img = rng.random((10, 10, 3), dtype=np.float32)
    out_a = apply_lut(img, lut_a)
    out_comp = apply_lut(img, composed)
    # Identity isn't quite exact through trilinear interpolation, but very close.
    np.testing.assert_allclose(out_comp, out_a, atol=5e-3)


def test_lut_from_function_bakes_callable():
    """A custom transform should bake into a LUT that reproduces it."""
    def gain_red(img):
        out = img.copy()
        out[..., 0] = np.clip(out[..., 0] * 1.5, 0.0, 1.0)
        return out

    baked = lut_from_function(gain_red, size=33, title="GainRed")
    img = np.array([[[0.4, 0.5, 0.6]]], dtype=np.float32)
    expected = gain_red(img)
    out = apply_lut(img, baked)
    np.testing.assert_allclose(out, expected, atol=8e-3)
