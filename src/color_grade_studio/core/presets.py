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
        description="Modern Hollywood default: teal shadows, warm highlights, lifted blacks.",
        reference="Netflix originals · Marvel",
        params=GradeParams(
            contrast=0.18,
            saturation=-0.05,
            temperature=0.06,
            shadows_rgb=(0.05, 0.01, -0.02),
            highlights_rgb=(0.95, 1.00, 1.07),
            fade=0.12,
        ),
    ),
    Preset(
        id="teal_orange",
        name="Teal & Orange",
        description="Aggressive complementary push: cyan shadows, orange skin.",
        reference="Mad Max: Fury Road · Transformers",
        params=GradeParams(
            contrast=0.25,
            saturation=0.25,
            temperature=0.12,
            shadows_rgb=(0.09, 0.02, -0.04),
            highlights_rgb=(0.85, 1.00, 1.15),
        ),
    ),
    Preset(
        id="moody_drama",
        name="Moody Drama",
        description="Low-key desaturated drama with cool shadows.",
        reference="Joker · Sicario",
        params=GradeParams(
            exposure=-0.12,
            contrast=0.12,
            saturation=-0.25,
            temperature=-0.10,
            shadows_rgb=(0.06, 0.02, -0.01),
            highlights_rgb=(0.97, 0.97, 0.97),
            fade=0.10,
        ),
    ),
    Preset(
        id="bleach_bypass",
        name="Bleach Bypass",
        description="Silver-halide look: crushed blacks, low saturation, hard contrast.",
        reference="Saving Private Ryan · Three Kings",
        params=GradeParams(
            contrast=0.40,
            saturation=-0.50,
            temperature=-0.05,
            shadows_rgb=(-0.03, -0.03, -0.03),
            highlights_rgb=(1.06, 1.06, 1.06),
        ),
    ),
    Preset(
        id="golden_hour",
        name="Golden Hour",
        description="Warm rolled-off highlights with magic-hour glow.",
        reference="Knives Out · La La Land (sunset)",
        params=GradeParams(
            exposure=0.04,
            contrast=0.06,
            saturation=0.08,
            temperature=0.32,
            highlights_rgb=(0.88, 0.97, 1.10),
            fade=0.12,
        ),
    ),
    Preset(
        id="anamorphic_dream",
        name="Anamorphic Dream",
        description="Soft cyan highlights, magenta shadows, gentle vignette.",
        reference="Drive · Atomic Blonde",
        params=GradeParams(
            contrast=0.10,
            saturation=-0.05,
            temperature=-0.10,
            shadows_rgb=(-0.02, -0.02, 0.04),
            highlights_rgb=(1.08, 1.02, 0.95),
            vignette=0.28,
        ),
    ),
    Preset(
        id="vintage_print",
        name="Vintage Print",
        description="Kodak Vision3 film emulation: lifted blacks, warm cast, green highlights.",
        reference="Killers of the Flower Moon",
        params=GradeParams(
            contrast=-0.08,
            saturation=-0.18,
            temperature=0.20,
            tint=-0.06,
            shadows_rgb=(-0.01, 0.00, 0.05),
            highlights_rgb=(0.95, 1.03, 1.00),
            fade=0.35,
        ),
    ),
    Preset(
        id="day_for_night",
        name="Day for Night",
        description="Daytime footage shifted to a cool night-time look.",
        reference="Skyfall (night scenes)",
        params=GradeParams(
            exposure=-0.30,
            contrast=0.22,
            saturation=-0.25,
            temperature=-0.40,
            shadows_rgb=(0.08, 0.00, -0.05),
            highlights_rgb=(1.12, 0.95, 0.82),
        ),
    ),
    Preset(
        id="drone_hero",
        name="Drone Hero",
        description="Landscape-punchy: boosted sky/earth contrast, skin-tones preserved.",
        reference="DJI showreel · Planet Earth",
        params=GradeParams(
            contrast=0.25,
            saturation=0.32,
            temperature=0.05,
            shadows_rgb=(0.02, 0.00, -0.01),
            highlights_rgb=(0.97, 1.00, 1.05),
        ),
    ),
    Preset(
        id="cinescope",
        name="Cinescope",
        description="Modern Nolan clean: slight cool cast, lifted blacks, neutral skin.",
        reference="Oppenheimer · Tenet",
        params=GradeParams(
            contrast=0.15,
            saturation=-0.10,
            temperature=-0.05,
            shadows_rgb=(0.04, 0.02, 0.00),
            highlights_rgb=(1.00, 1.00, 0.98),
            fade=0.08,
        ),
    ),
]


PRESETS: List[Preset] = _DEFS
_BY_ID: Dict[str, Preset] = {p.id: p for p in _DEFS}


def get_preset(preset_id: str) -> Preset:
    """Look up a preset by id. Falls back to the 'none' preset."""
    return _BY_ID.get(preset_id, _BY_ID["none"])
