"""3D LUT (.cube) loading, applying, and composing.

A ``.cube`` LUT is a 3D table of RGB values. The standard format (Adobe spec)
specifies inputs in [0, 1]^3 and outputs in the same range. We store the
table as a ``(N, N, N, 3)`` float32 numpy array indexed ``lut[b, g, r]`` —
the .cube spec iterates R fastest, then G, then B, so when we reshape we
get a B-major array.

Sources used in graceful order at load time:

  * comments / TITLE / DOMAIN_MIN / DOMAIN_MAX are tolerated and ignored
    except the domain (we re-scale inputs to the declared domain).
  * LUT_3D_SIZE is required; LUT_1D_SIZE is rejected (we only handle 3D).
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional, Tuple

import numpy as np


@dataclass
class Lut3D:
    """An in-memory 3D LUT. ``table`` is a (size, size, size, 3) float32 array
    where ``table[b_idx, g_idx, r_idx]`` is the output RGB for the grid sample
    at that integer index along each axis."""
    size: int
    table: np.ndarray  # shape (size, size, size, 3), float32, values in [0,1]
    domain_min: Tuple[float, float, float] = (0.0, 0.0, 0.0)
    domain_max: Tuple[float, float, float] = (1.0, 1.0, 1.0)
    title: str = ""

    def __post_init__(self) -> None:
        if self.table.shape != (self.size, self.size, self.size, 3):
            raise ValueError(
                f"LUT table shape {self.table.shape} does not match size {self.size}"
            )
        if self.table.dtype != np.float32:
            self.table = self.table.astype(np.float32)


def identity_lut(size: int = 33) -> Lut3D:
    """A neutral 3D LUT — applying it to an image leaves the image unchanged."""
    axis = np.linspace(0.0, 1.0, size, dtype=np.float32)
    # Build an (size, size, size, 3) array where table[b, g, r] = (r, g, b).
    gr, gg, gb = np.meshgrid(axis, axis, axis, indexing="ij")
    # meshgrid with indexing="ij" gives gr indexed as [first, second, third]
    # but our convention is table[b, g, r] -> (r, g, b). So:
    #   axis 0 = b, axis 1 = g, axis 2 = r
    b_grid, g_grid, r_grid = np.meshgrid(axis, axis, axis, indexing="ij")
    table = np.stack([r_grid, g_grid, b_grid], axis=-1)
    return Lut3D(size=size, table=table.astype(np.float32), title="Identity")


def parse_cube(path: str | Path) -> Lut3D:
    """Parse an Adobe .cube file into a :class:`Lut3D`.

    Raises :class:`ValueError` for malformed or 1D-only files.
    """
    p = Path(path)
    text = p.read_text(encoding="utf-8", errors="replace")
    size: Optional[int] = None
    title = ""
    domain_min = (0.0, 0.0, 0.0)
    domain_max = (1.0, 1.0, 1.0)
    samples: list[Tuple[float, float, float]] = []

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        upper = line.upper()
        if upper.startswith("TITLE"):
            # TITLE "something"
            after = line.split(maxsplit=1)
            if len(after) == 2:
                title = after[1].strip().strip('"').strip("'")
            continue
        if upper.startswith("DOMAIN_MIN"):
            parts = line.split()
            if len(parts) == 4:
                domain_min = (float(parts[1]), float(parts[2]), float(parts[3]))
            continue
        if upper.startswith("DOMAIN_MAX"):
            parts = line.split()
            if len(parts) == 4:
                domain_max = (float(parts[1]), float(parts[2]), float(parts[3]))
            continue
        if upper.startswith("LUT_1D_SIZE"):
            raise ValueError(f"{p.name}: 1D LUTs are not supported, only 3D")
        if upper.startswith("LUT_3D_SIZE"):
            parts = line.split()
            if len(parts) != 2:
                raise ValueError(f"{p.name}: malformed LUT_3D_SIZE line")
            size = int(parts[1])
            continue
        # Data line: three floats.
        parts = line.split()
        if len(parts) < 3:
            continue
        try:
            r, g, b = float(parts[0]), float(parts[1]), float(parts[2])
        except ValueError:
            continue
        samples.append((r, g, b))

    if size is None:
        raise ValueError(f"{p.name}: missing LUT_3D_SIZE header")
    expected = size ** 3
    if len(samples) != expected:
        raise ValueError(
            f"{p.name}: expected {expected} samples for size {size}, got {len(samples)}"
        )

    arr = np.array(samples, dtype=np.float32)
    # .cube ordering: R varies fastest, then G, then B. Reshape so the first
    # axis is B (slowest), then G, then R — matches our table[b, g, r] convention.
    table = arr.reshape(size, size, size, 3)
    return Lut3D(
        size=size,
        table=table,
        domain_min=domain_min,
        domain_max=domain_max,
        title=title or p.stem,
    )


def write_cube(lut: Lut3D, path: str | Path, title: Optional[str] = None) -> Path:
    """Serialise a :class:`Lut3D` to a .cube file."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    label = title or lut.title or p.stem
    with p.open("w", encoding="utf-8") as fh:
        fh.write(f'TITLE "{label}"\n')
        fh.write(f"LUT_3D_SIZE {lut.size}\n")
        fh.write(f"DOMAIN_MIN {lut.domain_min[0]:.6f} {lut.domain_min[1]:.6f} {lut.domain_min[2]:.6f}\n")
        fh.write(f"DOMAIN_MAX {lut.domain_max[0]:.6f} {lut.domain_max[1]:.6f} {lut.domain_max[2]:.6f}\n")
        # .cube iterates R fastest, then G, then B.
        table = lut.table  # (B, G, R, 3) in our convention
        flat = table.reshape(-1, 3)
        for row in flat:
            fh.write(f"{row[0]:.6f} {row[1]:.6f} {row[2]:.6f}\n")
    return p


def apply_lut(image_rgb_float: np.ndarray, lut: Lut3D) -> np.ndarray:
    """Apply ``lut`` to an RGB float32 image in [0, 1].

    Trilinear interpolation in the lookup grid. ``image_rgb_float`` must be
    of shape ``(H, W, 3)`` or ``(N, 3)`` with channel order **RGB** (not BGR).
    """
    if image_rgb_float.dtype != np.float32:
        image_rgb_float = image_rgb_float.astype(np.float32)
    if image_rgb_float.shape[-1] != 3:
        raise ValueError(f"expected last dim 3 (RGB), got {image_rgb_float.shape}")

    dmin = np.array(lut.domain_min, dtype=np.float32)
    dmax = np.array(lut.domain_max, dtype=np.float32)
    domain = np.maximum(dmax - dmin, 1e-6)

    # Normalise inputs into the declared domain [0, size-1].
    normed = (image_rgb_float - dmin) / domain
    normed = np.clip(normed, 0.0, 1.0)
    grid = normed * (lut.size - 1)

    # Integer floor + fractional remainder per channel.
    g0 = np.floor(grid).astype(np.int32)
    g1 = np.clip(g0 + 1, 0, lut.size - 1)
    t = grid - g0  # in [0, 1]

    r0, g0g, b0 = g0[..., 0], g0[..., 1], g0[..., 2]
    r1, g1g, b1 = g1[..., 0], g1[..., 1], g1[..., 2]
    tr, tg, tb = t[..., 0:1], t[..., 1:2], t[..., 2:3]

    # 8 corner samples from the lookup table.
    table = lut.table  # shape (B, G, R, 3)
    c000 = table[b0, g0g, r0]
    c100 = table[b0, g0g, r1]
    c010 = table[b0, g1g, r0]
    c110 = table[b0, g1g, r1]
    c001 = table[b1, g0g, r0]
    c101 = table[b1, g0g, r1]
    c011 = table[b1, g1g, r0]
    c111 = table[b1, g1g, r1]

    # Trilinear blend.
    c00 = c000 * (1.0 - tr) + c100 * tr
    c10 = c010 * (1.0 - tr) + c110 * tr
    c01 = c001 * (1.0 - tr) + c101 * tr
    c11 = c011 * (1.0 - tr) + c111 * tr

    c0 = c00 * (1.0 - tg) + c10 * tg
    c1 = c01 * (1.0 - tg) + c11 * tg

    out = c0 * (1.0 - tb) + c1 * tb
    return out.astype(np.float32)


def compose(*luts: Lut3D, size: Optional[int] = None) -> Lut3D:
    """Compose two or more LUTs into one.

    The result has the same effect as applying each LUT in sequence. Useful
    so the export path can ship one combined .cube to ffmpeg instead of a
    chain of ``lut3d`` filters.
    """
    if not luts:
        raise ValueError("compose() needs at least one LUT")
    out_size = size or max(l.size for l in luts)
    work = identity_lut(out_size)
    for lut in luts:
        # Treat the working LUT's table as an "image" of (size**3, 3) values
        # to look up in the next LUT.
        flat = work.table.reshape(-1, 3)
        looked_up = apply_lut(flat, lut)
        work = Lut3D(
            size=out_size,
            table=looked_up.reshape(out_size, out_size, out_size, 3).astype(np.float32),
            title=f"compose({', '.join(l.title for l in luts)})",
        )
    return work


def lut_from_function(
    fn,  # Callable[[np.ndarray], np.ndarray] mapping (H,W,3) RGB float -> RGB float
    size: int = 33,
    title: str = "",
) -> Lut3D:
    """Build a :class:`Lut3D` by evaluating ``fn`` on the identity grid.

    Used to bake the current preset + manual params into a LUT once, so the
    preview and the ffmpeg export both apply the same transformation.
    """
    ident = identity_lut(size).table.reshape(-1, 1, 3)  # (N,1,3) treat as "image"
    out = fn(ident).reshape(size, size, size, 3).astype(np.float32)
    return Lut3D(size=size, table=out, title=title or fn.__name__)


def to_bgr_image(arr_rgb_float: np.ndarray, *, dtype=np.uint8) -> np.ndarray:
    """Convert an RGB float [0,1] image back to OpenCV's BGR uint8 (or uint16)."""
    img = np.clip(arr_rgb_float, 0.0, 1.0)
    if dtype is np.uint16:
        img = (img * 65535.0 + 0.5).astype(np.uint16)
    else:
        img = (img * 255.0 + 0.5).astype(np.uint8)
    # RGB -> BGR
    return img[..., ::-1].copy()
