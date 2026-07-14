"""
Core functionality for KeyMimic v2.0.
"""

from .constants import SCAN_CODES, IS_WINDOWS
from .key_names import KEY_NAMES, resolve_key, get_key_display_name
from .input_sender import key_down, key_up, mouse_click, mouse_move
from .macro_parser import parse_macro
from .macro_runner import MacroRunner
from .recorder import KeyRecorder

__all__ = [
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
]
