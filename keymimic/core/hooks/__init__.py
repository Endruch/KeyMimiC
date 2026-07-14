"""
Optimized Windows low-level hooks for KeyMimic.

All hooks use zero-allocation pattern with structures created once in __init__.
"""

from .base_hook import BaseHook
from .keyboard_hook import KeyboardHook
from .mouse_hook import MouseHook

__all__ = ['BaseHook', 'KeyboardHook', 'MouseHook']
