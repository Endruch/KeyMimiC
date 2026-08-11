"""Settings dialog: configure global hotkeys and the record-mouse toggle."""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QCheckBox,
    QRadioButton, QButtonGroup, QDialogButtonBox, QGridLayout, QWidget,
)

from ..core.constants import SCAN_CODES
from ..core.key_names import get_key_display_name
from ..config.hotkeys import HotkeyConfig, ACTION_LABELS

_SORTED_KEYS = sorted(SCAN_CODES.keys(), key=lambda k: get_key_display_name(k))
_MODIFIERS = (("ctrl", "Ctrl"), ("shift", "Shift"), ("alt", "Alt"))


class SettingsDialog(QDialog):
    """
    Edits a HotkeyConfig in place; calls on_save() after the user hits Save.

    Every action requires exactly one modifier (enforced via an exclusive
    radio group per row), and the key dropdown of every row live-excludes
    whatever (modifier, key) combos are already used by the other rows, so a
    colliding hotkey simply can't be selected in the first place.
    """

    def __init__(self, parent, hotkey_config: HotkeyConfig, on_save=None):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.hotkey_config = hotkey_config
        self.on_save = on_save
        self._rows = {}
        self._updating = False

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("<b>Global Hotkeys</b> (work even while the window is minimized)"))
        note = QLabel(
            "Each action needs exactly one modifier; the same (modifier + key) combo can't be\n"
            "used twice. Modifier keys themselves are never recorded into a macro while recording."
        )
        note.setObjectName("MutedLabel")
        layout.addWidget(note)

        grid = QGridLayout()
        grid.addWidget(QLabel("Action"), 0, 0)
        grid.addWidget(QLabel("Modifier"), 0, 1)
        grid.addWidget(QLabel("Key"), 0, 2)

        for row, action in enumerate(("start", "stop", "start_record", "stop_record"), start=1):
            binding = hotkey_config.get_hotkey(action)
            grid.addWidget(QLabel(ACTION_LABELS.get(action, action)), row, 0)

            modifier_row = QHBoxLayout()
            modifier_row.setContentsMargins(0, 0, 0, 0)
            group = QButtonGroup(self)
            radios = {}
            for mod_name, label in _MODIFIERS:
                rb = QRadioButton(label)
                rb.setChecked(binding.get(mod_name, False))
                group.addButton(rb)
                modifier_row.addWidget(rb)
                radios[mod_name] = rb
                rb.toggled.connect(self._on_any_change)
            if not any(r.isChecked() for r in radios.values()):
                radios["shift"].setChecked(True)
            modifier_widget = QWidget()
            modifier_widget.setLayout(modifier_row)
            grid.addWidget(modifier_widget, row, 1)

            key_combo = QComboBox()
            key_combo.currentIndexChanged.connect(self._on_any_change)
            grid.addWidget(key_combo, row, 2)

            self._rows[action] = {
                "group": group, "radios": radios, "combo": key_combo,
                "current_key": binding.get("key", _SORTED_KEYS[0]),
            }

        layout.addLayout(grid)

        self.record_mouse_check = QCheckBox("Record mouse movement while recording")
        self.record_mouse_check.setChecked(hotkey_config.record_mouse)
        layout.addWidget(self.record_mouse_check)

        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._on_save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self._recompute_available_keys()

    # -- live collision prevention -------------------------------------------

    def _current_modifier(self, action) -> str:
        for mod_name, rb in self._rows[action]["radios"].items():
            if rb.isChecked():
                return mod_name
        return "shift"

    def _on_any_change(self, *_args):
        if self._updating:
            return
        for row in self._rows.values():
            data = row["combo"].currentData()
            if data:
                row["current_key"] = data
        self._recompute_available_keys()

    def _recompute_available_keys(self):
        self._updating = True
        try:
            for _ in range(6):  # tiny fixed-point iteration, 4 rows x ~70 keys
                changed = False
                wants = {a: (self._current_modifier(a), r["current_key"]) for a, r in self._rows.items()}
                for action, row in self._rows.items():
                    modifier = wants[action][0]
                    taken = {
                        wants[other][1] for other in self._rows
                        if other != action and wants[other][0] == modifier
                    }
                    allowed = [k for k in _SORTED_KEYS if k not in taken]
                    current_key = row["current_key"]
                    if current_key in taken or current_key not in allowed:
                        current_key = allowed[0] if allowed else _SORTED_KEYS[0]
                        row["current_key"] = current_key
                        wants[action] = (modifier, current_key)
                        changed = True

                    combo = row["combo"]
                    combo.blockSignals(True)
                    combo.clear()
                    for key_id in allowed:
                        combo.addItem(get_key_display_name(key_id), key_id)
                    idx = combo.findData(current_key)
                    combo.setCurrentIndex(idx if idx >= 0 else 0)
                    combo.blockSignals(False)
                if not changed:
                    break
        finally:
            self._updating = False

    # -- save -----------------------------------------------------------------

    def _on_save(self):
        for action, row in self._rows.items():
            modifier = self._current_modifier(action)
            self.hotkey_config.set_hotkey(
                action,
                row["combo"].currentData(),
                ctrl=(modifier == "ctrl"),
                shift=(modifier == "shift"),
                alt=(modifier == "alt"),
            )
        self.hotkey_config.record_mouse = self.record_mouse_check.isChecked()
        self.hotkey_config.save()
        if self.on_save:
            self.on_save()
        self.accept()
