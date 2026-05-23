"""Video preview widget — displays the current frame with scaling."""
from __future__ import annotations

from typing import Optional

import numpy as np
from PySide6.QtCore import Qt
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import QLabel, QSizePolicy, QVBoxLayout, QWidget


def bgr_to_qimage(frame_bgr: np.ndarray) -> QImage:
    """Convert a contiguous BGR uint8 numpy array to a QImage."""
    h, w, _ = frame_bgr.shape
    # Ensure contiguous memory; QImage references the buffer without copying.
    if not frame_bgr.flags["C_CONTIGUOUS"]:
        frame_bgr = np.ascontiguousarray(frame_bgr)
    img = QImage(frame_bgr.data, w, h, frame_bgr.strides[0], QImage.Format.Format_BGR888)
    return img.copy()  # copy so the QImage owns its bytes


class PreviewWidget(QWidget):
    """Holds two QImages (graded + original) and renders the active one to fit."""

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._graded: Optional[QImage] = None
        self._original: Optional[QImage] = None
        self._show_original = False
        self._placeholder_text = "Drop a video here or use File › Open…"

        self._label = QLabel()
        self._label.setObjectName("preview")
        self._label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._label.setMinimumSize(480, 270)
        self._label.setText(self._placeholder_text)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(self._label)

        self.setAcceptDrops(False)  # parent handles drops
        self.setMouseTracking(True)

    def set_frames(self, graded: Optional[np.ndarray], original: Optional[np.ndarray]) -> None:
        self._graded = bgr_to_qimage(graded) if graded is not None else None
        self._original = bgr_to_qimage(original) if original is not None else None
        self._render()

    def clear(self) -> None:
        self._graded = None
        self._original = None
        self._label.setText(self._placeholder_text)

    def set_show_original(self, show: bool) -> None:
        if self._show_original == show:
            return
        self._show_original = show
        self._render()

    def is_showing_original(self) -> bool:
        return self._show_original

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._render()

    def _render(self) -> None:
        img = self._original if self._show_original and self._original else self._graded
        if img is None:
            return
        target = self._label.size()
        if target.width() <= 0 or target.height() <= 0:
            return
        pix = QPixmap.fromImage(img).scaled(
            target,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self._label.setPixmap(pix)

