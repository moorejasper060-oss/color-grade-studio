"""Transport row: play/pause, before/after, jump to in/out, photo export."""
from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QWidget


class TransportControls(QWidget):
    """Row of compact buttons under the preview pane."""

    playToggled = Signal(bool)        # True = should play
    beforeAfterChanged = Signal(bool)  # True = show original
    jumpToIn = Signal()
    jumpToOut = Signal()
    photoRequested = Signal()

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)

        self.play_btn = QPushButton("▶  Play")
        self.play_btn.setCheckable(True)
        self.play_btn.setMinimumWidth(96)
        self.play_btn.toggled.connect(self._on_play_toggled)

        self.before_btn = QPushButton("Before / After")
        self.before_btn.setCheckable(True)
        self.before_btn.setToolTip("Hold to compare with the original")
        self.before_btn.toggled.connect(self.beforeAfterChanged.emit)

        self.jump_in_btn = QPushButton("⤓ In")
        self.jump_in_btn.setToolTip("Jump to the trim-in point")
        self.jump_in_btn.clicked.connect(self.jumpToIn.emit)

        self.jump_out_btn = QPushButton("Out ⤒")
        self.jump_out_btn.setToolTip("Jump to the trim-out point")
        self.jump_out_btn.clicked.connect(self.jumpToOut.emit)

        self.photo_btn = QPushButton("📷  Save Frame")
        self.photo_btn.setToolTip("Export the current frame as JPG/PNG")
        self.photo_btn.clicked.connect(self.photoRequested.emit)

        self.position_label = QLabel("—")
        self.position_label.setObjectName("dim")
        self.position_label.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight)
        self.position_label.setMinimumWidth(110)

        lay = QHBoxLayout(self)
        lay.setContentsMargins(2, 4, 2, 4)
        lay.setSpacing(8)
        lay.addWidget(self.play_btn)
        lay.addWidget(self.before_btn)
        lay.addStretch(1)
        lay.addWidget(self.jump_in_btn)
        lay.addWidget(self.jump_out_btn)
        lay.addStretch(1)
        lay.addWidget(self.photo_btn)
        lay.addWidget(self.position_label)

    def set_playing(self, playing: bool) -> None:
        self.play_btn.blockSignals(True)
        self.play_btn.setChecked(playing)
        self.play_btn.blockSignals(False)
        self._sync_play_label(playing)

    def set_position_text(self, text: str) -> None:
        self.position_label.setText(text)

    def set_enabled(self, enabled: bool) -> None:
        for w in (
            self.play_btn, self.before_btn, self.jump_in_btn,
            self.jump_out_btn, self.photo_btn,
        ):
            w.setEnabled(enabled)

    def _on_play_toggled(self, checked: bool) -> None:
        self._sync_play_label(checked)
        self.playToggled.emit(checked)

    def _sync_play_label(self, playing: bool) -> None:
        self.play_btn.setText("⏸  Pause" if playing else "▶  Play")
