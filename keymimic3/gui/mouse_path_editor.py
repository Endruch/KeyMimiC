"""Dialog to inspect/edit the individual points of a Mouse Path block."""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTableWidget,
    QTableWidgetItem, QHeaderView, QDialogButtonBox, QMessageBox, QComboBox,
)

from ..model import MousePathPoint

_KIND_LABELS = [("move", "Move"), ("click", "Click"), ("right_click", "Right Click")]


class MousePathEditorDialog(QDialog):
    """Edits a list of mouse-path points. Result is in `self.result_points`."""

    def __init__(self, parent=None, points=None):
        super().__init__(parent)
        self.setWindowTitle("Edit Mouse Path")
        self.setMinimumSize(480, 480)
        self.result_points = None

        layout = QVBoxLayout(self)
        total_dt = sum(p.dt for p in (points or []))
        layout.addWidget(QLabel(
            f"{len(points or [])} point(s), {total_dt:.2f}s total. "
            "dx/dy are relative moves (ignored for clicks); dt is the delay before this point fires."
        ))

        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["Type", "dx", "dy", "delay before (s)"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        layout.addWidget(self.table)

        for p in points or []:
            self._add_row(p.dx, p.dy, p.dt, p.kind)

        buttons_row = QHBoxLayout()
        add_move_btn = QPushButton("+ Add move")
        add_move_btn.clicked.connect(lambda: self._add_row(0, 0, 0.0, "move"))
        add_click_btn = QPushButton("+ Add click")
        add_click_btn.clicked.connect(lambda: self._add_row(0, 0, 0.0, "click"))
        remove_btn = QPushButton("- Remove selected")
        remove_btn.clicked.connect(self._remove_selected)
        buttons_row.addWidget(add_move_btn)
        buttons_row.addWidget(add_click_btn)
        buttons_row.addWidget(remove_btn)
        buttons_row.addStretch()
        layout.addLayout(buttons_row)

        box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        box.accepted.connect(self._on_accept)
        box.rejected.connect(self.reject)
        layout.addWidget(box)

    def _add_row(self, dx, dy, dt, kind="move"):
        row = self.table.rowCount()
        self.table.insertRow(row)

        kind_combo = QComboBox()
        for value, label in _KIND_LABELS:
            kind_combo.addItem(label, value)
        idx = kind_combo.findData(kind)
        kind_combo.setCurrentIndex(idx if idx >= 0 else 0)
        self.table.setCellWidget(row, 0, kind_combo)

        self.table.setItem(row, 1, QTableWidgetItem(str(dx)))
        self.table.setItem(row, 2, QTableWidgetItem(str(dy)))
        self.table.setItem(row, 3, QTableWidgetItem(str(dt)))

    def _remove_selected(self):
        for row in sorted({i.row() for i in self.table.selectedIndexes()}, reverse=True):
            self.table.removeRow(row)

    def _on_accept(self):
        points = []
        for row in range(self.table.rowCount()):
            try:
                kind_combo = self.table.cellWidget(row, 0)
                kind = kind_combo.currentData()
                dx = int(float(self.table.item(row, 1).text()))
                dy = int(float(self.table.item(row, 2).text()))
                dt = float(self.table.item(row, 3).text())
            except (ValueError, AttributeError):
                QMessageBox.warning(self, "Invalid point", f"Row {row + 1} has an invalid number.")
                return
            points.append(MousePathPoint(dx, dy, dt, kind=kind))
        self.result_points = points
        self.accept()
