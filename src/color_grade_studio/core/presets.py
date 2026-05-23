"""Built-in cinematic grade presets.

Each preset is a tuned :class:`GradeParams` matched to a recognisable film
look — Mad Max teal-and-orange, Joker low-key, Drive neon, etc. The values
were dialed in by reference to free cinematic LUT packs (Color Grading
Central, FilterGrade, RocketStock) — those LUTs serve only as design
references, not redistribution.

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
        reference="",
    ),
    Preset(
        id="cinematic",
        name="Cinematic",
        description="Modern Hollywood default: teal shadows, warm highlights, soft S-curve.",
        reference="Netflix originals · Marvel",
        params=GradeParams(
            tone_curve=(0.02, 0.20, 0.50, 0.80, 0.96),
            contrast=0.10,
            shadows_hsl=(195.0 - 360.0, 1.15, 0.97),
            midtones_hsl=(0.0, 1.00, 1.0),
            highlights_hsl=(25.0, 1.10, 1.02),
            luma_sat=(0.80, 1.05, 0.90),
            halation=0.08,
            fade=0.08,
        ),
    ),
    Preset(
        id="teal_orange",
        name="Teal & Orange",
        description="Aggressive complementary push: cyan shadows, orange skin.",
        reference="Mad Max: Fury Road · Transformers",
        params=GradeParams(
            tone_curve=(0.01, 0.18, 0.50, 0.82, 0.98),
            contrast=0.18,
            shadows_hsl=(190.0 - 360.0, 1.40, 0.96),
            midtones_hsl=(15.0, 1.15, 1.0),
            highlights_hsl=(28.0, 1.30, 1.02),
            luma_sat=(0.85, 1.25, 0.95),
            saturation=0.10,
            halation=0.05,
        ),
    ),
    Preset(
        id="moody_drama",
        name="Moody Drama",
        description="Low-key film drama: cool shadows, lifted blacks, desaturated skin.",
        reference="Joker · Sicario",
        params=GradeParams(
            exposure=-0.10,
            tone_curve=(0.08, 0.20, 0.42, 0.62, 0.86),
            contrast=0.05,
            shadows_hsl=(210.0 - 360.0, 0.85, 1.00),
            midtones_hsl=(180.0 - 360.0, 0.70, 0.95),
            highlights_hsl=(40.0, 0.85, 0.95),
            luma_sat=(0.55, 0.80, 0.70),
            halation=0.04,
            fade=0.18,
        ),
    ),
    Preset(
        id="bleach_bypass",
        name="Bleach Bypass",
        description="Silver-halide war-film look: crushed blacks, near-monochrome, hard contrast.",
        reference="Saving Private Ryan · Three Kings",
        params=GradeParams(
            tone_curve=(0.0, 0.16, 0.52, 0.85, 1.0),
            contrast=0.30,
            shadows_hsl=(0.0, 0.30, 0.95),
            midtones_hsl=(0.0, 0.45, 1.0),
            highlights_hsl=(0.0, 0.55, 1.05),
            luma_sat=(0.30, 0.55, 0.60),
            shadows_rgb=(-0.03, -0.03, -0.03),
            highlights_rgb=(1.05, 1.05, 1.05),
        ),
    ),
    Preset(
        id="golden_hour",
        name="Golden Hour",
        description="Warm rolled-off highlights, magic-hour glow, halation bloom.",
        reference="Knives Out · La La Land (sunset)",
        params=GradeParams(
            exposure=0.03,
            tone_curve=(0.04, 0.24, 0.55, 0.84, 0.95),
            shadows_hsl=(35.0, 1.05, 1.0),
            midtones_hsl=(28.0, 1.20, 1.02),
            highlights_hsl=(38.0, 1.15, 1.05),
            luma_sat=(0.90, 1.20, 1.10),
            temperature=0.18,
            halation=0.18,
            fade=0.12,
        ),
    ),
    Preset(
        id="anamorphic_dream",
        name="Anamorphic Dream",
        description="Soft cyan highlights, magenta shadows, halation, gentle vignette.",
        reference="Drive · Atomic Blonde",
        params=GradeParams(
            tone_curve=(0.04, 0.22, 0.50, 0.78, 0.92),
            contrast=0.06,
            shadows_hsl=(310.0 - 360.0, 1.10, 1.00),
            midtones_hsl=(220.0 - 360.0, 0.90, 0.98),
            highlights_hsl=(190.0 - 360.0, 1.20, 1.03),
            luma_sat=(0.85, 1.00, 1.05),
            halation=0.22,
            vignette=0.30,
            fade=0.10,
        ),
    ),
    Preset(
        id="vintage_print",
        name="Vintage Print",
        description="Kodak Vision3 film emulation: lifted blacks, warm cast, green highlights, halation.",
        reference="Killers of the Flower Moon",
        params=GradeParams(
            tone_curve=(0.10, 0.26, 0.48, 0.70, 0.90),
            shadows_hsl=(28.0, 0.90, 1.0),
            midtones_hsl=(35.0, 1.05, 1.0),
            highlights_hsl=(80.0, 0.95, 0.98),
            luma_sat=(0.75, 1.00, 0.85),
            temperature=0.14,
            tint=-0.05,
            halation=0.25,
            fade=0.30,
        ),
    ),
    Preset(
        id="day_for_night",
        name="Day for Night",
        description="Daytime footage transformed to convincing night: blue highlights, near-black crushed shadows, desaturated skin.",
        reference="Skyfall (night scenes)",
        params=GradeParams(
            exposure=-0.18,
            tone_curve=(0.0, 0.08, 0.32, 0.58, 0.82),
            contrast=0.18,
            shadows_hsl=(285.0 - 360.0, 1.10, 0.50),
            midtones_hsl=(215.0 - 360.0, 0.80, 0.85),
            highlights_hsl=(210.0 - 360.0, 1.30, 0.90),
            luma_sat=(0.40, 0.55, 1.05),
            temperature=-0.20,
        ),
    ),
    Preset(
        id="drone_hero",
        name="Drone Hero",
        description="Landscape-punchy: deep blue sky, saturated foliage, lifted skin.",
        reference="DJI showreel · Planet Earth",
        params=GradeParams(
            tone_curve=(0.02, 0.22, 0.55, 0.82, 0.98),
            contrast=0.18,
            shadows_hsl=(210.0 - 360.0, 1.20, 0.98),
            midtones_hsl=(140.0, 1.20, 1.00),
            highlights_hsl=(210.0 - 360.0, 1.20, 1.02),
            luma_sat=(0.95, 1.30, 1.10),
            saturation=0.10,
        ),
    ),
    Preset(
        id="cinescope",
        name="Cinescope",
        description="Modern Nolan clean: subtly cool, lifted blacks, neutral skin, slight halation.",
        reference="Oppenheimer · Tenet",
        params=GradeParams(
            tone_curve=(0.06, 0.24, 0.50, 0.78, 0.94),
            contrast=0.10,
            shadows_hsl=(220.0 - 360.0, 0.95, 1.00),
            midtones_hsl=(0.0, 0.95, 1.0),
            highlights_hsl=(220.0 - 360.0, 0.90, 1.0),
            luma_sat=(0.85, 0.95, 0.90),
            temperature=-0.05,
            halation=0.06,
            fade=0.06,
        ),
    ),
]


PRESETS: List[Preset] = _DEFS
_BY_ID: Dict[str, Preset] = {p.id: p for p in _DEFS}


def get_preset(preset_id: str) -> Preset:
    """Look up a preset by id. Falls back to the 'none' preset."""
    return _BY_ID.get(preset_id, _BY_ID["none"])
