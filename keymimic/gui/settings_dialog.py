"""
Settings dialog for configuring global hotkeys.
"""

import tkinter as tk
from tkinter import ttk, messagebox
from ..core.constants import IS_WINDOWS


class SettingsDialog(tk.Toplevel):
    """Settings dialog for hotkey configuration."""

    def __init__(self, parent, hotkey_config, on_save_callback):
        super().__init__(parent)
        self.title("KeyMimic Settings")
        self.geometry("500x300")
        self.transient(parent)
        self.resizable(False, False)

        self.hotkey_config = hotkey_config
        self.on_save_callback = on_save_callback  # Called when settings are saved
        self.temp_hotkeys = hotkey_config.get_all_hotkeys().copy()

        self._build_ui()

        # Center on parent
        self.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() - self.winfo_width()) // 2
        y = parent.winfo_y() + (parent.winfo_height() - self.winfo_height()) // 2
        self.geometry(f"+{x}+{y}")

    def _build_ui(self):
        """Build the settings dialog UI."""
        main_frame = ttk.Frame(self, padding=20)
        main_frame.pack(fill="both", expand=True)

        # Title
        title = ttk.Label(
            main_frame,
            text="Configure Global Hotkeys",
            font=("Segoe UI", 14, "bold")
        )
        title.pack(pady=(0, 10))

        # Warning for non-Windows
        if not IS_WINDOWS:
            warning = ttk.Label(
                main_frame,
                text="⚠ Hotkeys are only available on Windows",
                font=("Segoe UI", 9),
                foreground="red"
            )
            warning.pack(pady=(0, 10))

        # Description
        desc = ttk.Label(
            main_frame,
            text="Hotkeys work globally, even when KeyMimic is not focused.",
            font=("Segoe UI", 9),
            foreground="gray"
        )
        desc.pack(pady=(0, 20))

        # Hotkey configuration rows
        config_frame = ttk.Frame(main_frame)
        config_frame.pack(fill="x", pady=10)

        self.hotkey_labels = {}

        actions = [
            ("record", "Record:"),
            ("start", "Start:"),
            ("stop", "Stop:")
        ]

        for idx, (action, label_text) in enumerate(actions):
            row = ttk.Frame(config_frame)
            row.pack(fill="x", pady=5)

            # Label
            ttk.Label(
                row,
                text=label_text,
                font=("Segoe UI", 10),
                width=10
            ).pack(side="left", padx=5)

            # Display current hotkey
            hotkey_info = self.temp_hotkeys.get(action, {})
            current_key = hotkey_info.get("key", "Not Set")

            key_label = ttk.Label(
                row,
                text=current_key,
                font=("Consolas", 10, "bold"),
                foreground="#0066cc",
                width=15,
                relief="sunken",
                padding=5
            )
            key_label.pack(side="left", padx=5)
            self.hotkey_labels[action] = key_label

            # Change button
            ttk.Button(
                row,
                text="Change...",
                command=lambda a=action: self._change_hotkey(a),
                width=12
            ).pack(side="left", padx=5)

        # Bottom buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(side="bottom", fill="x", pady=(20, 0))

        ttk.Button(
            button_frame,
            text="Reset Defaults",
            command=self._reset_defaults,
            width=15
        ).pack(side="left", padx=5)

        ttk.Button(
            button_frame,
            text="Cancel",
            command=self.destroy,
            width=15
        ).pack(side="right", padx=5)

        ttk.Button(
            button_frame,
            text="Save",
            command=self._save,
            width=15
        ).pack(side="right", padx=5)

    def _change_hotkey(self, action):
        """Open dialog to record new hotkey for an action."""
        if not IS_WINDOWS:
            messagebox.showwarning(
                "Not Available",
                "Hotkey recording is only available on Windows."
            )
            return

        # For now, use a simple input dialog
        # In a full implementation, this would listen for a keypress
        new_key = tk.simpledialog.askstring(
            "Change Hotkey",
            f"Enter new hotkey for {action.capitalize()}:\n\n"
            f"Function keys: F1-F12\n"
            f"Examples: F9, F10, F11, F12",
            initialvalue=self.temp_hotkeys[action]["key"]
        )

        if new_key:
            # Validate and convert to scan code
            new_key_upper = new_key.upper().strip()
            scan_code = self._key_name_to_code(new_key_upper)

            if scan_code is not None:
                # Check for conflicts
                for other_action, hotkey_info in self.temp_hotkeys.items():
                    if other_action != action and hotkey_info["code"] == scan_code:
                        messagebox.showwarning(
                            "Conflict",
                            f"This key is already assigned to {other_action.capitalize()}!"
                        )
                        return

                # Update temp config
                self.temp_hotkeys[action] = {"key": new_key_upper, "code": scan_code}
                self.hotkey_labels[action].config(text=new_key_upper)
            else:
                messagebox.showerror(
                    "Invalid Key",
                    f"'{new_key}' is not a valid key name.\n\n"
                    f"Supported keys: F1-F12"
                )

    def _key_name_to_code(self, key_name):
        """Convert key name to scan code."""
        # Function keys mapping
        f_keys = {
            "F1": 59, "F2": 60, "F3": 61, "F4": 62,
            "F5": 63, "F6": 64, "F7": 65, "F8": 66,
            "F9": 67, "F10": 68, "F11": 87, "F12": 88
        }

        return f_keys.get(key_name)

    def _reset_defaults(self):
        """Reset all hotkeys to default values."""
        if messagebox.askyesno(
            "Reset to Defaults",
            "Reset all hotkeys to default values?\n\nRecord: F12\nStart: F10\nStop: F11"
        ):
            self.temp_hotkeys = self.hotkey_config.DEFAULT_HOTKEYS.copy()

            # Update labels
            for action, hotkey_info in self.temp_hotkeys.items():
                self.hotkey_labels[action].config(text=hotkey_info["key"])

    def _save(self):
        """Save hotkey configuration."""
        # Update the actual config
        for action, hotkey_info in self.temp_hotkeys.items():
            self.hotkey_config.set_hotkey(
                action,
                hotkey_info["key"],
                hotkey_info["code"]
            )

        # Call the callback to update UI
        if self.on_save_callback:
            self.on_save_callback()

        messagebox.showinfo("Saved", "Hotkey settings have been saved!")
        self.destroy()
