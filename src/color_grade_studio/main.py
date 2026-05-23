"""Application entry point.

PyInstaller wraps this file as the top-level script, so ``__package__`` is
empty at runtime and relative imports (``from .core import …``) fail. Use
absolute imports here even though the rest of the package uses relative
ones — this file is the one the bootloader sees as `main`.
"""
from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication, QIcon
from PySide6.QtWidgets import QApplication

from color_grade_studio.core import SUPPORTED_EXTENSIONS
from color_grade_studio.resources import icon_path
from color_grade_studio.ui.main_window import MainWindow


APP_ID = "ColorGradeStudio.JasperMoore.ColorGradeStudio.1"


def _register_appusermodelid() -> None:
    """Tell Windows this app is its own thing so the taskbar uses our icon.

    Without this, PyInstaller-bundled Qt apps end up grouped under the
    generic Python icon. Failure here is non-fatal — it only affects how
    the taskbar groups windows.
    """
    if sys.platform != "win32":
        return
    try:
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_ID)
    except Exception:
        pass


def main() -> int:
    _register_appusermodelid()

    QGuiApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    app = QApplication(sys.argv)
    app.setApplicationName("Color Grade Studio")
    app.setOrganizationName("Color Grade Studio")
    app.setStyle("Fusion")

    # Use the bundled PNG icon — Qt scales it for the title bar and the
    # taskbar. The .ico is for the .exe shell metadata; Qt itself prefers PNG.
    p = icon_path("app.png")
    if p is not None:
        app_icon = QIcon(str(p))
        app.setWindowIcon(app_icon)

    win = MainWindow()
    if p is not None:
        win.setWindowIcon(QIcon(str(p)))
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
