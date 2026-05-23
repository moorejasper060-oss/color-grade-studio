"""Export pipeline.

Architecture (since the LUT pipeline rewrite):

1. The current grade (preset + manual sliders) is composed with the user's
   optional input/creative LUTs into a single 3D LUT.
2. We dump that LUT to a temp ``.cube`` file.
3. ffmpeg does the actual export with one filter graph:

       [0:v]format=rgb48,lut3d=<temp.cube>,vignette=...,format=<out>[v]

   ``format=rgb48`` upcasts to 16-bit so ``lut3d`` runs at high precision
   (it refuses to operate on YUV directly). The final ``format=`` converts
   back to the output pixel format (``yuv420p`` for 8-bit sources,
   ``yuv420p10le`` + ``-profile:v high10`` for 10-bit sources like D-Log M).
4. Audio passes through as-is via ``-map 1:a?``.
5. Progress comes from ``-progress -`` (key=value on stdout); cancel calls
   ``proc.terminate()`` and unlinks any partial output file.
"""
from __future__ import annotations

import os
import re
import subprocess
import tempfile
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

from .color_engine import GradeParams, compute_combined_lut
from .lut import Lut3D, write_cube
from .video_io import find_ffmpeg, find_ffprobe, probe_audio_streams


ProgressCallback = Callable[[int, int], None]  # (frame_done, frame_total)


@dataclass
class ExportSettings:
    output_path: Path
    trim_start_frame: int = 0
    trim_end_frame: Optional[int] = None  # inclusive; None = last frame
    crf: int = 18
    preset: str = "medium"      # libx264 preset
    include_audio: bool = True
    force_10bit: Optional[bool] = None  # None = auto-detect from source


@dataclass
class _SourceProbe:
    width: int
    height: int
    fps: float
    frame_count: int
    pix_fmt: str
    is_10bit: bool
    has_audio: bool


class ExportError(RuntimeError):
    pass


class ExportJob:
    """One export = one combined LUT + one ffmpeg invocation."""

    def __init__(
        self,
        source_path: Path,
        grade_params: GradeParams,
        settings: ExportSettings,
        *,
        input_lut: Optional[Lut3D] = None,
        creative_lut: Optional[Lut3D] = None,
    ):
        self.source_path = Path(source_path)
        self.grade_params = grade_params
        self.settings = settings
        self.input_lut = input_lut
        self.creative_lut = creative_lut
        self._cancel = threading.Event()
        self._progress_cb: Optional[ProgressCallback] = None
        self._proc: Optional[subprocess.Popen] = None

    def cancel(self) -> None:
        self._cancel.set()
        proc = self._proc
        if proc and proc.poll() is None:
            try:
                proc.terminate()
            except OSError:
                pass

    def on_progress(self, cb: ProgressCallback) -> None:
        self._progress_cb = cb

    def run(self) -> Path:
        probe = self._probe()
        start = max(0, self.settings.trim_start_frame)
        end = (
            self.settings.trim_end_frame
            if self.settings.trim_end_frame is not None
            else probe.frame_count - 1
        )
        end = min(end, probe.frame_count - 1)
        if end < start:
            raise ExportError("trim range is empty")
        total_frames = end - start + 1
        fps = max(probe.fps, 1.0)
        t_start = start / fps
        t_end = (end + 1) / fps

        # Compose the user's LUTs with the current grade into one .cube file.
        # Write the temp file into a dedicated short directory (no spaces, no
        # special characters) and pass ffmpeg only the bare filename plus a
        # cwd. That sidesteps the Windows `C:` escaping nightmare in
        # ffmpeg's filter-arg parser.
        combined = compute_combined_lut(
            self.grade_params,
            input_lut=self.input_lut,
            creative_lut=self.creative_lut,
        )
        cube_dir = Path(tempfile.mkdtemp(prefix="cgs_lut_"))
        cube_path = cube_dir / "grade.cube"
        write_cube(combined, cube_path)

        want_10bit = (
            self.settings.force_10bit
            if self.settings.force_10bit is not None
            else probe.is_10bit
        )

        cmd = self._build_cmd(
            cube_name=cube_path.name,
            t_start=t_start,
            t_end=t_end,
            has_audio=probe.has_audio and self.settings.include_audio,
            want_10bit=want_10bit,
            vignette=self.grade_params.vignette,
        )

        self.settings.output_path.parent.mkdir(parents=True, exist_ok=True)
        success = False
        proc: Optional[subprocess.Popen] = None
        try:
            proc = subprocess.Popen(
                cmd,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=str(cube_dir),
            )
            self._proc = proc

            stderr_buf: list[bytes] = []
            stderr_thread = threading.Thread(
                target=_drain, args=(proc.stderr, stderr_buf), daemon=True,
            )
            stderr_thread.start()

            self._read_progress(proc, total_frames)

            return_code = proc.wait()
            stderr_thread.join(timeout=2)

            if self._cancel.is_set():
                raise ExportError("export cancelled")
            if return_code != 0:
                stderr = b"".join(stderr_buf).decode("utf-8", errors="replace")
                raise ExportError(
                    f"ffmpeg failed (exit {return_code}):\n{stderr[-800:]}"
                )

            success = True
            if self._progress_cb:
                self._progress_cb(total_frames, total_frames)
            return self.settings.output_path
        finally:
            self._proc = None
            if proc is not None and proc.poll() is None:
                try:
                    proc.terminate()
                    proc.wait(timeout=3)
                except (OSError, subprocess.TimeoutExpired):
                    try:
                        proc.kill()
                    except OSError:
                        pass
            if not success:
                try:
                    if self.settings.output_path.exists():
                        self.settings.output_path.unlink()
                except OSError:
                    pass
            try:
                cube_path.unlink()
            except OSError:
                pass
            try:
                cube_dir.rmdir()
            except OSError:
                pass

    # ---- internals -----------------------------------------------------

    def _probe(self) -> _SourceProbe:
        """Read source resolution, fps, frame count, pixel format."""
        ffprobe = find_ffprobe()
        if ffprobe is None:
            raise ExportError("ffprobe not found — install ffmpeg with ffprobe alongside")
        cmd = [
            ffprobe, "-v", "error",
            "-select_streams", "v:0",
            "-show_entries", "stream=width,height,pix_fmt,r_frame_rate,nb_frames,duration",
            "-of", "default=noprint_wrappers=1",
            str(self.source_path),
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, check=False, timeout=15)
        if result.returncode != 0:
            raise ExportError(f"ffprobe failed for {self.source_path}:\n{result.stderr[-500:]}")
        info: dict[str, str] = {}
        for line in result.stdout.splitlines():
            if "=" in line:
                k, v = line.split("=", 1)
                info[k.strip()] = v.strip()

        width = int(info.get("width", 0))
        height = int(info.get("height", 0))
        if not width or not height:
            raise ExportError("could not read video dimensions")

        # r_frame_rate is "num/den".
        fps = 30.0
        rate = info.get("r_frame_rate", "30/1")
        if "/" in rate:
            n, d = rate.split("/", 1)
            try:
                fn, fd = float(n), float(d)
                fps = fn / fd if fd else 30.0
            except ValueError:
                pass

        nb_frames = info.get("nb_frames")
        if nb_frames and nb_frames.isdigit():
            frame_count = int(nb_frames)
        else:
            # nb_frames is missing for some containers; estimate from duration.
            duration = info.get("duration", "0")
            try:
                dur = float(duration)
            except ValueError:
                dur = 0.0
            frame_count = max(1, int(round(dur * fps)))

        pix_fmt = info.get("pix_fmt", "yuv420p")
        is_10bit = "10" in pix_fmt or "p010" in pix_fmt or "p210" in pix_fmt

        has_audio = self.settings.include_audio and probe_audio_streams(self.source_path)

        return _SourceProbe(
            width=width, height=height, fps=fps, frame_count=frame_count,
            pix_fmt=pix_fmt, is_10bit=is_10bit, has_audio=has_audio,
        )

    def _build_cmd(
        self,
        *,
        cube_name: str,
        t_start: float,
        t_end: float,
        has_audio: bool,
        want_10bit: bool,
        vignette: float,
    ) -> list[str]:
        ffmpeg = find_ffmpeg()
        out_fmt = "yuv420p10le" if want_10bit else "yuv420p"
        profile = "high10" if want_10bit else "high"

        # ffmpeg's lut3d requires RGB; format=rgb48 upcasts to 16-bit so the
        # LUT runs at high precision for 10-bit sources. The .cube file lives
        # in this process's cwd so we pass just the bare filename — avoids
        # the `C:` escape mess inside ffmpeg's filter-argument parser.
        vf = f"format=rgb48,lut3d={cube_name}"
        if vignette > 1e-4:
            vf += f",vignette=PI/5*{vignette:.4f}"
        vf += f",format={out_fmt}"

        cmd = [
            ffmpeg, "-y", "-hide_banner", "-loglevel", "error",
            "-nostdin",
            "-i", str(self.source_path),
            "-ss", f"{t_start:.3f}",
            "-to", f"{t_end:.3f}",
            "-vf", vf,
            "-c:v", "libx264",
            "-preset", self.settings.preset,
            "-crf", str(self.settings.crf),
            "-pix_fmt", out_fmt,
            "-profile:v", profile,
            "-movflags", "+faststart",
        ]
        if has_audio:
            cmd += ["-map", "0:v:0", "-map", "0:a:0", "-c:a", "aac", "-b:a", "192k"]
        else:
            cmd += ["-map", "0:v:0", "-an"]
        cmd += ["-progress", "-", "-nostats", str(self.settings.output_path)]
        return cmd

    def _read_progress(self, proc: subprocess.Popen, total_frames: int) -> None:
        """Read ffmpeg's ``-progress -`` key=value stream from stdout."""
        if proc.stdout is None:
            return
        last_reported = -1
        for raw in iter(proc.stdout.readline, b""):
            if self._cancel.is_set():
                break
            line = raw.decode("utf-8", errors="replace").strip()
            if not line:
                continue
            if line.startswith("frame="):
                try:
                    n = int(line.split("=", 1)[1])
                except ValueError:
                    continue
                if self._progress_cb and n > last_reported:
                    last_reported = n
                    self._progress_cb(min(n, total_frames), total_frames)
            if line == "progress=end":
                break


def _drain(stream, sink: list[bytes]) -> None:
    try:
        for chunk in iter(lambda: stream.read(4096), b""):
            sink.append(chunk)
    except Exception:
        pass


# ---- still-frame export ------------------------------------------------


def export_photo(
    source_path: Path,
    frame_index: int,
    grade: GradeParams,
    out_path: Path,
    jpeg_quality: int = 95,
    *,
    input_lut: Optional[Lut3D] = None,
    creative_lut: Optional[Lut3D] = None,
    source=None,  # Optional VideoSource to reuse
) -> Path:
    """Save the graded still frame at ``frame_index`` as JPG or PNG.

    Uses the same combined-LUT pipeline as the video export so previews and
    photos are visually identical to the exported video.
    """
    import cv2  # local import — avoids hard dep at module import for headless tests

    from .color_engine import apply_pipeline
    from .video_io import VideoSource

    owns = source is None
    if owns:
        source = VideoSource(source_path)
    try:
        frame = source.read_frame(frame_index)
        if frame is None:
            raise ExportError(f"could not read frame {frame_index}")
        combined = compute_combined_lut(grade, input_lut=input_lut, creative_lut=creative_lut)
        graded = apply_pipeline(frame, combined, vignette=grade.vignette)
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
    finally:
        if owns:
            source.release()
