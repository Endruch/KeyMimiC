#!/usr/bin/env python3
"""
KeyMimic v3 - Main Entry Point
================================
Block-based keyboard & mouse automation tool for Windows.
"""

import sys

from PySide6.QtWidgets import QApplication

from keymimic3.config.paths import PROFILES_DIR
from keymimic3.gui import MainWindow


def main():
    PROFILES_DIR.mkdir(parents=True, exist_ok=True)

    app = QApplication(sys.argv)
    app.setApplicationName("KeyMimic v3")

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
