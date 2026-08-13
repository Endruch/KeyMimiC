"""
Action Picker dialog: choose a keyboard-track action (keyboard / sleep / log
/ wait-with-keys) and fill in its parameters, then produce a `Step`.

This is the entry point for adding or editing a step inside a "block"-kind
(keyboard-track) block. Mouse-track content is edited separately, through
MousePathEditorDialog - the two tracks use different data (Step vs
MousePathPoint), so there's no single shared "type" concept anymore.
"""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QStackedWidget, QWidget, QLabel,
    QPushButton, QRadioButton, QButtonGroup, QDoubleSpinBox,
    QLineEdit, QComboBox, QDialogButtonBox, QTableWidget, QTableWidgetItem,
    QHeaderView, QMessageBox,
)

from ..core.key_names import resolve_key
from ..model import Step
from .keyboard_picker import KeyboardPickerWidget

TYPE_PAGES = ["keyboard", "sleep", "log", "wait_with_keys"]
TYPE_LABELS = {
    "keyboard": "Keyboard",
    "sleep": "Sleep",
    "log": "Log",
    "wait_with_keys": "Wait + Tap Keys",
}


class ActionPickerDialog(QDialog):
    """Modal dialog that returns a `Step` in `self.result_step` if accepted."""

    def __init__(self, parent=None, initial_step: Step = None):
        super().__init__(parent)
        self.setWindowTitle("Add Action" if initial_step is None else "Edit Action")
        self.setMinimumWidth(520)
        self.result_step = None

        self._build_ui()
        if initial_step is not None:
            self._load_step(initial_step)

    # -- UI construction ------------------------------------------------------

    def _build_ui(self):
        root = QVBoxLayout(self)

        self.type_selector = QComboBox()
        for key in TYPE_PAGES:
            self.type_selector.addItem(TYPE_LABELS[key], key)
        self.type_selector.currentIndexChanged.connect(self._on_type_changed)
        root.addWidget(QLabel("Action type:"))
        root.addWidget(self.type_selector)

        self.stack = QStackedWidget()
        self.stack.addWidget(self._build_keyboard_page())
        self.stack.addWidget(self._build_sleep_page())
        self.stack.addWidget(self._build_log_page())
        self.stack.addWidget(self._build_wait_page())
        root.addWidget(self.stack)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

    def _build_keyboard_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)

        mode_row = QHBoxLayout()
        self.press_radio = QRadioButton("Press")
        self.release_radio = QRadioButton("Release")
        self.press_radio.setChecked(True)
        group = QButtonGroup(page)
        group.addButton(self.press_radio)
        group.addButton(self.release_radio)
        mode_row.addWidget(self.press_radio)
        mode_row.addWidget(self.release_radio)
        mode_row.addStretch()
        layout.addLayout(mode_row)

        self.keyboard_picker = KeyboardPickerWidget()
        layout.addWidget(self.keyboard_picker)

        duration_row = QHBoxLayout()
        self.press_duration = QDoubleSpinBox()
        self.press_duration.setRange(0.0, 3600.0)
        self.press_duration.setDecimals(2)
        self.press_duration.setSpecialValueText("no auto-release")
        self.press_duration.setSuffix(" s")
        duration_row.addWidget(QLabel("Hold for (Press only, 0 = leave held):"))
        duration_row.addWidget(self.press_duration)
        duration_row.addStretch()
        layout.addLayout(duration_row)

        return page

    def _build_sleep_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        row = QHBoxLayout()
        self.sleep_duration = QDoubleSpinBox()
        self.sleep_duration.setRange(0.0, 3600.0)
        self.sleep_duration.setDecimals(2)
        self.sleep_duration.setValue(1.0)
        self.sleep_duration.setSuffix(" s")
        self.sleep_variation = QDoubleSpinBox()
        self.sleep_variation.setRange(0.0, 3600.0)
        self.sleep_variation.setDecimals(2)
        self.sleep_variation.setSuffix(" s")
        row.addWidget(QLabel("Duration:"))
        row.addWidget(self.sleep_duration)
        row.addWidget(QLabel("+/- variation:"))
        row.addWidget(self.sleep_variation)
        row.addStretch()
        layout.addLayout(row)
        layout.addStretch()
        return page

    def _build_log_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        self.log_message = QLineEdit()
        self.log_message.setPlaceholderText("Message to write to the thread log")
        layout.addWidget(QLabel("Message:"))
        layout.addWidget(self.log_message)
        layout.addStretch()
        return page

    def _build_wait_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)

        row = QHBoxLayout()
        self.wait_duration = QDoubleSpinBox()
        self.wait_duration.setRange(0.0, 36000.0)
        self.wait_duration.setDecimals(1)
        self.wait_duration.setValue(10.0)
        self.wait_duration.setSuffix(" s")
        row.addWidget(QLabel("Total wait:"))
        row.addWidget(self.wait_duration)
        row.addStretch()
        layout.addLayout(row)

        layout.addWidget(QLabel("Tap these keys periodically while waiting:"))
        self.taps_table = QTableWidget(0, 2)
        self.taps_table.setHorizontalHeaderLabels(["Key", "Every (s)"])
        self.taps_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        layout.addWidget(self.taps_table)

        taps_buttons = QHBoxLayout()
        add_tap_btn = QPushButton("+ Add tap")
        add_tap_btn.clicked.connect(self._add_tap_row)
        remove_tap_btn = QPushButton("- Remove selected")
        remove_tap_btn.clicked.connect(self._remove_tap_row)
        taps_buttons.addWidget(add_tap_btn)
        taps_buttons.addWidget(remove_tap_btn)
        taps_buttons.addStretch()
        layout.addLayout(taps_buttons)

        return page

    def _add_tap_row(self, key="space", interval=2.0):
        row = self.taps_table.rowCount()
        self.taps_table.insertRow(row)
        self.taps_table.setItem(row, 0, QTableWidgetItem(key))
        self.taps_table.setItem(row, 1, QTableWidgetItem(str(interval)))

    def _remove_tap_row(self):
        for item in sorted({i.row() for i in self.taps_table.selectedIndexes()}, reverse=True):
            self.taps_table.removeRow(item)

    # -- state ----------------------------------------------------------------

    def _on_type_changed(self, combo_index):
        key = self.type_selector.itemData(combo_index)
        if key is not None:
            self.stack.setCurrentIndex(TYPE_PAGES.index(key))

    def _load_step(self, step: Step):
        type_key = {
            "press": "keyboard", "release": "keyboard",
            "sleep": "sleep", "log": "log", "wait_with_keys": "wait_with_keys",
        }.get(step.type, "keyboard")
        combo_index = self.type_selector.findData(type_key)
        if combo_index >= 0:
            self.type_selector.setCurrentIndex(combo_index)
        self.stack.setCurrentIndex(TYPE_PAGES.index(type_key))

        if step.type in ("press", "release"):
            (self.press_radio if step.type == "press" else self.release_radio).setChecked(True)
            if step.key:
                self.keyboard_picker.set_selected_key(step.key)
            self.press_duration.setValue(step.duration or 0.0)
        elif step.type == "sleep":
            self.sleep_duration.setValue(step.duration or 0.0)
            self.sleep_variation.setValue(step.variation or 0.0)
        elif step.type == "log":
            self.log_message.setText(step.message or "")
        elif step.type == "wait_with_keys":
            self.wait_duration.setValue(step.duration or 0.0)
            for tap in step.taps or []:
                self._add_tap_row(tap.get("key", ""), tap.get("interval", 1.0))

    def _on_accept(self):
        kind = TYPE_PAGES[self.stack.currentIndex()]
        try:
            step = self._build_step(kind)
        except ValueError as exc:
            QMessageBox.warning(self, "Invalid action", str(exc))
            return
        self.result_step = step
        self.accept()

    def _build_step(self, kind) -> Step:
        if kind == "keyboard":
            key = self.keyboard_picker.selected_key()
            if not key:
                raise ValueError("Pick a key on the keyboard.")
            resolve_key(key)  # validates
            if self.press_radio.isChecked():
                duration = self.press_duration.value()
                return Step(type="press", key=key, duration=duration if duration > 0 else None)
            return Step(type="release", key=key)

        if kind == "sleep":
            return Step(
                type="sleep",
                duration=self.sleep_duration.value(),
                variation=self.sleep_variation.value() or None,
            )

        if kind == "log":
            return Step(type="log", message=self.log_message.text())

        if kind == "wait_with_keys":
            taps = []
            for row in range(self.taps_table.rowCount()):
                key_item = self.taps_table.item(row, 0)
                interval_item = self.taps_table.item(row, 1)
                if not key_item or not key_item.text().strip():
                    continue
                key = key_item.text().strip()
                resolve_key(key)  # validates
                try:
                    interval = float(interval_item.text()) if interval_item else 1.0
                except ValueError:
                    raise ValueError(f"Invalid interval for key '{key}'.")
                taps.append({"key": key, "interval": interval})
            return Step(type="wait_with_keys", duration=self.wait_duration.value(), taps=taps)

        raise ValueError(f"Unknown action kind: {kind}")
