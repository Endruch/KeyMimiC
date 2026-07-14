"""
KeyMimic v2.0 - Keyboard & Mouse Automation
============================================
Professional macro automation tool for Windows.

Features:
- Symbolic key names (press('s') instead of press(31))
- Mouse action aliases (mouse_left(), mouse_right())
- Visual keyboard editor for generating macros
- Help dialog with comprehensive key code reference
- Multi-threaded macro execution
- Profile management
- Keyboard recording
"""

__version__ = "2.0.0"
__author__ = "KeyMimic Team"

from .core import (
    SCAN_CODES,
    IS_WINDOWS,
    KEY_NAMES,
    resolve_key,
    get_key_display_name,
    key_down,
    key_up,
    mouse_click,
    mouse_move,
    parse_macro,
    MacroRunner,
    KeyRecorder,
)

from .utils import (
    ProfileManager,
)

# GUI imports are optional (requires tkinter)
try:
    from .gui import (
        MainWindow,
        ThreadPanel,
        HelpDialog,
        VisualEditor,
    )
    _GUI_AVAILABLE = True
except ImportError:
    _GUI_AVAILABLE = False
    MainWindow = None
    ThreadPanel = None
    HelpDialog = None
    VisualEditor = None

__all__ = [
    '__version__',
    '__author__',
    'SCAN_CODES',
    'IS_WINDOWS',
    'KEY_NAMES',
    'resolve_key',
    'get_key_display_name',
    'key_down',
    'key_up',
    'mouse_click',
    'mouse_move',
    'parse_macro',
    'MacroRunner',
    'KeyRecorder',
    'MainWindow',
    'ThreadPanel',
    'HelpDialog',
    'VisualEditor',
    'ProfileManager',
]
