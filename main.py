#!/usr/bin/env python3
"""
KeyMimic v3 - Main Entry Point
================================
Block-based keyboard & mouse automation tool for Windows.
"""

import sys
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon, QGuiApplication
from PySide6.QtWidgets import QApplication

from keymimic3.config.paths import PROFILES_DIR
from keymimic3.gui import MainWindow


def _resource_path(relative_path: str) -> Path:
    """
    Resolve a bundled resource, working both when run from source and when
    packaged by PyInstaller (--onefile extracts data files to sys._MEIPASS).
    """
    base_dir = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    return base_dir / relative_path


def main():
    PROFILES_DIR.mkdir(parents=True, exist_ok=True)

    # Qt6 enables high-DPI scaling by default, but at fractional scale factors
    # (125%/150%, common on Windows laptops) it rounds to the nearest integer
    # unless told otherwise - PassThrough uses the exact factor instead, so
    # text and layout don't come out slightly blurry/mis-sized.
    QGuiApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    app = QApplication(sys.argv)
    app.setApplicationName("KeyMimic v3")

    icon_path = _resource_path("assets/icon.ico")
    icon = QIcon(str(icon_path)) if icon_path.exists() else None
    if icon:
        app.setWindowIcon(icon)

    window = MainWindow()
    if icon:
        window.setWindowIcon(icon)
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
