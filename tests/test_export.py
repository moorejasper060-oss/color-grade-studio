"""Tests for export pipeline edge cases: cancel cleanup, path validation, audio probing."""
from __future__ import annotations

import subprocess
import threading
import time
from pathlib import Path

import pytest

from color_grade_studio.core import (
    ExportError,
    ExportJob,
    ExportSettings,
    GradeParams,
    find_ffmpeg,
    get_preset,
    probe_audio_streams,
)
from color_grade_studio.ui.export_dialog import sanitize_output_path


@pytest.fixture(scope="module")
def clip_with_audio(tmp_path_factory) -> Path:
    try:
        ffmpeg = find_ffmpeg()
    except FileNotFoundError:
        pytest.skip("ffmpeg not installed")
    out = tmp_path_factory.mktemp("audio") / "audio.mp4"
    subprocess.run(
        [ffmpeg, "-y", "-hide_banner", "-loglevel", "error",
         "-f", "lavfi", "-i", "testsrc=size=160x120:rate=24:duration=3",
         "-f", "lavfi", "-i", "sine=frequency=440:duration=3",
         "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "ultrafast",
         "-c:a", "aac", "-shortest", str(out)],
        check=True, capture_output=True,
    )
    return out


@pytest.fixture(scope="module")
def clip_silent(tmp_path_factory) -> Path:
    try:
        ffmpeg = find_ffmpeg()
    except FileNotFoundError:
        pytest.skip("ffmpeg not installed")
    out = tmp_path_factory.mktemp("silent") / "silent.mp4"
    subprocess.run(
        [ffmpeg, "-y", "-hide_banner", "-loglevel", "error",
         "-f", "lavfi", "-i", "testsrc=size=160x120:rate=24:duration=2",
         "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "ultrafast",
         str(out)],
        check=True, capture_output=True,
    )
    return out


# --- Path sanitisation --------------------------------------------------


def test_sanitize_forces_mp4_extension():
    assert sanitize_output_path("foo.mov").suffix == ".mp4"
    assert sanitize_output_path("foo").suffix == ".mp4"


def test_sanitize_preserves_mp4():
    p = sanitize_output_path("video.mp4")
    assert p.name == "video.mp4"


def test_sanitize_rejects_empty_string():
    with pytest.raises(ValueError):
        sanitize_output_path("")
    with pytest.raises(ValueError):
        sanitize_output_path("   ")


def test_sanitize_strips_surrounding_quotes():
    # Windows paths copied from Explorer sometimes arrive quoted.
    assert sanitize_output_path('"out.mp4"').name == "out.mp4"


def test_sanitize_rejects_control_characters():
    with pytest.raises(ValueError):
        sanitize_output_path("foo\nbar.mp4")
    with pytest.raises(ValueError):
        sanitize_output_path("foo\x00bar.mp4")


def test_sanitize_rejects_windows_reserved_names():
    for name in ("CON", "PRN", "NUL", "COM1", "LPT9"):
        with pytest.raises(ValueError):
            sanitize_output_path(f"{name}.mp4")
        with pytest.raises(ValueError):
            sanitize_output_path(name)


def test_sanitize_user_home_expansion():
    expanded = sanitize_output_path("~/Videos/out.mp4")
    assert "~" not in str(expanded)


# --- Audio probing ------------------------------------------------------


def test_probe_audio_detects_audio_track(clip_with_audio):
    assert probe_audio_streams(clip_with_audio) is True


def test_probe_audio_returns_false_for_silent_clip(clip_silent):
    assert probe_audio_streams(clip_silent) is False


# --- Export cancellation -----------------------------------------------


def test_export_cancel_cleans_up_partial_file(clip_silent, tmp_path):
    out = tmp_path / "cancelled.mp4"
    settings = ExportSettings(
        output_path=out,
        trim_start_frame=0,
        trim_end_frame=47,
        crf=23,
        preset="ultrafast",
        include_audio=False,
    )
    job = ExportJob(clip_silent, get_preset("cinematic").params, settings)

    # Cancel after the first progress callback fires so we know the job has
    # actually started writing.
    started = threading.Event()
    job.on_progress(lambda d, t: started.set())

    def runner():
        try:
            job.run()
        except ExportError:
            pass

    t = threading.Thread(target=runner, daemon=True)
    t.start()
    assert started.wait(timeout=5), "export never produced its first progress tick"
    job.cancel()
    t.join(timeout=10)
    assert not t.is_alive(), "export job did not stop after cancel"
    assert not out.exists(), "cancelled export should not leave a partial file"


def test_export_failure_cleans_up_partial_file(clip_silent, tmp_path, monkeypatch):
    """If ffmpeg returns non-zero, the output file should be removed."""
    out = tmp_path / "doomed.mp4"
    settings = ExportSettings(
        output_path=out,
        trim_start_frame=0,
        trim_end_frame=23,
        crf=23,
        preset="ultrafast",
        include_audio=False,
    )
    job = ExportJob(clip_silent, get_preset("cinematic").params, settings)

    # Force ffmpeg to fail by handing it a bogus preset.
    settings.preset = "no-such-preset-please"
    with pytest.raises(ExportError):
        job.run()
    assert not out.exists(), "failed export should not leave a partial file"


# --- 10-bit handling ---------------------------------------------------


@pytest.fixture(scope="module")
def clip_10bit(tmp_path_factory) -> Path:
    """A 10-bit (yuv420p10le, high10 profile) source clip via ffmpeg."""
    try:
        ffmpeg = find_ffmpeg()
    except FileNotFoundError:
        pytest.skip("ffmpeg not installed")
    out = tmp_path_factory.mktemp("10bit") / "src10.mp4"
    subprocess.run(
        [ffmpeg, "-y", "-hide_banner", "-loglevel", "error",
         "-f", "lavfi", "-i", "testsrc=size=160x120:rate=24:duration=2",
         "-c:v", "libx264", "-pix_fmt", "yuv420p10le", "-profile:v", "high10",
         "-preset", "ultrafast", str(out)],
        check=True, capture_output=True,
    )
    return out


def test_export_preserves_10bit_when_source_is_10bit(clip_10bit, tmp_path):
    """Encoding a 10-bit source should land in yuv420p10le with high10 profile."""
    out = tmp_path / "out10.mp4"
    settings = ExportSettings(
        output_path=out,
        trim_start_frame=0,
        trim_end_frame=23,
        crf=20,
        preset="ultrafast",
        include_audio=False,
    )
    job = ExportJob(clip_10bit, get_preset("cinematic").params, settings)
    job.run()
    assert out.exists()

    # Probe the output and verify it's actually 10-bit.
    from color_grade_studio.core.video_io import find_ffprobe
    ffprobe = find_ffprobe()
    assert ffprobe is not None
    result = subprocess.run(
        [ffprobe, "-v", "error", "-select_streams", "v:0",
         "-show_entries", "stream=pix_fmt,profile",
         "-of", "default=noprint_wrappers=1", str(out)],
        capture_output=True, text=True, check=True,
    )
    pix_fmt = ""
    profile = ""
    for line in result.stdout.splitlines():
        if line.startswith("pix_fmt="):
            pix_fmt = line.split("=", 1)[1].strip()
        elif line.startswith("profile="):
            profile = line.split("=", 1)[1].strip()
    assert "10" in pix_fmt, f"expected 10-bit pix_fmt, got {pix_fmt!r}"
    assert "High 10" in profile or "high10" in profile.lower(), (
        f"expected High 10 profile, got {profile!r}"
    )


def test_export_uses_8bit_for_8bit_sources(clip_silent, tmp_path):
    """Make sure 8-bit sources don't get unnecessarily upgraded to 10-bit."""
    out = tmp_path / "out8.mp4"
    settings = ExportSettings(
        output_path=out, trim_start_frame=0, trim_end_frame=23,
        crf=23, preset="ultrafast", include_audio=False,
    )
    job = ExportJob(clip_silent, get_preset("cinematic").params, settings)
    job.run()

    from color_grade_studio.core.video_io import find_ffprobe
    ffprobe = find_ffprobe()
    result = subprocess.run(
        [ffprobe, "-v", "error", "-select_streams", "v:0",
         "-show_entries", "stream=pix_fmt", "-of",
         "default=noprint_wrappers=1:nokey=1", str(out)],
        capture_output=True, text=True, check=True,
    )
    pix_fmt = result.stdout.strip()
    assert "10" not in pix_fmt, f"8-bit source unexpectedly produced {pix_fmt}"


# --- End-to-end LUT export -------------------------------------------


def test_export_applies_loaded_lut(clip_silent, tmp_path):
    """End-to-end: a custom LUT loaded into ExportJob actually changes pixels
    of the encoded output as expected."""
    import cv2
    from color_grade_studio.core import GradeParams, write_cube, Lut3D
    import numpy as np

    # Build a LUT that scales red way down. After applying it, the red
    # channel of any pixel should be much lower than in the original.
    size = 9
    axis = np.linspace(0.0, 1.0, size, dtype=np.float32)
    b_grid, g_grid, r_grid = np.meshgrid(axis, axis, axis, indexing="ij")
    # output = (r * 0.1, g, b)
    new_r = r_grid * 0.1
    table = np.stack([new_r, g_grid, b_grid], axis=-1).astype(np.float32)
    lut = Lut3D(size=size, table=table, title="kill_red")
    cube_path = tmp_path / "kill_red.cube"
    write_cube(lut, cube_path)

    out = tmp_path / "killed.mp4"
    settings = ExportSettings(
        output_path=out,
        trim_start_frame=0, trim_end_frame=23,
        crf=18, preset="ultrafast", include_audio=False,
    )
    job = ExportJob(
        clip_silent,
        GradeParams(),  # no programmatic grade — just the LUT
        settings,
        creative_lut=lut,
    )
    job.run()

    # Compare a frame from the original vs the LUT-exported output.
    cap_src = cv2.VideoCapture(str(clip_silent))
    cap_src.set(cv2.CAP_PROP_POS_FRAMES, 5.0)
    _, src_frame = cap_src.read()
    cap_src.release()
    cap_out = cv2.VideoCapture(str(out))
    cap_out.set(cv2.CAP_PROP_POS_FRAMES, 5.0)
    _, out_frame = cap_out.read()
    cap_out.release()
    # BGR ordering — channel 2 is red.
    src_red = int(src_frame[..., 2].mean())
    out_red = int(out_frame[..., 2].mean())
    assert out_red < src_red * 0.5, (
        f"LUT was supposed to crush red but src={src_red}, out={out_red}"
    )
