"""
Hotkey manager using composition pattern.

Uses KeyboardHook for event detection, manages hotkey registration and event queue.
"""

import queue
import ctypes

from ..core.hooks import KeyboardHook
from ..core.constants import SCAN_TO_CODE, SCAN_TO_CODE_EXT, IS_WINDOWS


# Windows constants
WM_KEYDOWN = 0x0100
WM_SYSKEYDOWN = 0x0104


class HotkeyManager:
    """
    Manages global hotkeys through keyboard hook.

    Uses composition - owns a KeyboardHook, doesn't inherit from it.
    """

    def __init__(self):
        """Initialize hotkey manager."""
        self.hotkey_map = {}  # {(code, ctrl, shift, alt): action}
        self.event_queue = queue.Queue(maxsize=100)
        self.keyboard_hook = None

    def register(self, code, action, modifiers=None):
        """
        Register a hotkey.

        Args:
            code: Internal key code (e.g., 87 for F11)
            action: Action name (e.g., 'start', 'stop', 'start_record')
            modifiers: Dict with 'ctrl', 'shift', 'alt' booleans
        """
        if modifiers is None:
            modifiers = {}

        key = (
            code,
            modifiers.get('ctrl', False),
            modifiers.get('shift', False),
            modifiers.get('alt', False)
        )

        self.hotkey_map[key] = action

    def unregister(self, code, modifiers=None):
        """
        Unregister a hotkey.

        Args:
            code: Internal key code
            modifiers: Dict with modifier states
        """
        if modifiers is None:
            modifiers = {}

        key = (
            code,
            modifiers.get('ctrl', False),
            modifiers.get('shift', False),
            modifiers.get('alt', False)
        )

        self.hotkey_map.pop(key, None)

    def clear(self):
        """Clear all registered hotkeys."""
        self.hotkey_map.clear()

    def start(self):
        """Start the keyboard hook."""
        if not IS_WINDOWS:
            return

        if self.keyboard_hook is None:
            self.keyboard_hook = KeyboardHook(self._on_keyboard_event)

        self.keyboard_hook.start()

    def stop(self):
        """Stop the keyboard hook."""
        if self.keyboard_hook:
            self.keyboard_hook.stop()
            self.keyboard_hook = None

    def _on_keyboard_event(self, nCode, wParam, kb_struct):
        """
        Callback from KeyboardHook.

        Args:
            nCode: Hook code
            wParam: Message identifier
            kb_struct: KBDLLHOOKSTRUCT instance
        """
        # Only process key down events
        if wParam not in (WM_KEYDOWN, WM_SYSKEYDOWN):
            return

        # Extract scan code and extended flag
        scan_code = kb_struct.scanCode
        extended = (kb_struct.flags & 0x1) != 0

        # Resolve to internal code
        if extended:
            code = SCAN_TO_CODE_EXT.get(scan_code)
        else:
            code = SCAN_TO_CODE.get(scan_code)

        if not code:
            return

        # ALWAYS check modifier state for accurate matching
        ctrl = (ctypes.windll.user32.GetKeyState(0x11) & 0x8000) != 0
        shift = (ctypes.windll.user32.GetKeyState(0x10) & 0x8000) != 0
        alt = (ctypes.windll.user32.GetKeyState(0x12) & 0x8000) != 0

        # Check if this exact key combination is registered
        key = (code, ctrl, shift, alt)
        if key in self.hotkey_map:
            action = self.hotkey_map[key]
            try:
                self.event_queue.put_nowait((action, None))
            except queue.Full:
                pass  # Drop event if queue full

    def get_hotkeys(self):
        """
        Get all registered hotkeys.

        Returns:
            Dict mapping (code, modifiers) to action
        """
        result = {}
        for (code, ctrl, shift, alt), action in self.hotkey_map.items():
            modifiers = {
                'ctrl': ctrl,
                'shift': shift,
                'alt': alt
            }
            result[(code, modifiers)] = action
        return result
