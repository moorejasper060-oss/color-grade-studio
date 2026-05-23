"""Export dialog and progress dialog for background encoding."""
from __future__ import annotations

import threading
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QObject, QThread, Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QProgressDialog,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
    QFileDialog,
)

from ..core import ExportJob, ExportSettings, GradeParams


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
        buttons.accepted.connect(self.accept)
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
            output_path=Path(self._path_edit.text()).expanduser(),
            crf=int(self._quality_combo.currentData()),
            preset=self._preset_combo.currentText(),
            include_audio=self._audio_check.isChecked(),
        )

    def _pick_path(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, "Export video",
            self._path_edit.text(),
            "MP4 video (*.mp4)",
        )
        if path:
            self._path_edit.setText(path)


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
