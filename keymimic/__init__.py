"""
KeyMimic v2.0 - Keyboard & Mouse Automation
============================================
Professional macro automation tool for Windows.

Features:
- Optimized Windows hooks with zero-allocation callbacks
- Clean architecture with composition over inheritance
- Thread-safe profile and configuration management
- Symbolic key names for easy macro writing
- Visual keyboard editor for generating macros
- Profile management with hot-reloading
- Keyboard and mouse recording
"""

__version__ = "2.0.0"
__author__ = "KeyMimic Team"

# Core exports
from .core import (
    SCAN_CODES,
    SCAN_TO_CODE,
    SCAN_TO_CODE_EXT,
    IS_WINDOWS,
    KEY_NAMES,
    resolve_key,
    get_key_display_name,
)

# Automation exports
from .core.automation import (
    parse_macro,
    validate_commands,
    MacroExecutor,
    send_key_down,
    send_key_up,
    send_mouse_move,
    send_mouse_click,
)

# Manager exports
from .managers import (
    HotkeyManager,
    Recorder,
)

# Config exports
from .config import (
    ProfileManager,
    HotkeyConfig,
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
    # Core
    'SCAN_CODES',
    'SCAN_TO_CODE',
    'SCAN_TO_CODE_EXT',
    'IS_WINDOWS',
    'KEY_NAMES',
    'resolve_key',
    'get_key_display_name',
    # Automation
    'parse_macro',
    'validate_commands',
    'MacroExecutor',
    'send_key_down',
    'send_key_up',
    'send_mouse_move',
    'send_mouse_click',
    # Managers
    'HotkeyManager',
    'Recorder',
    # Config
    'ProfileManager',
    'HotkeyConfig',
    # GUI
    'MainWindow',
    'ThreadPanel',
    'HelpDialog',
    'VisualEditor',
]
