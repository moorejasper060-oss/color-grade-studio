"""Custom timeline widget with trim handles and a playhead."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto
from typing import Optional

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QMouseEvent, QPainter, QPen
from PySide6.QtWidgets import QSizePolicy, QWidget


class _Drag(Enum):
    NONE = auto()
    IN_HANDLE = auto()
    OUT_HANDLE = auto()
    PLAYHEAD = auto()


@dataclass
class TimelineState:
    total_frames: int = 0
    fps: float = 30.0
    in_frame: int = 0
    out_frame: int = 0
    playhead: int = 0


class TimelineWidget(QWidget):
    """Lightweight timeline.

    Signals:
        playheadMoved(frame: int)        - user dragged the playhead
        trimRangeChanged(in_f: int, out_f: int) - user moved a trim handle
    """

    playheadMoved = Signal(int)
    trimRangeChanged = Signal(int, int)

    HANDLE_HALF_WIDTH = 6  # pixels — clickable zone around each trim handle
    PLAYHEAD_HALF_WIDTH = 4

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.state = TimelineState()
        self._drag = _Drag.NONE
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setMinimumHeight(58)
        self.setMaximumHeight(72)
        self.setMouseTracking(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    # --- Public API -----------------------------------------------------

    def set_video(self, total_frames: int, fps: float) -> None:
        self.state.total_frames = max(total_frames, 1)
        self.state.fps = max(fps, 1.0)
        self.state.in_frame = 0
        self.state.out_frame = self.state.total_frames - 1
        self.state.playhead = 0
        self.update()

    def set_playhead(self, frame: int) -> None:
        frame = max(0, min(frame, self.state.total_frames - 1))
        if frame != self.state.playhead:
            self.state.playhead = frame
            self.update()

    def trim_range(self) -> tuple[int, int]:
        return self.state.in_frame, self.state.out_frame

    # --- Painting -------------------------------------------------------

    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        r = self.rect().adjusted(8, 12, -8, -12)
        track_top = r.top() + r.height() // 2 - 5
        track_h = 10
        track = QRectF(r.left(), track_top, r.width(), track_h)

        # Background track.
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor("#2a2a2a"))
        p.drawRoundedRect(track, 4, 4)

        if self.state.total_frames > 1:
            in_x = self._frame_to_x(self.state.in_frame)
            out_x = self._frame_to_x(self.state.out_frame)
            # Selected (trim) region.
            sel = QRectF(in_x, track_top, max(out_x - in_x, 1), track_h)
            p.setBrush(QColor("#4a9eff"))
            p.drawRoundedRect(sel, 4, 4)

            # Trim handles.
            self._draw_handle(p, in_x, r.top(), r.bottom())
            self._draw_handle(p, out_x, r.top(), r.bottom())

            # Playhead.
            play_x = self._frame_to_x(self.state.playhead)
            p.setPen(QPen(QColor("#ffffff"), 2))
            p.drawLine(int(play_x), r.top() - 2, int(play_x), r.bottom() + 2)
            p.setBrush(QColor("#ffffff"))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawEllipse(QPointF(play_x, r.top() - 1), 3, 3)

            # Time label.
            cur_t = self.state.playhead / self.state.fps
            tot_t = self.state.total_frames / self.state.fps
            p.setPen(QColor("#9a9a9a"))
            p.drawText(
                self.rect().adjusted(10, 0, -10, -2),
                int(Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignLeft),
                f"{_format_time(cur_t)}  /  {_format_time(tot_t)}",
            )

    def _draw_handle(self, p: QPainter, x: float, top: int, bottom: int) -> None:
        rect = QRectF(x - 4, top, 8, bottom - top)
        p.setBrush(QColor("#f4f4f4"))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawRoundedRect(rect, 2, 2)

    def _frame_to_x(self, frame: int) -> float:
        r = self.rect().adjusted(8, 0, -8, 0)
        if self.state.total_frames <= 1:
            return float(r.left())
        ratio = frame / (self.state.total_frames - 1)
        return r.left() + ratio * r.width()

    def _x_to_frame(self, x: float) -> int:
        r = self.rect().adjusted(8, 0, -8, 0)
        if r.width() <= 0:
            return 0
        ratio = (x - r.left()) / r.width()
        ratio = max(0.0, min(1.0, ratio))
        return int(round(ratio * (self.state.total_frames - 1)))

    # --- Mouse ----------------------------------------------------------

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() != Qt.MouseButton.LeftButton:
            return
        if self.state.total_frames <= 1:
            return
        x = event.position().x()
        in_x = self._frame_to_x(self.state.in_frame)
        out_x = self._frame_to_x(self.state.out_frame)
        if abs(x - in_x) <= self.HANDLE_HALF_WIDTH:
            self._drag = _Drag.IN_HANDLE
        elif abs(x - out_x) <= self.HANDLE_HALF_WIDTH:
            self._drag = _Drag.OUT_HANDLE
        else:
            # Click anywhere else moves the playhead and starts scrubbing.
            self._drag = _Drag.PLAYHEAD
            new_frame = self._x_to_frame(x)
            self.state.playhead = new_frame
            self.playheadMoved.emit(new_frame)
            self.update()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._drag == _Drag.NONE:
            return
        new_frame = self._x_to_frame(event.position().x())
        if self._drag == _Drag.IN_HANDLE:
            new_frame = min(new_frame, self.state.out_frame - 1)
            new_frame = max(0, new_frame)
            if new_frame != self.state.in_frame:
                self.state.in_frame = new_frame
                self.trimRangeChanged.emit(self.state.in_frame, self.state.out_frame)
                self.update()
        elif self._drag == _Drag.OUT_HANDLE:
            new_frame = max(new_frame, self.state.in_frame + 1)
            new_frame = min(new_frame, self.state.total_frames - 1)
            if new_frame != self.state.out_frame:
                self.state.out_frame = new_frame
                self.trimRangeChanged.emit(self.state.in_frame, self.state.out_frame)
                self.update()
        elif self._drag == _Drag.PLAYHEAD:
            if new_frame != self.state.playhead:
                self.state.playhead = new_frame
                self.playheadMoved.emit(new_frame)
                self.update()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        self._drag = _Drag.NONE


def _format_time(seconds: float) -> str:
    seconds = max(0.0, seconds)
    m, s = divmod(seconds, 60)
    return f"{int(m):02d}:{s:05.2f}"
