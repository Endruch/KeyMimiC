"""
Thread panel widget with individual log.
"""

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, simpledialog
from datetime import datetime

from ..core.automation import parse_macro, validate_commands, MacroExecutor
from ..managers import Recorder
from ..core.constants import IS_WINDOWS
from ..config import ProfileManager
from .help_dialog import HelpDialog
from .visual_editor import VisualEditor
from .settings_dialog import SettingsDialog


class ThreadPanel(ttk.Frame):
    """Panel for a single macro thread with its own log."""

    def __init__(self, master, panel_id, on_close, hotkey_config=None):
        super().__init__(master, padding=8)
        self.panel_id = panel_id
        self.on_close = on_close
        self.hotkey_config = hotkey_config
        self.runner = None
        self.profile_manager = ProfileManager(panel_id)
        self.current_profile = list(self.profile_manager.profiles.keys())[0]
        self.recorder = None
        self.is_recording = False

        self._build_ui()
        self._load_profile()

        # Update button labels with hotkeys if config is available
        if self.hotkey_config:
            self.update_hotkey_labels()

    def _build_ui(self):
        """Build the UI components."""

        # Profile selector
        profile_frame = ttk.Frame(self)
        profile_frame.pack(fill="x", pady=(4, 2))
        ttk.Label(profile_frame, text="Profile:").pack(side="left", padx=2)

        self.profile_var = tk.StringVar(value=self.current_profile)
        self.profile_combo = ttk.Combobox(
            profile_frame,
            textvariable=self.profile_var,
            values=list(self.profile_manager.profiles.keys()),
            width=20,
            state="readonly"
        )
        self.profile_combo.pack(side="left", padx=2)
        self.profile_combo.bind("<<ComboboxSelected>>", self._on_profile_change)

        ttk.Button(profile_frame, text="+", width=3,
                  command=self._add_profile).pack(side="left", padx=2)
        ttk.Button(profile_frame, text="Edit", width=4,
                  command=self._rename_profile).pack(side="left", padx=2)
        ttk.Button(profile_frame, text="Del", width=4,
                  command=self._delete_profile).pack(side="left", padx=2)

        # Toolbar
        toolbar = ttk.Frame(self)
        toolbar.pack(fill="x", pady=(4, 2))

        # Record button (will show both start and stop hotkeys)
        self.record_btn = ttk.Button(toolbar, text="Record",
                                     command=self._toggle_recording)
        self.record_btn.pack(side="left", padx=2)

        ttk.Button(toolbar, text="Visual Editor", command=self._show_visual_editor).pack(side="left", padx=2)
        ttk.Button(toolbar, text="Settings", command=self._show_settings).pack(side="left", padx=2)

        self.loop_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(toolbar, text="Loop",
                       variable=self.loop_var).pack(side="left", padx=10)

        # Help button on the right side
        ttk.Button(toolbar, text="Help", command=self._show_help).pack(side="right", padx=2)

        # Text editor
        self.text = scrolledtext.ScrolledText(
            self, width=50, height=15,
            font=("Consolas", 10), wrap="none"
        )
        self.text.pack(fill="both", expand=True)
        self.text.bind("<<Modified>>", self._on_text_modified)

        # Control buttons
        bottom = ttk.Frame(self)
        bottom.pack(fill="x", pady=(4, 0))
        self.start_btn = ttk.Button(bottom, text="Start", command=self.start)
        self.start_btn.pack(side="left", padx=2)
        self.stop_btn = ttk.Button(bottom, text="Stop", command=self.stop,
                                   state="disabled")
        self.stop_btn.pack(side="left", padx=2)
        self.status_lbl = ttk.Label(bottom, text="Stopped")
        self.status_lbl.pack(side="left", padx=10)

        # Individual log for this thread
        ttk.Label(self, text="Thread Log:", font=("Segoe UI", 9, "bold")).pack(
            anchor="w", pady=(4, 2))
        self.log_box = scrolledtext.ScrolledText(
            self, height=8, font=("Consolas", 9),
            state="disabled", wrap="word"
        )
        self.log_box.pack(fill="both")

    def _load_profile(self):
        """Load current profile into text editor."""
        content = self.profile_manager.get_profile(self.current_profile)
        self.text.delete("1.0", "end")
        self.text.insert("1.0", content)
        self.text.edit_modified(False)

    def _close(self):
        """Close this panel."""
        self.stop()
        if self.on_close:
            self.on_close(self.panel_id)

    def _on_profile_change(self, event=None):
        """Handle profile selection change."""
        # Save current profile before switching
        old_content = self.text.get("1.0", "end-1c")
        self.profile_manager.update_profile(self.current_profile, old_content)

        # Load new profile
        self.current_profile = self.profile_var.get()
        self._load_profile()

    def _on_text_modified(self, event=None):
        """Auto-save on text modification."""
        if self.text.edit_modified():
            content = self.text.get("1.0", "end-1c")
            self.profile_manager.update_profile(self.current_profile, content)
            self.text.edit_modified(False)

    def _add_profile(self):
        """Add a new profile."""
        name = simpledialog.askstring("New Profile", "Enter profile name:")
        if name and name not in self.profile_manager.profiles:
            self.profile_manager.add_profile(name, "# New macro\n")
            self.profile_combo['values'] = list(self.profile_manager.profiles.keys())
            self.profile_var.set(name)
            self._on_profile_change()
            self._log("Created new profile: " + name)

    def _rename_profile(self):
        """Rename current profile."""
        old_name = self.current_profile
        new_name = simpledialog.askstring(
            "Rename Profile",
            f"New name for '{old_name}':",
            initialvalue=old_name
        )
        if new_name and new_name != old_name:
            if self.profile_manager.rename_profile(old_name, new_name):
                self.current_profile = new_name
                self.profile_combo['values'] = list(self.profile_manager.profiles.keys())
                self.profile_var.set(new_name)
                self._log(f"Profile renamed: '{old_name}' -> '{new_name}'")

    def _delete_profile(self):
        """Delete current profile."""
        if len(self.profile_manager.profiles) <= 1:
            messagebox.showwarning("Error", "Cannot delete the last profile!")
            return

        if messagebox.askyesno("Delete Profile",
                              f"Delete profile '{self.current_profile}'?"):
            if self.profile_manager.delete_profile(self.current_profile):
                self.current_profile = list(self.profile_manager.profiles.keys())[0]
                self.profile_combo['values'] = list(self.profile_manager.profiles.keys())
                self.profile_var.set(self.current_profile)
                self._on_profile_change()
                self._log("Profile deleted")

    def _show_help(self):
        """Show help dialog."""
        HelpDialog(self)

    def _show_visual_editor(self):
        """Show visual keyboard editor."""
        def add_command(cmd):
            # Insert at cursor position
            self.text.insert("insert", cmd)
            self.text.see("insert")
            # Trigger auto-save
            self.text.event_generate("<<Modified>>")

        VisualEditor(self, add_command)

    def _show_settings(self):
        """Show settings dialog for hotkey configuration."""
        if not self.hotkey_config:
            messagebox.showinfo("Settings", "Hotkey configuration is not available.")
            return

        def on_save():
            # Update all panels' button labels
            self.update_hotkey_labels()

        SettingsDialog(self, self.hotkey_config, on_save)

    def _toggle_recording(self):
        """Toggle keyboard recording (for button click)."""
        if self.is_recording:
            self._stop_recording()
        else:
            self._start_recording()

    def _start_recording(self):
        """Start keyboard recording."""
        if not IS_WINDOWS:
            messagebox.showwarning("Not Available", "Recording is only available on Windows")
            return

        if self.is_recording:
            return  # Already recording

        # START recording
        self.is_recording = True
        self.update_hotkey_labels()  # Update button to show stop hotkey
        self.recorder = Recorder()
        self.recorder.start(record_mouse=self.hotkey_config.record_mouse)
        self._log("Recording started... Press keys" + (" and mouse" if self.hotkey_config.record_mouse else ""))

    def _stop_recording(self):
        """Stop keyboard recording."""
        if not self.is_recording:
            return  # Not recording

        # STOP recording
        self.is_recording = False
        self.update_hotkey_labels()  # Update button to show start hotkey

        if self.recorder:
            macro_text = self.recorder.stop()

            # Create new profile with recorded macro
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            profile_name = f"Recording {timestamp}"
            self.profile_manager.add_profile(profile_name, macro_text)

            self.profile_combo['values'] = list(self.profile_manager.profiles.keys())
            self.profile_var.set(profile_name)
            self._on_profile_change()

            self._log(f"Recording stopped. Saved as '{profile_name}'")

    def start(self):
        """Start macro execution."""
        if self.runner and self.runner.is_alive():
            return

        raw = self.text.get("1.0", "end-1c")
        try:
            metadata, commands = parse_macro(raw)
            validate_commands(commands)
        except Exception as exc:
            messagebox.showerror("Parse Error", str(exc))
            return

        if not commands:
            messagebox.showwarning("Empty", "No commands in macro.")
            return

        thread_name = metadata.get('thread_name') or f"Thread {self.panel_id}"
        humanize = metadata.get('humanize', 0)

        self.runner = MacroExecutor(
            thread_name,
            commands,
            loop=self.loop_var.get(),
            humanize=humanize,
            log_callback=self._log
        )
        self.runner.start()
        self.start_btn.config(state="disabled")
        self.stop_btn.config(state="normal")
        self.status_lbl.config(text="Running...")

    def stop(self):
        """Stop macro execution."""
        if self.runner:
            self.runner.stop()
        self.start_btn.config(state="normal")
        self.stop_btn.config(state="disabled")
        self.status_lbl.config(text="Stopped")

    def _log(self, message):
        """Add message to this thread's log."""
        self.log_box.config(state="normal")
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_box.insert("end", f"[{timestamp}] {message}\n")
        self.log_box.see("end")
        self.log_box.config(state="disabled")

    def update_hotkey_labels(self):
        """Update button labels to display assigned hotkeys."""
        if not self.hotkey_config:
            return

        # Update Record button - show start or stop recording hotkey depending on state
        if self.is_recording:
            stop_record_key = self.hotkey_config.get_hotkey("stop_record")["key"]
            self.record_btn.config(text=f"Stop Recording {stop_record_key}")
        else:
            start_record_key = self.hotkey_config.get_hotkey("start_record")["key"]
            self.record_btn.config(text=f"Record {start_record_key}")

        # Update Start button
        start_key = self.hotkey_config.get_hotkey("start")["key"]
        self.start_btn.config(text=f"Start {start_key}")

        # Update Stop button
        stop_key = self.hotkey_config.get_hotkey("stop")["key"]
        self.stop_btn.config(text=f"Stop {stop_key}")
