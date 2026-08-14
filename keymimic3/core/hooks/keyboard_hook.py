"""Low-level keyboard hook (WH_KEYBOARD_LL)."""

import ctypes
from ctypes import wintypes

from .base_hook import BaseHook, WH_KEYBOARD_LL
from ..constants import IS_WINDOWS

if IS_WINDOWS:
    LRESULT = ctypes.c_ssize_t
    HOOKPROC = ctypes.WINFUNCTYPE(LRESULT, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM)

    class KBDLLHOOKSTRUCT(ctypes.Structure):
        _fields_ = [
            ("vkCode", wintypes.DWORD),
            ("scanCode", wintypes.DWORD),
            ("flags", wintypes.DWORD),
            ("time", wintypes.DWORD),
            ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong)),
        ]


class KeyboardHook(BaseHook):
    """
    Installs a global low-level keyboard hook and forwards every key event
    to `callback(nCode, wParam, kb_struct)`.

    If the callback returns a truthy value, the event is swallowed - it is
    not passed to the rest of the hook chain or the target application (used
    by RemoteControlManager to suppress local keys while forwarding them to
    a peer). Every other callback in the app returns None implicitly, which
    keeps the previous always-pass-through behavior unchanged.
    """

    def __init__(self, callback):
        super().__init__(WH_KEYBOARD_LL)
        self._callback = callback
        if IS_WINDOWS:
            self.hook_proc = HOOKPROC(self._hook_callback)

    def _hook_callback(self, nCode, wParam, lParam):
        if nCode >= 0:
            try:
                kb_struct = ctypes.cast(lParam, ctypes.POINTER(KBDLLHOOKSTRUCT)).contents
                if self._callback(nCode, wParam, kb_struct):
                    return 1
            except Exception:
                pass
        return ctypes.windll.user32.CallNextHookEx(self.hook_id, nCode, wParam, lParam)
