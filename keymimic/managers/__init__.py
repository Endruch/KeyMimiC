"""
Management layer for KeyMimic.

Coordinates hooks for hotkey detection and input recording.
"""

from .hotkey_manager import HotkeyManager
from .recorder import Recorder

__all__ = ['HotkeyManager', 'Recorder']
