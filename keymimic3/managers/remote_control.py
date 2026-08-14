"""
Phase 2: LAN remote control between two KeyMiglic instances (see SPEC.md §2).

CapsLock's native OS toggle/lamp is reused as-is as the arm/disarm switch
for remote control - never intercepted itself, only polled (see
core.input.get_capslock_toggle_state). While armed, every other physical
key press/release on this machine is captured by a dedicated keyboard hook
(suppressed locally, never reaches this machine's own apps/hotkeys) and
forwarded to the peer, which replays it via SendInput exactly like
ScriptExecutor replays a macro step - to the peer's own OS this is
indistinguishable from someone physically at that keyboard, which is what
lets a forwarded hotkey combo trigger the peer's own HotkeyManager with no
separate "run script" protocol message needed (HotkeyManager, unlike
Recorder, does not filter out SendInput-injected events).

This class must be a QObject (not just own one) so that Qt can auto-queue
signal deliveries from PeerConnection's background socket threads onto the
GUI thread that constructs it - the same reason Recorder's control_hotkey
signal is safe to connect straight to a ThreadPanel method.
"""

from PySide6.QtCore import QObject, Signal, QTimer

from ..core.hooks import KeyboardHook
from ..core.constants import SCAN_CODES, SCAN_TO_CODE, SCAN_TO_CODE_EXT, IS_WINDOWS
from ..core.input import get_capslock_toggle_state, tap_capslock, send_key_down, send_key_up

WM_KEYDOWN = 0x0100
WM_KEYUP = 0x0101
WM_SYSKEYDOWN = 0x0104
WM_SYSKEYUP = 0x0105

CAPSLOCK_POLL_MS = 50


class RemoteControlManager(QObject):
    """Owns the CapsLock-armed capture/forward state machine for one peer connection."""

    armed_changed = Signal(bool)             # this machine is now controlling the peer (or stopped)
    being_controlled_changed = Signal(bool)  # this machine is now being controlled by the peer (or stopped)
    peer_script_status_changed = Signal(bool)  # the peer's own macro just started/stopped

    def __init__(self, peer, parent=None):
        super().__init__(parent)
        self.peer = peer
        self.armed = False
        self.being_controlled = False
        self._last_capslock_state = False
        self._hook = None
        self._poll_timer = None

        self.peer.disconnected.connect(self._on_peer_disconnected)
        self.peer.message.connect(self._on_peer_message)

    def start(self):
        if not IS_WINDOWS:
            return
        self._last_capslock_state = get_capslock_toggle_state()
        self._hook = KeyboardHook(self._on_keyboard_event)
        self._hook.start()
        self._poll_timer = QTimer(self)
        self._poll_timer.timeout.connect(self._poll_capslock)
        self._poll_timer.start(CAPSLOCK_POLL_MS)

    def stop(self):
        if self._poll_timer is not None:
            self._poll_timer.stop()
            self._poll_timer = None
        if self._hook is not None:
            self._hook.stop()
            self._hook = None
        self.armed = False
        self.being_controlled = False

    def notify_script_status(self, running: bool):
        """Called by ThreadPanel on every local start/stop, broadcast to the peer if connected."""
        if self.peer.is_connected():
            self.peer.send({"type": "script_status", "running": running})

    # -- CapsLock polling ---------------------------------------------------

    def _poll_capslock(self):
        state = get_capslock_toggle_state()
        if state == self._last_capslock_state:
            return
        self._last_capslock_state = state
        if state:
            self._try_arm()
        elif self.armed:
            self._do_disarm(notify_peer=True)

    def _try_arm(self):
        if not self.peer.is_connected():
            return  # CapsLock behaves as a normal OS toggle without an active connection
        self.armed = True
        self.peer.send({"type": "arm"})
        self.armed_changed.emit(True)

    def _do_disarm(self, notify_peer: bool):
        self.armed = False
        if notify_peer and self.peer.is_connected():
            self.peer.send({"type": "disarm"})
        self.armed_changed.emit(False)

    # -- keyboard hook (active capture while armed) --------------------------

    def _on_keyboard_event(self, nCode, wParam, kb_struct):
        if not self.armed:
            return False
        if wParam not in (WM_KEYDOWN, WM_KEYUP, WM_SYSKEYDOWN, WM_SYSKEYUP):
            return False

        extended = (kb_struct.flags & 0x1) != 0
        code = (SCAN_TO_CODE_EXT if extended else SCAN_TO_CODE).get(kb_struct.scanCode)
        if not code:
            return False
        if code == "caps":
            return False  # never intercepted - its own OS toggle/lamp keeps working as-is

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
