"""
Thread-safe hotkey configuration management.
"""

import json
import threading
from pathlib import Path


# Config directory
CONFIG_DIR = Path.home() / "Documents" / "KeyMimic" / "profiles"


class HotkeyConfig:
    """
    Manages global hotkey settings with thread-safety.

    Uses threading.Lock to prevent race conditions during file operations.
    """

    DEFAULT_HOTKEYS = {
        "start_record": {
            "key": "F12",
            "code": 88,
            "modifiers": {"ctrl": False, "shift": False, "alt": False}
        },
        "stop_record": {
            "key": "Shift+F12",
            "code": 88,
            "modifiers": {"ctrl": False, "shift": True, "alt": False}
        },
        "start": {
            "key": "F11",
            "code": 87,
            "modifiers": {"ctrl": False, "shift": False, "alt": False}
        },
        "stop": {
            "key": "Shift+F11",
            "code": 87,
            "modifiers": {"ctrl": False, "shift": True, "alt": False}
        }
    }

    def __init__(self):
        """Initialize hotkey configuration."""
        self.config_file = CONFIG_DIR / "hotkeys.json"
        self._lock = threading.Lock()
        self.hotkeys = self._load_hotkeys()
        self.record_mouse = self._load_record_mouse()

    def _ensure_dir(self):
        """Ensure config directory exists."""
        try:
            CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        except Exception:
            pass

    def _load_hotkeys(self):
        """Load hotkey configuration from JSON file."""
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    loaded = json.load(f)
                    # Merge with defaults (in case new actions are added)
                    hotkeys = self.DEFAULT_HOTKEYS.copy()
                    for action in self.DEFAULT_HOTKEYS:
                        if action in loaded:
                            hotkeys[action] = loaded[action]
                    return hotkeys
            except Exception:
                pass

        return self.DEFAULT_HOTKEYS.copy()

    def _load_record_mouse(self):
        """Load mouse recording preference."""
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    return data.get("record_mouse", False)
            except Exception:
                pass
        return False

    def get_hotkey(self, action):
        """
        Get hotkey for an action (thread-safe).

        Args:
            action: One of "start_record", "stop_record", "start", "stop"

        Returns:
            Dict with "key" (display name), "code", and "modifiers"
        """
        with self._lock:
            return self.hotkeys.get(action, self.DEFAULT_HOTKEYS.get(action)).copy()

    def set_hotkey(self, action, key_name, key_code, modifiers=None):
        """
        Set hotkey for an action (thread-safe).

        Args:
            action: One of "start_record", "stop_record", "start", "stop"
            key_name: Display name (e.g., "F12", "Shift+F12")
            key_code: Internal key code integer
            modifiers: Dict with ctrl/shift/alt bools (optional)
        """
        if modifiers is None:
            modifiers = {"ctrl": False, "shift": False, "alt": False}

        with self._lock:
            self.hotkeys[action] = {
                "key": key_name,
                "code": key_code,
                "modifiers": modifiers
            }
            self._save()

    def get_all_hotkeys(self):
        """
        Get all hotkey configurations (thread-safe).

        Returns:
            Dict mapping action to hotkey config
        """
        with self._lock:
            return {k: v.copy() for k, v in self.hotkeys.items()}

    def reset_to_defaults(self):
        """Reset all hotkeys to default values (thread-safe)."""
        with self._lock:
            self.hotkeys = self.DEFAULT_HOTKEYS.copy()
            self._save()

    def get_record_mouse(self):
        """
        Get mouse recording preference (thread-safe).

        Returns:
            True if mouse recording is enabled
        """
        with self._lock:
            return self.record_mouse

    def set_record_mouse(self, enabled):
        """
        Set mouse recording preference (thread-safe).

        Args:
            enabled: True to enable mouse recording
        """
        with self._lock:
            self.record_mouse = enabled
            self._save()

    def _save(self):
        """Save configuration to JSON file (internal, assumes lock is held)."""
        self._ensure_dir()
        try:
            # Combine hotkeys and record_mouse setting
            data = self.hotkeys.copy()
            data["record_mouse"] = self.record_mouse

            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Error saving hotkey config: {e}")

    def save(self):
        """Save configuration to JSON file (thread-safe)."""
        with self._lock:
            self._save()
