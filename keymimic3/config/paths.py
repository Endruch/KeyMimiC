"""Filesystem locations used to persist profiles and settings."""

from pathlib import Path

_OLD_APP_DATA_DIR = Path.home() / "Documents" / "KeyMimic v3"  # pre-rename branding
APP_DATA_DIR = Path.home() / "Documents" / "KeyMiglic"
PROFILES_DIR = APP_DATA_DIR / "profiles"
HOTKEYS_FILE = APP_DATA_DIR / "hotkeys.json"


def migrate_old_app_data_dir():
    """
    One-time rename of the whole data directory from the old "KeyMimic v3"
    branding to "KeyMiglic", preserving every existing profile/hotkey file
    already on disk instead of silently starting fresh under the new name.
    Call once, early, at app startup - before anything else touches
    APP_DATA_DIR/PROFILES_DIR/HOTKEYS_FILE.
    """
    if _OLD_APP_DATA_DIR.exists() and not APP_DATA_DIR.exists():
        try:
            _OLD_APP_DATA_DIR.rename(APP_DATA_DIR)
        except OSError:
            pass  # e.g. cross-device rename on an unusual setup - fall back to a fresh dir
