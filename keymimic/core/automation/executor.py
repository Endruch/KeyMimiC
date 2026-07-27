"""
Clean macro executor without patches.

Executes parsed macro commands with proper key management and humanization.
"""

import threading
import time
import random

from ..constants import SCAN_CODES
from ..key_names import resolve_key
from .input import send_key_down, send_key_up, send_mouse_move, send_mouse_click, send_mouse_move_absolute


class MacroExecutor(threading.Thread):
    """Executes macro commands in a separate thread."""

    def __init__(self, label, commands, loop=True, humanize=0, log_callback=None):
        """
        Initialize macro executor.

        Args:
            label: Display name for this macro
            commands: List of (command_name, args) tuples
            loop: Whether to loop the macro
            humanize: Percentage of timing variation (0-100)
            log_callback: Optional callback for log messages
        """
        super().__init__(daemon=True)
        self.label = label
        self.commands = commands
        self.loop = loop
        self.humanize = humanize
        self.log_callback = log_callback or (lambda msg: None)

        self._stop_event = threading.Event()
        self._held_keys = set()

    def stop(self):
        """Stop macro execution."""
        self._stop_event.set()

    def _log(self, message):
        """Send log message to callback."""
        self.log_callback(f"[{self.label}] {message}")

    def _sleep(self, duration, max_variation=None):
        """
        Sleep with optional humanization and early stop support.

        Args:
            duration: Base sleep time in seconds
            max_variation: Maximum variation (overrides humanize if smaller)
        """
        duration = float(duration)

        # Apply humanization
        if self.humanize > 0:
            variation = duration * (self.humanize / 100.0)
            if max_variation is not None:
                variation = min(variation, float(max_variation))
            duration = max(0.0, duration + random.uniform(-variation, variation))

        # Interruptible sleep (check every 50ms)
        end_time = time.time() + duration
        while time.time() < end_time:
            if self._stop_event.is_set():
                return
            remaining = end_time - time.time()
            time.sleep(min(0.05, max(0, remaining)))

    def _press(self, key):
        """
        Press a key down.

        Args:
            key: Key name (string) or code (int)
        """
        try:
            code = resolve_key(key)
        except ValueError as e:
            self._log(f"Unknown key: {e}")
            return

        entry = SCAN_CODES.get(code)
        if entry is None:
            self._log(f"Unknown key code: {code}")
            return

        scan_code, extended = entry
        result = send_key_down(scan_code, extended)

        if result == 0:
            self._log(f"WARNING: SendInput BLOCKED for key {code} (scan {scan_code:#x})")

        self._held_keys.add(code)

    def _release(self, key):
        """
        Release a key.

        Args:
            key: Key name (string) or code (int)
        """
        try:
            code = resolve_key(key)
        except ValueError:
            return

        entry = SCAN_CODES.get(code)
        if entry is None:
            return

        scan_code, extended = entry
        send_key_up(scan_code, extended)
        self._held_keys.discard(code)

    def _tap(self, key):
        """
        Tap a key (press and release).

        Args:
            key: Key name (string) or code (int)
        """
        self._press(key)
        time.sleep(0.05)
        self._release(key)

    def _release_all_held_keys(self):
        """Release all currently held keys."""
        for code in list(self._held_keys):
            self._release(code)

    def _wait_with_keys(self, args):
        """
        Wait while periodically tapping specified keys.

        Args:
            args: [total_duration, key1, interval1, key2, interval2, ...]

        Example:
            wait_with_keys 10 w 2 space 5
            # Wait 10 seconds, tapping 'w' every 2 seconds and 'space' every 5 seconds
        """
        if not args:
            return

        total_duration = float(args[0])
        taps = []

        # Parse key-interval pairs
        i = 1
        while i + 1 < len(args):
            try:
                key_code = resolve_key(args[i])
                interval = float(args[i + 1])
                taps.append([key_code, interval, interval])  # [code, interval, next_time]
            except (ValueError, IndexError):
                break
            i += 2

        # Execute taps
        start_time = time.time()
        while True:
            elapsed = time.time() - start_time

            if elapsed >= total_duration or self._stop_event.is_set():
                return

            # Check each tap
            for tap_info in taps:
                if elapsed >= tap_info[2]:
                    self._tap(tap_info[0])
                    tap_info[2] += tap_info[1]  # Schedule next tap

            time.sleep(0.05)

    def run(self):
        """Execute macro commands."""
        self._log("Macro started")

        try:
            while not self._stop_event.is_set():
                for command_name, args in self.commands:
                    if self._stop_event.is_set():
                        break

                    try:
                        self._execute_command(command_name, args)
                    except Exception as e:
                        self._log(f"Error in {command_name}(): {e}")

                if not self.loop:
                    break

        finally:
            self._release_all_held_keys()
            self._log("Macro stopped")

    def _execute_command(self, name, args):
        """
        Execute a single command.

        Args:
            name: Command name
            args: Command arguments
        """
        if name == 'press':
            # press key [duration]
            self._press(args[0])
            if len(args) > 1:
                # Hold for duration, then release
                duration = float(args[1])
                self._sleep(duration)
                self._release(args[0])

        elif name == 'release':
            # release key
            self._release(args[0])

        elif name == 'click':
            # click
            send_mouse_click(button='left')

        elif name == 'right_click':
            # right_click
            send_mouse_click(button='right')

        elif name == 'move':
            # move dx dy (relative)
            dx = int(args[0])
            dy = int(args[1])
            send_mouse_move(dx, dy)

        elif name == 'move_to':
            # move_to x y (absolute)
            x = int(args[0])
            y = int(args[1])
            send_mouse_move_absolute(x, y)

        elif name == 'sleep':
            # sleep duration [max_variation]
            self._sleep(*args)

        elif name == 'log':
            # log message
            self._log(args[0] if args else "")

        elif name == 'wait_with_keys':
            # wait_with_keys total_time key1 interval1 key2 interval2 ...
            self._wait_with_keys(args)

        else:
            self._log(f"Unknown command: {name}")
