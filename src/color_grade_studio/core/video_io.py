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
        self.meta = VideoMetadata(
            path=self.path,
            width=int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
            height=int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)),
            fps=float(cap.get(cv2.CAP_PROP_FPS)) or 30.0,
            frame_count=max(int(cap.get(cv2.CAP_PROP_FRAME_COUNT)), 1),
        )

    def read_frame(self, index: int) -> Optional[np.ndarray]:
        """Return the BGR uint8 frame at the given index, or None on EOF."""
        if index < 0:
            index = 0
        if index >= self.meta.frame_count:
            index = self.meta.frame_count - 1
        self._cap.set(cv2.CAP_PROP_POS_FRAMES, float(index))
        ok, frame = self._cap.read()
        if not ok or frame is None:
            return None
        return frame

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

    Search order:
      1. ``COLOR_GRADE_FFMPEG`` env var
      2. PyInstaller bundle: ``sys._MEIPASS`` (onefile) and the ``_internal``
         folder next to the .exe (onedir)
      3. Directory of the running executable (frozen builds)
      4. ``ffmpeg`` on ``PATH``

    Raises :class:`FileNotFoundError` if nothing is found.
    """
    env = os.environ.get("COLOR_GRADE_FFMPEG")
    if env and Path(env).exists():
        return env

    if getattr(sys, "frozen", False):
        candidate_dirs = []
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            candidate_dirs.append(Path(meipass))
        exe_dir = Path(sys.executable).parent
        candidate_dirs.append(exe_dir)
        candidate_dirs.append(exe_dir / "_internal")
        for d in candidate_dirs:
            for name in ("ffmpeg.exe", "ffmpeg"):
                p = d / name
                if p.exists():
                    return str(p)

    found = shutil.which("ffmpeg") or shutil.which("ffmpeg.exe")
    if found:
        return found

    raise FileNotFoundError(
        "ffmpeg not found. Install it (winget install Gyan.FFmpeg) or set "
        "COLOR_GRADE_FFMPEG to its path."
    )


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
    try:
        ffmpeg = find_ffmpeg()
    except FileNotFoundError:
        return False
    ffprobe = ffmpeg.replace("ffmpeg.exe", "ffprobe.exe").replace("ffmpeg", "ffprobe")
    if not Path(ffprobe).exists():
        # Fall back: try ffmpeg -i (returns nonzero but stderr lists streams).
        try:
            proc = subprocess.run(
                [ffmpeg, "-i", str(path)],
                capture_output=True, text=True, check=False, timeout=10,
            )
            return "Audio:" in proc.stderr
        except Exception:
            return False
    try:
        proc = subprocess.run(
            [ffprobe, "-v", "error", "-select_streams", "a", "-show_entries",
             "stream=index", "-of", "csv=p=0", str(path)],
            capture_output=True, text=True, check=False, timeout=10,
        )
        return bool(proc.stdout.strip())
    except Exception:
        return False
