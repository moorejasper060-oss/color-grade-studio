"""Generate the Color Grade Studio app logo.

Produces, at the repo root::

    src/color_grade_studio/resources/icons/app.png   (1024x1024, app surface)
    src/color_grade_studio/resources/icons/app.ico   (multi-resolution Windows icon)
    docs/screenshots/logo.png                        (large copy for the README)

Design:
    Modern Windows-11-style app icon. Dark rounded-square background with a
    subtle inner shine, three overlapping color-grading wheels arranged in a
    triangle (shadows / midtones / highlights), each rendered as a soft
    radial gradient so the overlaps blend smoothly into the classic
    "color picker" white core.
"""
from __future__ import annotations

import math
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter


HERE = Path(__file__).resolve().parent
REPO = HERE.parent
ICONS_DIR = REPO / "src" / "color_grade_studio" / "resources" / "icons"
DOCS_DIR = REPO / "docs" / "screenshots"

MASTER_SIZE = 1024  # render large, downscale for everything else

# Color grading classic 3-wheel palette (BGR feel translated to RGB here).
SHADOW_COLOR = (74, 158, 255)      # cool blue
MIDTONE_COLOR = (102, 220, 142)    # forest green
HIGHLIGHT_COLOR = (255, 152, 92)   # warm orange


def make_rounded_mask(size: int, radius: int) -> Image.Image:
    """A grayscale mask used to clip the icon into a rounded square."""
    mask = Image.new("L", (size, size), 0)
    draw = ImageDraw.Draw(mask)
    draw.rounded_rectangle((0, 0, size - 1, size - 1), radius, fill=255)
    return mask


def make_background(size: int) -> Image.Image:
    """Dark base panel with a subtle top-edge highlight for depth."""
    img = Image.new("RGB", (size, size), (16, 16, 18))
    # Top sheen via a thin vertical gradient.
    grad = np.linspace(0.0, 1.0, size, dtype=np.float32)
    sheen = np.zeros((size, size, 3), dtype=np.uint8)
    base = np.array([16, 16, 18], dtype=np.float32)
    top = np.array([42, 44, 52], dtype=np.float32)
    for y in range(size):
        # fade strength: strong at top, gone by ~25% height
        t = max(0.0, 1.0 - y / (size * 0.28))
        color = base + (top - base) * t
        sheen[y, :, :] = color.astype(np.uint8)
    img = Image.fromarray(sheen)
    return img.convert("RGB")


def draw_color_wheel(layer_size: int, color: tuple[int, int, int]) -> Image.Image:
    """A single radial color disc on a transparent background.

    Bright saturated core, slight specular highlight, soft alpha rim — looks
    like a glowing gel filter. Designed so overlapping discs blend into
    near-white in the middle (the classic 3-wheel grading icon look).
    """
    arr = np.zeros((layer_size, layer_size, 4), dtype=np.float32)
    cx = cy = layer_size / 2.0
    radius = layer_size / 2.0
    y, x = np.mgrid[0:layer_size, 0:layer_size].astype(np.float32)
    dist = np.sqrt((x - cx) ** 2 + (y - cy) ** 2) / radius
    dist = np.clip(dist, 0.0, 1.0)

    r, g, b = color
    edge_color = np.array([r, g, b], dtype=np.float32)
    # Brighter, more saturated than the original — push toward an almost
    # neon vibe in the core so overlaps light up.
    boosted = np.minimum(edge_color * 1.1 + 35.0, 255.0)
    near_white = np.array([255, 255, 255], dtype=np.float32)

    # Two-zone gradient: small bright core (0..0.25) -> saturated body
    # (0.25..0.85) -> deep color rim.
    t_core = np.clip(dist / 0.25, 0.0, 1.0)
    body = near_white * (1.0 - t_core)[..., None] + boosted * t_core[..., None]
    t_rim = np.clip((dist - 0.55) / 0.45, 0.0, 1.0)
    rgb = body * (1.0 - t_rim)[..., None] + edge_color * t_rim[..., None]
    arr[..., 0:3] = rgb

    # Alpha: strong solid up to 0.85, then quick falloff to 0 by 1.0.
    alpha = np.clip(1.0 - (np.clip(dist - 0.84, 0.0, 1.0) / 0.16), 0.0, 1.0)
    alpha *= 0.97
    arr[..., 3] = alpha * 255.0

    # Subtle specular dot top-left of center for depth.
    sx = cx - radius * 0.22
    sy = cy - radius * 0.22
    sdist = np.sqrt((x - sx) ** 2 + (y - sy) ** 2) / (radius * 0.55)
    sdist = np.clip(sdist, 0.0, 1.0)
    specular = np.clip(1.0 - sdist, 0.0, 1.0) ** 3 * 80.0
    arr[..., 0:3] = np.minimum(arr[..., 0:3] + specular[..., None], 255.0)

    return Image.fromarray(arr.astype(np.uint8), "RGBA")


def composite_wheels(size: int) -> Image.Image:
    """Logo content: a film-style frame with a teal-and-orange color split.

    The frame is the universal "video" symbol; the split palette is the
    universal "color grading" signature. Sprocket holes on the left and
    right edges sell the film-strip metaphor.
    """
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))

    # ------- inner frame (rounded rect, slight margin) -------
    margin = int(size * 0.16)
    frame_box = (margin, margin, size - margin, size - margin)
    inner_radius = int(size * 0.05)

    # Render the colored interior as two horizontal halves on a transparent
    # canvas the size of the frame interior, then composite.
    interior_w = frame_box[2] - frame_box[0]
    interior_h = frame_box[3] - frame_box[1]
    interior = _make_grade_split(interior_w, interior_h)

    # Mask the interior into the rounded rectangle.
    mask = Image.new("L", (interior_w, interior_h), 0)
    md = ImageDraw.Draw(mask)
    md.rounded_rectangle((0, 0, interior_w - 1, interior_h - 1),
                         inner_radius, fill=255)
    img.paste(interior, (frame_box[0], frame_box[1]), mask)

    # ------- film sprocket holes on left and right edges -------
    hole_w = int(size * 0.035)
    hole_h = int(size * 0.05)
    hole_r = int(size * 0.012)
    hole_color = (10, 10, 12, 255)
    rows = 4
    edge_inset = int(size * 0.06)
    spacing = (interior_h - hole_h * rows) // (rows + 1)
    for row in range(rows):
        y = frame_box[1] + spacing * (row + 1) + hole_h * row
        # left hole
        draw = ImageDraw.Draw(img)
        draw.rounded_rectangle(
            (edge_inset, y, edge_inset + hole_w, y + hole_h),
            hole_r, fill=hole_color,
        )
        # right hole
        rx = size - edge_inset - hole_w
        draw.rounded_rectangle(
            (rx, y, rx + hole_w, y + hole_h),
            hole_r, fill=hole_color,
        )

    # ------- inner frame outline (subtle, light) -------
    out = ImageDraw.Draw(img)
    out.rounded_rectangle(frame_box, inner_radius,
                          outline=(255, 255, 255, 70),
                          width=max(2, size // 320))
    return img


def _make_grade_split(w: int, h: int) -> Image.Image:
    """Two-tone color split: cool teal on top, warm orange on bottom,
    with a soft horizontal seam.

    This is the literal teal-and-orange cinematic look. We use it as the
    interior of the film frame so the icon "shows what the app does."
    """
    arr = np.zeros((h, w, 3), dtype=np.float32)
    # Build vertical gradient from teal -> seam -> orange.
    teal_top = np.array([28, 130, 145], dtype=np.float32)
    teal_mid = np.array([72, 200, 215], dtype=np.float32)
    orange_mid = np.array([255, 180, 110], dtype=np.float32)
    orange_bot = np.array([220, 110, 60], dtype=np.float32)

    for y in range(h):
        t = y / max(h - 1, 1)
        if t < 0.45:
            local = t / 0.45
            color = teal_top * (1 - local) + teal_mid * local
        elif t < 0.55:
            local = (t - 0.45) / 0.10
            color = teal_mid * (1 - local) + orange_mid * local
        else:
            local = (t - 0.55) / 0.45
            color = orange_mid * (1 - local) + orange_bot * local
        arr[y, :, :] = color

    # Add a horizontal slight darkening at the very top and bottom for depth.
    for y in range(h):
        d_edge = min(y, h - 1 - y) / (h * 0.18)
        d_edge = min(d_edge, 1.0)
        arr[y, :, :] *= 0.85 + 0.15 * d_edge

    # Slight side vignette so the frame interior looks 3D.
    cx = w / 2
    x = np.arange(w, dtype=np.float32)
    side_falloff = 1.0 - np.clip(np.abs(x - cx) / cx - 0.7, 0, 1) * 0.4
    arr *= side_falloff[None, :, None]

    arr = np.clip(arr, 0, 255).astype(np.uint8)
    img = Image.fromarray(arr, mode="RGB")
    # Tiny blur on the seam to soften.
    img = img.filter(ImageFilter.GaussianBlur(radius=max(1, h // 256)))
    return img.convert("RGBA")


def draw_glow(layer_size: int, color: tuple[int, int, int]) -> Image.Image:
    """Soft outer glow halo for a wheel — a blurred translucent ring."""
    layer = Image.new("RGBA", (layer_size * 2, layer_size * 2), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    cx = layer_size
    cy = layer_size
    r = int(layer_size * 0.55)
    draw.ellipse((cx - r, cy - r, cx + r, cy + r), fill=color + (110,))
    layer = layer.filter(ImageFilter.GaussianBlur(radius=layer_size // 6))
    # crop the centered region back to layer_size
    left = layer_size // 2
    return layer.crop((left, left, left + layer_size, left + layer_size))


def add_specular_ring(base: Image.Image, size: int) -> Image.Image:
    """A thin highlight stroke around the icon, sub-pixel above the rounded edge."""
    overlay = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    radius = size // 5
    inset = max(1, size // 256)
    # White-ish soft inner stroke for the rounded edge.
    draw.rounded_rectangle(
        (inset, inset, size - 1 - inset, size - 1 - inset),
        radius - inset,
        outline=(255, 255, 255, 38),
        width=max(1, size // 320),
    )
    overlay = overlay.filter(ImageFilter.GaussianBlur(radius=max(1, size // 512)))
    return Image.alpha_composite(base.convert("RGBA"), overlay)


def render_master() -> Image.Image:
    size = MASTER_SIZE
    bg = make_background(size).convert("RGBA")
    wheels = composite_wheels(size)
    combined = Image.alpha_composite(bg, wheels)
    combined = add_specular_ring(combined, size)
    mask = make_rounded_mask(size, size // 5)
    # Apply the rounded mask: transparent corners on the final RGBA.
    final = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    final.paste(combined, (0, 0), mask)
    return final


def write_png(master: Image.Image, target: Path, size: int) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    if master.size != (size, size):
        out = master.resize((size, size), Image.Resampling.LANCZOS)
    else:
        out = master
    out.save(target, format="PNG", optimize=True)


def write_ico(master: Image.Image, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    sizes = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
    # Pillow takes the original and resamples per size internally when
    # passed `sizes=`. Pre-resampling each size by hand and passing as
    # `append_images` gives nicer downscales for small icon sizes.
    base = master.resize((256, 256), Image.Resampling.LANCZOS)
    extra = [master.resize(s, Image.Resampling.LANCZOS) for s in sizes if s != (256, 256)]
    base.save(target, format="ICO", sizes=sizes, append_images=extra)


def main() -> int:
    master = render_master()
    write_png(master, ICONS_DIR / "app.png", 1024)
    write_png(master, ICONS_DIR / "app_256.png", 256)
    write_ico(master, ICONS_DIR / "app.ico")
    write_png(master, DOCS_DIR / "logo.png", 512)
    print(f"Wrote: {ICONS_DIR / 'app.png'}")
    print(f"Wrote: {ICONS_DIR / 'app_256.png'}")
    print(f"Wrote: {ICONS_DIR / 'app.ico'}")
    print(f"Wrote: {DOCS_DIR / 'logo.png'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
