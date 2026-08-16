"""
Phase 2: LAN remote control between two KeyMiglic instances (see SPEC.md §2).

CapsLock's native OS toggle/lamp is reused as-is as the arm/disarm switch
for remote control - never intercepted itself, only polled (see
core.input.get_capslock_toggle_state). While armed, every other physical
key press/release on this machine is captured (via MainWindow's shared
keyboard hook, see below), suppressed locally so it never reaches this
machine's own apps/hotkeys, and forwarded to the peer, which replays it
via SendInput exactly like ScriptExecutor replays a macro step - to the
peer's own OS this is indistinguishable from someone physically at that
keyboard, which is what lets a forwarded hotkey combo trigger the peer's
own HotkeyManager with no separate "run script" protocol message needed
(HotkeyManager, unlike Recorder, does not filter out SendInput-injected
events).

This class must be a QObject (not just own one) so that Qt can auto-queue
signal deliveries from PeerConnection's background socket threads onto the
GUI thread that constructs it - the same reason Recorder's control_hotkey
signal is safe to connect straight to a ThreadPanel method.

peer.send() is safe to call directly from the hook callback (or any other
thread) - it only ever enqueues, see peer_connection.py's module
docstring. WH_KEYBOARD_LL callbacks run under a hard OS-enforced timeout
(and always on the hook's own dedicated thread, see BaseHook), and
Windows will silently start ignoring/unhooking a hook procedure that
doesn't return fast, exactly the "never do I/O here" rule already called
out in base_hook.py - actual socket I/O for every message this class
sends (arm/disarm/key/script_status) happens on PeerConnection's own
dedicated sender thread, never here.

This class does not own a keyboard hook itself - MainWindow owns a single
shared one for the whole app and calls _on_keyboard_event() directly
whenever this manager is armed, so there's only ever one low-level
keyboard hook installed at a time instead of a separate one per feature
(see MainWindow._on_shared_keyboard_event). Multiple simultaneous
low-level hooks on the same machine were found to interfere with each
other and broke global hotkeys - see git history.
"""

from PySide6.QtCore import QObject, Signal, QTimer

from ..core.constants import SCAN_CODES, SCAN_TO_CODE, SCAN_TO_CODE_EXT, IS_WINDOWS
from ..core.input import get_capslock_toggle_state, tap_capslock, send_key_down, send_key_up

WM_KEYDOWN = 0x0100
WM_KEYUP = 0x0101
WM_SYSKEYDOWN = 0x0104
WM_SYSKEYUP = 0x0105

# LLKHF_INJECTED | LLKHF_LOWER_IL_INJECTED - same as Recorder's mask (see
# managers/recorder.py). Without this, a local macro running on this same
# machine (nothing prevents ScriptExecutor and armed remote control from
# being active at once - ThreadPanel.is_locked() never checks .armed) would
# have its own SendInput-injected keys picked up here as if they were real
# physical presses: suppressed from reaching this machine's own target
# window, and forwarded to the peer as if the user typed them there.
LLKHF_INJECTED_MASK = 0x10 | 0x02

CAPSLOCK_POLL_MS = 50


class RemoteControlManager(QObject):
    """Owns the CapsLock-armed capture/forward state machine for one peer connection."""

    armed_changed = Signal(bool)             # this machine is now controlling the peer (or stopped)
    being_controlled_changed = Signal(bool)  # this machine is now being controlled by the peer (or stopped)
    peer_script_status_changed = Signal(bool)  # the peer's own macro just started/stopped
    capslock_state_changed = Signal(bool)    # real CapsLock lamp state, for the UI indicator button

    def __init__(self, peer, parent=None):
        super().__init__(parent)
        self.peer = peer
        self.armed = False
        self.being_controlled = False
        self._last_capslock_state = False
        self._poll_timer = None

        self.peer.disconnected.connect(self._on_peer_disconnected)
        self.peer.message.connect(self._on_peer_message)

    def start(self):
        if not IS_WINDOWS:
            return
        self._last_capslock_state = get_capslock_toggle_state()
        self.capslock_state_changed.emit(self._last_capslock_state)
        self._poll_timer = QTimer(self)
        self._poll_timer.timeout.connect(self._poll_capslock)
        self._poll_timer.start(CAPSLOCK_POLL_MS)

    def stop(self):
        if self._poll_timer is not None:
            self._poll_timer.stop()
            self._poll_timer = None
        # Restore the lamp *before* clearing the flag, not after - app
        # shutdown (MainWindow.closeEvent) calls this before peer.disconnect(),
        # whose own disarm-on-disconnect path (_on_peer_disconnected) checks
        # self.armed and would otherwise find it already False and skip
        # tap_capslock(), leaving CapsLock lit after the process exits.
        if self.armed:
            tap_capslock()
        self.armed = False
        self.being_controlled = False

    def notify_script_status(self, running: bool):
        """Called by ThreadPanel on every local start/stop, broadcast to the peer if connected."""
        if self.peer.is_connected():
            self.peer.send({"type": "script_status", "running": running})

    def disarm_for_recording(self):
        """
        Called by ThreadPanel right before a local recording starts. Can't
        do both at once - the shared keyboard hook always favors an active
        Recorder over armed remote control (see MainWindow's
        _on_shared_keyboard_event), which would otherwise leave this
        machine silently "armed but not actually forwarding anything" for
        the whole recording, with the peer still believing it's being
        controlled. Disarming outright (lamp off, peer notified) instead of
        just letting it silently stall keeps the state honest.
        """
        if self.armed:
            self._do_disarm(notify_peer=True)
            tap_capslock()

    # -- CapsLock polling ---------------------------------------------------

    def _poll_capslock(self):
        self._check_capslock_transition()

    def _check_capslock_transition(self):
        """
        Shared by the GUI-thread poll timer and (while armed - see
        _on_keyboard_event) the hook thread's own direct check on every
        observed CapsLock keydown. The direct hook-thread check exists
        because the poll timer alone was found unreliable while a lot of
        other keys were actively being forwarded at once: the lamp would
        toggle off (real OS state) but this class's own bookkeeping could
        miss/lag the transition, leaving forwarding stuck on until the
        *other* machine's CapsLock was pressed instead. GetKeyState itself
        is a cheap, fast call - safe to do directly on the hook thread,
        same as HotkeyManager already does for its modifier-key checks.
        """
        state = get_capslock_toggle_state()
        if state == self._last_capslock_state:
            return
        self._last_capslock_state = state
        self.capslock_state_changed.emit(state)
        if state:
            self._try_arm()
        elif self.armed:
            self._do_disarm(notify_peer=True)

    def _try_arm(self):
        if not self.peer.is_connected():
            return  # CapsLock behaves as a normal OS toggle without an active connection
        self.armed = True
        # armed and being_controlled are mutually exclusive - taking control
        # back (the peer had been controlling this machine) must clear the
        # stale flag now, or it lingers after a later _do_disarm() and shows
        # this machine's UI as "being controlled" when nobody controls it.
        if self.being_controlled:
            self.being_controlled = False
            self.being_controlled_changed.emit(False)
        self.peer.send({"type": "arm"})
        self.armed_changed.emit(True)

    def _do_disarm(self, notify_peer: bool):
        self.armed = False
        if notify_peer and self.peer.is_connected():
            self.peer.send({"type": "disarm"})
        self.armed_changed.emit(False)

    # -- key capture (called by MainWindow's shared hook while armed) --------

    def _on_keyboard_event(self, nCode, wParam, kb_struct):
        if not self.armed:
            return False
        if wParam not in (WM_KEYDOWN, WM_KEYUP, WM_SYSKEYDOWN, WM_SYSKEYUP):
            return False
        if kb_struct.flags & LLKHF_INJECTED_MASK:
            return False  # a local macro's own SendInput, not the real user - never forward or suppress it

        extended = (kb_struct.flags & 0x1) != 0
        code = (SCAN_TO_CODE_EXT if extended else SCAN_TO_CODE).get(kb_struct.scanCode)
        if not code:
            return False
        if code == "caps":
            # Never intercepted - its own OS toggle/lamp keeps working as-is.
            # Check the transition right here too (not just via the poll
            # timer) - see _check_capslock_transition's docstring.
            if wParam in (WM_KEYDOWN, WM_SYSKEYDOWN):
                self._check_capslock_transition()
            return False

        is_down = wParam in (WM_KEYDOWN, WM_SYSKEYDOWN)
        self.peer.send({"type": "key", "key": code, "down": is_down})
        return True  # suppress locally - this machine's keyboard is "at the peer" right now

    # -- peer connection lifecycle --------------------------------------------

    def _on_peer_disconnected(self):
        # Can't forward to nowhere - drop out of either role and restore
        # this machine's own keyboard immediately rather than leaving it
        # "stuck" mid-remote-control.
        if self.armed:
            self._do_disarm(notify_peer=False)
            tap_capslock()  # turn the lamp back off to match
        if self.being_controlled:
            self.being_controlled = False
            self.being_controlled_changed.emit(False)

    def _on_peer_message(self, msg: dict):
        msg_type = msg.get("type")
        if msg_type == "arm":
            # Mutual exclusion: whoever armed last wins - if we were already
            # controlling the peer ourselves, back off automatically instead
            # of both sides fighting over the same keyboard.
            if self.armed:
                self._do_disarm(notify_peer=False)
                tap_capslock()
            self.being_controlled = True
            self.being_controlled_changed.emit(True)
        elif msg_type == "disarm":
            self.being_controlled = False
            self.being_controlled_changed.emit(False)
        elif msg_type == "key":
            code = msg.get("key")
            if code not in SCAN_CODES:
                return
            scan_code, extended = SCAN_CODES[code]
            if msg.get("down"):
                send_key_down(scan_code, extended)
            else:
                send_key_up(scan_code, extended)
        elif msg_type == "script_status":
            self.peer_script_status_changed.emit(bool(msg.get("running")))
