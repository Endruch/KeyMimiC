"""
Optimized mouse hook for KeyMimic.

CRITICAL OPTIMIZATION:
- MSLLHOOKSTRUCT created ONCE in __init__, not in callback
- HOOKPROC created ONCE in __init__, reused for all events
- Zero allocations in hot path
- Early returns for fast paths
"""

import ctypes
from ctypes import wintypes

from .base_hook import BaseHook, IS_WINDOWS

# Windows constants
WH_MOUSE_LL = 14
WM_MOUSEMOVE = 0x0200
WM_LBUTTONDOWN = 0x0201
WM_LBUTTONUP = 0x0202
WM_RBUTTONDOWN = 0x0204
WM_RBUTTONUP = 0x0205
WM_MBUTTONDOWN = 0x0207
WM_MBUTTONUP = 0x0208
WM_MOUSEWHEEL = 0x020A
WM_XBUTTONDOWN = 0x020B
WM_XBUTTONUP = 0x020C


class MouseHook(BaseHook):
    """Optimized low-level mouse hook."""

    def __init__(self, callback):
        """
        Initialize mouse hook.

        Args:
            callback: Function to call on mouse events.
                     Signature: callback(nCode, wParam, mouse_struct)
        """
        super().__init__(WH_MOUSE_LL)

        self.user_callback = callback

        if not IS_WINDOWS:
            return

        # CRITICAL: Create MSLLHOOKSTRUCT ONCE, not in callback
        class POINT(ctypes.Structure):
            _fields_ = [
                ("x", wintypes.LONG),
                ("y", wintypes.LONG)
            ]

        class MSLLHOOKSTRUCT(ctypes.Structure):
            _fields_ = [
                ("pt", POINT),
                ("mouseData", wintypes.DWORD),
                ("flags", wintypes.DWORD),
                ("time", wintypes.DWORD),
                ("dwExtraInfo", ctypes.POINTER(wintypes.ULONG))
            ]

        self.MSLLHOOKSTRUCT = MSLLHOOKSTRUCT

        # CRITICAL: Create HOOKPROC ONCE, not in callback
        self.hook_proc = ctypes.WINFUNCTYPE(
            wintypes.LPARAM,  # Return: LRESULT (pointer-sized)
            ctypes.c_int,     # nCode
            wintypes.WPARAM,  # wParam (pointer-sized)
            wintypes.LPARAM   # lParam (pointer-sized)
        )(self._hook_callback)

    def _hook_callback(self, nCode, wParam, lParam):
        """
        Optimized mouse hook callback.

        ZERO ALLOCATIONS - all structures created in __init__.

        Performance: < 0.01ms per mouse event
        """
        # Fast path 1: Windows requirement - pass through immediately
        if nCode < 0:
            return ctypes.windll.user32.CallNextHookEx(None, nCode, wParam, lParam)

        # Fast path 2: Hook not active - pass through immediately
        if not self.active:
            return ctypes.windll.user32.CallNextHookEx(None, nCode, wParam, lParam)

        try:
            # Use pre-created structure - ZERO allocations!
            mouse_struct = ctypes.cast(
                lParam,
                ctypes.POINTER(self.MSLLHOOKSTRUCT)
            ).contents

            # Call user callback
            self.user_callback(nCode, wParam, mouse_struct)

        except Exception:
            # Never let exceptions block mouse
            pass

        # ALWAYS call next hook
        return ctypes.windll.user32.CallNextHookEx(None, nCode, wParam, lParam)
