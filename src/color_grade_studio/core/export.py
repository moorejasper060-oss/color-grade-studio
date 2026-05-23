"""Export pipeline.

A single export job reads frames from the source via OpenCV, applies the
current grade to each frame, and pipes the raw BGR result into a long-running
ffmpeg process for encoding. Audio is muxed from the original file with
``-ss / -to`` so it matches the trim range.
"""
from __future__ import annotations

import os
import subprocess
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

import cv2
import numpy as np

from .color_engine import GradeParams, apply_grade
from .video_io import VideoSource, find_ffmpeg, probe_audio_streams


ProgressCallback = Callable[[int, int], None]  # (frame_done, frame_total)


@dataclass
class ExportSettings:
    output_path: Path
    trim_start_frame: int = 0
    trim_end_frame: Optional[int] = None  # inclusive end; None = last frame
    crf: int = 18                          # 18 ~= visually lossless
    preset: str = "medium"                 # x264 preset
    include_audio: bool = True


class ExportError(RuntimeError):
    pass


class ExportJob:
    """Encapsulates one video export. Run on a background thread."""

    def __init__(
        self,
        source_path: Path,
        grade: GradeParams,
        settings: ExportSettings,
    ):
        self.source_path = Path(source_path)
        self.grade = grade
        self.settings = settings
        self._cancel = threading.Event()
        self._progress_cb: Optional[ProgressCallback] = None

    def cancel(self) -> None:
        self._cancel.set()

    def on_progress(self, cb: ProgressCallback) -> None:
        self._progress_cb = cb

    def run(self) -> Path:
        with VideoSource(self.source_path) as src:
            meta = src.meta
            start = max(0, self.settings.trim_start_frame)
            end = (
                self.settings.trim_end_frame
                if self.settings.trim_end_frame is not None
                else meta.frame_count - 1
            )
            end = min(end, meta.frame_count - 1)
            if end < start:
                raise ExportError("trim range is empty")
            total = end - start + 1
            fps = max(meta.fps, 1.0)

            t_start = start / fps
            t_end = (end + 1) / fps

            has_audio = (
                self.settings.include_audio
                and probe_audio_streams(self.source_path)
            )

            cmd = self._build_ffmpeg_cmd(
                width=meta.width,
                height=meta.height,
                fps=fps,
                t_start=t_start,
                t_end=t_end,
                has_audio=has_audio,
            )

            self.settings.output_path.parent.mkdir(parents=True, exist_ok=True)

            proc = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                bufsize=0,
            )

            err_buffer: list[bytes] = []
            stderr_thread = threading.Thread(
                target=_drain_stderr, args=(proc.stderr, err_buffer), daemon=True,
            )
            stderr_thread.start()

            try:
                done = 0
                for idx in range(start, end + 1):
                    if self._cancel.is_set():
                        break
                    frame = src.read_frame(idx)
                    if frame is None:
                        # Past EOF; treat as a clean stop rather than error.
                        break
                    if frame.shape[1] != meta.width or frame.shape[0] != meta.height:
                        frame = cv2.resize(frame, (meta.width, meta.height))
                    graded = apply_grade(frame, self.grade)
                    try:
                        proc.stdin.write(graded.tobytes())
                    except BrokenPipeError:
                        break
                    done += 1
                    if self._progress_cb and (done % 4 == 0 or done == total):
                        self._progress_cb(done, total)
                proc.stdin.close()
            except Exception:
                proc.kill()
                raise

            return_code = proc.wait()
            stderr_thread.join(timeout=2)

            if self._cancel.is_set():
                # Best effort cleanup
                if self.settings.output_path.exists():
                    try:
                        self.settings.output_path.unlink()
                    except OSError:
                        pass
                raise ExportError("export cancelled")
            if return_code != 0:
                stderr = b"".join(err_buffer).decode("utf-8", errors="replace")
                raise ExportError(f"ffmpeg failed (exit {return_code}):\n{stderr[-800:]}")

            if self._progress_cb:
                self._progress_cb(total, total)
            return self.settings.output_path

    def _build_ffmpeg_cmd(
        self,
        width: int,
        height: int,
        fps: float,
        t_start: float,
        t_end: float,
        has_audio: bool,
    ) -> list[str]:
        ffmpeg = find_ffmpeg()
        cmd: list[str] = [
            ffmpeg, "-y", "-hide_banner", "-loglevel", "error",
            "-f", "rawvideo",
            "-vcodec", "rawvideo",
            "-pix_fmt", "bgr24",
            "-s", f"{width}x{height}",
            "-r", f"{fps:.6f}",
            "-i", "-",
        ]
        if has_audio:
            cmd += [
                "-ss", f"{t_start:.3f}",
                "-to", f"{t_end:.3f}",
                "-i", str(self.source_path),
                "-map", "0:v:0",
                "-map", "1:a:0",
                "-c:a", "aac",
                "-b:a", "192k",
            ]
        cmd += [
            "-c:v", "libx264",
            "-preset", self.settings.preset,
            "-crf", str(self.settings.crf),
            "-pix_fmt", "yuv420p",
            "-movflags", "+faststart",
        ]
        if has_audio:
            cmd += ["-shortest"]
        cmd += [str(self.settings.output_path)]
        return cmd


def _drain_stderr(stream, sink: list[bytes]) -> None:
    try:
        for chunk in iter(lambda: stream.read(4096), b""):
            sink.append(chunk)
    except Exception:
        pass


def export_photo(
    source_path: Path,
    frame_index: int,
    grade: GradeParams,
    out_path: Path,
    jpeg_quality: int = 95,
) -> Path:
    """Save a graded still frame as JPG or PNG."""
    with VideoSource(source_path) as src:
        frame = src.read_frame(frame_index)
        if frame is None:
            raise ExportError(f"could not read frame {frame_index}")
        graded = apply_grade(frame, grade)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        ext = out_path.suffix.lower()
        if ext in {".jpg", ".jpeg"}:
            ok = cv2.imwrite(
                str(out_path), graded,
                [int(cv2.IMWRITE_JPEG_QUALITY), int(jpeg_quality)],
            )
        elif ext == ".png":
            ok = cv2.imwrite(str(out_path), graded, [int(cv2.IMWRITE_PNG_COMPRESSION), 3])
        else:
            raise ExportError(f"unsupported photo extension: {ext}")
        if not ok:
            raise ExportError(f"failed to write {out_path}")
        return out_path
