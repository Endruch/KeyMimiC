"""
Automation engine for KeyMimic.

Provides input injection, macro parsing, and execution.
"""

from .input import send_key_down, send_key_up, send_mouse_move, send_mouse_click
from .parser import parse_macro, validate_commands
from .executor import MacroExecutor

__all__ = [
    'send_key_down',
    'send_key_up',
    'send_mouse_move',
    'send_mouse_click',
    'parse_macro',
    'validate_commands',
    'MacroExecutor',
]
