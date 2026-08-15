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
    send_key_down, send_key_up, send_mouse_move_absolute, send_mouse_move_relative,
    send_mouse_button_down, send_mouse_button_up,
)

# A recorded "move"/"move_rel" point is a single sample taken at record
# time; played back naively (sleep, then one instant SendInput jump/delta)
# it looks like a teleport rather than the smooth motion that was actually
# made - which reads as jerky/flicky rather than one continuous hold+drag,
# especially for a fast-moving in-game camera. _glide_to/_glide_relative
# fix this by splitting the movement into small steps. A long gap between
# two points only glides for the final MOUSE_GLIDE_MAX_DURATION_S seconds
# (waiting out the rest stationary first) - the mouse more likely was
# genuinely still for most of a long gap and then moved, so gliding across
# the *entire* gap would invent slow drift that never happened; but the
# arrival should still ease in rather than snap instantly.
MOUSE_INTERPOLATION_STEP_S = 0.015
MOUSE_GLIDE_MAX_DURATION_S = 0.2


class ExecutorSignals(QObject):
    """Qt signals used to report execution progress back to the GUI thread."""

    block_started = Signal(str)   # block id
    block_finished = Signal(str)  # block id
    log = Signal(str)             # message
    pass_finished = Signal()      # one full pass through the track's blocks completed
    stopped = Signal()            # emitted once, when the thread is fully done


class ScriptExecutor(threading.Thread):
    """Runs one track's blocks in a background thread, reporting via Qt signals."""

    def __init__(self, blocks, loop: bool = True, label: str = "Macro",
                 sync_barrier: threading.Barrier = None):
        super().__init__(daemon=True)
        self.blocks = blocks
        self.loop = loop
        self.label = label
        self.sync_barrier = sync_barrier
        self.signals = ExecutorSignals()

        self._stop_event = threading.Event()
        self._held_keys = set()
        self._held_mouse_buttons = set()

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
            self._release_all_held_mouse_buttons()
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
                else:
                    self._log(f"Unknown block kind: {block.kind}")
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
        last_pos = None
        for point in points:
            if self._stop_event.is_set():
                return
            if point.kind == "move":
                if point.dt and last_pos is not None:
                    if not self._glide_to(last_pos, (point.x, point.y), point.dt):
                        return
                else:
                    if point.dt:
                        self._sleep(point.dt)
                        if self._stop_event.is_set():
                            return
                    send_mouse_move_absolute(point.x, point.y)
                last_pos = (point.x, point.y)
            elif point.kind == "move_rel":
                if not self._glide_relative(point.x, point.y, point.dt):
                    return
                # The absolute position is no longer known - a raw-input
                # game likely moved its own aim/camera state without moving
                # the (possibly hidden/confined) OS cursor by the same
                # amount, so a later "move" point can't glide FROM here,
                # only teleport TO its own absolute target.
                last_pos = None
            else:
                if point.dt:
                    self._sleep(point.dt)
                    if self._stop_event.is_set():
                        return
                if point.kind == "left_down":
                    self._mouse_down("left")
                elif point.kind == "left_up":
                    self._mouse_up("left")
                elif point.kind == "right_down":
                    self._mouse_down("right")
                elif point.kind == "right_up":
                    self._mouse_up("right")
                else:
                    self._log(f"Unknown mouse point kind: {point.kind}")

    def _glide_to(self, start, end, duration):
        """
        Move the cursor from `start` to `end`, arriving `duration` seconds
        from now, via a series of small absolute steps instead of one
        instant jump. A long duration only glides for the final
        MOUSE_GLIDE_MAX_DURATION_S seconds (waiting out the rest first,
        stationary) - a real pause-then-flick shouldn't be smoothed into
        slow drift across the whole pause, but the arrival should still
        ease in rather than snap instantly. Returns False if stopped
        mid-glide (caller should bail out immediately).
        """
        glide_duration = min(duration, MOUSE_GLIDE_MAX_DURATION_S)
        wait_before = duration - glide_duration
        if wait_before > 0:
            self._sleep(wait_before)
            if self._stop_event.is_set():
                return False

        steps = max(1, round(glide_duration / MOUSE_INTERPOLATION_STEP_S))
        sx, sy = start
        ex, ey = end
        per_step = glide_duration / steps
        for i in range(1, steps + 1):
            self._sleep(per_step)
            if self._stop_event.is_set():
                return False
            t = i / steps
            send_mouse_move_absolute(round(sx + (ex - sx) * t), round(sy + (ey - sy) * t))
        return True

    def _glide_relative(self, dx, dy, duration):
        """
        Like _glide_to, but for a point recorded as a relative delta (see
        Recorder / MousePathPoint - movement while a mouse button is held is
        captured as deltas rather than absolute positions, since many games
        read raw relative mouse input for camera look/aim while a button is
        held). Splits the delta into small relative steps, carrying the
        rounding remainder forward so the total sent still equals exactly
        (dx, dy) even though each individual step is rounded to whole
        pixels. Returns False if stopped mid-glide.
        """
        if not duration:
            send_mouse_move_relative(dx, dy)
            return True

        glide_duration = min(duration, MOUSE_GLIDE_MAX_DURATION_S)
        wait_before = duration - glide_duration
        if wait_before > 0:
            self._sleep(wait_before)
            if self._stop_event.is_set():
                return False

        steps = max(1, round(glide_duration / MOUSE_INTERPOLATION_STEP_S))
        per_step = glide_duration / steps
        sent_x = sent_y = 0
        for i in range(1, steps + 1):
            self._sleep(per_step)
            if self._stop_event.is_set():
                return False
            target_x = round(dx * i / steps)
            target_y = round(dy * i / steps)
            send_mouse_move_relative(target_x - sent_x, target_y - sent_y)
            sent_x, sent_y = target_x, target_y
        return True

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
        self._held_mouse_buttons.add(button)

    def _mouse_up(self, button):
        send_mouse_button_up(button)
        self._held_mouse_buttons.discard(button)

    def _release_all_held_mouse_buttons(self):
        # Mirrors _release_all_held_keys - Stop can land between a mouse
        # path's *_down and *_up points (e.g. a click-and-drag gesture),
        # which would otherwise leave a mouse button physically stuck down
        # system-wide until the user manually clicks again.
        for button in list(self._held_mouse_buttons):
            self._mouse_up(button)

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
        """Interruptible sleep, with optional per-step +/- random variation (checked every 50ms)."""
        duration = float(duration)
        if max_variation:
            duration = max(0.0, duration + random.uniform(-max_variation, max_variation))

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
