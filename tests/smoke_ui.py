"""Headless-ish UI smoke test.

Creates the main window, lets the event loop spin briefly, then quits. Verifies
that widgets construct and lay out without crashing. Run via ``python -m`` so
it picks up the package on PYTHONPATH.
"""
from __future__ import annotations

import sys

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from color_grade_studio.ui.main_window import MainWindow


def main() -> int:
    app = QApplication.instance() or QApplication(sys.argv)
    win = MainWindow()
    win.show()
    # Render a frame, then exit cleanly.
    QTimer.singleShot(800, app.quit)
    code = app.exec()
    win.close()
    print("smoke OK")
    return code


if __name__ == "__main__":
    sys.exit(main())
