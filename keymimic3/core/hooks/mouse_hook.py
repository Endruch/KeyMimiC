"""Low-level mouse hook (WH_MOUSE_LL)."""

import ctypes
from ctypes import wintypes

from .base_hook import BaseHook, WH_MOUSE_LL
from ..constants import IS_WINDOWS

if IS_WINDOWS:
    LRESULT = ctypes.c_ssize_t
    HOOKPROC = ctypes.WINFUNCTYPE(LRESULT, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM)

    class MSLLHOOKSTRUCT(ctypes.Structure):
        _fields_ = [
            ("pt", wintypes.POINT),
            ("mouseData", wintypes.DWORD),
            ("flags", wintypes.DWORD),
            ("time", wintypes.DWORD),
            ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong)),
        ]


class MouseHook(BaseHook):
    """
    Installs a global low-level mouse hook and forwards every mouse event
    to `callback(nCode, wParam, mouse_struct)`.
    """

    def __init__(self, callback):
        super().__init__(WH_MOUSE_LL)
        self._callback = callback
        if IS_WINDOWS:
            self.hook_proc = HOOKPROC(self._hook_callback)

    def _hook_callback(self, nCode, wParam, lParam):
        if nCode >= 0:
            try:
                mouse_struct = ctypes.cast(lParam, ctypes.POINTER(MSLLHOOKSTRUCT)).contents
                self._callback(nCode, wParam, mouse_struct)
            except Exception:
                pass
        return ctypes.windll.user32.CallNextHookEx(self.hook_id, nCode, wParam, lParam)
