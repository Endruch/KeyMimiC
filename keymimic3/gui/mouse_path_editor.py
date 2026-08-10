"""Dialog to inspect/edit the individual points of a Mouse Path block."""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTableWidget,
    QTableWidgetItem, QHeaderView, QDialogButtonBox, QMessageBox,
)

from ..model import MousePathPoint


class MousePathEditorDialog(QDialog):
    """Edits a list of (dx, dy, dt) points. Result is in `self.result_points`."""

    def __init__(self, parent=None, points=None):
        super().__init__(parent)
        self.setWindowTitle("Edit Mouse Path")
        self.setMinimumSize(420, 480)
        self.result_points = None

        layout = QVBoxLayout(self)
        total_dt = sum(p.dt for p in (points or []))
        layout.addWidget(QLabel(
            f"{len(points or [])} point(s), {total_dt:.2f}s total. "
            "dx/dy are relative to the previous point; dt is the delay before this move."
        ))

        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["dx", "dy", "delay before (s)"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        layout.addWidget(self.table)

        for p in points or []:
            self._add_row(p.dx, p.dy, p.dt)

        buttons_row = QHBoxLayout()
        add_btn = QPushButton("+ Add point")
        add_btn.clicked.connect(lambda: self._add_row(0, 0, 0.0))
        remove_btn = QPushButton("- Remove selected")
        remove_btn.clicked.connect(self._remove_selected)
        buttons_row.addWidget(add_btn)
        buttons_row.addWidget(remove_btn)
        buttons_row.addStretch()
        layout.addLayout(buttons_row)

        box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        box.accepted.connect(self._on_accept)
        box.rejected.connect(self.reject)
        layout.addWidget(box)

    def _add_row(self, dx, dy, dt):
        row = self.table.rowCount()
        self.table.insertRow(row)
        self.table.setItem(row, 0, QTableWidgetItem(str(dx)))
        self.table.setItem(row, 1, QTableWidgetItem(str(dy)))
        self.table.setItem(row, 2, QTableWidgetItem(str(dt)))

    def _remove_selected(self):
        for row in sorted({i.row() for i in self.table.selectedIndexes()}, reverse=True):
            self.table.removeRow(row)

    def _on_accept(self):
        points = []
        for row in range(self.table.rowCount()):
            try:
                dx = int(float(self.table.item(row, 0).text()))
                dy = int(float(self.table.item(row, 1).text()))
                dt = float(self.table.item(row, 2).text())
            except (ValueError, AttributeError):
                QMessageBox.warning(self, "Invalid point", f"Row {row + 1} has an invalid number.")
                return
            points.append(MousePathPoint(dx, dy, dt))
        self.result_points = points
        self.accept()
