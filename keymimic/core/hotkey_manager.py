"""
Global hotkey manager using Windows low-level keyboard hooks.
Allows hotkeys to work even when the application is not focused.
"""

import queue
import threading
from .constants import IS_WINDOWS, SCAN_TO_CODE, SCAN_TO_CODE_EXT

if IS_WINDOWS:
    import ctypes
    from ctypes import wintypes


class HotkeyManager:
    """Global hotkey listener using Windows hooks."""

    def __init__(self):
        self.hotkey_map = {}  # {scan_code: action_name}
        self.hook_id = None
        self.hook_proc = None
        self.event_queue = queue.Queue()  # Thread-safe communication
        self._running = False
        self._hook_thread = None

    def register(self, key_code, action):
        """
        Register a global hotkey.

        Args:
            key_code: Scan code integer (e.g., 88 for F12)
            action: Action name (e.g., "record", "start", "stop")
        """
        self.hotkey_map[key_code] = action

    def unregister(self, key_code):
        """
        Remove hotkey registration.

        Args:
            key_code: Scan code integer
        """
        if key_code in self.hotkey_map:
            del self.hotkey_map[key_code]

    def start(self):
        """Start listening for global hotkeys."""
        if not IS_WINDOWS:
            return

        if self._running:
            return

        self._running = True

        # Start hook in separate thread
        self._hook_thread = threading.Thread(target=self._run_hook, daemon=True)
        self._hook_thread.start()

    def stop(self):
        """Stop listening and cleanup hook."""
        self._running = False
        if self.hook_id and IS_WINDOWS:
            ctypes.windll.user32.UnhookWindowsHookEx(self.hook_id)
            self.hook_id = None

    def _run_hook(self):
        """Run the keyboard hook (must be in dedicated thread)."""
        if not IS_WINDOWS:
            return

        # Set low-level keyboard hook
        CMPFUNC = ctypes.CFUNCTYPE(ctypes.c_long, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM)
        self.hook_proc = CMPFUNC(self._hook_callback)

        WH_KEYBOARD_LL = 13
        kernel32 = ctypes.windll.kernel32
        self.hook_id = ctypes.windll.user32.SetWindowsHookExA(
            WH_KEYBOARD_LL,
            self.hook_proc,
            kernel32.GetModuleHandleW(None),
            0
        )

        # Message loop (required for hook to work)
        msg = wintypes.MSG()
        while self._running:
            result = ctypes.windll.user32.GetMessageW(ctypes.byref(msg), None, 0, 0)
            if result <= 0:
                break
            ctypes.windll.user32.TranslateMessage(ctypes.byref(msg))
            ctypes.windll.user32.DispatchMessageW(ctypes.byref(msg))

    def _hook_callback(self, nCode, wParam, lParam):
        """Low-level keyboard hook callback."""
        WM_KEYDOWN = 0x0100
        WM_SYSKEYDOWN = 0x0104

        if nCode >= 0 and self._running:
            # Extract scan code from lParam
            kb_struct = ctypes.cast(lParam, ctypes.POINTER(wintypes.DWORD * 5)).contents
            scan_code = kb_struct[0] & 0xFF
            extended = (kb_struct[1] >> 24) & 0x1

            # Find our code
            if extended:
                code = SCAN_TO_CODE_EXT.get(scan_code)
            else:
                code = SCAN_TO_CODE.get(scan_code)

            # Check if this key is registered as a hotkey (only on key down)
            if code and wParam in (WM_KEYDOWN, WM_SYSKEYDOWN):
                if code in self.hotkey_map:
                    action = self.hotkey_map[code]
                    # Put event in queue for main thread to process
                    self.event_queue.put((action, None))

        return ctypes.windll.user32.CallNextHookEx(None, nCode, wParam, lParam)


# Stub for non-Windows platforms
if not IS_WINDOWS:
    class HotkeyManager:
        def __init__(self):
            self.event_queue = queue.Queue()

        def register(self, key_code, action):
            pass

        def unregister(self, key_code):
            pass

        def start(self):
            pass

        def stop(self):
            pass
