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
