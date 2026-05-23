"""Built-in color grade presets.

Each preset is a tuned :class:`GradeParams`. Values were dialed in by eye on
neutral test footage; the goal is a recognisable look the moment you click,
which the user can then nudge with the manual sliders.

Lift/Gain/Gamma triplets are BGR (matching OpenCV channel order).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List

from .color_engine import GradeParams


@dataclass
class Preset:
    id: str
    name: str
    description: str
    params: GradeParams
    reference: str = ""  # film reference shown in UI tooltip; "" = none


_DEFS: List[Preset] = [
    Preset(
        id="none",
        name="Original",
        description="No grading applied. Use the sliders to adjust manually.",
        params=GradeParams(),
    ),
    Preset(
        id="cinematic",
        name="Cinematic",
        description="Classic teal shadows, warm highlights, lifted blacks.",
        params=GradeParams(
            contrast=0.15,
            saturation=-0.10,
            temperature=0.05,
            shadows_rgb=(0.04, 0.01, -0.01),
            highlights_rgb=(0.97, 1.00, 1.05),
            fade=0.10,
        ),
    ),
    Preset(
        id="teal_orange",
        name="Teal & Orange",
        description="Strong complementary push: cyan/teal shadows, orange skin tones.",
        params=GradeParams(
            contrast=0.20,
            saturation=0.15,
            temperature=0.10,
            shadows_rgb=(0.07, 0.02, -0.03),
            highlights_rgb=(0.90, 1.00, 1.10),
        ),
    ),
    Preset(
        id="moody",
        name="Moody",
        description="Low-key, desaturated, cool shadow tint.",
        params=GradeParams(
            exposure=-0.10,
            contrast=0.10,
            saturation=-0.20,
            temperature=-0.10,
            shadows_rgb=(0.05, 0.02, 0.00),
            fade=0.05,
        ),
    ),
    Preset(
        id="vintage",
        name="Vintage",
        description="Faded warm look, lifted blacks, slight green in highlights.",
        params=GradeParams(
            contrast=-0.05,
            saturation=-0.15,
            temperature=0.18,
            tint=-0.05,
            shadows_rgb=(-0.02, 0.00, 0.06),
            highlights_rgb=(0.95, 1.03, 1.00),
            fade=0.30,
        ),
    ),
    Preset(
        id="faded_film",
        name="Faded Film",
        description="Soft, washed-out film stock with green-tinted shadows.",
        params=GradeParams(
            contrast=-0.15,
            saturation=-0.25,
            tint=-0.08,
            shadows_rgb=(0.00, 0.04, 0.00),
            fade=0.45,
        ),
    ),
    Preset(
        id="bleach_bypass",
        name="Bleach Bypass",
        description="Silver-halide look: low saturation, high contrast.",
        params=GradeParams(
            contrast=0.35,
            saturation=-0.45,
            temperature=-0.05,
            highlights_rgb=(1.05, 1.05, 1.05),
        ),
    ),
    Preset(
        id="day_for_night",
        name="Day for Night",
        description="Daytime footage shifted toward a cool night-time look.",
        params=GradeParams(
            exposure=-0.25,
            contrast=0.20,
            saturation=-0.20,
            temperature=-0.35,
            shadows_rgb=(0.06, 0.00, -0.04),
            highlights_rgb=(1.10, 0.95, 0.85),
        ),
    ),
    Preset(
        id="cross_process",
        name="Cross Process",
        description="Cyan shadows and yellow-green highlights, like XPRO film.",
        params=GradeParams(
            contrast=0.20,
            saturation=0.20,
            tint=-0.10,
            shadows_rgb=(0.06, 0.04, -0.04),
            highlights_rgb=(0.92, 1.05, 1.02),
        ),
    ),
    Preset(
        id="anamorphic",
        name="Anamorphic",
        description="Cool cyan cast in highlights with subtle magenta in shadows.",
        params=GradeParams(
            contrast=0.10,
            saturation=-0.05,
            temperature=-0.08,
            shadows_rgb=(-0.01, -0.01, 0.03),
            highlights_rgb=(1.06, 1.02, 0.96),
            vignette=0.25,
        ),
    ),
    Preset(
        id="sepia",
        name="Sepia",
        description="Warm brown monochrome.",
        params=GradeParams(
            saturation=-1.0,
            temperature=0.35,
            tint=0.05,
            highlights_rgb=(0.75, 0.95, 1.10),
            shadows_rgb=(-0.03, 0.00, 0.04),
        ),
    ),
    Preset(
        id="bw",
        name="Black & White",
        description="Neutral monochrome conversion.",
        params=GradeParams(
            saturation=-1.0,
            contrast=0.05,
        ),
    ),
    Preset(
        id="bw_high_contrast",
        name="B&W High Contrast",
        description="Punchy monochrome: crushed blacks, bright whites.",
        params=GradeParams(
            saturation=-1.0,
            contrast=0.45,
            shadows_rgb=(-0.04, -0.04, -0.04),
            highlights_rgb=(1.08, 1.08, 1.08),
        ),
    ),
    Preset(
        id="warm",
        name="Warm",
        description="Pushes the image toward golden/orange.",
        params=GradeParams(
            contrast=0.05,
            saturation=0.05,
            temperature=0.25,
        ),
    ),
    Preset(
        id="cool",
        name="Cool",
        description="Pushes the image toward blue/cyan.",
        params=GradeParams(
            contrast=0.05,
            saturation=0.05,
            temperature=-0.25,
        ),
    ),
    Preset(
        id="vibrant",
        name="Vibrant",
        description="Boost saturation while keeping skin tones natural.",
        params=GradeParams(
            contrast=0.10,
            saturation=0.30,
        ),
    ),
    Preset(
        id="punch",
        name="Punch",
        description="High contrast + saturation for snappy social-media energy.",
        params=GradeParams(
            contrast=0.30,
            saturation=0.30,
            shadows_rgb=(-0.02, -0.02, -0.02),
            highlights_rgb=(1.04, 1.04, 1.04),
        ),
    ),
    Preset(
        id="golden_hour",
        name="Golden Hour",
        description="Warm with rolled-off highlights, like late-afternoon sun.",
        params=GradeParams(
            exposure=0.05,
            contrast=0.05,
            saturation=0.05,
            temperature=0.30,
            highlights_rgb=(0.90, 0.97, 1.08),
            fade=0.10,
        ),
    ),
    Preset(
        id="sunset",
        name="Sunset",
        description="Magenta/orange skies; great for landscape footage.",
        params=GradeParams(
            contrast=0.10,
            saturation=0.15,
            temperature=0.20,
            tint=0.08,
            highlights_rgb=(0.92, 0.97, 1.10),
        ),
    ),
    Preset(
        id="clean_crisp",
        name="Clean & Crisp",
        description="Subtle contrast and saturation bump for a clean modern look.",
        params=GradeParams(
            contrast=0.12,
            saturation=0.10,
            highlights_rgb=(1.02, 1.02, 1.02),
        ),
    ),
    Preset(
        id="pastel",
        name="Pastel",
        description="Lifted whites, low saturation, soft shadows.",
        params=GradeParams(
            contrast=-0.10,
            saturation=-0.15,
            tint=0.05,
            shadows_rgb=(0.03, 0.03, 0.03),
            highlights_rgb=(1.00, 1.02, 1.02),
            fade=0.20,
        ),
    ),
]


PRESETS: List[Preset] = _DEFS
_BY_ID: Dict[str, Preset] = {p.id: p for p in _DEFS}


def get_preset(preset_id: str) -> Preset:
    """Look up a preset by id. Falls back to the 'none' preset."""
    return _BY_ID.get(preset_id, _BY_ID["none"])
