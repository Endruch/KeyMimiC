"""
One independent macro thread: profile selector, block editor, run controls
and its own log. Up to 4 of these live side by side in the MainWindow.
"""

from datetime import datetime

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QFrame, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QPushButton,
    QCheckBox, QSpinBox, QScrollArea, QPlainTextEdit, QMessageBox,
    QInputDialog, QWidget,
)

from ..model import Script, Block, validate_script, ScriptValidationError
from ..managers import ProfileManager, Recorder
from ..execution import ScriptExecutor
from ..core.constants import IS_WINDOWS
from . import styles
from .block_widgets import BlockListPanel, BlockListWidget
from .settings_dialog import SettingsDialog


class ThreadPanel(QFrame):
    """A single independent macro thread panel."""

    def __init__(self, panel_id, on_close, hotkey_config, on_hotkeys_changed=None, parent=None):
        super().__init__(parent)
        self.setObjectName("ThreadPanel")
        self.panel_id = panel_id
        self.on_close = on_close
        self.hotkey_config = hotkey_config
        self.on_hotkeys_changed = on_hotkeys_changed

        self.profile_manager = ProfileManager(panel_id)
        self.current_profile = self.profile_manager.get_profile_names()[0]
        self.script: Script = self.profile_manager.get_profile(self.current_profile)

        self._undo_stack = [self.script.to_dict()]
        self._undo_index = 0
        self._dirty = False
        self._clipboard = []

        self.block_widgets = {}      # block id -> BlockCardWidget, refreshed on every render
        self.current_block_id = None
        self.running = False
        self.executor = None
        self.recorder = None
        self.is_recording = False

        self._build_ui()
        self._refresh_blocks_area()
        self._update_unsaved_indicator()

    # -- panel interface used by block_widgets.py --------------------------

    def is_locked(self) -> bool:
        return self.running

    def is_current_block(self, block_id) -> bool:
        return block_id == self.current_block_id

    def notify_change(self):
        """Called by child widgets right after they mutated self.script in place."""
        del self._undo_stack[self._undo_index + 1:]
        self._undo_stack.append(self.script.to_dict())
        self._undo_index += 1
        self._dirty = True
        self._update_unsaved_indicator()
        self._update_undo_redo_buttons()
        self._update_start_button()
        QTimer.singleShot(0, self._refresh_blocks_area)

    # -- UI construction ------------------------------------------------------

    def _build_ui(self):
        self.setMinimumWidth(380)
        root = QVBoxLayout(self)

        header = QHBoxLayout()
        header.addWidget(QLabel(f"<b>Thread {self.panel_id}</b>"))
        self.unsaved_label = QLabel("")
        self.unsaved_label.setObjectName("UnsavedIndicator")
        header.addWidget(self.unsaved_label)
        header.addStretch()
        close_btn = QPushButton("x")
        close_btn.setObjectName("DangerButton")
        close_btn.setFixedWidth(28)
        close_btn.clicked.connect(self._on_close_panel)
        header.addWidget(close_btn)
        root.addLayout(header)

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

        settings_btn = QPushButton("Settings")
        settings_btn.clicked.connect(self._on_settings)
        toolbar1.addWidget(settings_btn)

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

        toolbar3 = QHBoxLayout()
        toolbar3.addWidget(QLabel("Selected:"))
        self._bulk_buttons = []
        for text, handler in (
            ("Enable", self._on_bulk_enable),
            ("Disable", self._on_bulk_disable),
            ("Delete", self._on_bulk_delete),
            ("Copy", self._on_copy),
            ("Paste", self._on_paste),
            ("Merge", self._on_merge),
            ("Split", self._on_split),
        ):
            btn = QPushButton(text)
            btn.clicked.connect(handler)
            toolbar3.addWidget(btn)
            self._bulk_buttons.append(btn)
        toolbar3.addStretch()
        root.addLayout(toolbar3)

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

        root.addWidget(QLabel("<b>Thread Log</b>"))
        self.log_box = QPlainTextEdit()
        self.log_box.setReadOnly(True)
        self.log_box.setFixedHeight(120)
        root.addWidget(self.log_box)

        self._update_record_label()
        self._update_undo_redo_buttons()
        self._update_start_button()
        self._update_lock_state()

    def _update_lock_state(self):
        """Disable everything that mutates the script/profile while it's running."""
        locked = self.running
        for w in (
            self.profile_combo, self.new_profile_btn, self.rename_profile_btn,
            self.delete_profile_btn, self.record_btn, self.loop_check, self.humanize_spin,
        ):
            w.setEnabled(not locked)
        for btn in self._bulk_buttons:
            btn.setEnabled(not locked)

    def _refresh_blocks_area(self):
        self.block_widgets.clear()
        panel_widget = BlockListPanel(self.script.blocks, self)
        self.scroll_area.setWidget(panel_widget)
        self.loop_check.blockSignals(True)
        self.loop_check.setChecked(self.script.loop)
        self.loop_check.blockSignals(False)
        self.humanize_spin.blockSignals(True)
        self.humanize_spin.setValue(self.script.humanize)
        self.humanize_spin.blockSignals(False)

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
        self._update_unsaved_indicator()
        self._update_undo_redo_buttons()
        self._update_start_button()
        self._refresh_blocks_area()

    def _on_redo(self):
        if self._undo_index >= len(self._undo_stack) - 1:
            return
        self._undo_index += 1
        self.script = Script.from_dict(self._undo_stack[self._undo_index])
        self._dirty = True
        self._update_unsaved_indicator()
        self._update_undo_redo_buttons()
        self._update_start_button()
        self._refresh_blocks_area()

    # -- dirty / save state ----------------------------------------------------

    def _update_unsaved_indicator(self):
        self.unsaved_label.setText("* unsaved" if self._dirty else "")

    def _update_start_button(self):
        try:
            validate_script(self.script)
            self.start_btn.setEnabled(not self.running)
            self.start_btn.setToolTip("")
        except ScriptValidationError as exc:
            self.start_btn.setEnabled(False)
            self.start_btn.setToolTip(str(exc))

    def _on_save(self):
        self.profile_manager.update_profile(self.current_profile, self.script)
        self._dirty = False
        self._update_unsaved_indicator()
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
        self.current_block_id = None
        self._update_unsaved_indicator()
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

    def _update_record_label(self):
        if self.is_recording:
            self.record_btn.setText(f"Stop Recording ({self.hotkey_config.format_hotkey('stop_record')})")
        else:
            self.record_btn.setText(f"Record ({self.hotkey_config.format_hotkey('start_record')})")

    def _on_toggle_recording(self):
        self.stop_recording() if self.is_recording else self.start_recording()

    def start_recording(self):
        if not IS_WINDOWS:
            QMessageBox.warning(self, "Not available", "Recording only works on Windows.")
            return
        if self.is_recording or self.running:
            return
        self.is_recording = True
        self._update_record_label()
        self.recorder = Recorder()
        self.recorder.start(record_mouse=self.hotkey_config.record_mouse)
        self._log("Recording started...")

    def stop_recording(self):
        if not self.is_recording or not self.recorder:
            return
        self.is_recording = False
        self._update_record_label()
        blocks = self.recorder.stop()
        self.recorder = None

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        name = f"Recording {timestamp}"
        new_script = Script(thread_name=name, blocks=blocks)
        self.profile_manager.add_profile(name, new_script)
        self.profile_combo.blockSignals(True)
        self.profile_combo.clear()
        self.profile_combo.addItems(self.profile_manager.get_profile_names())
        self.profile_combo.setCurrentText(name)
        self.profile_combo.blockSignals(False)
        self._load_profile(name)
        self._log(f"Recording stopped, saved as '{name}'")

    # -- settings -------------------------------------------------------------

    def _on_settings(self):
        def _on_saved():
            self._update_record_label()
            if self.on_hotkeys_changed:
                self.on_hotkeys_changed()
        SettingsDialog(self, self.hotkey_config, on_save=_on_saved).exec()

    # -- run / stop -------------------------------------------------------

    def start(self):
        if self.running or (self.executor and self.executor.is_alive()):
            return
        try:
            validate_script(self.script)
        except ScriptValidationError as exc:
            QMessageBox.warning(self, "Cannot start", str(exc))
            return

        self.running = True
        self.current_block_id = None
        self._refresh_blocks_area()
        self._update_undo_redo_buttons()
        self._update_lock_state()

        label = self.script.thread_name or f"Thread {self.panel_id}"
        self.executor = ScriptExecutor(self.script, label=label)
        self.executor.signals.log.connect(self._log)
        self.executor.signals.block_started.connect(self._on_block_started)
        self.executor.signals.block_finished.connect(self._on_block_finished)
        self.executor.signals.stopped.connect(self._on_executor_stopped)
        self.executor.start()

        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.status_label.setText("Running...")

    def stop(self):
        if self.executor:
            self.executor.stop()
        self.stop_btn.setEnabled(False)

    def _on_block_started(self, block_id):
        self.current_block_id = block_id
        widget = self.block_widgets.get(block_id)
        if widget:
            widget.set_current(True)

    def _on_block_finished(self, block_id):
        widget = self.block_widgets.get(block_id)
        if widget:
            widget.set_current(False)
        if self.current_block_id == block_id:
            self.current_block_id = None

    def _on_executor_stopped(self):
        self.running = False
        self.executor = None
        self.current_block_id = None
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.status_label.setText("Stopped")
        self._update_start_button()
        self._update_undo_redo_buttons()
        self._update_lock_state()
        self._refresh_blocks_area()

    # -- logging --------------------------------------------------------------

    def _log(self, message):
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_box.appendPlainText(f"[{timestamp}] {message}")

    # -- closing ------------------------------------------------------------

    def _on_close_panel(self):
        self.stop()
        if not self._confirm_discard_if_dirty():
            return
        if self.on_close:
            self.on_close(self.panel_id)

    # -- selection helpers (multi-select bulk actions) -----------------------

    def _all_list_widgets(self):
        return self.findChildren(BlockListWidget)

    def _selected_ids_everywhere(self):
        ids = []
        for lw in self._all_list_widgets():
            ids.extend(lw.selected_block_ids())
        return ids

    def _find_block_and_container(self, block_id, blocks=None):
        """Recursively find (block, container_list, index) for a block id."""
        blocks = self.script.blocks if blocks is None else blocks
        for i, b in enumerate(blocks):
            if b.id == block_id:
                return b, blocks, i
            if b.kind == "repeat":
                found = self._find_block_and_container(block_id, b.children)
                if found:
                    return found
        return None

    def _on_bulk_enable(self):
        self._bulk_set_enabled(True)

    def _on_bulk_disable(self):
        self._bulk_set_enabled(False)

    def _bulk_set_enabled(self, enabled):
        ids = self._selected_ids_everywhere()
        if not ids:
            return
        for block_id in ids:
            found = self._find_block_and_container(block_id)
            if found:
                found[0].enabled = enabled
        self.notify_change()

    def _on_bulk_delete(self):
        ids = self._selected_ids_everywhere()
        if not ids:
            return
        if QMessageBox.question(self, "Delete blocks", f"Delete {len(ids)} block(s)?") != QMessageBox.Yes:
            return
        for block_id in set(ids):
            found = self._find_block_and_container(block_id)
            if found:
                _, container, index = found
                del container[index]
        self.notify_change()

    def _active_list_widget(self):
        for lw in self._all_list_widgets():
            if lw.selected_block_ids():
                return lw
        return None

    def _on_copy(self):
        lw = self._active_list_widget()
        if not lw:
            return
        ids = set(lw.selected_block_ids())
        self._clipboard = [b.clone() for b in lw.blocks_ref if b.id in ids]
        self._log(f"Copied {len(self._clipboard)} block(s)")

    def _on_paste(self):
        if not self._clipboard:
            return
        lw = self._active_list_widget()
        target = lw.blocks_ref if lw is not None else self.script.blocks
        for b in self._clipboard:
            target.append(b.clone())
        self.notify_change()

    def _on_merge(self):
        lw = self._active_list_widget()
        if not lw:
            return
        ids = lw.selected_block_ids()
        if len(ids) < 2:
            QMessageBox.information(self, "Merge", "Select at least two blocks to merge.")
            return
        blocks = lw.blocks_ref
        selected = [b for b in blocks if b.id in ids]
        if any(b.kind != "block" for b in selected):
            QMessageBox.warning(self, "Merge", "Only plain blocks (not Repeat/Mouse Path) can be merged.")
            return
        merged_steps = []
        for b in selected:
            merged_steps.extend(b.steps)
        first_index = min(i for i, b in enumerate(blocks) if b.id in ids)
        blocks[:] = [b for b in blocks if b.id not in ids]
        blocks.insert(first_index, Block.new_block(merged_steps))
        self.notify_change()

    def _on_split(self):
        lw = self._active_list_widget()
        if not lw:
            return
        ids = lw.selected_block_ids()
        if len(ids) != 1:
            QMessageBox.information(self, "Split", "Select exactly one block to split.")
            return
        blocks = lw.blocks_ref
        index = next(i for i, b in enumerate(blocks) if b.id == ids[0])
        block = blocks[index]
        if block.kind != "block":
            QMessageBox.warning(self, "Split", "Only plain blocks can be split.")
            return
        if not block.steps:
            return
        new_blocks = [Block.new_block([s]) for s in block.steps]
        blocks[index:index + 1] = new_blocks
        self.notify_change()
