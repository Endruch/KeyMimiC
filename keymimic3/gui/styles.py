"""Color palette and application-wide stylesheet (dark theme)."""

# Auto color tag per block "dominant_type" (see model.Block.dominant_type).
TYPE_COLORS = {
    "keyboard": "#3b82f6",  # blue
    "mouse": "#ec4899",     # pink
    "sleep": "#f59e0b",     # amber
    "log": "#10b981",       # green
    "wait": "#8b5cf6",      # purple
    "repeat": "#f97316",    # orange
    "empty": "#6b7280",     # gray
}

DISABLED_COLOR = "#5b5f66"      # overrides type color when a block is disabled
CURRENT_BLOCK_BORDER = "#22d3ee"  # live-highlight border while a block executes
SELECTED_BORDER = "#eab308"       # border used for multi-selected blocks
DROP_TARGET_BORDER = "#22d3ee"    # highlight around a list while a block is dragged over it

ENABLED_ON_COLOR = "#16a34a"    # ON/OFF toggle button when the block is enabled
DISABLED_OFF_COLOR = "#4b4f56"  # ON/OFF toggle button when the block is disabled

BACKGROUND = "#1e1f22"
PANEL_BG = "#26282c"
CARD_BG = "#2f3136"
CARD_BG_DISABLED = "#28292c"
BORDER = "#3a3d42"
TEXT = "#e6e6e6"
TEXT_MUTED = "#9a9da3"
ACCENT = "#3b82f6"
DANGER = "#ef4444"

APP_STYLESHEET = f"""
QWidget {{
    background-color: {BACKGROUND};
    color: {TEXT};
    font-family: "Segoe UI", "Helvetica Neue", Arial, sans-serif;
    font-size: 12px;
}}

QMainWindow, QDialog {{
    background-color: {BACKGROUND};
}}

QFrame#ThreadPanel {{
    background-color: {PANEL_BG};
    border: 1px solid {BORDER};
    border-radius: 8px;
}}

QPushButton {{
    background-color: #35373c;
    border: 1px solid {BORDER};
    border-radius: 4px;
    padding: 2px 7px;
    color: {TEXT};
}}
QPushButton:hover {{
    background-color: #3f4247;
}}
QPushButton:pressed {{
    background-color: #26282c;
}}
QPushButton:disabled {{
    color: {TEXT_MUTED};
    background-color: #2a2c30;
}}

QPushButton#PrimaryButton {{
    background-color: {ACCENT};
    border: 1px solid {ACCENT};
    color: white;
    font-weight: 600;
}}
QPushButton#PrimaryButton:hover {{
    background-color: #2f6fe0;
}}

QPushButton#DangerButton {{
    background-color: transparent;
    border: 1px solid {DANGER};
    color: {DANGER};
}}
QPushButton#DangerButton:hover {{
    background-color: {DANGER};
    color: white;
}}

QLineEdit, QPlainTextEdit, QTextEdit, QSpinBox, QDoubleSpinBox, QComboBox {{
    background-color: #1c1d20;
    border: 1px solid {BORDER};
    border-radius: 4px;
    padding: 2px 4px;
    color: {TEXT};
    selection-background-color: {ACCENT};
}}

QListWidget {{
    background-color: transparent;
    border: none;
}}
QListWidget::item {{
    background: transparent;
    border: none;
    margin: 1px 0px;
}}
QListWidget::item:selected {{
    background: transparent;
}}

QLabel#MutedLabel {{
    color: {TEXT_MUTED};
}}

QLabel#UnsavedIndicator {{
    color: {DANGER};
    font-weight: 700;
}}

QScrollArea {{
    border: none;
}}

QCheckBox {{
    spacing: 6px;
}}

QTabWidget::pane {{
    border: 1px solid {BORDER};
}}
"""


def block_card_stylesheet(color_hex: str, disabled: bool, is_current: bool, selected: bool = False) -> str:
    """Stylesheet for a single block card, driven by its color tag / state."""
    bg = CARD_BG_DISABLED if disabled else CARD_BG
    if is_current:
        border_color, border_width = CURRENT_BLOCK_BORDER, 3
    elif selected:
        border_color, border_width = SELECTED_BORDER, 2
    elif disabled:
        border_color, border_width = DISABLED_COLOR, 1
    else:
        border_color, border_width = color_hex, 1
    text_color = TEXT_MUTED if disabled else TEXT
    return f"""
    QFrame#BlockCard {{
        background-color: {bg};
        border: {border_width}px solid {border_color};
        border-left: 5px solid {border_color};
        border-radius: 6px;
    }}
    QFrame#BlockCard QLabel {{
        color: {text_color};
    }}
    """


def toggle_button_stylesheet(enabled: bool) -> str:
    """Small ON/OFF pill button used as the block enable/disable control."""
    color = ENABLED_ON_COLOR if enabled else DISABLED_OFF_COLOR
    return f"""
    QPushButton {{
        background-color: {color};
        border: 1px solid {color};
        border-radius: 4px;
        color: white;
        font-weight: 600;
        padding: 1px 6px;
    }}
    QPushButton:hover {{
        background-color: {color};
    }}
    """
