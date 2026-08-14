"""
The macro editor: profile selector, two-track (keyboard/mouse) block editor,
run controls and log for the single thread the app runs (see MainWindow).

Both tracks run on their own ScriptExecutor thread, started together and
(when looping) resynchronized at the top of every pass via a shared
threading.Barrier(2) - see start()/ScriptExecutor. There is no visible
"unsaved changes" indicator; the existing save/discard/cancel prompt (see
_confirm_discard_if_dirty) already covers that case whenever it matters.
"""

import threading
from datetime import datetime

from PySide6.QtCore import QTimer
from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import (
    QFrame, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QPushButton,
    QCheckBox, QSpinBox, QScrollArea, QPlainTextEdit, QMessageBox,
    QInputDialog, QWidget, QLineEdit,
)

from ..model import Script, validate_script, ScriptValidationError
from ..managers import ProfileManager, Recorder
from ..execution import ScriptExecutor
from ..core.constants import IS_WINDOWS
from ..core.input import get_mouse_position
from .block_widgets import BlockListPanel
from .settings_dialog import SettingsDialog
from . import styles

LOG_MAX_LINES = 300
MOUSE_POS_POLL_MS = 100
RECORDING_PREVIEW_POLL_MS = 500


class ThreadPanel(QFrame):
    """The (single) macro thread panel."""

    def __init__(self, panel_id, hotkey_config, peer, remote_control, on_hotkeys_changed=None, parent=None):
        super().__init__(parent)
        self.setObjectName("ThreadPanel")
        self.panel_id = panel_id
        self.hotkey_config = hotkey_config
        self.peer = peer
        self.remote_control = remote_control
        self.on_hotkeys_changed = on_hotkeys_changed

        self.profile_manager = ProfileManager(panel_id)
        self.current_profile = self.profile_manager.get_profile_names()[0]
        self.script: Script = self.profile_manager.get_profile(self.current_profile)

        self._undo_stack = [self.script.to_dict()]
        self._undo_index = 0
        self._dirty = False

        self.block_widgets = {}      # block id -> BlockCardWidget, refreshed on every render
        self.current_block_ids = set()
        self.running = False
        self.keyboard_executor = None
        self.mouse_executor = None
        self._stopped_count = 0
        self.recorder = None
        self.is_recording = False

        self._build_ui()
        self._refresh_blocks_area()

        self._mouse_pos_timer = QTimer(self)
        self._mouse_pos_timer.timeout.connect(self._update_mouse_pos_label)
        self._mouse_pos_timer.start(MOUSE_POS_POLL_MS)

        self._recording_preview_timer = QTimer(self)
        self._recording_preview_timer.timeout.connect(self._refresh_blocks_area)

        self.peer.connected.connect(self._on_net_connected)
        self.peer.disconnected.connect(self._on_net_disconnected)
        self.peer.error.connect(self._on_net_error)
        self.remote_control.armed_changed.connect(self._on_armed_changed)
        self.remote_control.being_controlled_changed.connect(self._on_being_controlled_changed)
        self.remote_control.peer_script_status_changed.connect(self._on_peer_script_status_changed)

    # -- panel interface used by block_widgets.py --------------------------

    def is_locked(self) -> bool:
        return self.running or self.is_recording

    def is_current_block(self, block_id) -> bool:
        return block_id in self.current_block_ids

    def notify_change(self):
        """Called by child widgets right after they mutated self.script in place."""
        del self._undo_stack[self._undo_index + 1:]
        self._undo_stack.append(self.script.to_dict())
        self._undo_index += 1
        self._dirty = True
        self._update_undo_redo_buttons()
        self._update_start_button()
        QTimer.singleShot(0, self._refresh_blocks_area)

    # -- UI construction ------------------------------------------------------

    def _build_ui(self):
        self.setMinimumWidth(380)
        root = QVBoxLayout(self)

        profile_row = QHBoxLayout()
        profile_row.addWidget(QLabel("Profile:"))
        self.profile_combo = QComboBox()
        self.profile_combo.addItems(self.profile_manager.get_profile_names())
        self.profile_combo.setCurrentText(self.current_profile)
        self.profile_combo.currentTextChanged.connect(self._on_profile_combo_changed)
        profile_row.addWidget(self.profile_combo, stretch=1)

        self.new_profile_btn = QPushButton("+")
        self.new_profile_btn.setFixedWidth(28)
        self.new_profile_btn.clicked.connect(self._on_new_profile)
        profile_row.addWidget(self.new_profile_btn)

        self.rename_profile_btn = QPushButton("Edit")
        self.rename_profile_btn.clicked.connect(self._on_rename_profile)
        profile_row.addWidget(self.rename_profile_btn)

        self.delete_profile_btn = QPushButton("Del")
        self.delete_profile_btn.clicked.connect(self._on_delete_profile)
        profile_row.addWidget(self.delete_profile_btn)
        root.addLayout(profile_row)

        toolbar1 = QHBoxLayout()
        self.record_btn = QPushButton()
        self.record_btn.clicked.connect(self._on_toggle_recording)
        toolbar1.addWidget(self.record_btn)

        self.settings_btn = QPushButton("Settings")
        self.settings_btn.clicked.connect(self._on_settings)
        toolbar1.addWidget(self.settings_btn)

        self.loop_check = QCheckBox("Loop")
        self.loop_check.setChecked(self.script.loop)
        self.loop_check.toggled.connect(self._on_loop_toggled)
        toolbar1.addWidget(self.loop_check)

        toolbar1.addWidget(QLabel("Humanize %:"))
        self.humanize_spin = QSpinBox()
        self.humanize_spin.setRange(0, 100)
        self.humanize_spin.setValue(self.script.humanize)
        self.humanize_spin.editingFinished.connect(self._on_humanize_changed)
        toolbar1.addWidget(self.humanize_spin)
        toolbar1.addStretch()
        root.addLayout(toolbar1)

        toolbar2 = QHBoxLayout()
        self.undo_btn = QPushButton("Undo")
        self.undo_btn.clicked.connect(self._on_undo)
        toolbar2.addWidget(self.undo_btn)
        self.redo_btn = QPushButton("Redo")
        self.redo_btn.clicked.connect(self._on_redo)
        toolbar2.addWidget(self.redo_btn)

        self.save_btn = QPushButton("Save")
        self.save_btn.setObjectName("PrimaryButton")
        self.save_btn.clicked.connect(self._on_save)
        toolbar2.addWidget(self.save_btn)
        toolbar2.addStretch()
        root.addLayout(toolbar2)

        net_row = QHBoxLayout()
        self.net_start_server_btn = QPushButton("Start Server")
        self.net_start_server_btn.clicked.connect(self._on_start_server)
        net_row.addWidget(self.net_start_server_btn)

        self.net_status_label = QLabel("")
        self.net_status_label.setObjectName("MutedLabel")
        net_row.addWidget(self.net_status_label)

        self.net_connect_ip_edit = QLineEdit()
        self.net_connect_ip_edit.setPlaceholderText("IP address")
        self.net_connect_ip_edit.setFixedWidth(110)
        self.net_connect_ip_edit.setText(self.hotkey_config.last_connect_ip)
        net_row.addWidget(self.net_connect_ip_edit)

        self.net_connect_btn = QPushButton("Connect")
        self.net_connect_btn.clicked.connect(self._on_connect)
        net_row.addWidget(self.net_connect_btn)

        self.net_disconnect_btn = QPushButton("Disconnect")
        self.net_disconnect_btn.clicked.connect(self._on_disconnect)
        self.net_disconnect_btn.setVisible(False)
        net_row.addWidget(self.net_disconnect_btn)

        net_row.addStretch()
        root.addLayout(net_row)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setMinimumHeight(260)
        root.addWidget(self.scroll_area, stretch=1)

        bottom = QHBoxLayout()
        self.start_btn = QPushButton("Start")
        self.start_btn.setObjectName("PrimaryButton")
        self.start_btn.clicked.connect(self.start)
        bottom.addWidget(self.start_btn)
        self.stop_btn = QPushButton("Stop")
        self.stop_btn.setEnabled(False)
        self.stop_btn.clicked.connect(self.stop)
        bottom.addWidget(self.stop_btn)
        self.status_label = QLabel("Stopped")
        bottom.addWidget(self.status_label)
        bottom.addStretch()
        root.addLayout(bottom)

        self.log_box = QPlainTextEdit()
        self.log_box.setReadOnly(True)
        self.log_box.setFixedHeight(140)
        root.addWidget(self.log_box)

        # Peer script status is shown here rather than as a normal scrolling
        # log entry, so it always stays the last thing visible in this area
        # no matter how many other log lines come in afterwards.
        self.peer_status_label = QLabel("")
        self.peer_status_label.setVisible(False)
        root.addWidget(self.peer_status_label)

        footer = QHBoxLayout()
        self.mouse_pos_label = QLabel("Mouse: -, -")
        self.mouse_pos_label.setObjectName("MutedLabel")
        footer.addWidget(self.mouse_pos_label)
        footer.addStretch()
        coffee_label = QLabel(
            '<a href="https://buymeacoffee.com/migli" style="color: #facc15;">'
            '☕ Buy Migli a coffee!</a>'
        )
        coffee_label.setOpenExternalLinks(True)
        footer.addWidget(coffee_label)
        root.addLayout(footer)

        self._update_hotkey_labels()
        self._update_undo_redo_buttons()
        self._update_start_button()
        self._update_lock_state()

    def _update_lock_state(self):
        """Disable everything that mutates the script/profile while running or recording."""
        locked = self.is_locked()
        for w in (
            self.profile_combo, self.new_profile_btn, self.rename_profile_btn,
            self.delete_profile_btn, self.loop_check, self.humanize_spin,
            self.settings_btn,
        ):
            w.setEnabled(not locked)
        # Only gated by "running", not "recording" - otherwise there'd be no way
        # to click Record again to stop an in-progress recording.
        self.record_btn.setEnabled(not self.running)

    def _refresh_blocks_area(self):
        self.block_widgets.clear()

        # While actively recording, show a live preview of what's been
        # captured so far instead of the previously-loaded profile - purely
        # a display swap (self.script itself is untouched until Stop creates
        # the new profile). Safe to render through the normal editable
        # widgets: editing is already fully disabled while is_locked(), and
        # these preview Block objects aren't tied to self.script anyway.
        if self.is_recording and self.recorder:
            keyboard_blocks, mouse_blocks = self.recorder.preview_blocks()
        else:
            keyboard_blocks, mouse_blocks = self.script.keyboard_blocks, self.script.mouse_blocks

        container = QWidget()
        columns = QHBoxLayout(container)
        columns.setContentsMargins(0, 0, 0, 0)
        columns.setSpacing(10)

        for title, blocks_ref, track in (
            ("Keyboard", keyboard_blocks, "keyboard"),
            ("Mouse", mouse_blocks, "mouse"),
        ):
            col = QVBoxLayout()
            col.addWidget(QLabel(f"<b>{title}</b>"))
            col.addWidget(BlockListPanel(blocks_ref, self, track))
            col_widget = QWidget()
            col_widget.setLayout(col)
            columns.addWidget(col_widget, stretch=1)

        self.scroll_area.setWidget(container)
        self.loop_check.blockSignals(True)
        self.loop_check.setChecked(self.script.loop)
        self.loop_check.blockSignals(False)
        self.humanize_spin.blockSignals(True)
        self.humanize_spin.setValue(self.script.humanize)
        self.humanize_spin.blockSignals(False)

    # -- mouse position footer -------------------------------------------------

    def _update_mouse_pos_label(self):
        x, y = get_mouse_position()
        self.mouse_pos_label.setText(f"Mouse: {x}, {y}")

    # -- undo / redo ----------------------------------------------------------

    def _update_undo_redo_buttons(self):
        self.undo_btn.setEnabled(self._undo_index > 0 and not self.running)
        self.redo_btn.setEnabled(self._undo_index < len(self._undo_stack) - 1 and not self.running)

    def _on_undo(self):
        if self._undo_index <= 0:
            return
        self._undo_index -= 1
        self.script = Script.from_dict(self._undo_stack[self._undo_index])
        self._dirty = True
        self._update_undo_redo_buttons()
        self._update_start_button()
        self._refresh_blocks_area()

    def _on_redo(self):
        if self._undo_index >= len(self._undo_stack) - 1:
            return
        self._undo_index += 1
        self.script = Script.from_dict(self._undo_stack[self._undo_index])
        self._dirty = True
        self._update_undo_redo_buttons()
        self._update_start_button()
        self._refresh_blocks_area()

    # -- dirty / save state ----------------------------------------------------

    def _update_start_button(self):
        try:
            validate_script(self.script)
            self.start_btn.setEnabled(not self.is_locked())
            self.start_btn.setToolTip("")
        except ScriptValidationError as exc:
            self.start_btn.setEnabled(False)
            self.start_btn.setToolTip(str(exc))

    def _on_save(self):
        self.profile_manager.update_profile(self.current_profile, self.script)
        self._dirty = False
        self._log(f"Saved profile '{self.current_profile}'")

    def _confirm_discard_if_dirty(self) -> bool:
        """Returns True if it's OK to proceed (saved, discarded, or not dirty)."""
        if not self._dirty:
            return True
        box = QMessageBox(self)
        box.setWindowTitle("Unsaved changes")
        box.setText(f"Profile '{self.current_profile}' has unsaved changes.")
        save_btn = box.addButton("Save", QMessageBox.AcceptRole)
        discard_btn = box.addButton("Discard", QMessageBox.DestructiveRole)
        cancel_btn = box.addButton("Cancel", QMessageBox.RejectRole)
        box.exec()
        clicked = box.clickedButton()
        if clicked is save_btn:
            self._on_save()
            return True
        if clicked is discard_btn:
            return True
        return False

    # -- profiles ---------------------------------------------------------

    def _on_profile_combo_changed(self, new_name):
        if new_name == self.current_profile or not new_name:
            return
        if not self._confirm_discard_if_dirty():
            self.profile_combo.blockSignals(True)
            self.profile_combo.setCurrentText(self.current_profile)
            self.profile_combo.blockSignals(False)
            return
        self._load_profile(new_name)

    def _load_profile(self, name):
        self.current_profile = name
        self.script = self.profile_manager.get_profile(name)
        self._undo_stack = [self.script.to_dict()]
        self._undo_index = 0
        self._dirty = False
        self.current_block_ids = set()
        self._update_undo_redo_buttons()
        self._update_start_button()
        self._refresh_blocks_area()

    def _on_new_profile(self):
        name, ok = QInputDialog.getText(self, "New Profile", "Profile name:")
        if not ok or not name.strip():
            return
        name = name.strip()
        if name in self.profile_manager.get_profile_names():
            QMessageBox.warning(self, "Error", "A profile with that name already exists.")
            return
        if not self._confirm_discard_if_dirty():
            return
        self.profile_manager.add_profile(name, Script.empty(name))
        self.profile_combo.blockSignals(True)
        self.profile_combo.clear()
        self.profile_combo.addItems(self.profile_manager.get_profile_names())
        self.profile_combo.setCurrentText(name)
        self.profile_combo.blockSignals(False)
        self._load_profile(name)
        self._log(f"Created new profile '{name}'")

    def _on_rename_profile(self):
        old_name = self.current_profile
        new_name, ok = QInputDialog.getText(self, "Rename Profile", "New name:", text=old_name)
        if not ok or not new_name.strip() or new_name == old_name:
            return
        if self.profile_manager.rename_profile(old_name, new_name.strip()):
            self.current_profile = new_name.strip()
            self.profile_combo.blockSignals(True)
            self.profile_combo.clear()
            self.profile_combo.addItems(self.profile_manager.get_profile_names())
            self.profile_combo.setCurrentText(self.current_profile)
            self.profile_combo.blockSignals(False)
            self._log(f"Renamed profile '{old_name}' -> '{self.current_profile}'")

    def _on_delete_profile(self):
        if len(self.profile_manager.get_profile_names()) <= 1:
            QMessageBox.warning(self, "Error", "Cannot delete the last profile.")
            return
        if QMessageBox.question(self, "Delete Profile", f"Delete '{self.current_profile}'?") != QMessageBox.Yes:
            return
        if self.profile_manager.delete_profile(self.current_profile):
            names = self.profile_manager.get_profile_names()
            self.profile_combo.blockSignals(True)
            self.profile_combo.clear()
            self.profile_combo.addItems(names)
            self.profile_combo.setCurrentText(names[0])
            self.profile_combo.blockSignals(False)
            self._log("Profile deleted")
            self._load_profile(names[0])

    # -- metadata toggles ---------------------------------------------------

    def _on_loop_toggled(self, checked):
        self.script.loop = checked
        self.notify_change()

    def _on_humanize_changed(self):
        self.script.humanize = self.humanize_spin.value()
        self.notify_change()

    # -- recording ----------------------------------------------------------

    def _update_hotkey_labels(self):
        if self.is_recording:
            self.record_btn.setText(f"Stop Recording ({self.hotkey_config.format_hotkey('stop_record')})")
        else:
            self.record_btn.setText(f"Record ({self.hotkey_config.format_hotkey('start_record')})")
        self.start_btn.setText(f"Start ({self.hotkey_config.format_hotkey('start')})")
        self.stop_btn.setText(f"Stop ({self.hotkey_config.format_hotkey('stop')})")

    def _on_toggle_recording(self):
        self.stop_recording() if self.is_recording else self.start_recording()

    def start_recording(self):
        if not IS_WINDOWS:
            QMessageBox.warning(self, "Not available", "Recording only works on Windows.")
            return
        if self.is_recording or self.running:
            return
        self.is_recording = True
        self._update_hotkey_labels()
        self._update_lock_state()
        self._update_start_button()
        self._refresh_blocks_area()

        self.recorder = Recorder()
        self.recorder.set_control_hotkeys({
            "start_record": self.hotkey_config.get_hotkey("start_record"),
            "stop_record": self.hotkey_config.get_hotkey("stop_record"),
        })
        self.recorder.signals.control_hotkey.connect(self._on_recorder_control_hotkey)
        self.recorder.start(record_mouse=self.hotkey_config.record_mouse)
        self._recording_preview_timer.start(RECORDING_PREVIEW_POLL_MS)
        self._log("Recording started...")

    def _on_recorder_control_hotkey(self, action):
        if action == "stop_record":
            self.stop_recording()

    def cancel_recording(self):
        """Stop recording without turning it into a profile (used when closing a panel)."""
        if not self.is_recording:
            return
        self.is_recording = False
        self._recording_preview_timer.stop()
        if self.recorder:
            self.recorder.stop()
            self.recorder = None
        self._update_hotkey_labels()
        self._update_lock_state()
        self._update_start_button()

    def stop_recording(self):
        if not self.is_recording or not self.recorder:
            return
        self.is_recording = False
        self._recording_preview_timer.stop()
        self._update_hotkey_labels()
        self._update_lock_state()
        self._update_start_button()

        # Checked before .stop() clears/consumes the recorder's raw event
        # lists - an accidental instant Record/Stop with nothing captured
        # would otherwise still save a profile (keyboard_blocks/mouse_blocks
        # come back empty, or - if mouse recording was on - containing only
        # the synthetic "Return to starting position" block), cluttering
        # the profile list with nothing of value.
        had_activity = bool(self.recorder.keyboard_events or self.recorder.mouse_events)
        keyboard_blocks, mouse_blocks = self.recorder.stop()
        self.recorder = None

        if not had_activity:
            self._log("Recording stopped - nothing was captured, no profile created.")
            self._refresh_blocks_area()
            return

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        name = f"Recording {timestamp}"
        new_script = Script(thread_name=name, keyboard_blocks=keyboard_blocks, mouse_blocks=mouse_blocks)
        name = self.profile_manager.add_profile(name, new_script)

        self.profile_combo.blockSignals(True)
        self.profile_combo.clear()
        self.profile_combo.addItems(self.profile_manager.get_profile_names())
        self.profile_combo.setCurrentText(self.current_profile)
        self.profile_combo.blockSignals(False)

        # Switching the view to the new recording would silently throw away
        # any unsaved edits in whatever was open here - go through the same
        # save/discard/cancel prompt as a normal profile switch.
        if self._confirm_discard_if_dirty():
            self.profile_combo.setCurrentText(name)
            self._load_profile(name)
        self._log(f"Recording stopped, saved as '{name}'")

    # -- LAN remote control (see SPEC.md §2) -----------------------------------

    def _on_start_server(self):
        self.net_status_label.setText(f"IP: {self.peer.local_ip()}")
        self.net_status_label.setStyleSheet("")  # plain/muted while just listening, not connected yet
        self.peer.start_server()
        self._set_net_ui_state("listening")
        self._log("Starting server, waiting for the other computer to connect...")

    def _on_connect(self):
        ip = self.net_connect_ip_edit.text().strip()
        if not ip:
            return
        self.hotkey_config.last_connect_ip = ip
        self.hotkey_config.save()
        self.peer.connect_to(ip)
        self._log(f"Connecting to {ip}...")

    def _on_disconnect(self):
        # Covers both "actually connected" (tears down the socket) and
        # "still just listening, no peer yet" (tears down the listen socket)
        # - PeerConnection.disconnect() handles either case the same way.
        self.peer.disconnect()

    def _set_net_ui_state(self, state: str):
        """state: 'idle' (not connected, not listening) / 'listening' (Start Server, waiting for a peer) / 'connected'."""
        idle = state == "idle"
        self.net_start_server_btn.setVisible(idle)
        self.net_connect_ip_edit.setVisible(idle)
        self.net_connect_btn.setVisible(idle)
        self.net_status_label.setVisible(state != "idle")
        self.net_disconnect_btn.setVisible(not idle)
        self.net_disconnect_btn.setText("Disconnect" if state == "connected" else "Stop Server")

    def _on_net_connected(self):
        self.net_status_label.setText(f"Connected: {self.peer.peer_ip}")
        self.net_status_label.setStyleSheet(f"color: {styles.REMOTE_ARMED_BG}; font-weight: 600;")
        self._set_net_ui_state("connected")
        self._log("Connected to peer.")

    def _on_net_disconnected(self):
        self._set_net_ui_state("idle")
        self.peer_status_label.setVisible(False)  # no peer left to report a script status for
        self._log("Disconnected from peer.")

    def _on_net_error(self, message):
        self._log(f"Network error: {message}")

    def _on_armed_changed(self, armed):
        self._update_remote_bg()
        if armed:
            self._log("Remote control: now controlling the peer's keyboard.")
        else:
            self._log("Remote control: stopped controlling the peer's keyboard.")

    def _on_being_controlled_changed(self, controlled):
        self._update_remote_bg()
        if controlled:
            self._log("Remote control: the peer is now controlling this computer.")
        else:
            self._log("Remote control: the peer stopped controlling this computer.")

    def _update_remote_bg(self):
        if self.remote_control.armed:
            color = styles.REMOTE_ARMED_BG
        elif self.remote_control.being_controlled:
            color = styles.REMOTE_CONTROLLED_BG
        else:
            color = ""
        self.scroll_area.viewport().setStyleSheet(f"background-color: {color};" if color else "")

    def _on_peer_script_status_changed(self, running):
        if not self.peer.is_connected():
            # A status message can race a disconnect that just happened -
            # never show stale peer info once there's no active connection.
            return
        ip = self.peer.peer_ip or "peer"
        color = styles.REMOTE_ARMED_BG if running else styles.REMOTE_CONTROLLED_BG
        text = f"Script running on {ip}" if running else f"Script stopped on {ip}"
        self.peer_status_label.setText(text)
        self.peer_status_label.setStyleSheet(f"color: {color}; font-weight: 600;")
        self.peer_status_label.setVisible(True)

    # -- settings -------------------------------------------------------------

    def _on_settings(self):
        def _on_saved():
            self._update_hotkey_labels()
            if self.on_hotkeys_changed:
                self.on_hotkeys_changed()
        SettingsDialog(self, self.hotkey_config, on_save=_on_saved).exec()

    # -- run / stop -------------------------------------------------------

    def start(self):
        if self.is_locked():
            return
        try:
            validate_script(self.script)
        except ScriptValidationError as exc:
            QMessageBox.warning(self, "Cannot start", str(exc))
            return

        self.running = True
        self.current_block_ids = set()
        self._stopped_count = 0
        self._refresh_blocks_area()
        self._update_undo_redo_buttons()
        self._update_lock_state()

        label = self.script.thread_name or f"Thread {self.panel_id}"
        # Both tracks are always started together; when looping, they share a
        # barrier so neither one starts its next pass before the other has
        # finished its current one - otherwise the two tracks would slowly
        # drift apart over long/looped runs.
        barrier = threading.Barrier(2) if self.script.loop else None
        self.keyboard_executor = ScriptExecutor(
            self.script.keyboard_blocks, humanize=self.script.humanize, loop=self.script.loop,
            label=f"{label} [Keyboard]", sync_barrier=barrier,
        )
        self.mouse_executor = ScriptExecutor(
            self.script.mouse_blocks, humanize=self.script.humanize, loop=self.script.loop,
            label=f"{label} [Mouse]", sync_barrier=barrier,
        )
        for executor in (self.keyboard_executor, self.mouse_executor):
            executor.signals.log.connect(self._log)
            executor.signals.block_started.connect(self._on_block_started)
            executor.signals.block_finished.connect(self._on_block_finished)
            executor.signals.stopped.connect(self._on_executor_stopped)
            executor.start()

        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.status_label.setText("Running...")
        self.remote_control.notify_script_status(True)

    def stop(self):
        if self.keyboard_executor:
            self.keyboard_executor.stop()
        if self.mouse_executor:
            self.mouse_executor.stop()
        self.stop_btn.setEnabled(False)

    def join_executors(self, timeout: float = 2.0):
        """
        Block until both track executors have actually exited (or timeout).
        Used on app shutdown: stop() only signals them to stop, it doesn't
        wait - without this, the process can exit while a background
        executor thread is still mid-shutdown, and since these are daemon
        threads they'd simply be killed rather than getting to run their
        release-all-held-keys cleanup.
        """
        for executor in (self.keyboard_executor, self.mouse_executor):
            if executor is not None and executor.is_alive():
                executor.join(timeout=timeout)

    def _on_block_started(self, block_id):
        self.current_block_ids.add(block_id)
        widget = self.block_widgets.get(block_id)
        if widget:
            widget.set_current(True)

    def _on_block_finished(self, block_id):
        widget = self.block_widgets.get(block_id)
        if widget:
            widget.set_current(False)
        self.current_block_ids.discard(block_id)

    def _on_executor_stopped(self):
        # Emitted once per track's executor - only finalize once both are done.
        self._stopped_count += 1
        if self._stopped_count < 2:
            return
        self.running = False
        self.keyboard_executor = None
        self.mouse_executor = None
        self.current_block_ids = set()
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.status_label.setText("Stopped")
        self._update_start_button()
        self._update_undo_redo_buttons()
        self._update_lock_state()
        self._refresh_blocks_area()
        self.remote_control.notify_script_status(False)

    # -- logging --------------------------------------------------------------

    def _log(self, message):
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_box.appendPlainText(f"[{timestamp}] {message}")
        doc = self.log_box.document()
        excess = doc.blockCount() - LOG_MAX_LINES
        if excess > 0:
            cursor = self.log_box.textCursor()
            cursor.movePosition(QTextCursor.Start)
            cursor.movePosition(QTextCursor.Down, QTextCursor.KeepAnchor, excess)
            cursor.removeSelectedText()
            cursor.deleteChar()  # remove the now-empty line left at the top
