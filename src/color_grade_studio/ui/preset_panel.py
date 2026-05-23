"""Preset gallery: list of named looks with thumbnails."""
from __future__ import annotations

from typing import Optional

import cv2
import numpy as np
from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QIcon, QImage, QPixmap
from PySide6.QtWidgets import (
    QGroupBox,
    QListWidget,
    QListWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..core import PRESETS, apply_grade


THUMB_W = 132
THUMB_H = 74


class PresetPanel(QGroupBox):
    """Scrollable list of grade presets. Selecting an item emits its id."""

    presetSelected = Signal(str)  # preset id

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__("Look", parent)
        self.list = QListWidget()
        self.list.setIconSize(QSize(THUMB_W, THUMB_H))
        self.list.setSpacing(2)
        self.list.setUniformItemSizes(True)
        self.list.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        self.list.itemSelectionChanged.connect(self._on_selection)

        for preset in PRESETS:
            item = QListWidgetItem(preset.name)
            item.setData(Qt.ItemDataRole.UserRole, preset.id)
            tooltip = preset.description
            if preset.reference:
                tooltip += f"\n\nLook: {preset.reference}"
            item.setToolTip(tooltip)
            item.setSizeHint(QSize(0, THUMB_H + 14))
            self.list.addItem(item)
        # Default to first preset (Original).
        self.list.setCurrentRow(0)

        lay = QVBoxLayout(self)
        lay.addWidget(self.list)

    def selected_id(self) -> str:
        item = self.list.currentItem()
        if item is None:
            return "none"
        return item.data(Qt.ItemDataRole.UserRole)

    def select(self, preset_id: str) -> None:
        for i in range(self.list.count()):
            item = self.list.item(i)
            if item.data(Qt.ItemDataRole.UserRole) == preset_id:
                self.list.setCurrentRow(i)
                return

    def update_thumbnails(self, source_frame_bgr: Optional[np.ndarray]) -> None:
        """Re-render every preset's thumbnail using the given representative frame."""
        if source_frame_bgr is None:
            for i in range(self.list.count()):
                self.list.item(i).setIcon(QIcon())
            return
        small = _fit(source_frame_bgr, THUMB_W, THUMB_H)
        for i, preset in enumerate(PRESETS):
            graded = apply_grade(small, preset.params)
            item = self.list.item(i)
            item.setIcon(QIcon(_bgr_to_pixmap(graded)))

    def _on_selection(self) -> None:
        pid = self.selected_id()
        if pid:
            self.presetSelected.emit(pid)


def _fit(frame_bgr: np.ndarray, w: int, h: int) -> np.ndarray:
    src_h, src_w = frame_bgr.shape[:2]
    scale = min(w / src_w, h / src_h)
    new_w = max(1, int(src_w * scale))
    new_h = max(1, int(src_h * scale))
    resized = cv2.resize(frame_bgr, (new_w, new_h), interpolation=cv2.INTER_AREA)
    # Letterbox onto a black canvas so all thumbs have identical aspect.
    canvas = np.zeros((h, w, 3), dtype=np.uint8)
    y_off = (h - new_h) // 2
    x_off = (w - new_w) // 2
    canvas[y_off:y_off + new_h, x_off:x_off + new_w] = resized
    return canvas


def _bgr_to_pixmap(frame_bgr: np.ndarray) -> QPixmap:
    h, w, _ = frame_bgr.shape
    img = QImage(frame_bgr.data, w, h, frame_bgr.strides[0], QImage.Format.Format_BGR888).copy()
    return QPixmap.fromImage(img)
