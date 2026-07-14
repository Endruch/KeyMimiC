#!/usr/bin/env python3
"""
KeyMimic v2.0 - Main Entry Point
=================================
Professional keyboard and mouse automation tool for Windows.
"""

from keymimic.gui.main_window import MainWindow
from keymimic.config import PROFILES_DIR


def main():
    """Main entry point for the application."""
    # Ensure profile directory exists
    PROFILES_DIR.mkdir(parents=True, exist_ok=True)

    app = MainWindow()
    app.mainloop()


if __name__ == "__main__":
    main()
