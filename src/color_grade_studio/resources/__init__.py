"""Bundled resource accessors (icons, etc.)."""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional


_RESOURCES_DIR = Path(__file__).resolve().parent


def icon_path(name: str = "app.png") -> Optional[Path]:
    """Return the absolute path to a bundled resource, or None if missing.

    Looks first relative to this file (works for both ``python -m`` and the
    PyInstaller bundle), then in ``sys._MEIPASS`` as a fallback in case
    PyInstaller laid resources out somewhere else.
    """
    direct = _RESOURCES_DIR / "icons" / name
    if direct.exists():
        return direct
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        bundled = Path(meipass) / "color_grade_studio" / "resources" / "icons" / name
        if bundled.exists():
            return bundled
    return None
