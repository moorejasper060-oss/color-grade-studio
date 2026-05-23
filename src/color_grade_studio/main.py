"""Application entry point."""
from __future__ import annotations

import os
import sys

from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QApplication

from .ui.main_window import MainWindow


def main() -> int:
    # Ask Qt to use the high-DPI image scaling.
    QGuiApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    app = QApplication(sys.argv)
    app.setApplicationName("Color Grade Studio")
    app.setOrganizationName("Color Grade Studio")
    app.setStyle("Fusion")

    win = MainWindow()
    win.show()

    # Optionally open a file passed on the CLI.
    if len(sys.argv) > 1 and os.path.exists(sys.argv[1]):
        from pathlib import Path
        win._load_video(Path(sys.argv[1]))

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
