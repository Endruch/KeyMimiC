"""
Core functionality for KeyMimic v2.0.

Provides:
- Constants and key mappings
- Optimized Windows hooks
- Automation engine (input, parsing, execution)
"""

from .constants import SCAN_CODES, IS_WINDOWS, SCAN_TO_CODE, SCAN_TO_CODE_EXT
from .key_names import KEY_NAMES, resolve_key, get_key_display_name

__all__ = [
    'SCAN_CODES',
    'SCAN_TO_CODE',
    'SCAN_TO_CODE_EXT',
    'IS_WINDOWS',
    'KEY_NAMES',
    'resolve_key',
    'get_key_display_name',
]
