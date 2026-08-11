"""
Widgets for the block editor: a draggable list of block "cards", each card
rendering its own kind (plain block / repeat / mouse path), and a draggable
list of step rows inside a plain block's card.

Mutation strategy: every widget here mutates the live Script/Block/Step
objects it was given directly (they're plain Python objects, passed by
reference), then calls `panel.notify_change()`. The panel owns undo/save
state and is responsible for re-rendering the whole tree from the (now
updated) data - see ThreadPanel.notify_change(). This keeps every widget
here "dumb": no widget tries to patch itself in place, which sidesteps a
whole class of stale-index/partial-update bugs.
"""

from PySide6.QtCore import Qt, QMimeData
from PySide6.QtGui import QDrag
from PySide6.QtWidgets import (
    QFrame, QLabel, QPushButton, QSpinBox,
    QPlainTextEdit, QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem,
    QAbstractItemView, QColorDialog, QMessageBox, QWidget, QStackedWidget,
)

from ..model import Block, Step
from . import styles
from .action_picker import ActionPickerDialog
from .mouse_path_editor import MousePathEditorDialog

BLOCK_MIME = "application/x-keymimic-block"
STEP_MIME = "application/x-keymimic-step"

KIND_TITLES = {"block": "Block", "repeat": "Repeat", "mouse_path": "Mouse Path"}


def _collect_descendant_lists(block: Block):
    """Yield every children-list reachable inside `block` (repeat blocks only)."""
    if block.kind == "repeat":
        yield block.children
        for child in block.children:
            yield from _collect_descendant_lists(child)


# ---------------------------------------------------------------------------
# Step rows (inside a plain "block")
# ---------------------------------------------------------------------------

class StepRowWidget(QFrame):
    """One step inside a block: text summary, edit button, remove button."""

    def __init__(self, step: Step, index: int, block: Block, panel, step_list, parent=None):
        super().__init__(parent)
        self.step = step
        self.index = index
        self.block = block
        self.panel = panel
        self.step_list = step_list  # the owning StepListWidget (for drag)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(3, 1, 3, 1)
        layout.setSpacing(4)

        handle = QLabel("::")
        handle.setFixedWidth(12)
        handle.setStyleSheet(f"color: {styles.TEXT_MUTED};")
        handle.setCursor(Qt.SizeAllCursor)
        handle.mousePressEvent = self._handle_press
        handle.mouseMoveEvent = self._handle_move
        self._drag_start_pos = None
        layout.addWidget(handle)

        text = QLabel(step.to_text())
        text.setStyleSheet("font-family: Consolas, monospace; font-size: 12px;")
        layout.addWidget(text, stretch=1)

        edit_btn = QPushButton("Edit")
        edit_btn.setFixedWidth(38)
        edit_btn.clicked.connect(self._on_edit)
        layout.addWidget(edit_btn)

        remove_btn = QPushButton("-")
        remove_btn.setFixedWidth(22)
        remove_btn.clicked.connect(self._on_remove)
        layout.addWidget(remove_btn)

        self.setEnabled(not panel.is_locked())

    def _on_edit(self):
        dlg = ActionPickerDialog(self.window(), initial_step=self.step)
        if dlg.exec() and dlg.result_step is not None:
            self.block.steps[self.index] = dlg.result_step
            self.panel.notify_change()

    def _on_remove(self):
        del self.block.steps[self.index]
        self.panel.notify_change()

    def _handle_press(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_start_pos = event.position().toPoint()

    def _handle_move(self, event):
        if self._drag_start_pos is None or self.panel.is_locked():
            return
        if (event.position().toPoint() - self._drag_start_pos).manhattanLength() < 10:
            return
        drag = QDrag(self)
        mime = QMimeData()
        mime.setData(STEP_MIME, str(self.index).encode())
        mime.setProperty("source_steps_id", id(self.block.steps))
        drag.setMimeData(mime)
        drag.exec(Qt.MoveAction)
        self._drag_start_pos = None


class StepListWidget(QListWidget):
    """Draggable, reorderable list of a block's steps."""

    def __init__(self, block: Block, panel, parent=None):
        super().__init__(parent)
        self.block = block
        self.panel = panel
        self.setFrameShape(QFrame.NoFrame)
        self.setAcceptDrops(True)
        self.setSelectionMode(QAbstractItemView.NoSelection)
        self.setVerticalScrollMode(QListWidget.ScrollPerPixel)
        self.setSpacing(1)
        self._render()

    def _render(self):
        self.clear()
        for i, step in enumerate(self.block.steps):
            item = QListWidgetItem()
            row = StepRowWidget(step, i, self.block, self.panel, self)
            item.setSizeHint(row.sizeHint())
            self.addItem(item)
            self.setItemWidget(item, row)
        total_height = sum(self.sizeHintForRow(i) for i in range(self.count())) + 4
        self.setFixedHeight(max(total_height, 4))

    def dragEnterEvent(self, event):
        if event.mimeData().hasFormat(STEP_MIME):
            event.acceptProposedAction()

    def dragMoveEvent(self, event):
        if event.mimeData().hasFormat(STEP_MIME):
            event.acceptProposedAction()

    def dropEvent(self, event):
        mime = event.mimeData()
        if not mime.hasFormat(STEP_MIME):
            return
        if mime.property("source_steps_id") != id(self.block.steps):
            event.ignore()
            return
        try:
            old_index = int(bytes(mime.data(STEP_MIME)).decode())
        except (ValueError, TypeError):
            event.ignore()
            return

        target_item = self.itemAt(event.position().toPoint())
        raw_index = self.row(target_item) if target_item else len(self.block.steps) - 1
        raw_index = max(0, min(raw_index, len(self.block.steps) - 1))
        # Removing old_index first shifts everything after it down by one, so the
        # drop target's effective index must be adjusted when dragging downward.
        new_index = raw_index - 1 if old_index < raw_index else raw_index

        step = self.block.steps.pop(old_index)
        new_index = max(0, min(new_index, len(self.block.steps)))
        self.block.steps.insert(new_index, step)
        event.acceptProposedAction()
        self.panel.notify_change()


# ---------------------------------------------------------------------------
# Block cards
# ---------------------------------------------------------------------------

class BlockCardWidget(QFrame):
    """Renders one Block (any kind) as a card, and owns its own body content."""

    def __init__(self, block: Block, owner_list, panel, parent=None):
        super().__init__(parent)
        self.block = block
        self.owner_list = owner_list  # BlockListWidget this card lives in (for drag)
        self.panel = panel
        self.setObjectName("BlockCard")
        self._selected = False

        outer = QVBoxLayout(self)
        outer.setContentsMargins(5, 3, 5, 3)
        outer.setSpacing(3)

        outer.addLayout(self._build_header())

        self.body_container = QWidget()
        self.body_layout = QVBoxLayout(self.body_container)
        self.body_layout.setContentsMargins(15, 2, 0, 0)
        self.body_layout.setSpacing(3)
        outer.addWidget(self.body_container)
        self._build_body()

        self.body_container.setVisible(not block.collapsed)
        self._apply_style()
        self.panel.block_widgets[block.id] = self

    # -- header -----------------------------------------------------------

    def _build_header(self):
        row = QHBoxLayout()
        row.setSpacing(3)

        handle = QLabel("::")
        handle.setFixedWidth(12)
        handle.setCursor(Qt.SizeAllCursor)
        handle.setStyleSheet(f"color: {styles.TEXT_MUTED};")
        handle.mousePressEvent = self._handle_press
        handle.mouseMoveEvent = self._handle_move
        self._drag_start_pos = None
        row.addWidget(handle)

        self.enabled_btn = QPushButton()
        self.enabled_btn.setFixedWidth(30)
        self.enabled_btn.setToolTip("Enable/disable this block")
        self.enabled_btn.clicked.connect(self._on_toggle_enabled)
        self._update_enabled_btn()
        row.addWidget(self.enabled_btn)

        self.collapse_btn = QPushButton("v" if not self.block.collapsed else ">")
        self.collapse_btn.setFixedWidth(20)
        self.collapse_btn.clicked.connect(self._on_toggle_collapsed)
        row.addWidget(self.collapse_btn)

        self.color_btn = QPushButton()
        self.color_btn.setFixedSize(15, 15)
        self.color_btn.setToolTip("Pick a custom color")
        self.color_btn.clicked.connect(self._on_pick_color)
        row.addWidget(self.color_btn)

        auto_color_btn = QPushButton("A")
        auto_color_btn.setFixedSize(15, 15)
        auto_color_btn.setToolTip("Reset to automatic color")
        auto_color_btn.clicked.connect(self._on_auto_color)
        row.addWidget(auto_color_btn)

        title = KIND_TITLES.get(self.block.kind, "Block")
        self.title_label = QLabel(f"<b>{title}</b>")
        row.addWidget(self.title_label)

        self.summary_label = QLabel(self.block.summary())
        self.summary_label.setObjectName("MutedLabel")
        self.summary_label.setStyleSheet(f"color: {styles.TEXT_MUTED};")
        row.addWidget(self.summary_label, stretch=1)

        dup_btn = QPushButton("Duplicate")
        dup_btn.clicked.connect(self._on_duplicate)
        row.addWidget(dup_btn)

        delete_btn = QPushButton("x")
        delete_btn.setObjectName("DangerButton")
        delete_btn.setFixedWidth(22)
        delete_btn.setToolTip("Delete this block")
        delete_btn.clicked.connect(self._on_delete)
        row.addWidget(delete_btn)

        for w in (self.enabled_btn, self.collapse_btn, self.color_btn, auto_color_btn,
                  dup_btn, delete_btn):
            w.setEnabled(not self.panel.is_locked())

        return row

    def _update_enabled_btn(self):
        self.enabled_btn.setText("ON" if self.block.enabled else "OFF")
        self.enabled_btn.setStyleSheet(styles.toggle_button_stylesheet(self.block.enabled))

    def _on_toggle_enabled(self):
        self.block.enabled = not self.block.enabled
        self.panel.notify_change()

    def _on_toggle_collapsed(self):
        self.block.collapsed = not self.block.collapsed
        self.panel.notify_change()

    def _on_pick_color(self):
        color = QColorDialog.getColor(parent=self.window())
        if color.isValid():
            self.block.color = color.name()
            self.panel.notify_change()

    def _on_auto_color(self):
        self.block.color = None
        self.panel.notify_change()

    def _on_duplicate(self):
        clone = self.block.clone()
        blocks = self.owner_list.blocks_ref
        idx = next((i for i, b in enumerate(blocks) if b.id == self.block.id), len(blocks) - 1)
        blocks.insert(idx + 1, clone)
        self.panel.notify_change()

    def _on_delete(self):
        blocks = self.owner_list.blocks_ref
        blocks[:] = [b for b in blocks if b.id != self.block.id]
        self.panel.notify_change()

    def _handle_press(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_start_pos = event.position().toPoint()

    def _handle_move(self, event):
        if self._drag_start_pos is None or self.panel.is_locked():
            return
        if (event.position().toPoint() - self._drag_start_pos).manhattanLength() < 10:
            return
        drag = QDrag(self)
        mime = QMimeData()
        mime.setData(BLOCK_MIME, self.block.id.encode())
        mime.setProperty("source_widget", self.owner_list)
        drag.setMimeData(mime)
        drag.exec(Qt.MoveAction)
        self._drag_start_pos = None

    # -- body ---------------------------------------------------------------

    def _build_body(self):
        if self.block.kind == "block":
            self._build_plain_block_body()
        elif self.block.kind == "repeat":
            self._build_repeat_body()
        elif self.block.kind == "mouse_path":
            self._build_mouse_path_body()

    def _build_plain_block_body(self):
        self.body_stack = QStackedWidget()
        self.body_layout.addWidget(self.body_stack)

        # Page 0: step rows + add button
        steps_page = QWidget()
        steps_layout = QVBoxLayout(steps_page)
        steps_layout.setContentsMargins(0, 0, 0, 0)
        self.step_list = StepListWidget(self.block, self.panel)
        steps_layout.addWidget(self.step_list)

        add_row = QHBoxLayout()
        add_step_btn = QPushButton("+")
        add_step_btn.setFixedWidth(28)
        add_step_btn.setToolTip("Add a step to this block")
        add_step_btn.clicked.connect(self._on_add_step)
        add_step_btn.setEnabled(not self.panel.is_locked())
        add_row.addWidget(add_step_btn)

        text_toggle_btn = QPushButton("</> Edit as text")
        text_toggle_btn.clicked.connect(self._on_toggle_text_mode)
        text_toggle_btn.setEnabled(not self.panel.is_locked())
        add_row.addWidget(text_toggle_btn)
        add_row.addStretch()
        steps_layout.addLayout(add_row)

        self.body_stack.addWidget(steps_page)

        # Page 1: mini text editor
        text_page = QWidget()
        text_layout = QVBoxLayout(text_page)
        text_layout.setContentsMargins(0, 0, 0, 0)
        self.text_editor = QPlainTextEdit()
        self.text_editor.setPlainText("\n".join(s.to_text() for s in self.block.steps))
        self.text_editor.setFixedHeight(120)
        text_layout.addWidget(self.text_editor)

        text_buttons = QHBoxLayout()
        apply_btn = QPushButton("Apply")
        apply_btn.clicked.connect(self._on_apply_text)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self._on_cancel_text_mode)
        text_buttons.addWidget(apply_btn)
        text_buttons.addWidget(cancel_btn)
        text_buttons.addStretch()
        text_layout.addLayout(text_buttons)

        self.body_stack.addWidget(text_page)

    def _on_add_step(self):
        dlg = ActionPickerDialog(self.window())
        if dlg.exec() and dlg.result_step is not None:
            self.block.steps.append(dlg.result_step)
            self.panel.notify_change()

    def _on_toggle_text_mode(self):
        self.body_stack.setCurrentIndex(1)
        self.text_editor.setPlainText("\n".join(s.to_text() for s in self.block.steps))
        self.sync_item_size()

    def _on_cancel_text_mode(self):
        self.body_stack.setCurrentIndex(0)
        self.sync_item_size()

    def _on_apply_text(self):
        lines = [ln for ln in self.text_editor.toPlainText().splitlines() if ln.strip()]
        new_steps = []
        for i, line in enumerate(lines, start=1):
            try:
                new_steps.append(Step.from_text(line))
            except ValueError as exc:
                QMessageBox.warning(self, "Invalid step", f"Line {i}: {exc}")
                return
        self.block.steps = new_steps
        self.panel.notify_change()

    def _build_repeat_body(self):
        count_row = QHBoxLayout()
        count_row.addWidget(QLabel("Repeat count:"))
        self.count_spin = QSpinBox()
        self.count_spin.setRange(1, 100000)
        self.count_spin.setValue(self.block.count)
        self.count_spin.setEnabled(not self.panel.is_locked())
        self.count_spin.editingFinished.connect(self._on_count_changed)
        count_row.addWidget(self.count_spin)
        count_row.addStretch()
        self.body_layout.addLayout(count_row)

        nested = BlockListPanel(self.block.children, self.panel)
        self.body_layout.addWidget(nested)

    def _on_count_changed(self):
        self.block.count = self.count_spin.value()
        self.panel.notify_change()

    def _build_mouse_path_body(self):
        row = QHBoxLayout()
        edit_btn = QPushButton("Edit points...")
        edit_btn.setEnabled(not self.panel.is_locked())
        edit_btn.clicked.connect(self._on_edit_points)
        row.addWidget(edit_btn)
        row.addStretch()
        self.body_layout.addLayout(row)

    def _on_edit_points(self):
        dlg = MousePathEditorDialog(self.window(), points=self.block.points)
        if dlg.exec() and dlg.result_points is not None:
            self.block.points = dlg.result_points
            self.panel.notify_change()

    # -- visual state ---------------------------------------------------------

    def _apply_style(self):
        color = self.block.color or styles.TYPE_COLORS.get(self.block.dominant_type, styles.TYPE_COLORS["empty"])
        is_current = self.panel.is_current_block(self.block.id)
        self.setStyleSheet(styles.block_card_stylesheet(
            color, disabled=not self.block.enabled, is_current=is_current, selected=self._selected
        ))
        if not self.block.color:
            self.color_btn.setStyleSheet(
                f"background-color: {color}; border-radius: 4px; border: 1px solid {styles.BORDER};"
            )
        else:
            self.color_btn.setStyleSheet(
                f"background-color: {self.block.color}; border-radius: 4px; border: 1px solid {styles.BORDER};"
            )

    def set_current(self, is_current: bool):
        color = self.block.color or styles.TYPE_COLORS.get(self.block.dominant_type, styles.TYPE_COLORS["empty"])
        self.setStyleSheet(styles.block_card_stylesheet(
            color, disabled=not self.block.enabled, is_current=is_current, selected=self._selected
        ))

    def set_selected(self, selected: bool):
        self._selected = selected
        self._apply_style()

    def sync_item_size(self):
        """Ask the owning list to re-measure this card's item (e.g. after a
        body content swap that doesn't go through a full notify_change rebuild)."""
        if self.owner_list:
            self.owner_list.sync_item_size(self)


# ---------------------------------------------------------------------------
# Block list (top-level, or one repeat's children)
# ---------------------------------------------------------------------------

class BlockListWidget(QListWidget):
    """Draggable, multi-selectable list of block cards for one list of Blocks."""

    def __init__(self, blocks_ref: list, panel, parent=None):
        super().__init__(parent)
        self.blocks_ref = blocks_ref
        self.panel = panel
        self.setFrameShape(QFrame.NoFrame)
        self.setAcceptDrops(True)
        self.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.setVerticalScrollMode(QListWidget.ScrollPerPixel)
        self.setSpacing(4)
        self.itemSelectionChanged.connect(self._sync_selection_visuals)
        self._render()

    def _render(self):
        self.clear()
        for block in self.blocks_ref:
            item = QListWidgetItem()
            item.setData(Qt.UserRole, block.id)
            card = BlockCardWidget(block, self, self.panel)
            item.setSizeHint(card.sizeHint())
            self.addItem(item)
            self.setItemWidget(item, card)
        total_height = sum(self.sizeHintForRow(i) for i in range(self.count())) + 8
        self.setMinimumHeight(min(total_height, 4000))

    def _sync_selection_visuals(self):
        for i in range(self.count()):
            item = self.item(i)
            card = self.itemWidget(item)
            if card:
                card.set_selected(item.isSelected())

    def selected_block_ids(self):
        return [self.item(i).data(Qt.UserRole) for i in range(self.count()) if self.item(i).isSelected()]

    def sync_item_size(self, card):
        """Re-measure the item hosting `card` (its content size changed in place)."""
        for i in range(self.count()):
            item = self.item(i)
            if self.itemWidget(item) is card:
                item.setSizeHint(card.sizeHint())
                break

    def peek_block(self, block_id):
        """Find a block by id without removing it."""
        return next((b for b in self.blocks_ref if b.id == block_id), None)

    def take_block(self, block_id):
        """Find and remove a block by id, returning it (or None if not found)."""
        for i, b in enumerate(self.blocks_ref):
            if b.id == block_id:
                return self.blocks_ref.pop(i)
        return None

    # -- drag & drop --------------------------------------------------------
    #
    # Blocks can be dropped into ANY BlockListWidget - the same list (reorder),
    # a different nesting level within the same panel (e.g. root <-> inside a
    # Repeat), or a list belonging to a completely different open ThreadPanel.
    # The dragged block's identity is carried via a direct object reference to
    # its source BlockListWidget (QMimeData.setProperty), which only works for
    # in-process drags - fine here, dragging out of the app isn't a thing.

    def dragEnterEvent(self, event):
        if event.mimeData().hasFormat(BLOCK_MIME) and not self.panel.is_locked():
            event.acceptProposedAction()
            self._set_drop_highlight(True)

    def dragMoveEvent(self, event):
        if event.mimeData().hasFormat(BLOCK_MIME) and not self.panel.is_locked():
            event.acceptProposedAction()

    def dragLeaveEvent(self, event):
        self._set_drop_highlight(False)

    def _set_drop_highlight(self, active):
        if active:
            self.setStyleSheet(
                f"QListWidget {{ border: 2px dashed {styles.DROP_TARGET_BORDER}; border-radius: 6px; }}"
            )
        else:
            self.setStyleSheet("")

    def dropEvent(self, event):
        self._set_drop_highlight(False)
        if self.panel.is_locked():
            event.ignore()
            return

        mime = event.mimeData()
        if not mime.hasFormat(BLOCK_MIME):
            return
        source_widget = mime.property("source_widget")
        if source_widget is None:
            event.ignore()
            return
        block_id = bytes(mime.data(BLOCK_MIME)).decode()

        if source_widget is self:
            self._reorder_within(block_id, event)
            return

        if source_widget.panel.is_locked():
            event.ignore()
            return

        dragged = source_widget.peek_block(block_id)
        if dragged is None:
            event.ignore()
            return
        if any(lst is self.blocks_ref for lst in _collect_descendant_lists(dragged)):
            # Can't drop a Repeat block inside its own (possibly nested) children.
            event.ignore()
            return

        block = source_widget.take_block(block_id)
        if block is None:
            event.ignore()
            return

        target_item = self.itemAt(event.position().toPoint())
        new_index = self.row(target_item) if target_item else len(self.blocks_ref)
        new_index = max(0, min(new_index, len(self.blocks_ref)))
        self.blocks_ref.insert(new_index, block)
        event.acceptProposedAction()

        source_widget.panel.notify_change()
        if self.panel is not source_widget.panel:
            self.panel.notify_change()

    def _reorder_within(self, block_id, event):
        old_index = next((i for i, b in enumerate(self.blocks_ref) if b.id == block_id), None)
        if old_index is None:
            event.ignore()
            return

        target_item = self.itemAt(event.position().toPoint())
        raw_index = self.row(target_item) if target_item else len(self.blocks_ref) - 1
        raw_index = max(0, min(raw_index, len(self.blocks_ref) - 1))
        # Removing old_index first shifts everything after it down by one, so the
        # drop target's effective index must be adjusted when dragging downward.
        new_index = raw_index - 1 if old_index < raw_index else raw_index

        block = self.blocks_ref.pop(old_index)
        new_index = max(0, min(new_index, len(self.blocks_ref)))
        self.blocks_ref.insert(new_index, block)
        event.acceptProposedAction()
        self.panel.notify_change()


class BlockListPanel(QWidget):
    """A BlockListWidget plus its own trailing '+ Add Block' button."""

    def __init__(self, blocks_ref: list, panel, parent=None):
        super().__init__(parent)
        self.blocks_ref = blocks_ref
        self.panel = panel

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        self.list_widget = BlockListWidget(blocks_ref, panel, self)
        layout.addWidget(self.list_widget)

        add_row = QHBoxLayout()
        self.add_btn = QPushButton("+ Add Block")
        self.add_btn.setObjectName("PrimaryButton")
        self.add_btn.clicked.connect(self._on_add_block)
        self.add_btn.setEnabled(not panel.is_locked())
        add_row.addWidget(self.add_btn)

        add_repeat_btn = QPushButton("+ Add Repeat")
        add_repeat_btn.clicked.connect(self._on_add_repeat)
        add_repeat_btn.setEnabled(not panel.is_locked())
        add_row.addWidget(add_repeat_btn)
        add_row.addStretch()
        layout.addLayout(add_row)

    def _on_add_block(self):
        dlg = ActionPickerDialog(self.window())
        if dlg.exec() and dlg.result_step is not None:
            self.blocks_ref.append(Block.new_block([dlg.result_step]))
            self.panel.notify_change()

    def _on_add_repeat(self):
        self.blocks_ref.append(Block.new_repeat(count=2, children=[]))
        self.panel.notify_change()
