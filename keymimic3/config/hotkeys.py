"""Persisted configuration for global hotkeys (works even while minimized)."""

import json

from ..core.key_names import get_key_display_name
from .paths import APP_DATA_DIR, HOTKEYS_FILE

DEFAULT_HOTKEYS = {
    "start": {"key": "f6", "ctrl": False, "shift": False, "alt": False},
    "stop": {"key": "f7", "ctrl": False, "shift": False, "alt": False},
    "start_record": {"key": "f8", "ctrl": False, "shift": False, "alt": False},
    "stop_record": {"key": "f9", "ctrl": False, "shift": False, "alt": False},
}

ACTION_LABELS = {
    "start": "Start macro",
    "stop": "Stop macro",
    "start_record": "Start recording",
    "stop_record": "Stop recording",
}


class HotkeyConfig:
    """Loads/saves global hotkey bindings plus the record-mouse toggle."""

    def __init__(self):
        self.hotkeys = {k: dict(v) for k, v in DEFAULT_HOTKEYS.items()}
        self.record_mouse = True
        self.load()

    def load(self):
        if HOTKEYS_FILE.exists():
            try:
                with open(HOTKEYS_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                for action, binding in data.get("hotkeys", {}).items():
                    if action in self.hotkeys:
                        self.hotkeys[action] = binding
                self.record_mouse = data.get("record_mouse", True)
            except Exception:
                pass

    def save(self):
        try:
            APP_DATA_DIR.mkdir(parents=True, exist_ok=True)
            with open(HOTKEYS_FILE, "w", encoding="utf-8") as f:
                json.dump(
                    {"hotkeys": self.hotkeys, "record_mouse": self.record_mouse},
                    f, ensure_ascii=False, indent=2,
                )
        except Exception:
            pass

    def get_hotkey(self, action):
        return self.hotkeys.get(action, DEFAULT_HOTKEYS.get(action))

    def set_hotkey(self, action, key, ctrl=False, shift=False, alt=False):
        self.hotkeys[action] = {"key": key, "ctrl": ctrl, "shift": shift, "alt": alt}
        self.save()

    def format_hotkey(self, action) -> str:
        """Return a short display string, e.g. 'Ctrl+F6'."""
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
