"""
Base class for Windows low-level hooks (WH_KEYBOARD_LL / WH_MOUSE_LL).

Handles hook installation, the required message loop, and cleanup. Subclasses
only need to implement `_hook_callback`.
"""

import ctypes
import threading
import time
from ctypes import wintypes

from ..constants import IS_WINDOWS

WH_KEYBOARD_LL = 13
WH_MOUSE_LL = 14


class BaseHook:
    """Abstract base class for a Windows low-level hook running on its own thread."""

    def __init__(self, hook_type):
        self.hook_type = hook_type
        self.hook_id = None
        self.hook_proc = None
        self.active = False
        self._thread = None
        self._running = False

    def start(self):
        """Install the hook and start its dedicated message-loop thread."""
        if not IS_WINDOWS or self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._run_hook, daemon=True)
        self._thread.start()

    def stop(self):
        """Uninstall the hook and stop its thread."""
        if not IS_WINDOWS:
            return
        self._running = False
        self.active = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.0)
        if self.hook_id:
            try:
                ctypes.windll.user32.UnhookWindowsHookEx(self.hook_id)
            except Exception:
                pass
            self.hook_id = None

    def _run_hook(self):
        try:
            self.hook_id = ctypes.windll.user32.SetWindowsHookExA(
                self.hook_type, self.hook_proc, None, 0
            )
            if not self.hook_id:
                return
            self.active = True

            msg = wintypes.MSG()
            while self._running:
                got_msg = ctypes.windll.user32.PeekMessageW(
                    ctypes.byref(msg), None, 0, 0, 1  # PM_REMOVE
                )
                if got_msg:
                    ctypes.windll.user32.TranslateMessage(ctypes.byref(msg))
                    ctypes.windll.user32.DispatchMessageW(ctypes.byref(msg))
                else:
                    time.sleep(0.001)
        except Exception:
            pass
        finally:
            self.active = False
            if self.hook_id:
                try:
                    ctypes.windll.user32.UnhookWindowsHookEx(self.hook_id)
                except Exception:
                    pass
                self.hook_id = None

    def _hook_callback(self, nCode, wParam, lParam):
        """
        Hook callback, overridden by subclasses.

        Performance rules: never allocate heavy objects or do I/O here, always
        call CallNextHookEx, never let an exception escape.
        """
        raise NotImplementedError
