"""
Main application window.
"""

import tkinter as tk
from tkinter import ttk, messagebox
import queue

from .thread_panel import ThreadPanel
from ..core.constants import IS_WINDOWS
from ..managers import HotkeyManager
from ..config import HotkeyConfig


class MainWindow(tk.Tk):
    """Main application window."""

    def __init__(self):
        super().__init__()
        self.title("KeyMimic v2.0 - Keyboard & Mouse Automation")

        if not IS_WINDOWS:
            messagebox.showwarning(
                "Windows Only",
                "KeyMimic uses Windows API (SendInput).\n"
                "The interface will run on this system, but actual "
                "key/mouse inputs will not be sent."
            )

        # Initialize hotkey system
        self.hotkey_config = HotkeyConfig()
        self.hotkey_manager = HotkeyManager()
        self._register_hotkeys()
        self.hotkey_manager.start()

        self._build_ui()

        # Start polling for hotkey events
        self._check_hotkey_queue()

        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _build_ui(self):
        """Build the UI components."""
        # Single panel (no multi-threading)
        self.panel = ThreadPanel(self, 1, None, self.hotkey_config)
        self.panel.pack(fill="both", expand=True, padx=8, pady=8)

    def _register_hotkeys(self):
        """Register all hotkeys from config."""
        for action in ["start_record", "stop_record", "start", "stop"]:
            hk = self.hotkey_config.get_hotkey(action)
            modifiers = hk.get("modifiers", {"ctrl": False, "shift": False, "alt": False})
            self.hotkey_manager.register(hk["code"], action, modifiers)

    def _on_hotkey_pressed(self, action):
        """Handle hotkey press - dispatch to panel."""
        if not hasattr(self, 'panel'):
            return

        if action == "start_record":
            self.panel._start_recording()
        elif action == "stop_record":
            self.panel._stop_recording()
        elif action == "start":
            self.panel.start()
        elif action == "stop":
            self.panel.stop()

    def _check_hotkey_queue(self):
        """Poll hotkey event queue (thread-safe).

        Processes all pending hotkey events in the queue.
        This runs every 50ms to ensure hotkeys are responsive.
        """
        # Process all pending events (not just one)
        processed = 0
        while processed < 10:  # Max 10 events per cycle to avoid UI freeze
            try:
                action, _ = self.hotkey_manager.event_queue.get_nowait()
                self._on_hotkey_pressed(action)
                processed += 1
            except queue.Empty:
                break

        # Check again in 50ms
        self.after(50, self._check_hotkey_queue)

    def _on_close(self):
        """Handle window close event."""
        # Stop hotkey manager
        self.hotkey_manager.stop()

        # Stop panel
        if hasattr(self, 'panel'):
            self.panel.stop()

        self.destroy()
