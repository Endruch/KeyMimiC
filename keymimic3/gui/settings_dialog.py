"""Settings dialog: configure global hotkeys and the record-mouse toggle."""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QCheckBox,
    QPushButton, QDialogButtonBox, QGridLayout,
)

from ..core.constants import SCAN_CODES
from ..core.key_names import get_key_display_name
from ..config.hotkeys import HotkeyConfig, ACTION_LABELS

_SORTED_KEYS = sorted(SCAN_CODES.keys(), key=lambda k: get_key_display_name(k))


class SettingsDialog(QDialog):
    """Edits a HotkeyConfig in place; calls on_save() after the user hits Save."""

    def __init__(self, parent, hotkey_config: HotkeyConfig, on_save=None):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.hotkey_config = hotkey_config
        self.on_save = on_save
        self._rows = {}

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("<b>Global Hotkeys</b> (work even while the window is minimized)"))

        grid = QGridLayout()
        grid.addWidget(QLabel("Action"), 0, 0)
        grid.addWidget(QLabel("Ctrl"), 0, 1)
        grid.addWidget(QLabel("Shift"), 0, 2)
        grid.addWidget(QLabel("Alt"), 0, 3)
        grid.addWidget(QLabel("Key"), 0, 4)

        for row, action in enumerate(("start", "stop", "start_record", "stop_record"), start=1):
            binding = hotkey_config.get_hotkey(action)
            grid.addWidget(QLabel(ACTION_LABELS.get(action, action)), row, 0)

            ctrl_check = QCheckBox()
            ctrl_check.setChecked(binding.get("ctrl", False))
            grid.addWidget(ctrl_check, row, 1)

            shift_check = QCheckBox()
            shift_check.setChecked(binding.get("shift", False))
            grid.addWidget(shift_check, row, 2)

            alt_check = QCheckBox()
            alt_check.setChecked(binding.get("alt", False))
            grid.addWidget(alt_check, row, 3)

            key_combo = QComboBox()
            for key_id in _SORTED_KEYS:
                key_combo.addItem(get_key_display_name(key_id), key_id)
            current_index = key_combo.findData(binding.get("key"))
            if current_index >= 0:
                key_combo.setCurrentIndex(current_index)
            grid.addWidget(key_combo, row, 4)

            self._rows[action] = (ctrl_check, shift_check, alt_check, key_combo)

        layout.addLayout(grid)

        self.record_mouse_check = QCheckBox("Record mouse movement while recording")
        self.record_mouse_check.setChecked(hotkey_config.record_mouse)
        layout.addWidget(self.record_mouse_check)

        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._on_save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _on_save(self):
        for action, (ctrl_check, shift_check, alt_check, key_combo) in self._rows.items():
            self.hotkey_config.set_hotkey(
                action,
                key_combo.currentData(),
                ctrl=ctrl_check.isChecked(),
                shift=shift_check.isChecked(),
                alt=alt_check.isChecked(),
            )
        self.hotkey_config.record_mouse = self.record_mouse_check.isChecked()
        self.hotkey_config.save()
        if self.on_save:
            self.on_save()
        self.accept()
