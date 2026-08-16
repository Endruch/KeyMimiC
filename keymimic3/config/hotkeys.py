"""Hard-wired global hotkeys (work even while minimized) plus small persisted settings."""

import json

from ..core.key_names import get_key_display_name
from .paths import APP_DATA_DIR, HOTKEYS_FILE

# Not user-configurable - there is no Settings UI to change these anymore.
HOTKEYS = {
    "start": {"key": "f8", "ctrl": True, "shift": False, "alt": False},
    "stop": {"key": "f9", "ctrl": True, "shift": False, "alt": False},
    "start_record": {"key": "f8", "ctrl": False, "shift": True, "alt": False},
    "stop_record": {"key": "f9", "ctrl": False, "shift": True, "alt": False},
}


class HotkeyConfig:
    """Exposes the fixed hotkey bindings, plus the one small setting that's still persisted: last_connect_ip."""

    def __init__(self):
        self.last_connect_ip = ""
        self.load()

    def load(self):
        if HOTKEYS_FILE.exists():
            try:
                with open(HOTKEYS_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self.last_connect_ip = data.get("last_connect_ip", "")
            except Exception:
                pass

    def save(self):
        try:
            APP_DATA_DIR.mkdir(parents=True, exist_ok=True)
            with open(HOTKEYS_FILE, "w", encoding="utf-8") as f:
                json.dump({"last_connect_ip": self.last_connect_ip}, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def get_hotkey(self, action):
        return HOTKEYS.get(action)

    def format_hotkey(self, action) -> str:
        """Return a short display string, e.g. 'Ctrl+F8'."""
        binding = self.get_hotkey(action)
        if not binding:
            return ""
        parts = []
        if binding.get("ctrl"):
            parts.append("Ctrl")
        if binding.get("shift"):
            parts.append("Shift")
        if binding.get("alt"):
            parts.append("Alt")
        parts.append(get_key_display_name(binding["key"]).upper())
        return "+".join(parts)
