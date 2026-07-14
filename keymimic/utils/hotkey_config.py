"""
Hotkey configuration management for storing and loading global hotkey settings.
"""

import os
import json
from .profile_manager import PROFILES_DIR, ensure_profiles_dir


class HotkeyConfig:
    """Manages global hotkey settings."""

    DEFAULT_HOTKEYS = {
        "record": {"key": "F12", "code": 88},
        "start": {"key": "F10", "code": 68},
        "stop": {"key": "F11", "code": 87}
    }

    def __init__(self):
        self.config_file = os.path.join(PROFILES_DIR, "hotkeys.json")
        self.hotkeys = self.load()

    def load(self):
        """Load hotkey configuration from JSON file."""
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    loaded = json.load(f)
                    # Merge with defaults (in case new actions are added)
                    return {**self.DEFAULT_HOTKEYS, **loaded}
            except Exception:
                pass
        return self.DEFAULT_HOTKEYS.copy()

    def save(self):
        """Save hotkey configuration to JSON file."""
        ensure_profiles_dir()
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.hotkeys, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Error saving hotkey config: {e}")

    def get_hotkey(self, action):
        """
        Get hotkey for an action.

        Args:
            action: One of "record", "start", "stop"

        Returns:
            dict with "key" (display name) and "code" (scan code)
        """
        return self.hotkeys.get(action, self.DEFAULT_HOTKEYS.get(action))

    def set_hotkey(self, action, key_name, key_code):
        """
        Set hotkey for an action.

        Args:
            action: One of "record", "start", "stop"
            key_name: Display name (e.g., "F12", "CTRL+S")
            key_code: Scan code integer
        """
        self.hotkeys[action] = {"key": key_name, "code": key_code}
        self.save()

    def get_all_hotkeys(self):
        """Get all hotkey configurations."""
        return self.hotkeys.copy()

    def reset_to_defaults(self):
        """Reset all hotkeys to default values."""
        self.hotkeys = self.DEFAULT_HOTKEYS.copy()
        self.save()
