"""Visual QWERTY keyboard used to pick a key for press/release/wait_with_keys steps."""

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QPushButton

from ..core.key_names import KEYBOARD_LAYOUT, get_key_display_name


class KeyboardPickerWidget(QWidget):
    """A clickable QWERTY layout. Emits `key_selected(key_id)` on click."""

    key_selected = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._selected = None
        self._buttons = {}

        layout = QVBoxLayout(self)
        layout.setSpacing(4)
        layout.setContentsMargins(0, 0, 0, 0)

        for row in KEYBOARD_LAYOUT:
            row_layout = QHBoxLayout()
            row_layout.setSpacing(4)
            for key_id in row:
                label = get_key_display_name(key_id)
                btn = QPushButton(label)
                btn.setCheckable(True)
                width = 56 if len(label) > 3 else (30 if len(label) == 1 else 44)
                btn.setFixedSize(width, 30)
                btn.clicked.connect(lambda _checked=False, k=key_id: self._pick(k))
                self._buttons[key_id] = btn
                row_layout.addWidget(btn)
            row_layout.addStretch()
            layout.addLayout(row_layout)

    def _pick(self, key_id, emit=True):
        self._selected = key_id
        for k, btn in self._buttons.items():
            btn.setChecked(k == key_id)
        if emit:
            self.key_selected.emit(key_id)

    def selected_key(self):
        return self._selected

    def set_selected_key(self, key_id):
        """Programmatically select a key without emitting the signal."""
        self._pick(key_id, emit=False)
