"""Dialog to inspect/edit the individual points of a Mouse Path block."""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTableWidget,
    QTableWidgetItem, QHeaderView, QDialogButtonBox, QMessageBox, QComboBox,
)

from ..model import MousePathPoint

_KIND_LABELS = [
    ("move", "Move to"),
    ("left_down", "Left button down"),
    ("left_up", "Left button up"),
    ("right_down", "Right button down"),
    ("right_up", "Right button up"),
]


class MousePathEditorDialog(QDialog):
    """Edits a list of mouse-path points. Result is in `self.result_points`."""

    def __init__(self, parent=None, points=None):
        super().__init__(parent)
        self.setWindowTitle("Edit Mouse Path")
        self.setMinimumSize(520, 480)
        self.result_points = None

        layout = QVBoxLayout(self)
        total_dt = sum(p.dt for p in (points or []))
        layout.addWidget(QLabel(
            f"{len(points or [])} point(s), {total_dt:.2f}s total. "
            "x/y are absolute screen coordinates (ignored for button events); "
            "dt is the delay before this point fires."
        ))

        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["Type", "x", "y", "delay before (s)"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        layout.addWidget(self.table)

        for p in points or []:
            self._add_row(p.x, p.y, p.dt, p.kind)

        buttons_row = QHBoxLayout()
        add_move_btn = QPushButton("+ Add move")
        add_move_btn.clicked.connect(lambda: self._add_row(0, 0, 0.0, "move"))
        add_left_btn = QPushButton("+ Add left click (down+up)")
        add_left_btn.clicked.connect(self._add_left_click_pair)
        add_right_btn = QPushButton("+ Add right click (down+up)")
        add_right_btn.clicked.connect(self._add_right_click_pair)
        remove_btn = QPushButton("- Remove selected")
        remove_btn.clicked.connect(self._remove_selected)
        buttons_row.addWidget(add_move_btn)
        buttons_row.addWidget(add_left_btn)
        buttons_row.addWidget(add_right_btn)
        buttons_row.addWidget(remove_btn)
        buttons_row.addStretch()
        layout.addLayout(buttons_row)

        box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        box.accepted.connect(self._on_accept)
        box.rejected.connect(self.reject)
        layout.addWidget(box)

    def _add_row(self, x, y, dt, kind="move"):
        row = self.table.rowCount()
        self.table.insertRow(row)

        kind_combo = QComboBox()
        for value, label in _KIND_LABELS:
            kind_combo.addItem(label, value)
        idx = kind_combo.findData(kind)
        kind_combo.setCurrentIndex(idx if idx >= 0 else 0)
        self.table.setCellWidget(row, 0, kind_combo)

        self.table.setItem(row, 1, QTableWidgetItem(str(x)))
        self.table.setItem(row, 2, QTableWidgetItem(str(y)))
        self.table.setItem(row, 3, QTableWidgetItem(str(dt)))

    def _add_left_click_pair(self):
        # A short, real duration between down/up (not instantaneous) - a
        # quick tap. Recorded clicks will have whatever the real hold was.
        self._add_row(0, 0, 0.0, "left_down")
        self._add_row(0, 0, 0.05, "left_up")

    def _add_right_click_pair(self):
        self._add_row(0, 0, 0.0, "right_down")
        self._add_row(0, 0, 0.05, "right_up")

    def _remove_selected(self):
        for row in sorted({i.row() for i in self.table.selectedIndexes()}, reverse=True):
            self.table.removeRow(row)

    def _on_accept(self):
        points = []
        for row in range(self.table.rowCount()):
            try:
                kind_combo = self.table.cellWidget(row, 0)
                kind = kind_combo.currentData()
                x = int(float(self.table.item(row, 1).text()))
                y = int(float(self.table.item(row, 2).text()))
                dt = float(self.table.item(row, 3).text())
            except (ValueError, AttributeError):
                QMessageBox.warning(self, "Invalid point", f"Row {row + 1} has an invalid number.")
                return
            points.append(MousePathPoint(kind=kind, x=x, y=y, dt=dt))
        self.result_points = points
        self.accept()
