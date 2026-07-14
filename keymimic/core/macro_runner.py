"""
Macro execution thread with support for symbolic key names.
"""

import threading
import time
import random
from .constants import SCAN_CODES
from .input_sender import key_down, key_up, mouse_click, mouse_move
from .key_names import resolve_key


class MacroRunner(threading.Thread):
    """Thread for executing macro commands."""

    def __init__(self, label, commands, humanize, log_callback, loop=True):
        super().__init__(daemon=True)
        self.label = label
        self.commands = commands
        self.humanize = humanize
        self.log_callback = log_callback
        self.loop = loop
        self._stop_event = threading.Event()
        self._held_keys = set()

    def stop(self):
        """Stop macro execution."""
        self._stop_event.set()

    def _log(self, msg):
        """Send log message."""
        if self.log_callback:
            self.log_callback(f"[{self.label}] {msg}")

    def _sleep(self, seconds, max_variation=None):
        """Sleep with optional humanization."""
        seconds = float(seconds)
        if self.humanize > 0:
            variation = seconds * (self.humanize / 100.0)
            if max_variation is not None:
                variation = min(variation, float(max_variation))
            seconds = max(0.0, seconds + random.uniform(-variation, variation))

        end = time.time() + seconds
        while True:
            remaining = end - time.time()
            if remaining <= 0 or self._stop_event.is_set():
                return
            time.sleep(min(0.05, remaining))

    def _press(self, code):
        """Press a key (supports both numeric codes and key names like 's', 'ctrl')."""
        try:
            code = resolve_key(code)
        except ValueError as e:
            self._log(f"Unknown key: {e}")
            return

        entry = SCAN_CODES.get(code)
        if entry is None:
            self._log(f"Unknown key code: {code}")
            return
        scan, ext = entry
        key_down(scan, ext)
        self._held_keys.add(code)

    def _release(self, code):
        """Release a key (supports both numeric codes and key names)."""
        try:
            code = resolve_key(code)
        except ValueError:
            return

        entry = SCAN_CODES.get(code)
        if entry is None:
            return
        scan, ext = entry
        key_up(scan, ext)
        self._held_keys.discard(code)

    def _tap(self, code):
        """Tap a key (press and release)."""
        self._press(code)
        time.sleep(0.05)
        self._release(code)

    def _release_all_held(self):
        """Release all currently held keys."""
        for code in list(self._held_keys):
            self._release(code)

    def _wait_with_keys(self, args):
        """Wait while periodically tapping specified keys."""
        if not args:
            return
        total = float(args[0])
        taps = []
        i = 1
        while i + 1 < len(args):
            code = resolve_key(args[i])
            interval = float(args[i + 1])
            taps.append([code, interval, interval])
            i += 2

        start = time.time()
        while True:
            elapsed = time.time() - start
            if elapsed >= total or self._stop_event.is_set():
                return
            for t in taps:
                if elapsed >= t[2]:
                    self._tap(t[0])
                    t[2] += t[1]
            time.sleep(0.05)

    def run(self):
        """Execute macro commands."""
        self._log("Macro started")
        try:
            while not self._stop_event.is_set():
                for name, args in self.commands:
                    if self._stop_event.is_set():
                        break
                    try:
                        if name == "press":
                            self._press(args[0])
                        elif name == "release":
                            self._release(args[0])
                        elif name == "click":
                            mouse_click(right=False)
                        elif name == "right_click":
                            mouse_click(right=True)
                        elif name == "move":
                            mouse_move(args[0], args[1])
                        elif name == "sleep":
                            self._sleep(*args)
                        elif name == "log":
                            self._log(args[0] if args else "")
                        elif name == "wait_with_keys":
                            self._wait_with_keys(args)
                        else:
                            self._log(f"Unknown command: {name}()")
                    except Exception as exc:
                        self._log(f"Error in {name}(): {exc}")
                if not self.loop:
                    break
        finally:
            self._release_all_held()
            self._log("Macro stopped")
