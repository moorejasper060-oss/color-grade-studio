"""Qt stylesheet for the modern-dark theme."""

DARK_QSS = """
* { font-family: 'Segoe UI', system-ui, sans-serif; font-size: 11pt; }

QMainWindow, QWidget { background-color: #181818; color: #e4e4e4; }

QMenuBar { background-color: #1f1f1f; color: #e4e4e4; padding: 4px; }
QMenuBar::item { padding: 4px 10px; background: transparent; border-radius: 4px; }
QMenuBar::item:selected { background-color: #2e2e2e; }
QMenu { background-color: #1f1f1f; color: #e4e4e4; border: 1px solid #303030; }
QMenu::item { padding: 6px 22px; }
QMenu::item:selected { background-color: #2e2e2e; }
QMenu::separator { height: 1px; background: #303030; margin: 4px 8px; }

QStatusBar { background-color: #1a1a1a; color: #9c9c9c; border-top: 1px solid #2a2a2a; }
QStatusBar::item { border: none; }

QToolTip { background-color: #2a2a2a; color: #e4e4e4; border: 1px solid #404040; padding: 4px; }

QSplitter::handle { background-color: #232323; }
QSplitter::handle:horizontal { width: 4px; }
QSplitter::handle:vertical { height: 4px; }

QGroupBox {
    background-color: #1f1f1f;
    border: 1px solid #2a2a2a;
    border-radius: 6px;
    margin-top: 14px;
    padding-top: 6px;
    color: #cfcfcf;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 10px; top: -2px;
    padding: 0 4px;
    color: #b6b6b6;
    font-size: 9pt;
    letter-spacing: 1px;
    text-transform: uppercase;
}

QPushButton {
    background-color: #2a2a2a;
    color: #e4e4e4;
    border: 1px solid #353535;
    border-radius: 5px;
    padding: 6px 14px;
}
QPushButton:hover { background-color: #333333; border-color: #4a4a4a; }
QPushButton:pressed { background-color: #1f1f1f; }
QPushButton:disabled { color: #666666; background-color: #232323; }
QPushButton#primary {
    background-color: #4a9eff;
    color: #ffffff;
    border: 1px solid #4a9eff;
    font-weight: 600;
}
QPushButton#primary:hover { background-color: #5dadff; }
QPushButton#primary:pressed { background-color: #3b8fef; }

QSlider::groove:horizontal {
    height: 4px;
    background: #2c2c2c;
    border-radius: 2px;
}
QSlider::sub-page:horizontal { background: #4a9eff; border-radius: 2px; }
QSlider::handle:horizontal {
    background: #f0f0f0;
    width: 14px; height: 14px;
    margin: -6px 0;
    border-radius: 7px;
    border: 1px solid #bdbdbd;
}
QSlider::handle:horizontal:hover { background: #ffffff; }

QListWidget {
    background-color: #1c1c1c;
    border: 1px solid #2a2a2a;
    border-radius: 6px;
    padding: 4px;
    outline: 0;
}
QListWidget::item {
    background-color: #232323;
    border: 1px solid transparent;
    border-radius: 5px;
    padding: 6px;
    margin: 3px 2px;
    color: #d0d0d0;
}
QListWidget::item:hover { background-color: #2a2a2a; }
QListWidget::item:selected {
    background-color: #2f3d52;
    border: 1px solid #4a9eff;
    color: #ffffff;
}

QLabel { color: #e4e4e4; }
QLabel#section { color: #b6b6b6; font-size: 9pt; letter-spacing: 1px; }
QLabel#title { color: #ffffff; font-weight: 600; font-size: 12pt; }
QLabel#dim { color: #888888; }
QLabel#preview {
    background-color: #0d0d0d;
    border: 1px solid #2a2a2a;
    border-radius: 6px;
}

QProgressBar {
    background-color: #202020;
    border: 1px solid #2a2a2a;
    border-radius: 4px;
    text-align: center;
    color: #ffffff;
}
QProgressBar::chunk { background-color: #4a9eff; border-radius: 3px; }

QSpinBox, QDoubleSpinBox, QComboBox, QLineEdit {
    background-color: #232323;
    border: 1px solid #303030;
    border-radius: 4px;
    padding: 4px 6px;
    color: #e4e4e4;
    selection-background-color: #4a9eff;
}
QComboBox::drop-down { border: none; width: 18px; }
QComboBox QAbstractItemView {
    background-color: #1f1f1f;
    border: 1px solid #303030;
    color: #e4e4e4;
    selection-background-color: #2f3d52;
}

QCheckBox { color: #e4e4e4; spacing: 6px; }
QCheckBox::indicator { width: 16px; height: 16px; border-radius: 3px; border: 1px solid #444; background: #232323; }
QCheckBox::indicator:checked { background: #4a9eff; border-color: #4a9eff; }

QScrollBar:vertical { background: #181818; width: 10px; margin: 0; }
QScrollBar::handle:vertical { background: #2f2f2f; border-radius: 5px; min-height: 24px; }
QScrollBar::handle:vertical:hover { background: #3a3a3a; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: none; }
QScrollBar:horizontal { background: #181818; height: 10px; margin: 0; }
QScrollBar::handle:horizontal { background: #2f2f2f; border-radius: 5px; min-width: 24px; }
QScrollBar::handle:horizontal:hover { background: #3a3a3a; }
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; }
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal { background: none; }
"""
