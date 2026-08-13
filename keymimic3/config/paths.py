"""Filesystem locations used to persist profiles and settings."""

from pathlib import Path

OLD_APP_DATA_DIR = Path.home() / "Documents" / "KeyMimic v3"  # pre-rename branding
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

    Returns True if a migration was performed, False if one was needed but
    failed (the caller should warn the user - their data is still safe at
    OLD_APP_DATA_DIR, just not where the app will look for it), or None if
    there was nothing to migrate.
    """
    if not OLD_APP_DATA_DIR.exists() or APP_DATA_DIR.exists():
        return None
    try:
        OLD_APP_DATA_DIR.rename(APP_DATA_DIR)
        return True
    except OSError:
        return False  # e.g. a file inside is open elsewhere, or a permissions issue
