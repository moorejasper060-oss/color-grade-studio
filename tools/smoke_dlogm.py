"""End-to-end smoke test against a real DJI D-Log M clip.

Runs an actual ExportJob on a short trim of a 4K HEVC Main 10 source,
verifying:
  * the file opens via OpenCV
  * the v2 grade applies cleanly through ffmpeg's lut3d filter
  * the output is yuv420p10le High 10 (10-bit preserved end-to-end)
  * the output is playable

Skips visual check (that's for you at the PC).
"""
from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from color_grade_studio.core import (
    ExportJob,
    ExportSettings,
    PRESETS,
    VideoSource,
    find_ffprobe,
    get_preset,
)


def probe(p: Path) -> dict:
    ffprobe = find_ffprobe()
    cmd = [
        ffprobe, "-v", "error", "-select_streams", "v:0",
        "-show_entries", "stream=codec_name,profile,pix_fmt,width,height,r_frame_rate",
        "-of", "default=noprint_wrappers=1",
        str(p),
    ]
    r = subprocess.run(cmd, capture_output=True, text=True, check=True)
    info = {}
    for line in r.stdout.splitlines():
        if "=" in line:
            k, v = line.split("=", 1)
            info[k.strip()] = v.strip()
    return info


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: python tools/smoke_dlogm.py <path_to_dlogm.mp4> [preset_id] [n_seconds]")
        return 2

    src = Path(sys.argv[1])
    preset_id = sys.argv[2] if len(sys.argv) > 2 else "cinematic"
    duration_sec = float(sys.argv[3]) if len(sys.argv) > 3 else 2.0

    print(f"Source: {src.name}")
    print(f"Preset: {preset_id}")
    print()

    src_info = probe(src)
    print("Source metadata:")
    for k, v in src_info.items():
        print(f"  {k} = {v}")

    # Open via OpenCV to confirm reading works.
    print()
    print("Opening via OpenCV...")
    vs = VideoSource(src)
    print(f"  Resolution: {vs.meta.width}x{vs.meta.height}")
    print(f"  FPS:        {vs.meta.fps:.3f}")
    print(f"  Frames:     {vs.meta.frame_count}")
    # Try reading frame 0.
    frame = vs.read_frame(0)
    if frame is None:
        print("  FAIL: cv2.VideoCapture could not decode frame 0")
        vs.release()
        return 1
    print(f"  Frame 0:    shape={frame.shape}, dtype={frame.dtype}, mean={frame.mean():.1f}")
    vs.release()

    # Build a trimmed-export job (don't burn 2 minutes on a 4K 60p re-encode).
    end_frame = int(round(duration_sec * vs.meta.fps)) - 1
    out_path = ROOT / "refs" / f"_smoke_{preset_id}_{src.stem}.mp4"
    out_path.parent.mkdir(exist_ok=True)
    if out_path.exists():
        out_path.unlink()

    settings = ExportSettings(
        output_path=out_path,
        trim_start_frame=0,
        trim_end_frame=end_frame,
        crf=23,
        preset="ultrafast",  # speed > quality for the smoke test
        include_audio=False,  # don't bother with audio for the smoke
    )
    preset = get_preset(preset_id)
    print()
    print(f"Exporting {duration_sec}s ({end_frame + 1} frames) with preset {preset.name!r}...")

    progress = {"done": 0, "total": end_frame + 1, "last_print": time.time()}

    def on_progress(done, total):
        progress["done"] = done
        if time.time() - progress["last_print"] > 1.0:
            print(f"  {done}/{total} frames ({100 * done / total:.0f}%)")
            progress["last_print"] = time.time()

    job = ExportJob(src, preset.params, settings)
    job.on_progress(on_progress)

    t0 = time.time()
    try:
        result = job.run()
    except Exception as exc:
        print(f"\nFAIL: export raised {type(exc).__name__}: {exc}")
        return 1
    elapsed = time.time() - t0
    print(f"\nExport finished in {elapsed:.1f}s ({progress['done'] / elapsed:.1f} fps)")
    print(f"  Output: {result}")
    print(f"  Size:   {result.stat().st_size / (1024 * 1024):.1f} MB")

    # Probe the output.
    out_info = probe(result)
    print()
    print("Output metadata:")
    for k, v in out_info.items():
        print(f"  {k} = {v}")

    # Verify 10-bit was preserved.
    print()
    if "10" in out_info.get("pix_fmt", ""):
        print(f"  OK pix_fmt {out_info['pix_fmt']} — 10-bit preserved")
    else:
        print(f"  FAIL pix_fmt {out_info.get('pix_fmt')} — 10-bit NOT preserved")
        return 1
    profile = out_info.get("profile", "")
    if "High 10" in profile or "high10" in profile.lower():
        print(f"  OK profile {profile!r} — High 10")
    else:
        print(f"  FAIL profile {profile!r} — not High 10")
        return 1

    print()
    print(f"PASS: real D-Log M clip -> graded -> 10-bit H.264 output at {result}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
