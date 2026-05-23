"""Build a standalone Windows distribution with PyInstaller.

Usage:
    python build_exe.py            # full build (onedir)
    python build_exe.py --onefile  # single-exe build (slower startup)

The script:
  * locates ffmpeg.exe / ffprobe.exe on PATH and copies them into the dist
    folder so the bundled app does not depend on a system ffmpeg install;
  * runs PyInstaller with the right flags for PySide6 + OpenCV;
  * prints the path to the built launcher.
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
ENTRY = SRC / "color_grade_studio" / "main.py"
NAME = "ColorGradeStudio"


def locate_ffmpeg() -> tuple[Path, Path | None]:
    ffmpeg = shutil.which("ffmpeg") or shutil.which("ffmpeg.exe")
    if not ffmpeg:
        raise SystemExit("ffmpeg not found on PATH — install it first (winget install Gyan.FFmpeg).")
    ffmpeg_path = Path(ffmpeg)
    ffprobe = shutil.which("ffprobe") or shutil.which("ffprobe.exe")
    return ffmpeg_path, Path(ffprobe) if ffprobe else None


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Build the Windows .exe")
    ap.add_argument("--onefile", action="store_true",
                    help="bundle as a single .exe (slower first-launch)")
    ap.add_argument("--clean", action="store_true",
                    help="remove previous build/dist directories first")
    return ap.parse_args()


def main() -> int:
    args = parse_args()
    ffmpeg, ffprobe = locate_ffmpeg()

    if args.clean:
        for d in (ROOT / "build", ROOT / "dist"):
            if d.exists():
                print(f"removing {d}")
                shutil.rmtree(d, ignore_errors=True)

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm",
        "--name", NAME,
        "--windowed",
        "--paths", str(SRC),
        "--collect-submodules", "color_grade_studio",
    ]
    if args.onefile:
        cmd.append("--onefile")
    else:
        cmd.append("--onedir")

    # Bundle ffmpeg binaries next to the exe (PyInstaller dest of '.').
    cmd += ["--add-binary", f"{ffmpeg};."]
    if ffprobe:
        cmd += ["--add-binary", f"{ffprobe};."]

    cmd.append(str(ENTRY))

    print("Running:", " ".join(cmd))
    result = subprocess.run(cmd, cwd=ROOT)
    if result.returncode != 0:
        return result.returncode

    dist_dir = ROOT / "dist" / NAME
    exe = (ROOT / "dist" / f"{NAME}.exe") if args.onefile else (dist_dir / f"{NAME}.exe")
    if exe.exists():
        print(f"\nBuilt: {exe}")
    else:
        print(f"\nCould not locate built exe (expected {exe})")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
