"""Application entry point."""
from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QApplication

from .core import SUPPORTED_EXTENSIONS
from .ui.main_window import MainWindow


def main() -> int:
    QGuiApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    app = QApplication(sys.argv)
    app.setApplicationName("Color Grade Studio")
    app.setOrganizationName("Color Grade Studio")
    app.setStyle("Fusion")

    win = MainWindow()
    win.show()

    # Optionally open a file passed on the CLI. Apply the same extension
    # check that drag-drop uses so we don't hand garbage to OpenCV.
    if len(sys.argv) > 1:
        candidate = Path(sys.argv[1])
        if candidate.exists() and candidate.suffix.lower() in SUPPORTED_EXTENSIONS:
            win._load_video(candidate)

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
