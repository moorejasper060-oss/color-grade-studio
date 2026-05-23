"""End-to-end test for video I/O and export.

Generates a tiny synthetic clip with ffmpeg, then verifies that:
  * VideoSource opens it and reads frames at expected dimensions
  * ExportJob produces a playable output mp4
  * export_photo saves a still frame
"""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

import cv2
import numpy as np
import pytest

from color_grade_studio.core import (
    ExportJob,
    ExportSettings,
    GradeParams,
    VideoSource,
    export_photo,
    find_ffmpeg,
    get_preset,
)


@pytest.fixture(scope="module")
def sample_clip(tmp_path_factory) -> Path:
    """Render a 2-second 320x240@24fps test clip via ffmpeg testsrc."""
    try:
        ffmpeg = find_ffmpeg()
    except FileNotFoundError:
        pytest.skip("ffmpeg not installed; skipping video I/O tests")
    out = tmp_path_factory.mktemp("clip") / "sample.mp4"
    cmd = [
        ffmpeg, "-y", "-hide_banner", "-loglevel", "error",
        "-f", "lavfi", "-i", "testsrc=size=320x240:rate=24:duration=2",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "ultrafast",
        str(out),
    ]
    proc = subprocess.run(cmd, capture_output=True)
    if proc.returncode != 0:
        pytest.skip(f"ffmpeg testsrc failed: {proc.stderr.decode(errors='replace')[:200]}")
    return out


def test_video_source_reads_frame(sample_clip: Path):
    with VideoSource(sample_clip) as src:
        assert src.meta.width == 320
        assert src.meta.height == 240
        assert src.meta.frame_count >= 24
        frame = src.read_frame(0)
        assert frame is not None
        assert frame.shape == (240, 320, 3)
        assert frame.dtype == np.uint8


def test_export_job_produces_output(sample_clip: Path, tmp_path: Path):
    out = tmp_path / "out.mp4"
    settings = ExportSettings(
        output_path=out,
        trim_start_frame=0,
        trim_end_frame=23,  # ~1 second
        crf=23,
        preset="ultrafast",
        include_audio=False,
    )
    grade = get_preset("cinematic").params
    progress_log: list[tuple[int, int]] = []
    job = ExportJob(sample_clip, grade, settings)
    job.on_progress(lambda done, total: progress_log.append((done, total)))
    result = job.run()
    assert result == out
    assert out.exists() and out.stat().st_size > 0
    # Verify the result is openable.
    cap = cv2.VideoCapture(str(out))
    assert cap.isOpened()
    fc = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    cap.release()
    assert fc >= 20  # ffmpeg may drop trailing frames in fast preset
    assert progress_log, "expected at least one progress callback"
    assert progress_log[-1][0] == progress_log[-1][1]


def test_export_photo_jpg(sample_clip: Path, tmp_path: Path):
    out = tmp_path / "frame.jpg"
    export_photo(sample_clip, 5, get_preset("punch").params, out)
    assert out.exists()
    img = cv2.imread(str(out))
    assert img is not None
    assert img.shape[2] == 3
