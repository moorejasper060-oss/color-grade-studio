"""Video input/output.

Reading and seeking use OpenCV's VideoCapture (good enough for preview).
Encoding goes through an FFmpeg subprocess via piped raw video, because
OpenCV's writer is unreliable across codecs and bundled OpenCV builds.

The :class:`VideoSource` class wraps a VideoCapture with the small set of
operations the UI actually needs.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import cv2
import numpy as np


SUPPORTED_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv", ".webm", ".m4v"}

DEFAULT_FPS = 30.0  # used whenever a file reports an invalid/zero fps


@dataclass
class VideoMetadata:
    path: Path
    width: int
    height: int
    fps: float
    frame_count: int

    @property
    def duration_seconds(self) -> float:
        if self.fps <= 0:
            return 0.0
        return self.frame_count / self.fps


class VideoSource:
    """A reusable wrapper around cv2.VideoCapture for preview seek+read."""

    def __init__(self, path: str | os.PathLike):
        self.path = Path(path)
        if not self.path.exists():
            raise FileNotFoundError(self.path)
        cap = cv2.VideoCapture(str(self.path))
        if not cap.isOpened():
            raise RuntimeError(f"OpenCV could not open {self.path}")
        self._cap = cap
        fps = float(cap.get(cv2.CAP_PROP_FPS))
        if not fps or fps <= 0:
            fps = DEFAULT_FPS
        self.meta = VideoMetadata(
            path=self.path,
            width=int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
            height=int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)),
            fps=fps,
            frame_count=max(int(cap.get(cv2.CAP_PROP_FRAME_COUNT)), 1),
        )
        self._next_index = 0  # frame index that the next sequential read will return

    def read_frame(self, index: int) -> Optional[np.ndarray]:
        """Return the BGR uint8 frame at the given index, or None on EOF.

        Triggers a real seek; use :meth:`read_next` during playback instead.
        """
        if index < 0:
            index = 0
        if index >= self.meta.frame_count:
            index = self.meta.frame_count - 1
        self._cap.set(cv2.CAP_PROP_POS_FRAMES, float(index))
        ok, frame = self._cap.read()
        if not ok or frame is None:
            self._next_index = index  # don't lie about where we are
            return None
        self._next_index = index + 1
        return frame

    def read_next(self) -> Optional[np.ndarray]:
        """Sequential read — much faster than seeking on every tick during playback."""
        ok, frame = self._cap.read()
        if not ok or frame is None:
            return None
        self._next_index += 1
        return frame

    def seek_to(self, index: int) -> None:
        """Position the cursor so the next :meth:`read_next` returns frame ``index``."""
        if index < 0:
            index = 0
        if index >= self.meta.frame_count:
            index = self.meta.frame_count - 1
        self._cap.set(cv2.CAP_PROP_POS_FRAMES, float(index))
        self._next_index = index

    @property
    def next_frame_index(self) -> int:
        return self._next_index

    def release(self) -> None:
        try:
            self._cap.release()
        except Exception:
            pass

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.release()


def find_ffmpeg() -> str:
    """Locate the ffmpeg executable.

    Trust order:
      1. In a frozen (PyInstaller) build: the bundled ``ffmpeg.exe`` —
         this is the high-integrity choice and overrides everything else.
      2. ``COLOR_GRADE_FFMPEG`` env var.  WARNING: this points at an
         executable that will be invoked with elevated user paths; only set
         it to a binary you trust.
      3. ``ffmpeg`` on ``PATH``.

    Raises :class:`FileNotFoundError` if nothing is found.
    """
    if getattr(sys, "frozen", False):
        bundled = _find_bundled_binary("ffmpeg")
        if bundled is not None:
            return str(bundled)

    env = os.environ.get("COLOR_GRADE_FFMPEG")
    if env and Path(env).exists():
        return env

    found = shutil.which("ffmpeg") or shutil.which("ffmpeg.exe")
    if found:
        return found

    raise FileNotFoundError(
        "ffmpeg not found. Install it (winget install Gyan.FFmpeg) or set "
        "COLOR_GRADE_FFMPEG to its path."
    )


def find_ffprobe() -> Optional[str]:
    """Locate ffprobe alongside ffmpeg. Returns None if not available."""
    if getattr(sys, "frozen", False):
        bundled = _find_bundled_binary("ffprobe")
        if bundled is not None:
            return str(bundled)
    # Prefer ffprobe sitting next to the ffmpeg we already chose.
    try:
        ffmpeg_path = Path(find_ffmpeg())
    except FileNotFoundError:
        ffmpeg_path = None
    if ffmpeg_path is not None:
        sibling = ffmpeg_path.with_name("ffprobe" + ffmpeg_path.suffix)
        if sibling.exists():
            return str(sibling)
    found = shutil.which("ffprobe") or shutil.which("ffprobe.exe")
    return found


def _find_bundled_binary(stem: str) -> Optional[Path]:
    """Look for ``ffmpeg`` / ``ffprobe`` next to a frozen executable."""
    candidate_dirs = []
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        candidate_dirs.append(Path(meipass))
    exe_dir = Path(sys.executable).parent
    candidate_dirs.append(exe_dir)
    candidate_dirs.append(exe_dir / "_internal")
    for d in candidate_dirs:
        for name in (f"{stem}.exe", stem):
            p = d / name
            if p.exists():
                return p
    return None


def downscale_to_preview(frame: np.ndarray, max_width: int = 1280) -> np.ndarray:
    """Resize a frame so its width is at most ``max_width``, preserving aspect."""
    h, w = frame.shape[:2]
    if w <= max_width:
        return frame
    scale = max_width / w
    new_w = max_width
    new_h = int(round(h * scale))
    return cv2.resize(frame, (new_w, new_h), interpolation=cv2.INTER_AREA)


def probe_audio_streams(path: str | os.PathLike) -> bool:
    """Return True if the file has at least one audio stream."""
    ffprobe = find_ffprobe()
    if ffprobe is not None:
        try:
            proc = subprocess.run(
                [ffprobe, "-v", "error", "-select_streams", "a", "-show_entries",
                 "stream=index", "-of", "csv=p=0", str(path)],
                capture_output=True, text=True, check=False, timeout=10,
            )
            return bool(proc.stdout.strip())
        except Exception:
            pass
    # Fall back: parse `ffmpeg -i` stderr.
    try:
        ffmpeg = find_ffmpeg()
    except FileNotFoundError:
        return False
    try:
        proc = subprocess.run(
            [ffmpeg, "-i", str(path)],
            capture_output=True, text=True, check=False, timeout=10,
        )
        return "Audio:" in proc.stderr
    except Exception:
        return False
