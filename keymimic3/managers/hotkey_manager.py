"""Global hotkey manager: fires registered actions even while the window is minimized."""

import ctypes
import queue

from ..core.hooks import KeyboardHook
from ..core.constants import SCAN_TO_CODE, SCAN_TO_CODE_EXT, IS_WINDOWS

WM_KEYDOWN = 0x0100
WM_SYSKEYDOWN = 0x0104

VK_CONTROL = 0x11
VK_SHIFT = 0x10
VK_MENU = 0x12  # Alt


class HotkeyManager:
    """Owns a KeyboardHook and dispatches matching key combos into a queue."""

    def __init__(self):
        self.hotkey_map = {}  # (code, ctrl, shift, alt) -> action name
        self.event_queue = queue.Queue(maxsize=100)
        self.keyboard_hook = None

    def register(self, code, action, ctrl=False, shift=False, alt=False):
        self.hotkey_map[(code, ctrl, shift, alt)] = action

    def clear(self):
        self.hotkey_map.clear()

    def start(self):
        if not IS_WINDOWS:
            return
        if self.keyboard_hook is None:
            self.keyboard_hook = KeyboardHook(self._on_keyboard_event)
        self.keyboard_hook.start()

    def stop(self):
        if self.keyboard_hook:
            self.keyboard_hook.stop()
            self.keyboard_hook = None

    def _on_keyboard_event(self, nCode, wParam, kb_struct):
        if wParam not in (WM_KEYDOWN, WM_SYSKEYDOWN):
            return

        extended = (kb_struct.flags & 0x1) != 0
        code = (SCAN_TO_CODE_EXT if extended else SCAN_TO_CODE).get(kb_struct.scanCode)
        if not code:
            return

        ctrl = (ctypes.windll.user32.GetKeyState(VK_CONTROL) & 0x8000) != 0
        shift = (ctypes.windll.user32.GetKeyState(VK_SHIFT) & 0x8000) != 0
        alt = (ctypes.windll.user32.GetKeyState(VK_MENU) & 0x8000) != 0

        action = self.hotkey_map.get((code, ctrl, shift, alt))
        if action:
            try:
                self.event_queue.put_nowait(action)
            except queue.Full:
                pass
