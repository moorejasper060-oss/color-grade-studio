"""Top-level QMainWindow that wires everything together."""
from __future__ import annotations

from pathlib import Path
from typing import Optional

import numpy as np
from PySide6.QtCore import Qt, QThread, QTimer
from PySide6.QtGui import (
    QAction,
    QDragEnterEvent,
    QDropEvent,
    QKeySequence,
)
from PySide6.QtWidgets import (
    QFileDialog,
    QMainWindow,
    QMessageBox,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from ..core import (
    PRESETS,
    SUPPORTED_EXTENSIONS,
    ExportJob,
    GradeParams,
    VideoSource,
    apply_grade,
    downscale_to_preview,
    export_photo,
    find_ffmpeg,
    get_preset,
    probe_audio_streams,
)
from .adjustments_panel import AdjustmentsPanel
from .export_dialog import (
    ExportDialog,
    ExportProgressDialog,
    ExportWorker,
)
from .preset_panel import PresetPanel
from .preview_widget import PreviewWidget
from .styles import DARK_QSS
from .timeline_widget import TimelineWidget
from .transport_controls import TransportControls


PREVIEW_MAX_WIDTH = 1280


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Color Grade Studio")
        self.setMinimumSize(1180, 720)
        self.setStyleSheet(DARK_QSS)
        self.setAcceptDrops(True)

        # --- State --------------------------------------------------
        self._source: Optional[VideoSource] = None
        self._raw_preview_frame: Optional[np.ndarray] = None
        self._current_grade: GradeParams = GradeParams()
        self._playing = False
        self._has_audio = False
        # Drop a tick when the previous render hasn't finished — keeps the
        # event loop responsive on heavy frames instead of letting the timer
        # queue back up.
        self._render_busy = False
        # Live export thread/worker, so closeEvent can shut them down cleanly.
        self._export_thread: Optional[QThread] = None
        self._export_worker: Optional[ExportWorker] = None

        # --- Widgets ------------------------------------------------
        self.preset_panel = PresetPanel()
        self.preset_panel.setMaximumWidth(220)
        self.preset_panel.presetSelected.connect(self._on_preset_selected)

        self.preview = PreviewWidget()

        self.timeline = TimelineWidget()
        self.timeline.playheadMoved.connect(self._on_playhead_moved)
        self.timeline.trimRangeChanged.connect(self._on_trim_changed)

        self.transport = TransportControls()
        self.transport.playToggled.connect(self._on_play_toggled)
        self.transport.beforeAfterChanged.connect(self.preview.set_show_original)
        self.transport.jumpToIn.connect(self._jump_to_in)
        self.transport.jumpToOut.connect(self._jump_to_out)
        self.transport.photoRequested.connect(self._on_export_photo)
        self.transport.set_enabled(False)

        self.adjustments = AdjustmentsPanel()
        self.adjustments.setMaximumWidth(280)
        self.adjustments.paramsChanged.connect(self._on_adjustments_changed)

        # --- Center layout ------------------------------------------
        center = QWidget()
        center_layout = QVBoxLayout(center)
        center_layout.setContentsMargins(8, 8, 8, 8)
        center_layout.setSpacing(8)
        center_layout.addWidget(self.preview, 1)
        center_layout.addWidget(self.timeline, 0)
        center_layout.addWidget(self.transport, 0)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self.preset_panel)
        splitter.addWidget(center)
        splitter.addWidget(self.adjustments)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setStretchFactor(2, 0)
        splitter.setSizes([220, 720, 240])

        self.setCentralWidget(splitter)

        # --- Menu / status -----------------------------------------
        self._build_menu()
        self.statusBar().showMessage(self._initial_status())

        # --- Playback timer -----------------------------------------
        # Sequential reads happen via VideoSource.read_next() — no per-tick seek.
        self._play_timer = QTimer(self)
        self._play_timer.timeout.connect(self._advance_playhead)

    # ---------- Menu & status ---------------------------------------

    def _build_menu(self) -> None:
        m_file = self.menuBar().addMenu("&File")

        act_open = QAction("&Open video…", self)
        act_open.setShortcut(QKeySequence.StandardKey.Open)
        act_open.triggered.connect(self._on_open)
        m_file.addAction(act_open)

        m_file.addSeparator()

        self._act_export_video = QAction("&Export video…", self)
        self._act_export_video.setShortcut("Ctrl+E")
        self._act_export_video.triggered.connect(self._on_export_video)
        self._act_export_video.setEnabled(False)
        m_file.addAction(self._act_export_video)

        self._act_export_photo = QAction("Save current &frame as photo…", self)
        self._act_export_photo.setShortcut("Ctrl+Shift+E")
        self._act_export_photo.triggered.connect(self._on_export_photo)
        self._act_export_photo.setEnabled(False)
        m_file.addAction(self._act_export_photo)

        m_file.addSeparator()

        act_quit = QAction("&Quit", self)
        act_quit.setShortcut(QKeySequence.StandardKey.Quit)
        act_quit.triggered.connect(self.close)
        m_file.addAction(act_quit)

        m_help = self.menuBar().addMenu("&Help")
        act_about = QAction("&About Color Grade Studio", self)
        act_about.triggered.connect(self._show_about)
        m_help.addAction(act_about)

    def _initial_status(self) -> str:
        try:
            ffmpeg = find_ffmpeg()
            return f"Ready · ffmpeg: {ffmpeg}"
        except FileNotFoundError as exc:
            return f"ffmpeg not found — exports will fail · {exc}"

    def _show_about(self) -> None:
        named = len(PRESETS) - 1  # subtract the "Original" pseudo-preset
        QMessageBox.about(
            self, "About Color Grade Studio",
            "<h3>Color Grade Studio</h3>"
            "<p>One-click video color grading for Windows.</p>"
            "<p>Built with PySide6, OpenCV, and FFmpeg.</p>"
            f"<p>{named} grade presets (plus Original) · MIT license</p>",
        )

    # ---------- Open / drop -----------------------------------------

    def _on_open(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Open video", "",
            "Videos (*.mp4 *.mov *.avi *.mkv *.webm *.m4v);;All files (*.*)",
        )
        if path:
            self._load_video(Path(path))

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        urls = event.mimeData().urls() if event.mimeData() else []
        if urls and Path(urls[0].toLocalFile()).suffix.lower() in SUPPORTED_EXTENSIONS:
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event: QDropEvent) -> None:
        urls = event.mimeData().urls()
        if not urls:
            return
        path = Path(urls[0].toLocalFile())
        if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
            QMessageBox.warning(self, "Unsupported file",
                                f"{path.suffix} files aren't supported.")
            return
        self._load_video(path)

    def _load_video(self, path: Path) -> None:
        self._stop_playback()
        if self._source is not None:
            self._source.release()
            self._source = None
        # Forget any frame cached from a previous video before we touch the UI.
        self._raw_preview_frame = None
        try:
            source = VideoSource(path)
        except Exception as exc:
            QMessageBox.critical(self, "Failed to open", f"{exc}")
            self.preview.clear()
            return
        self._source = source
        meta = source.meta
        self._has_audio = probe_audio_streams(path)
        self.timeline.set_video(meta.frame_count, meta.fps)
        self.transport.set_enabled(True)
        self._act_export_video.setEnabled(True)
        self._act_export_photo.setEnabled(True)
        self.setWindowTitle(f"{path.name} — Color Grade Studio")
        self.statusBar().showMessage(
            f"{path.name} · {meta.width}×{meta.height} · "
            f"{meta.fps:.2f} fps · {meta.frame_count} frames · "
            f"audio: {'yes' if self._has_audio else 'no'}"
        )
        self._refresh_frame(force_read=True)
        # Refresh preset thumbnails using a representative frame ~25% in.
        thumb_frame_idx = max(0, meta.frame_count // 4)
        thumb_frame = source.read_frame(thumb_frame_idx)
        if thumb_frame is not None:
            self.preset_panel.update_thumbnails(thumb_frame)
        # Restore playhead to start.
        self.timeline.set_playhead(0)
        self._refresh_frame(force_read=True)

    # ---------- Frame rendering -------------------------------------

    def _refresh_frame(self, force_read: bool = False) -> None:
        if self._source is None:
            return
        if force_read or self._raw_preview_frame is None:
            idx = self.timeline.state.playhead
            raw = self._source.read_frame(idx)
            if raw is None:
                return
            self._raw_preview_frame = downscale_to_preview(raw, PREVIEW_MAX_WIDTH)
        graded = apply_grade(self._raw_preview_frame, self._current_grade)
        self.preview.set_frames(graded, self._raw_preview_frame)
        self._update_position_label()

    def _update_position_label(self) -> None:
        if self._source is None:
            self.transport.set_position_text("—")
            return
        idx = self.timeline.state.playhead
        fps = self._source.meta.fps
        t = idx / fps
        self.transport.set_position_text(f"frame {idx} · {t:.2f}s")

    def _on_preset_selected(self, preset_id: str) -> None:
        preset_params = get_preset(preset_id).params
        manual = self.adjustments.params()
        self._current_grade = preset_params.combine(manual)
        self._refresh_frame()

    def _on_adjustments_changed(self, _manual: GradeParams) -> None:
        preset_params = get_preset(self.preset_panel.selected_id()).params
        manual = self.adjustments.params()
        self._current_grade = preset_params.combine(manual)
        self._refresh_frame()

    # ---------- Timeline / transport --------------------------------

    def _on_playhead_moved(self, _frame: int) -> None:
        # User scrubbed — discard any sequential read state and seek.
        if self._source is not None:
            self._source.seek_to(self.timeline.state.playhead)
        self._refresh_frame(force_read=True)

    def _on_trim_changed(self, _in_f: int, _out_f: int) -> None:
        pass

    def _on_play_toggled(self, play: bool) -> None:
        if play:
            self._start_playback()
        else:
            self._stop_playback()

    def _start_playback(self) -> None:
        if self._source is None:
            return
        self._playing = True
        # Seek the underlying capture once at the start; subsequent ticks call
        # read_next() so we don't trash the decoder with a seek per frame.
        self._source.seek_to(self.timeline.state.playhead)
        interval = max(int(1000 / max(self._source.meta.fps, 1.0)), 16)
        self._play_timer.start(interval)

    def _stop_playback(self) -> None:
        self._playing = False
        self._play_timer.stop()
        self.transport.set_playing(False)

    def _advance_playhead(self) -> None:
        if self._source is None:
            self._stop_playback()
            return
        if self._render_busy:
            # Previous tick hasn't finished — skip rather than queue up work.
            return
        state = self.timeline.state
        next_frame = state.playhead + 1
        if next_frame > state.out_frame:
            # Loop back to the in-point.
            self._source.seek_to(state.in_frame)
            next_frame = state.in_frame
        elif next_frame != self._source.next_frame_index:
            # We drifted out of sync (e.g. after a scrub during pause); resync.
            self._source.seek_to(next_frame)

        self._render_busy = True
        try:
            self.timeline.set_playhead(next_frame)
            frame = self._source.read_next()
            if frame is None:
                # Hit EOF before out_frame — bounce back to the in-point.
                self._source.seek_to(state.in_frame)
                self.timeline.set_playhead(state.in_frame)
                return
            self._raw_preview_frame = downscale_to_preview(frame, PREVIEW_MAX_WIDTH)
            graded = apply_grade(self._raw_preview_frame, self._current_grade)
            self.preview.set_frames(graded, self._raw_preview_frame)
            self._update_position_label()
        finally:
            self._render_busy = False

    def _jump_to_in(self) -> None:
        self.timeline.set_playhead(self.timeline.state.in_frame)
        if self._source is not None:
            self._source.seek_to(self.timeline.state.in_frame)
        self._refresh_frame(force_read=True)

    def _jump_to_out(self) -> None:
        self.timeline.set_playhead(self.timeline.state.out_frame)
        if self._source is not None:
            self._source.seek_to(self.timeline.state.out_frame)
        self._refresh_frame(force_read=True)

    # ---------- Export video ----------------------------------------

    def _on_export_video(self) -> None:
        if self._source is None:
            return
        if self._export_thread is not None:
            QMessageBox.information(self, "Export in progress",
                                    "An export is already running. Cancel it before starting another.")
            return
        self._stop_playback()
        src_path = self._source.path
        suggested = src_path.with_name(f"{src_path.stem}_graded.mp4")
        dialog = ExportDialog(suggested, self._has_audio, self)
        if dialog.exec() != dialog.DialogCode.Accepted:
            return
        settings = dialog.settings()
        in_f, out_f = self.timeline.trim_range()
        settings.trim_start_frame = in_f
        settings.trim_end_frame = out_f
        if settings.output_path.exists():
            ok = QMessageBox.question(
                self, "Overwrite?",
                f"{settings.output_path.name} already exists. Overwrite?",
            )
            if ok != QMessageBox.StandardButton.Yes:
                return

        job = ExportJob(src_path, self._current_grade, settings)
        total = (out_f - in_f + 1) if out_f is not None else self._source.meta.frame_count

        progress = ExportProgressDialog(total, self)
        worker = ExportWorker(job)
        thread = QThread(self)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.progress.connect(progress.setValue)
        progress.canceled.connect(worker.cancel)
        worker.finished.connect(
            lambda out: self._on_export_finished(out, progress, thread, worker))
        worker.failed.connect(
            lambda msg: self._on_export_failed(msg, progress, thread, worker))
        self._export_thread = thread
        self._export_worker = worker
        thread.start()
        progress.exec()

    def _on_export_finished(self, out_path, progress, thread, worker) -> None:
        progress.setValue(progress.maximum())
        progress.close()
        thread.quit()
        thread.wait(2000)
        worker.deleteLater()
        if self._export_thread is thread:
            self._export_thread = None
            self._export_worker = None
        QMessageBox.information(
            self, "Export complete",
            f"Saved to:\n{out_path}",
        )

    def _on_export_failed(self, message, progress, thread, worker) -> None:
        progress.close()
        thread.quit()
        thread.wait(2000)
        worker.deleteLater()
        if self._export_thread is thread:
            self._export_thread = None
            self._export_worker = None
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Critical)
        box.setWindowTitle("Export failed")
        box.setText("Export failed. Click 'Show details' for the ffmpeg log.")
        box.setDetailedText(message)
        box.exec()

    # ---------- Export photo ----------------------------------------

    def _on_export_photo(self) -> None:
        if self._source is None:
            return
        self._stop_playback()
        src_path = self._source.path
        suggested_name = f"{src_path.stem}_frame{self.timeline.state.playhead}.jpg"
        suggested = src_path.with_name(suggested_name)

        dialog = QFileDialog(self, "Save frame as photo", str(suggested),
                             "JPEG (*.jpg);;PNG (*.png)")
        dialog.setAcceptMode(QFileDialog.AcceptMode.AcceptSave)
        dialog.setDefaultSuffix("jpg")
        if dialog.exec() != QFileDialog.DialogCode.Accepted:
            return
        files = dialog.selectedFiles()
        if not files:
            return
        out_path = Path(files[0])
        # Honour the selected filter: if the user picked PNG but the file
        # name doesn't end in .png, switch the suffix.
        selected_filter = dialog.selectedNameFilter()
        if "PNG" in selected_filter and out_path.suffix.lower() != ".png":
            out_path = out_path.with_suffix(".png")
        elif "JPEG" in selected_filter and out_path.suffix.lower() not in {".jpg", ".jpeg"}:
            out_path = out_path.with_suffix(".jpg")

        try:
            # Reuse the already-open VideoSource so we don't pay another
            # full-decode cycle on a large file.
            out = export_photo(
                src_path,
                self.timeline.state.playhead,
                self._current_grade,
                out_path,
                source=self._source,
            )
        except Exception as exc:
            QMessageBox.critical(self, "Photo export failed", str(exc))
            return
        finally:
            # The shared VideoSource has just had its cursor moved by the
            # photo read — make the preview state coherent again.
            if self._source is not None:
                self._source.seek_to(self.timeline.state.playhead)
        QMessageBox.information(self, "Photo saved", f"Saved to:\n{out}")

    # ---------- Keyboard --------------------------------------------

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Space and not event.isAutoRepeat():
            self.transport.play_btn.toggle()
            return
        if event.key() == Qt.Key.Key_B and not event.isAutoRepeat():
            self.transport.before_btn.setChecked(True)
            return
        super().keyPressEvent(event)

    def keyReleaseEvent(self, event):
        if event.key() == Qt.Key.Key_B and not event.isAutoRepeat():
            self.transport.before_btn.setChecked(False)
            return
        super().keyReleaseEvent(event)

    # ---------- Close -----------------------------------------------

    def closeEvent(self, event):
        self._stop_playback()
        # If an export is still running, cancel it and wait for the thread to
        # finish before tearing the window down — otherwise Qt destroys the
        # QThread mid-encode and the user gets a crash on shutdown.
        if self._export_worker is not None and self._export_thread is not None:
            try:
                self._export_worker.cancel()
            except Exception:
                pass
            self._export_thread.quit()
            self._export_thread.wait(5000)
            self._export_worker = None
            self._export_thread = None
        if self._source is not None:
            self._source.release()
            self._source = None
        super().closeEvent(event)
