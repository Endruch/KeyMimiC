"""
Configuration management for KeyMimic.

Provides thread-safe profile and hotkey configuration storage.
"""

from .profiles import ProfileManager, PROFILES_DIR
from .hotkeys import HotkeyConfig, CONFIG_DIR

__all__ = ['ProfileManager', 'HotkeyConfig', 'PROFILES_DIR', 'CONFIG_DIR']
