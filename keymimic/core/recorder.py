"""
Keyboard input recorder using Windows hooks.
"""

import time
from datetime import datetime
from .constants import IS_WINDOWS, SCAN_TO_CODE, SCAN_TO_CODE_EXT
from .key_names import get_key_display_name

if IS_WINDOWS:
    import ctypes
    from ctypes import wintypes


class KeyRecorder:
    """Records keyboard input and generates macro code."""

    def __init__(self):
        self.recording = False
        self.last_time = None
        self.recorded_events = []
        self.hook_id = None
        self.hook_proc = None

    def start(self):
        """Start recording keyboard input."""
        if not IS_WINDOWS:
            return

        self.recording = True
        self.last_time = time.time()
        self.recorded_events = []

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

    def stop(self):
        """Stop recording and return generated macro."""
        self.recording = False
        if self.hook_id and IS_WINDOWS:
            ctypes.windll.user32.UnhookWindowsHookEx(self.hook_id)
            self.hook_id = None
        return self._generate_macro()

    def _hook_callback(self, nCode, wParam, lParam):
        """Low-level keyboard hook callback."""
        WM_KEYDOWN = 0x0100
        WM_KEYUP = 0x0101
        WM_SYSKEYDOWN = 0x0104
        WM_SYSKEYUP = 0x0105

        if nCode >= 0 and self.recording:
            kb_struct = ctypes.cast(lParam, ctypes.POINTER(wintypes.DWORD * 5)).contents
            scan_code = kb_struct[0] & 0xFF
            extended = (kb_struct[1] >> 24) & 0x1

            # Find our code
            if extended:
                code = SCAN_TO_CODE_EXT.get(scan_code)
            else:
                code = SCAN_TO_CODE.get(scan_code)

            if code:
                current_time = time.time()
                if self.last_time:
                    sleep_time = current_time - self.last_time
                    if sleep_time > 0.01:  # Ignore very small delays
                        self.recorded_events.append(('sleep', [round(sleep_time, 2)]))

                if wParam in (WM_KEYDOWN, WM_SYSKEYDOWN):
                    self.recorded_events.append(('press', [code]))
                elif wParam in (WM_KEYUP, WM_SYSKEYUP):
                    self.recorded_events.append(('release', [code]))

                self.last_time = current_time

        return ctypes.windll.user32.CallNextHookEx(None, nCode, wParam, lParam)

    def _generate_macro(self):
        """Convert recorded events to macro text (new simplified syntax with symbolic names)."""
        lines = [
            "# Recorded macro",
            f"# Created: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            ""
        ]

        for cmd, args in self.recorded_events:
            # Convert numeric codes to symbolic names where possible
            formatted_args = []
            for arg in args:
                if cmd in ('press', 'release') and isinstance(arg, int):
                    # Try to get symbolic name (e.g., 17 -> 'w')
                    key_name = get_key_display_name(arg)
                    formatted_args.append(key_name if key_name else str(arg))
                else:
                    formatted_args.append(str(arg))

            # New syntax: space-separated, no parentheses
            args_str = " ".join(formatted_args)
            lines.append(f"{cmd} {args_str}")

        return "\n".join(lines)


# Stub for non-Windows platforms
if not IS_WINDOWS:
    class KeyRecorder:
        def __init__(self):
            pass

        def start(self):
            pass

        def stop(self):
            return "# Recording not supported on this platform"
