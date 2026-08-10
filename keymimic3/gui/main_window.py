"""
Main application window: hosts up to 4 independent ThreadPanels side by side
and dispatches global hotkeys to them.

Hotkey dispatch policy (not fully specified by the original request, chosen
for safety/predictability):
- "stop"          -> stops every currently running panel (a single "panic"
                      key that never leaves something running by accident).
- "start"         -> starts the lowest-numbered idle panel whose script
                      currently validates.
- "start_record"  -> starts recording on the lowest-numbered panel that is
                      neither running nor already recording.
- "stop_record"   -> stops recording on whichever panel is currently
                      recording.
"""

from PySide6.QtCore import QTimer, Qt
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QPushButton, QScrollArea,
    QMessageBox, QLabel,
)
import queue

from ..config import HotkeyConfig
from ..managers import HotkeyManager
from .thread_panel import ThreadPanel
from . import styles

MAX_PANELS = 4


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("KeyMimic v3")
        self.resize(1500, 900)
        self.setStyleSheet(styles.APP_STYLESHEET)

        self.hotkey_config = HotkeyConfig()
        self.hotkey_manager = HotkeyManager()

        self.panels: dict[int, ThreadPanel] = {}
        self._next_panel_id = 1

        self._build_ui()
        self.add_panel()

        self._register_hotkeys()
        self.hotkey_manager.start()

        self._hotkey_timer = QTimer(self)
        self._hotkey_timer.timeout.connect(self._poll_hotkeys)
        self._hotkey_timer.start(50)

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        outer = QVBoxLayout(central)

        toolbar = QHBoxLayout()
        add_btn = QPushButton("+ Add Thread")
        add_btn.setObjectName("PrimaryButton")
        add_btn.clicked.connect(self.add_panel)
        toolbar.addWidget(add_btn)
        toolbar.addWidget(QLabel("KeyMimic v3 - block-based macro automation"))
        toolbar.addStretch()
        outer.addLayout(toolbar)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        outer.addWidget(self.scroll_area, stretch=1)

        self.panels_container = QWidget()
        self.panels_layout = QHBoxLayout(self.panels_container)
        self.panels_layout.setAlignment(Qt.AlignLeft)
        self.scroll_area.setWidget(self.panels_container)

    # -- panel management -------------------------------------------------

    def add_panel(self):
        if len(self.panels) >= MAX_PANELS:
            QMessageBox.information(self, "Limit reached", f"Maximum of {MAX_PANELS} threads.")
            return
        panel_id = self._next_panel_id
        self._next_panel_id += 1
        panel = ThreadPanel(
            panel_id, self._on_panel_closed, self.hotkey_config,
            on_hotkeys_changed=self._register_hotkeys,
        )
        self.panels[panel_id] = panel
        self.panels_layout.addWidget(panel)

    def _on_panel_closed(self, panel_id):
        panel = self.panels.pop(panel_id, None)
        if panel:
            self.panels_layout.removeWidget(panel)
            panel.deleteLater()
        if not self.panels:
            self.add_panel()

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
        for panel in self.panels.values():
            panel._update_record_label()

    def _poll_hotkeys(self):
        while True:
            try:
                action = self.hotkey_manager.event_queue.get_nowait()
            except queue.Empty:
                break
            self._dispatch_hotkey_action(action)

    def _dispatch_hotkey_action(self, action):
        ordered = [self.panels[k] for k in sorted(self.panels)]
        if action == "stop":
            for panel in ordered:
                if panel.running:
                    panel.stop()
        elif action == "start":
            for panel in ordered:
                if not panel.running and panel.start_btn.isEnabled():
                    panel.start()
                    break
        elif action == "start_record":
            for panel in ordered:
                if not panel.running and not panel.is_recording:
                    panel.start_recording()
                    break
        elif action == "stop_record":
            for panel in ordered:
                if panel.is_recording:
                    panel.stop_recording()
                    break

    # -- shutdown -----------------------------------------------------------

    def closeEvent(self, event):
        for panel in list(self.panels.values()):
            if not panel._confirm_discard_if_dirty():
                event.ignore()
                return
        for panel in self.panels.values():
            panel.stop()
        self.hotkey_manager.stop()
        event.accept()
