"""
Main application window: hosts up to 4 independent ThreadPanels side by side
and dispatches global hotkeys to them.

Hotkey dispatch policy (not fully specified by the original request, chosen
for safety/predictability):
- "stop"          -> stops every currently running panel (a single "panic"
                      key that never leaves something running by accident).
- "start"         -> starts the lowest-numbered idle panel whose script
                      currently validates.
- "start_record"  -> the hotkey has no implicit "target" panel, so it always
                      opens a brand new thread and records into that (never
                      silently takes over an existing panel's current view).
- "stop_record"   -> stops recording on whichever panel is currently
                      recording.

Starting a recording (either via the Record button on a panel, or via the
global hotkey above) always stops every currently running script first, in
every open panel - see ThreadPanel.on_before_record / _stop_all_running
below. Recording only ever captures real hardware input anyway (Recorder
filters out SendInput-injected events), but a macro still moving the mouse
or pressing keys while you're trying to record is too confusing to allow.
"""

from PySide6.QtCore import QTimer, Qt
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QPushButton, QScrollArea,
    QMessageBox,
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
        self.resize(550, 900)
        self.setStyleSheet(styles.APP_STYLESHEET)

        self.hotkey_config = HotkeyConfig()
        self.hotkey_manager = HotkeyManager()
        self.clipboard = []  # shared block clipboard, passed by reference to every panel

        self.panels: dict[int, ThreadPanel] = {}

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

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        outer.addWidget(self.scroll_area, stretch=1)

        self.panels_container = QWidget()
        self.panels_layout = QHBoxLayout(self.panels_container)
        self.panels_layout.setAlignment(Qt.AlignLeft)
        self.scroll_area.setWidget(self.panels_container)

        self.add_panel_btn = QPushButton("+\nAdd\nThread")
        self.add_panel_btn.setObjectName("PrimaryButton")
        self.add_panel_btn.setFixedWidth(70)
        self.add_panel_btn.setMinimumHeight(120)
        self.add_panel_btn.clicked.connect(self.add_panel)

    # -- panel management -------------------------------------------------

    def _lowest_free_id(self):
        used = set(self.panels.keys())
        for i in range(1, MAX_PANELS + 1):
            if i not in used:
                return i
        return None

    def add_panel(self):
        """Create a new thread panel and return it (or None if at MAX_PANELS)."""
        panel_id = self._lowest_free_id()
        if panel_id is None:
            QMessageBox.information(self, "Limit reached", f"Maximum of {MAX_PANELS} threads.")
            return None
        panel = ThreadPanel(
            panel_id, self._on_panel_closed, self.hotkey_config,
            on_hotkeys_changed=self._register_hotkeys, clipboard=self.clipboard,
            on_before_record=self._stop_all_running,
        )
        self.panels[panel_id] = panel
        self._relayout_panels()
        return panel

    def _stop_all_running(self):
        for panel in self.panels.values():
            if panel.running:
                panel.stop()

    def _on_panel_closed(self, panel_id):
        panel = self.panels.pop(panel_id, None)
        if panel:
            self.panels_layout.removeWidget(panel)
            panel.deleteLater()
        if not self.panels:
            self.add_panel()
        else:
            self._relayout_panels()

    def _relayout_panels(self):
        while self.panels_layout.count():
            self.panels_layout.takeAt(0)
        for panel_id in sorted(self.panels):
            self.panels_layout.addWidget(self.panels[panel_id])
        self.add_panel_btn.setVisible(len(self.panels) < MAX_PANELS)
        self.panels_layout.addWidget(self.add_panel_btn)

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
            panel._update_hotkey_labels()

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
            new_panel = self.add_panel()
            if new_panel is not None:
                new_panel.start_recording()
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
            panel.cancel_recording()
        self.hotkey_manager.stop()
        event.accept()
