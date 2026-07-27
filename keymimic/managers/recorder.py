"""
Recording manager using composition pattern.

Uses KeyboardHook and MouseHook for event capture, generates macro text.
"""

import time

from ..core.hooks import KeyboardHook, MouseHook
from ..core.constants import SCAN_TO_CODE, SCAN_TO_CODE_EXT, IS_WINDOWS
from ..core.key_names import get_key_display_name
from ..core.automation.input import get_mouse_position


# Windows message constants
WM_KEYDOWN = 0x0100
WM_KEYUP = 0x0101
WM_SYSKEYDOWN = 0x0104
WM_SYSKEYUP = 0x0105

WM_MOUSEMOVE = 0x0200
WM_LBUTTONDOWN = 0x0201
WM_LBUTTONUP = 0x0202
WM_RBUTTONDOWN = 0x0204
WM_RBUTTONUP = 0x0205


class Recorder:
    """
    Records keyboard and mouse input, generates macro text.

    Uses composition - owns KeyboardHook and MouseHook, doesn't inherit from them.
    """

    def __init__(self, record_mouse=False):
        """
        Initialize recorder.

        Args:
            record_mouse: Whether to record mouse events
        """
        self.record_mouse = record_mouse
        self.recording = False
        self.events = []
        self.last_time = None

        self.keyboard_hook = None
        self.mouse_hook = None

        # Mouse tracking for relative movements
        self.last_mouse_pos = None
        self.last_mouse_record_time = None
        self.mouse_sample_interval = 0.05  # Record mouse position every 50ms
        self.mouse_move_threshold = 10     # Minimum 10 pixels to record movement

        # Starting mouse position for playback return
        self.start_mouse_pos = None

    def start(self, record_mouse=None):
        """
        Start recording input.

        Args:
            record_mouse: Override mouse recording setting
        """
        if not IS_WINDOWS:
            return

        if record_mouse is not None:
            self.record_mouse = record_mouse

        # Reset state
        self.recording = True
        self.events = []
        self.last_time = time.time()
        self.last_mouse_pos = None
        self.last_mouse_record_time = None

        # Capture starting mouse position for return to origin
        self.start_mouse_pos = get_mouse_position()

        # Start keyboard hook
        self.keyboard_hook = KeyboardHook(self._on_keyboard_event)
        self.keyboard_hook.start()

        # Start mouse hook if enabled
        if self.record_mouse:
            self.mouse_hook = MouseHook(self._on_mouse_event)
            self.mouse_hook.start()

    def stop(self):
        """
        Stop recording and return generated macro.

        Returns:
            String containing macro text
        """
        self.recording = False

        # Stop hooks
        if self.keyboard_hook:
            self.keyboard_hook.stop()
            self.keyboard_hook = None

        if self.mouse_hook:
            self.mouse_hook.stop()
            self.mouse_hook = None

        return self._generate_macro()

    def _on_keyboard_event(self, nCode, wParam, kb_struct):
        """
        Callback from KeyboardHook.

        Args:
            nCode: Hook code
            wParam: Message identifier
            kb_struct: KBDLLHOOKSTRUCT instance
        """
        if not self.recording:
            return

        # Only process key down/up events
        if wParam not in (WM_KEYDOWN, WM_KEYUP, WM_SYSKEYDOWN, WM_SYSKEYUP):
            return

        # Extract scan code and extended flag
        scan_code = kb_struct.scanCode
        extended = (kb_struct.flags & 0x1) != 0

        # Resolve to internal code
        if extended:
            code = SCAN_TO_CODE_EXT.get(scan_code)
        else:
            code = SCAN_TO_CODE.get(scan_code)

        if not code:
            return

        # Record sleep time since last event
        current_time = time.time()
        if self.last_time:
            sleep_time = current_time - self.last_time
            if sleep_time > 0.01:  # Ignore very small delays
                self.events.append(('sleep', [round(sleep_time, 2)]))

        # Record key event
        if wParam in (WM_KEYDOWN, WM_SYSKEYDOWN):
            self.events.append(('press', [code]))
        elif wParam in (WM_KEYUP, WM_SYSKEYUP):
            self.events.append(('release', [code]))

        self.last_time = current_time

    def _on_mouse_event(self, nCode, wParam, mouse_struct):
        """
        Callback from MouseHook.

        Args:
            nCode: Hook code
            wParam: Message identifier
            mouse_struct: MSLLHOOKSTRUCT instance
        """
        if not self.recording:
            return

        current_time = time.time()
        current_pos = (mouse_struct.pt.x, mouse_struct.pt.y)

        # Record sleep time since last event
        if self.last_time:
            sleep_time = current_time - self.last_time
            if sleep_time > 0.01:
                self.events.append(('sleep', [round(sleep_time, 2)]))

        # Record mouse event
        if wParam == WM_LBUTTONDOWN:
            self.events.append(('click', []))
            self.last_time = current_time

        elif wParam == WM_RBUTTONDOWN:
            self.events.append(('right_click', []))
            self.last_time = current_time

        elif wParam == WM_MOUSEMOVE:
            # Sample mouse movements (not every single event)
            if self.last_mouse_record_time and (current_time - self.last_mouse_record_time < self.mouse_sample_interval):
                return  # Skip - too soon since last recording

            # If we have previous position, calculate relative movement
            if self.last_mouse_pos:
                dx = current_pos[0] - self.last_mouse_pos[0]
                dy = current_pos[1] - self.last_mouse_pos[1]

                # Only record if movement is significant
                distance = (dx*dx + dy*dy) ** 0.5
                if distance >= self.mouse_move_threshold:
                    self.events.append(('move', [dx, dy]))
                    self.last_mouse_pos = current_pos
                    self.last_mouse_record_time = current_time
                    self.last_time = current_time
            else:
                # First mouse event - just save position
                self.last_mouse_pos = current_pos
                self.last_mouse_record_time = current_time

    def _generate_macro(self):
        """
        Generate macro text from recorded events.

        Optimizes:
        1. Removes duplicate consecutive press events (Windows spam when key is held)
        2. Merges consecutive sleep events into one
        3. Merges consecutive move events into one (prevents mouse drift)
        4. Merges press + sleep + release into single press with duration

        Returns:
            String containing macro commands
        """
        if not self.events:
            return "# Empty macro\n"

        # Step 1: Remove duplicate consecutive presses
        # When a key is held, Windows generates: press, press, press, ..., release
        # We want: press, release (with accumulated sleep time in between)
        deduplicated = []
        i = 0

        while i < len(self.events):
            name, args = self.events[i]

            if name == 'press':
                key_code = args[0]

                # Skip all consecutive duplicate presses of the same key
                while (i + 1 < len(self.events) and
                       self.events[i + 1][0] == 'press' and
                       self.events[i + 1][1][0] == key_code):
                    i += 1  # Skip duplicate press

                # Add the single press
                deduplicated.append(('press', [key_code]))
                i += 1
            else:
                deduplicated.append((name, args))
                i += 1

        # Step 2: Merge consecutive sleep events
        merged_sleeps = []
        i = 0

        while i < len(deduplicated):
            name, args = deduplicated[i]

            if name == 'sleep':
                total_sleep = args[0]

                # Accumulate consecutive sleeps
                while (i + 1 < len(deduplicated) and
                       deduplicated[i + 1][0] == 'sleep'):
                    i += 1
                    total_sleep += deduplicated[i][1][0]

                merged_sleeps.append(('sleep', [round(total_sleep, 2)]))
                i += 1
            else:
                merged_sleeps.append((name, args))
                i += 1

        # Step 3: Merge consecutive move events
        merged_moves = []
        i = 0

        while i < len(merged_sleeps):
            name, args = merged_sleeps[i]

            if name == 'move':
                total_dx = args[0]
                total_dy = args[1]

                # Accumulate consecutive moves
                while (i + 1 < len(merged_sleeps) and
                       merged_sleeps[i + 1][0] == 'move'):
                    i += 1
                    total_dx += merged_sleeps[i][1][0]
                    total_dy += merged_sleeps[i][1][1]

                merged_moves.append(('move', [int(total_dx), int(total_dy)]))
                i += 1
            else:
                merged_moves.append((name, args))
                i += 1

        # Step 4: Merge press + sleep + release into press with duration
        optimized = []
        i = 0

        while i < len(merged_moves):
            name, args = merged_moves[i]

            # Look for pattern: press X, sleep Y, release X
            if (name == 'press' and
                i + 2 < len(merged_moves) and
                merged_moves[i + 1][0] == 'sleep' and
                merged_moves[i + 2][0] == 'release' and
                merged_moves[i + 2][1][0] == args[0]):

                # Merge into press with duration
                code = args[0]
                duration = merged_moves[i + 1][1][0]
                optimized.append(('press', [code, duration]))
                i += 3  # Skip sleep and release
            else:
                optimized.append((name, args))
                i += 1

        # Generate macro text
        lines = []

        # Add move_to command at the start to return to starting position
        if self.start_mouse_pos and self.record_mouse:
            start_x, start_y = self.start_mouse_pos
            lines.append(f"# Return to starting position")
            lines.append(f"move_to {start_x} {start_y}")
            lines.append("")  # Empty line for readability

        for name, args in optimized:
            if name == 'press':
                key_name = get_key_display_name(args[0])
                if len(args) == 1:
                    lines.append(f"press {key_name}")
                else:
                    duration = args[1]
                    lines.append(f"press {key_name} {duration}")

            elif name == 'release':
                key_name = get_key_display_name(args[0])
                lines.append(f"release {key_name}")

            elif name == 'sleep':
                lines.append(f"sleep {args[0]}")

            elif name == 'click':
                lines.append("click")

            elif name == 'right_click':
                lines.append("right_click")

            elif name == 'move':
                lines.append(f"move {args[0]} {args[1]}")

        return '\n'.join(lines) + '\n'
