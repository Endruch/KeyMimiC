#!/usr/bin/env python3
"""
KeyMimic v2.0 - Main Entry Point
=================================
Professional keyboard and mouse automation tool for Windows.
"""

from keymimic.gui.main_window import MainWindow
from keymimic.utils.profile_manager import ensure_profiles_dir


def main():
    """Main entry point for the application."""
    ensure_profiles_dir()
    app = MainWindow()
    app.mainloop()


if __name__ == "__main__":
    main()
