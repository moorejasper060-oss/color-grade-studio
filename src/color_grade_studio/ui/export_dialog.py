"""Export dialog and progress dialog for background encoding."""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressDialog,
    QPushButton,
    QVBoxLayout,
    QWidget,
    QFileDialog,
)

from ..core import ExportJob, ExportSettings


# Windows reserved device names — opening one of these would hang ffmpeg.
_WIN_RESERVED = {
    "CON", "PRN", "AUX", "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
}


def sanitize_output_path(raw: str) -> Path:
    """Normalize a user-typed export path. Raises :class:`ValueError` on bad input.

    Rules:
      * empty after stripping → reject
      * contains control characters → reject (filenames with newlines are weird
        even when subprocess passes them as a single argv element)
      * basename matches a Windows reserved device name → reject
      * suffix missing or not .mp4 → force .mp4 (the encoder is hard-wired to
        H.264/AAC in an mp4 muxer)
    """
    text = raw.strip().strip('"').strip("'")
    if not text:
        raise ValueError("Please choose a file path.")
    if any(ord(c) < 32 for c in text):
        raise ValueError("Path contains invalid control characters.")
    p = Path(text).expanduser()
    stem = p.stem.upper()
    if stem in _WIN_RESERVED:
        raise ValueError(f'"{p.stem}" is a reserved Windows name. Pick another.')
    if p.suffix.lower() != ".mp4":
        p = p.with_suffix(".mp4")
    return p


class ExportDialog(QDialog):
    """Collect output path and encoding options before kicking off export."""

    def __init__(
        self,
        suggested_path: Path,
        has_audio: bool,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.setWindowTitle("Export video")
        self.setMinimumWidth(460)

        self._path_edit = QLineEdit(str(suggested_path))
        browse = QPushButton("Browse…")
        browse.clicked.connect(self._pick_path)
        path_row = QHBoxLayout()
        path_row.addWidget(self._path_edit, 1)
        path_row.addWidget(browse, 0)

        self._quality_combo = QComboBox()
        self._quality_combo.addItem("Visually lossless (CRF 18)", 18)
        self._quality_combo.addItem("High quality (CRF 20)", 20)
        self._quality_combo.addItem("Balanced (CRF 23)", 23)
        self._quality_combo.addItem("Smaller file (CRF 26)", 26)
        self._quality_combo.setCurrentIndex(1)

        self._preset_combo = QComboBox()
        for p in ("ultrafast", "fast", "medium", "slow"):
            self._preset_combo.addItem(p)
        self._preset_combo.setCurrentText("medium")

        self._audio_check = QCheckBox("Include audio")
        self._audio_check.setChecked(has_audio)
        self._audio_check.setEnabled(has_audio)
        if not has_audio:
            self._audio_check.setToolTip("Source has no audio track.")

        form = QFormLayout()
        form.addRow("Output:", _wrap(path_row))
        form.addRow("Quality:", self._quality_combo)
        form.addRow("Encoder preset:", self._preset_combo)
        form.addRow("", self._audio_check)

        info = QLabel("Lower CRF = better quality and larger file. The encoder "
                      "preset trades CPU time for compression efficiency.")
        info.setWordWrap(True)
        info.setObjectName("dim")

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Export")
        buttons.button(QDialogButtonBox.StandardButton.Ok).setObjectName("primary")

        lay = QVBoxLayout(self)
        lay.addLayout(form)
        lay.addWidget(info)
        lay.addStretch(1)
        lay.addWidget(buttons)

    def settings(self) -> ExportSettings:
        return ExportSettings(
            output_path=sanitize_output_path(self._path_edit.text()),
            crf=int(self._quality_combo.currentData()),
            preset=self._preset_combo.currentText(),
            include_audio=self._audio_check.isChecked(),
        )

    def _on_accept(self) -> None:
        try:
            path = sanitize_output_path(self._path_edit.text())
        except ValueError as exc:
            QMessageBox.warning(self, "Check the output path", str(exc))
            return
        # Reflect any normalisation back to the user before closing the dialog.
        self._path_edit.setText(str(path))
        self.accept()

    def _pick_path(self) -> None:
        dialog = QFileDialog(self, "Export video", self._path_edit.text(),
                             "MP4 video (*.mp4)")
        dialog.setAcceptMode(QFileDialog.AcceptMode.AcceptSave)
        dialog.setDefaultSuffix("mp4")
        if dialog.exec() == QFileDialog.DialogCode.Accepted:
            files = dialog.selectedFiles()
            if files:
                self._path_edit.setText(files[0])


def _wrap(layout) -> QWidget:
    w = QWidget()
    w.setLayout(layout)
    return w


# --- Background worker --------------------------------------------------


class ExportWorker(QObject):
    """Runs an ExportJob on a QThread, emitting progress/finished signals."""

    progress = Signal(int, int)      # done, total
    finished = Signal(object)         # Path on success
    failed = Signal(str)              # error message

    def __init__(self, job: ExportJob):
        super().__init__()
        self._job = job
        self._job.on_progress(lambda d, t: self.progress.emit(d, t))

    def run(self) -> None:
        try:
            out = self._job.run()
        except Exception as exc:
            self.failed.emit(str(exc))
            return
        self.finished.emit(out)

    def cancel(self) -> None:
        self._job.cancel()


class ExportProgressDialog(QProgressDialog):
    """Modal progress bar that drives an ExportWorker."""

    def __init__(self, total_frames: int, parent: Optional[QWidget] = None):
        super().__init__("Exporting video…", "Cancel", 0, max(total_frames, 1), parent)
        self.setWindowTitle("Export progress")
        self.setWindowModality(Qt.WindowModality.ApplicationModal)
        self.setMinimumDuration(0)
        self.setAutoClose(False)
        self.setAutoReset(False)
        self.setValue(0)
