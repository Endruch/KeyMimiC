"""Filesystem locations used to persist profiles and settings."""

from pathlib import Path

APP_DATA_DIR = Path.home() / "Documents" / "KeyMimic"
PROFILES_DIR = APP_DATA_DIR / "profiles"
HOTKEYS_FILE = APP_DATA_DIR / "hotkeys.json"
