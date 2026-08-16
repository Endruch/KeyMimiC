"""
Main application window: hosts the single ThreadPanel and dispatches global
hotkeys to it.

Recording always stops the script first if it happens to be running (it
can't be, in practice - start_recording() already refuses to start while
running - but the guard is cheap and makes the intent explicit). Recording
itself only ever captures real hardware input regardless (Recorder filters
out SendInput-injected events).

HotkeyManager's own hook is the only one installed for the app's entire
lifetime. A second, shared hook (owned right here, used by Recorder while
actively recording and RemoteControlManager while armed - see
_on_shared_keyboard_event) is installed *only* while one of those is
actually active, and torn down the moment neither is - see
_update_shared_hook. This mirrors how Recorder's hook always behaved before
Phase 2 (installed only for the duration of an actual recording, not for
the app's whole lifetime). A version of this second hook that stayed
installed continuously from startup was tried and still interfered with
HotkeyManager's hook, breaking global hotkeys - keeping two low-level
keyboard hooks *simultaneously active most of the time* was the problem,
not merely having more than one hook class in the codebase.
"""

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QMainWindow, QWidget, QVBoxLayout
import queue

from ..config import HotkeyConfig
from ..core.hooks import KeyboardHook
from ..managers import HotkeyManager, RemoteControlManager
from ..network import PeerConnection
from .thread_panel import ThreadPanel
from . import styles


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("KeyMiglic")
        self.resize(550, 900)
        self.setStyleSheet(styles.APP_STYLESHEET)

        self.hotkey_config = HotkeyConfig()
        self.hotkey_manager = HotkeyManager()
        self.peer = PeerConnection()
        self.remote_control = RemoteControlManager(self.peer, parent=self)
        self.remote_control.start()
        self.remote_control.armed_changed.connect(lambda _armed: self._update_shared_hook())

        self._input_hook = None  # installed/removed on demand - see _update_shared_hook

        self._build_ui()

        self._register_hotkeys()
        self.hotkey_manager.start()

        self._hotkey_timer = QTimer(self)
        self._hotkey_timer.timeout.connect(self._poll_hotkeys)
        self._hotkey_timer.start(50)

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        outer = QVBoxLayout(central)
        outer.setContentsMargins(0, 0, 0, 0)

        self.panel = ThreadPanel(
            1, self.hotkey_config, self.peer, self.remote_control,
            on_recording_changed=self._update_shared_hook,
        )
        outer.addWidget(self.panel, stretch=1)

    # -- hotkeys ----------------------------------------------------------

    def _register_hotkeys(self):
        self.hotkey_manager.clear()
        for action in ("start", "stop", "start_record", "stop_record"):
            binding = self.hotkey_config.get_hotkey(action)
            self.hotkey_manager.register(
                binding["key"], action,
                ctrl=binding.get("ctrl", False),
                shift=binding.get("shift", False),
                alt=binding.get("alt", False),
            )
        self.panel._update_hotkey_labels()

    def _poll_hotkeys(self):
        while True:
            try:
                action = self.hotkey_manager.event_queue.get_nowait()
            except queue.Empty:
                break
            self._dispatch_hotkey_action(action)

    def _dispatch_hotkey_action(self, action):
        if action == "stop":
            if self.panel.running:
                self.panel.stop()
        elif action == "start":
            if not self.panel.is_locked() and self.panel.start_btn.isEnabled():
                self.panel.start()
        elif action == "start_record":
            if not self.panel.running and not self.panel.is_recording:
                self.panel.start_recording()
        elif action == "stop_record":
            if self.panel.is_recording:
                self.panel.stop_recording()

    # -- shared keyboard hook (recording + armed remote control) ------------

    def _update_shared_hook(self):
        """
        Install the shared hook only while it's actually needed (recording
        or armed), tear it down the moment neither is true anymore. Two
        low-level keyboard hooks installed *simultaneously, continuously*
        (this one running for the app's whole lifetime alongside
        HotkeyManager's) was found to interfere with HotkeyManager's own
        hook and break global hotkeys, even though only two hook classes
        existed - it was the near-constant simultaneous presence, not the
        count in the abstract, that mattered. Keeping this one installed
        only for the actual duration it's needed (mirroring how Recorder's
        hook always worked, even before Phase 2) keeps HotkeyManager's hook
        alone almost all the time, same as the last known-good state.
        """
        needed = self.remote_control.armed or (
            self.panel.recorder is not None and self.panel.recorder.recording
        )
        if needed and self._input_hook is None:
            self._input_hook = KeyboardHook(self._on_shared_keyboard_event)
            self._input_hook.start()
        elif not needed and self._input_hook is not None:
            self._input_hook.stop()
            self._input_hook = None

    def _on_shared_keyboard_event(self, nCode, wParam, kb_struct):
        """
        Routes one physical key event to whichever of Recorder/
        RemoteControlManager currently cares about it - at most one of the
        two is ever active at a time in normal use. Recorder's handler
        never suppresses (always returns None/falsy); RemoteControlManager's
        can, to keep this machine's own input from leaking out while armed.
        """
        recorder = self.panel.recorder
        if recorder is not None and recorder.recording:
            return recorder._on_keyboard_event(nCode, wParam, kb_struct)
        if self.remote_control.armed:
            return self.remote_control._on_keyboard_event(nCode, wParam, kb_struct)
        return False

    # -- shutdown -----------------------------------------------------------

    def closeEvent(self, event):
        if not self.panel._confirm_discard_if_dirty():
            event.ignore()
            return
        self.panel.stop()
        self.panel.join_executors()
        self.panel.cancel_recording()
        self.hotkey_manager.stop()
        if self._input_hook is not None:
            self._input_hook.stop()
            self._input_hook = None
        self.remote_control.stop()
        self.peer.disconnect()
        event.accept()
