"""
Main application window: hosts the single ThreadPanel and dispatches global
hotkeys to it.

Recording always stops the script first if it happens to be running (it
can't be, in practice - start_recording() already refuses to start while
running - but the guard is cheap and makes the intent explicit). Recording
itself only ever captures real hardware input regardless (Recorder filters
out SendInput-injected events).
"""

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QMainWindow, QWidget, QVBoxLayout
import queue

from ..config import HotkeyConfig
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

        self._build_ui()

        self._register_hotkeys()
        self.hotkey_manager.start()
        # Windows calls low-level hook chains in reverse install order (most
        # recently installed first) - starting this one last means it always
        # gets first look at a key event and can suppress it before
        # HotkeyManager's hook ever sees it, so a forwarded combo that also
        # happens to match a *local* hotkey can't double-fire here too.
        self.remote_control.start()

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

    # -- shutdown -----------------------------------------------------------

    def closeEvent(self, event):
        if not self.panel._confirm_discard_if_dirty():
            event.ignore()
            return
        self.panel.stop()
        self.panel.join_executors()
        self.panel.cancel_recording()
        self.hotkey_manager.stop()
        self.remote_control.stop()
        self.peer.disconnect()
        event.accept()
