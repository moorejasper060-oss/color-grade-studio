"""Adjustments panel: exposure, contrast, saturation, temperature, tint."""
from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from ..core import GradeParams


SLIDER_RESOLUTION = 100  # internal int range = [-100, 100] -> [-1.0, 1.0]


class LabelledSlider(QWidget):
    """A horizontal slider with title, value readout, and reset button."""

    valueChanged = Signal(float)

    def __init__(self, title: str, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._title = title

        self.title_label = QLabel(title)
        self.title_label.setStyleSheet("color: #cfcfcf;")

        self.value_label = QLabel("0")
        self.value_label.setObjectName("dim")
        self.value_label.setMinimumWidth(36)
        self.value_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(-SLIDER_RESOLUTION, SLIDER_RESOLUTION)
        self.slider.setValue(0)
        self.slider.setSingleStep(1)
        self.slider.setPageStep(5)
        self.slider.valueChanged.connect(self._on_slider_changed)

        self.reset_btn = QPushButton("Reset")
        self.reset_btn.setFixedWidth(56)
        self.reset_btn.clicked.connect(self.reset)

        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.addWidget(self.title_label, 1)
        header.addWidget(self.value_label, 0)

        bottom = QHBoxLayout()
        bottom.setContentsMargins(0, 0, 0, 0)
        bottom.addWidget(self.slider, 1)
        bottom.addWidget(self.reset_btn, 0)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 2, 0, 2)
        layout.setSpacing(2)
        layout.addLayout(header)
        layout.addLayout(bottom)

    def value(self) -> float:
        return self.slider.value() / SLIDER_RESOLUTION

    def set_value(self, v: float) -> None:
        self.slider.blockSignals(True)
        self.slider.setValue(int(round(v * SLIDER_RESOLUTION)))
        self.slider.blockSignals(False)
        self._update_value_label()

    def reset(self) -> None:
        self.slider.setValue(0)

    def _on_slider_changed(self, raw: int) -> None:
        self._update_value_label()
        self.valueChanged.emit(raw / SLIDER_RESOLUTION)

    def _update_value_label(self) -> None:
        v = self.slider.value() / SLIDER_RESOLUTION
        self.value_label.setText(f"{v:+.2f}" if abs(v) > 1e-6 else "0")


class AdjustmentsPanel(QGroupBox):
    """Five sliders that produce a manual GradeParams overlay."""

    paramsChanged = Signal(object)  # emits GradeParams

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__("Adjustments", parent)
        self.exposure = LabelledSlider("Exposure")
        self.contrast = LabelledSlider("Contrast")
        self.saturation = LabelledSlider("Saturation")
        self.temperature = LabelledSlider("Temperature")
        self.tint = LabelledSlider("Tint")

        self.reset_all_btn = QPushButton("Reset all adjustments")
        self.reset_all_btn.clicked.connect(self.reset_all)

        layout = QVBoxLayout(self)
        layout.setSpacing(8)
        for w in (self.exposure, self.contrast, self.saturation, self.temperature, self.tint):
            w.valueChanged.connect(self._emit)
            layout.addWidget(w)
        layout.addSpacing(4)
        layout.addWidget(self.reset_all_btn)
        layout.addStretch(1)

    def params(self) -> GradeParams:
        return GradeParams(
            exposure=self.exposure.value(),
            contrast=self.contrast.value(),
            saturation=self.saturation.value(),
            temperature=self.temperature.value(),
            tint=self.tint.value(),
        )

    def reset_all(self) -> None:
        for w in (self.exposure, self.contrast, self.saturation, self.temperature, self.tint):
            w.reset()

    def _emit(self, _v: float) -> None:
        self.paramsChanged.emit(self.params())
