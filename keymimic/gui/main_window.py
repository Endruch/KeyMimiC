"""
Main application window.
"""

import tkinter as tk
from tkinter import ttk, messagebox
import queue

from .thread_panel import ThreadPanel
from ..core.constants import IS_WINDOWS
from ..core.hotkey_manager import HotkeyManager
from ..utils.hotkey_config import HotkeyConfig


class MainWindow(tk.Tk):
    """Main application window."""

    def __init__(self):
        super().__init__()
        self.title("KeyMimic v2.0 - Keyboard & Mouse Automation")
        self.geometry("1400x800")

        if not IS_WINDOWS:
            messagebox.showwarning(
                "Windows Only",
                "KeyMimic uses Windows API (SendInput).\n"
                "The interface will run on this system, but actual "
                "key/mouse inputs will not be sent."
            )

        self.panels = {}
        self.next_panel_id = 1

        # Initialize hotkey system
        self.hotkey_config = HotkeyConfig()
        self.hotkey_manager = HotkeyManager()
        self._register_hotkeys()
        self.hotkey_manager.start()

        self._build_ui()
        self._add_panel()  # Add initial panel

        # Start polling for hotkey events
        self._check_hotkey_queue()

        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _build_ui(self):
        """Build the UI components."""
        # Top toolbar
        toolbar = ttk.Frame(self, padding=8)
        toolbar.pack(fill="x")

        ttk.Button(
            toolbar,
            text="+ Add Thread",
            command=self._add_panel
        ).pack(side="left", padx=4)

        ttk.Label(toolbar, text="Active Threads: ").pack(side="left", padx=(20, 0))
        self.panel_count_label = ttk.Label(
            toolbar, text="0",
            font=("Segoe UI", 10, "bold")
        )
        self.panel_count_label.pack(side="left")

        # Scrollable canvas for panels
        canvas_frame = ttk.Frame(self)
        canvas_frame.pack(fill="both", expand=True, padx=8)

        self.canvas = tk.Canvas(canvas_frame, highlightthickness=0)
        scrollbar = ttk.Scrollbar(
            canvas_frame,
            orient="horizontal",
            command=self.canvas.xview
        )
        self.scrollable_frame = ttk.Frame(self.canvas)

        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        )

        self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.canvas.configure(xscrollcommand=scrollbar.set)

        self.canvas.pack(side="top", fill="both", expand=True)
        scrollbar.pack(side="bottom", fill="x")

    def _add_panel(self):
        """Add a new thread panel."""
        panel_id = self.next_panel_id
        self.next_panel_id += 1

        panel = ThreadPanel(self.scrollable_frame, panel_id, self._remove_panel, self.hotkey_config)
        panel.pack(side="left", fill="both", expand=False, padx=4, pady=4)

        self.panels[panel_id] = panel
        self._update_panel_count()

    def _remove_panel(self, panel_id):
        """Remove a thread panel."""
        if panel_id in self.panels:
            self.panels[panel_id].destroy()
            del self.panels[panel_id]
            self._update_panel_count()

    def _update_panel_count(self):
        """Update the panel count display."""
        self.panel_count_label.config(text=str(len(self.panels)))

    def _register_hotkeys(self):
        """Register all hotkeys from config."""
        for action in ["record", "start", "stop"]:
            hk = self.hotkey_config.get_hotkey(action)
            self.hotkey_manager.register(hk["code"], action)

    def _on_hotkey_pressed(self, action):
        """Handle hotkey press - dispatch to first/active panel."""
        if not self.panels:
            return

        # Get first panel (or could track active panel in the future)
        panel = list(self.panels.values())[0]

        if action == "record":
            panel._toggle_recording()
        elif action == "start":
            panel.start()
        elif action == "stop":
            panel.stop()

    def _check_hotkey_queue(self):
        """Poll hotkey event queue (thread-safe)."""
        try:
            action, _ = self.hotkey_manager.event_queue.get_nowait()
            self._on_hotkey_pressed(action)
        except queue.Empty:
            pass

        # Check again in 50ms
        self.after(50, self._check_hotkey_queue)

    def _on_close(self):
        """Handle window close event."""
        # Stop hotkey manager
        self.hotkey_manager.stop()

        # Stop all panels
        for panel in self.panels.values():
            panel.stop()

        self.destroy()
