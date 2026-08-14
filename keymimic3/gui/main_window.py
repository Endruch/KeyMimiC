"""
Main application window: hosts the single ThreadPanel and dispatches global
hotkeys to it.

Recording always stops the script first if it happens to be running (it
can't be, in practice - start_recording() already refuses to start while
running - but the guard is cheap and makes the intent explicit). Recording
itself only ever captures real hardware input regardless (Recorder filters
out SendInput-injected events).

Exactly two low-level keyboard hooks exist for the app's whole lifetime:
HotkeyManager's own (global hotkeys), and one shared hook owned right here
that both Recorder (while actively recording) and RemoteControlManager
(while armed) feed off of - see _on_shared_keyboard_event. A third,
separate hook for remote control used to exist and was found to interfere
with HotkeyManager's, breaking global hotkeys.
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

        self._build_ui()

        self._register_hotkeys()
        self.hotkey_manager.start()

        # Shared with Recorder/RemoteControlManager - see _on_shared_keyboard_event.
        self._input_hook = KeyboardHook(self._on_shared_keyboard_event)
        self._input_hook.start()

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
            on_hotkeys_changed=self._register_hotkeys,
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
        self._input_hook.stop()
        self.remote_control.stop()
        self.peer.disconnect()
        event.accept()
