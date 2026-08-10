"""
Records keyboard and mouse input and turns it into a list of Blocks.

Design (per spec): every discrete action (press/release/click/right_click)
becomes its own block - no automatic grouping of "simultaneous" key holds,
the user merges related blocks manually afterwards with the editor's Merge
tool. Mouse movement is the one exception: a run of consecutive move samples
is folded into a single "mouse_path" block (not one block per sample) so
recording a gesture doesn't flood the block list, while still keeping every
sampled point for accurate, smooth playback.
"""

import time

from ..core.hooks import KeyboardHook, MouseHook
from ..core.constants import SCAN_TO_CODE, SCAN_TO_CODE_EXT, IS_WINDOWS
from ..core.input import get_mouse_position
from ..model import Block, Step, MousePathPoint

WM_KEYDOWN = 0x0100
WM_KEYUP = 0x0101
WM_SYSKEYDOWN = 0x0104
WM_SYSKEYUP = 0x0105

WM_MOUSEMOVE = 0x0200
WM_LBUTTONDOWN = 0x0201
WM_RBUTTONDOWN = 0x0204

MOUSE_SAMPLE_INTERVAL = 0.02  # seconds between recorded mouse samples
MOUSE_MOVE_THRESHOLD = 5      # minimum pixels to record a new sample
MIN_RECORDED_GAP = 0.01       # ignore gaps smaller than this (event-loop noise)


class Recorder:
    """Records keyboard (and optionally mouse) input using composition over the hooks."""

    def __init__(self, record_mouse: bool = False):
        self.record_mouse = record_mouse
        self.recording = False
        self.events = []  # list of (name, args) tuples, chronological
        self.last_time = None

        self.keyboard_hook = None
        self.mouse_hook = None

        self._last_mouse_pos = None
        self._last_mouse_sample_time = None
        self.start_mouse_pos = None

    def start(self, record_mouse=None):
        if not IS_WINDOWS:
            return
        if record_mouse is not None:
            self.record_mouse = record_mouse

        self.recording = True
        self.events = []
        self.last_time = time.time()
        self._last_mouse_pos = None
        self._last_mouse_sample_time = None
        self.start_mouse_pos = get_mouse_position()

        self.keyboard_hook = KeyboardHook(self._on_keyboard_event)
        self.keyboard_hook.start()

        if self.record_mouse:
            self.mouse_hook = MouseHook(self._on_mouse_event)
            self.mouse_hook.start()

    def stop(self):
        """Stop recording and return the recorded script as a list of Blocks."""
        self.recording = False

        if self.keyboard_hook:
            self.keyboard_hook.stop()
            self.keyboard_hook = None
        if self.mouse_hook:
            self.mouse_hook.stop()
            self.mouse_hook = None

        return self._build_blocks()

    # -- hook callbacks -----------------------------------------------------

    def _record_gap(self):
        current_time = time.time()
        if self.last_time:
            gap = current_time - self.last_time
            if gap > MIN_RECORDED_GAP:
                self.events.append(("sleep", [round(gap, 3)]))
        self.last_time = current_time

    def _on_keyboard_event(self, nCode, wParam, kb_struct):
        if not self.recording:
            return
        if wParam not in (WM_KEYDOWN, WM_KEYUP, WM_SYSKEYDOWN, WM_SYSKEYUP):
            return

        extended = (kb_struct.flags & 0x1) != 0
        code = (SCAN_TO_CODE_EXT if extended else SCAN_TO_CODE).get(kb_struct.scanCode)
        if not code:
            return

        self._record_gap()
        if wParam in (WM_KEYDOWN, WM_SYSKEYDOWN):
            self.events.append(("press", [code]))
        else:
            self.events.append(("release", [code]))

    def _on_mouse_event(self, nCode, wParam, mouse_struct):
        if not self.recording:
            return
        current_pos = (mouse_struct.pt.x, mouse_struct.pt.y)

        if wParam == WM_LBUTTONDOWN:
            self._record_gap()
            self.events.append(("click", []))
            return

        if wParam == WM_RBUTTONDOWN:
            self._record_gap()
            self.events.append(("right_click", []))
            return

        if wParam == WM_MOUSEMOVE:
            now = time.time()
            if (self._last_mouse_sample_time is not None and
                    now - self._last_mouse_sample_time < MOUSE_SAMPLE_INTERVAL):
                return

            if self._last_mouse_pos is not None:
                dx = current_pos[0] - self._last_mouse_pos[0]
                dy = current_pos[1] - self._last_mouse_pos[1]
                if (dx * dx + dy * dy) ** 0.5 >= MOUSE_MOVE_THRESHOLD:
                    self._record_gap()
                    self.events.append(("move", [dx, dy]))
                    self._last_mouse_pos = current_pos
                    self._last_mouse_sample_time = now
            else:
                self._last_mouse_pos = current_pos
                self._last_mouse_sample_time = now

    # -- post-processing: raw events -> Blocks -------------------------------

    def _dedupe_key_repeat(self, events):
        """Drop OS auto-repeat WM_KEYDOWN spam for keys that are already held."""
        held = set()
        result = []
        for name, args in events:
            if name == "press":
                code = args[0]
                if code in held:
                    continue
                held.add(code)
            elif name == "release":
                held.discard(args[0])
            result.append((name, args))
        return result

    def _build_blocks(self):
        blocks = []

        if self.record_mouse and self.start_mouse_pos:
            sx, sy = self.start_mouse_pos
            start_block = Block.new_block([Step(type="move_to", x=sx, y=sy)])
            start_block.label = "Return to starting position"
            blocks.append(start_block)

        events = self._dedupe_key_repeat(self.events)

        pending_delay = 0.0
        path_points = None  # list[MousePathPoint] while a path run is open, else None

        def flush_path():
            nonlocal path_points
            if path_points:
                blocks.append(Block.new_mouse_path(path_points))
            path_points = None

        for name, args in events:
            if name == "sleep":
                pending_delay += args[0]
                continue

            if name == "move":
                if path_points is None:
                    path_points = []
                dx, dy = args
                path_points.append(MousePathPoint(dx, dy, round(pending_delay, 3)))
                pending_delay = 0.0
                continue

            flush_path()
            steps = []
            if pending_delay > MIN_RECORDED_GAP:
                steps.append(Step(type="sleep", duration=round(pending_delay, 2)))
            pending_delay = 0.0

            if name in ("press", "release"):
                steps.append(Step(type=name, key=args[0]))
            elif name in ("click", "right_click"):
                steps.append(Step(type=name))

            blocks.append(Block.new_block(steps))

        flush_path()

        if not blocks:
            blocks.append(Block.new_block())

        return blocks
