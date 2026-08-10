#!/usr/bin/env python3
"""
KeyMimic v3 - Main Entry Point
================================
Block-based keyboard & mouse automation tool for Windows.
"""

import sys
from pathlib import Path

from PySide6.QtGui import QIcon
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

    app = QApplication(sys.argv)
    app.setApplicationName("KeyMimic v3")

    icon_path = _resource_path("assets/icon.ico")
    if icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
