"""
Executes one track (a flat list of Blocks) on a background thread.

A Script has two tracks - keyboard and mouse - each run by their own
ScriptExecutor, both started together so real recorded timing keeps them in
sync without any extra bookkeeping (see ThreadPanel.start()). Blocks within
one track are still strictly sequential - holding two keys "at once" is
expressed by ordering (press A, ..., press B, ..., release B, ..., release
A), not by real parallel threads *within* a track. Repeat blocks re-run
their children N times. Stop immediately releases every currently-held key
(checked every 50ms during any sleep, so it is effectively instant).

Looping: when `loop` is True, an executor runs one pass, emits
`pass_finished`, and - if given a shared `sync_barrier` - waits there for
the *other* track's executor to also finish its pass before starting the
next one, so both tracks always restart together rather than drifting.
"""

import random
import threading
import time

from PySide6.QtCore import QObject, Signal

from ..core.constants import SCAN_CODES
from ..core.key_names import resolve_key
from ..core.input import (
    send_key_down, send_key_up, send_mouse_move_absolute,
    send_mouse_button_down, send_mouse_button_up,
)


class ExecutorSignals(QObject):
    """Qt signals used to report execution progress back to the GUI thread."""

    block_started = Signal(str)   # block id
    block_finished = Signal(str)  # block id
    log = Signal(str)             # message
    pass_finished = Signal()      # one full pass through the track's blocks completed
    stopped = Signal()            # emitted once, when the thread is fully done


class ScriptExecutor(threading.Thread):
    """Runs one track's blocks in a background thread, reporting via Qt signals."""

    def __init__(self, blocks, humanize: int = 0, loop: bool = True, label: str = "Macro",
                 sync_barrier: threading.Barrier = None):
        super().__init__(daemon=True)
        self.blocks = blocks
        self.humanize = humanize
        self.loop = loop
        self.label = label
        self.sync_barrier = sync_barrier
        self.signals = ExecutorSignals()

        self._stop_event = threading.Event()
        self._held_keys = set()

    def stop(self):
        self._stop_event.set()
        if self.sync_barrier is not None:
            try:
                self.sync_barrier.abort()
            except threading.BrokenBarrierError:
                pass

    def _log(self, message: str):
        self.signals.log.emit(f"[{self.label}] {message}")

    # -- run loop -------------------------------------------------------------

    def run(self):
        self._log("Started")
        try:
            while not self._stop_event.is_set():
                self._run_blocks(self.blocks)
                if self._stop_event.is_set():
                    break
                self.signals.pass_finished.emit()
                if not self.loop:
                    break
                if self.sync_barrier is not None:
                    try:
                        self.sync_barrier.wait()
                    except threading.BrokenBarrierError:
                        break
        finally:
            self._release_all_held_keys()
            self._log("Stopped")
            self.signals.stopped.emit()

    def _run_blocks(self, blocks):
        for block in blocks:
            if self._stop_event.is_set():
                return
            if not block.enabled:
                continue

            self.signals.block_started.emit(block.id)
            try:
                if block.kind == "block":
                    self._run_steps(block.steps)
                elif block.kind == "repeat":
                    for _ in range(block.count):
                        if self._stop_event.is_set():
                            break
                        self._run_blocks(block.children)
                elif block.kind == "mouse_path":
                    self._run_mouse_path(block.points)
            finally:
                self.signals.block_finished.emit(block.id)

    def _run_steps(self, steps):
        for step in steps:
            if self._stop_event.is_set():
                return
            try:
                self._execute_step(step)
            except Exception as exc:
                self._log(f"Error in step '{step.type}': {exc}")

    def _run_mouse_path(self, points):
        for point in points:
            if self._stop_event.is_set():
                return
            if point.dt:
                self._sleep(point.dt)
                if self._stop_event.is_set():
                    return
            if point.kind == "move":
                send_mouse_move_absolute(point.x, point.y)
            elif point.kind == "left_down":
                self._mouse_down("left")
            elif point.kind == "left_up":
                self._mouse_up("left")
            elif point.kind == "right_down":
                self._mouse_down("right")
            elif point.kind == "right_up":
                self._mouse_up("right")
            else:
                self._log(f"Unknown mouse point kind: {point.kind}")

    # -- step execution ---------------------------------------------------

    def _execute_step(self, step):
        t = step.type
        if t == "press":
            self._press(step.key)
            if step.duration is not None:
                self._sleep(step.duration)
                self._release(step.key)
        elif t == "release":
            self._release(step.key)
        elif t == "sleep":
            self._sleep(step.duration, max_variation=step.variation)
        elif t == "log":
            self._log(step.message or "")
        elif t == "wait_with_keys":
            self._wait_with_keys(step.duration, step.taps or [])
        else:
            self._log(f"Unknown step type: {t}")

    def _mouse_down(self, button):
        result = send_mouse_button_down(button)
        if result == 0:
            self._log(
                f"WARNING: SendInput blocked for {button} mouse-down - the target window may be "
                f"running with higher privileges (try running KeyMimic as Administrator)"
            )

    def _mouse_up(self, button):
        send_mouse_button_up(button)

    def _press(self, key):
        try:
            code = resolve_key(key)
        except ValueError as exc:
            self._log(f"Unknown key: {exc}")
            return
        scan_code, extended = SCAN_CODES[code]
        result = send_key_down(scan_code, extended)
        if result == 0:
            self._log(f"WARNING: SendInput blocked for key {code}")
        self._held_keys.add(code)

    def _release(self, key):
        try:
            code = resolve_key(key)
        except ValueError:
            return
        scan_code, extended = SCAN_CODES[code]
        send_key_up(scan_code, extended)
        self._held_keys.discard(code)

    def _release_all_held_keys(self):
        for code in list(self._held_keys):
            self._release(code)

    def _sleep(self, duration, max_variation=None):
        """Interruptible sleep with optional humanize jitter (checked every 50ms)."""
        duration = float(duration)
        humanize = self.humanize or 0
        if humanize > 0:
            variation = duration * (humanize / 100.0)
            if max_variation is not None:
                variation = min(variation, float(max_variation))
            duration = max(0.0, duration + random.uniform(-variation, variation))

        end_time = time.time() + duration
        while time.time() < end_time:
            if self._stop_event.is_set():
                return
            remaining = end_time - time.time()
            time.sleep(min(0.05, max(0.0, remaining)))

    def _wait_with_keys(self, total_duration, taps):
        """Wait total_duration seconds, tapping each (key, interval) periodically."""
        schedule = []
        for tap in taps:
            try:
                code = resolve_key(tap["key"])
                interval = float(tap["interval"])
            except (ValueError, KeyError):
                continue
            schedule.append([code, interval, interval])  # [code, interval, next_due]

        start = time.time()
        while True:
            elapsed = time.time() - start
            if elapsed >= float(total_duration) or self._stop_event.is_set():
                return
            for entry in schedule:
                if elapsed >= entry[2]:
                    self._press(entry[0])
                    time.sleep(0.05)
                    self._release(entry[0])
                    entry[2] += entry[1]
            time.sleep(0.05)
