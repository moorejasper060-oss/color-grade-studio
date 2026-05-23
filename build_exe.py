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
import hashlib
import os
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
ENTRY = SRC / "color_grade_studio" / "main.py"
NAME = "ColorGradeStudio"
ICON_ICO = SRC / "color_grade_studio" / "resources" / "icons" / "app.ico"
ICON_PNG = SRC / "color_grade_studio" / "resources" / "icons" / "app.png"


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
    ap.add_argument("--skip-verify", action="store_true",
                    help="skip the post-build smoke test")
    return ap.parse_args()


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    args = parse_args()
    ffmpeg, ffprobe = locate_ffmpeg()

    print("Bundling FFmpeg:")
    print(f"  ffmpeg : {ffmpeg}   sha256={_sha256(ffmpeg)}")
    if ffprobe:
        print(f"  ffprobe: {ffprobe}   sha256={_sha256(ffprobe)}")

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

    if ICON_ICO.exists():
        cmd += ["--icon", str(ICON_ICO)]
    else:
        print(f"WARNING: icon missing at {ICON_ICO} — exe will use the default icon. "
              f"Run `python tools/generate_logo.py` first.")

    # Bundle ffmpeg binaries next to the exe (PyInstaller dest of '.').
    cmd += ["--add-binary", f"{ffmpeg};."]
    if ffprobe:
        cmd += ["--add-binary", f"{ffprobe};."]

    # Bundle the PNG icon so QApplication.setWindowIcon can find it at runtime.
    if ICON_PNG.exists():
        cmd += ["--add-data", f"{ICON_PNG};color_grade_studio/resources/icons"]

    cmd.append(str(ENTRY))

    print("Running:", " ".join(cmd))
    result = subprocess.run(cmd, cwd=ROOT)
    if result.returncode != 0:
        return result.returncode

    dist_dir = ROOT / "dist" / NAME
    exe = (ROOT / "dist" / f"{NAME}.exe") if args.onefile else (dist_dir / f"{NAME}.exe")
    if not exe.exists():
        print(f"\nCould not locate built exe (expected {exe})")
        return 1

    print(f"\nBuilt: {exe}")

    if not args.skip_verify:
        print("Verifying the built exe boots cleanly...")
        rc = subprocess.run(
            [sys.executable, str(ROOT / "tools" / "verify_exe.py"), str(exe)],
            cwd=ROOT,
        ).returncode
        if rc != 0:
            print("Verification FAILED. The exe exists but does not boot cleanly.")
            return rc
    return 0


if __name__ == "__main__":
    sys.exit(main())
