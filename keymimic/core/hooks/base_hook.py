"""
Base class for Windows low-level hooks.

Provides common functionality for keyboard and mouse hooks:
- Hook installation and cleanup
- Message loop management
- Thread safety
"""

import ctypes
import threading
import time
from ctypes import wintypes

try:
    IS_WINDOWS = True
    # Windows constants
    WH_KEYBOARD_LL = 13
    WH_MOUSE_LL = 14
except:
    IS_WINDOWS = False


class BaseHook:
    """Abstract base class for Windows low-level hooks."""

    def __init__(self, hook_type):
        """
        Initialize base hook.

        Args:
            hook_type: WH_KEYBOARD_LL (13) or WH_MOUSE_LL (14)
        """
        self.hook_type = hook_type
        self.hook_id = None
        self.hook_proc = None
        self.active = False
        self._thread = None
        self._running = False

    def start(self):
        """Start the hook in a separate thread."""
        if not IS_WINDOWS:
            return

        if self._running:
            return

        self._running = True
        self._thread = threading.Thread(target=self._run_hook, daemon=True)
        self._thread.start()

    def stop(self):
        """Stop the hook and cleanup."""
        if not IS_WINDOWS:
            return

        self._running = False
        self.active = False

        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.0)

        if self.hook_id:
            try:
                ctypes.windll.user32.UnhookWindowsHookEx(self.hook_id)
            except:
                pass
            self.hook_id = None

    def _run_hook(self):
        """Run hook in dedicated thread with message loop."""
        try:
            # Install hook
            self.hook_id = ctypes.windll.user32.SetWindowsHookExA(
                self.hook_type,
                self.hook_proc,
                None,
                0
            )

            if not self.hook_id:
                return

            self.active = True

            # Message loop (required for hooks to work)
            msg = wintypes.MSG()
            while self._running:
                result = ctypes.windll.user32.PeekMessageW(
                    ctypes.byref(msg),
                    None,
                    0,
                    0,
                    1  # PM_REMOVE
                )

                if result:
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
                except:
                    pass
                self.hook_id = None

    def _hook_callback(self, nCode, wParam, lParam):
        """
        Hook callback - to be overridden by subclasses.

        CRITICAL PERFORMANCE RULES:
        1. If nCode < 0, return CallNextHookEx immediately
        2. Never do I/O (file writes, prints) in callback
        3. Never allocate classes/objects in hot path
        4. Always call CallNextHookEx at the end
        5. Never raise exceptions outside try/except

        Args:
            nCode: Hook code
            wParam: Message identifier
            lParam: Pointer to hook structure

        Returns:
            Result of CallNextHookEx
        """
        raise NotImplementedError("Subclasses must implement _hook_callback")
