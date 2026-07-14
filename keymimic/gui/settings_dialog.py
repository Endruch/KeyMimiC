"""
Settings dialog for configuring global hotkeys.
"""

import tkinter as tk
from tkinter import ttk, messagebox
from ..core.constants import IS_WINDOWS

if IS_WINDOWS:
    import ctypes
    from ctypes import wintypes


class KeyCaptureDialog(tk.Toplevel):
    """Dialog for capturing a key combination."""

    def __init__(self, parent, current_key=""):
        super().__init__(parent)
        self.title("Press a key combination")
        self.transient(parent)
        self.resizable(False, False)
        self.grabbed_grab_set = False

        self.result = None
        self.hook_id = None
        self.hook_proc = None
        self.captured_key = None
        self.captured_modifiers = {"ctrl": False, "shift": False, "alt": False}

        self._build_ui(current_key)

        # Center on parent
        self.update_idletasks()
        parent_x = parent.winfo_x()
        parent_y = parent.winfo_y()
        parent_w = parent.winfo_width()
        parent_h = parent.winfo_height()
        w = 400
        h = 150
        x = parent_x + (parent_w - w) // 2
        y = parent_y + (parent_h - h) // 2
        self.geometry(f"{w}x{h}+{x}+{y}")

        # Install keyboard hook
        if IS_WINDOWS:
            self._install_hook()

        self.protocol("WM_DELETE_WINDOW", self._on_cancel)

    def _build_ui(self, current_key):
        """Build the dialog UI."""
        main_frame = ttk.Frame(self, padding=20)
        main_frame.pack(fill="both", expand=True)

        ttk.Label(
            main_frame,
            text=f"Press any key or combination\n\nCurrent: {current_key}",
            font=("Segoe UI", 10),
            justify="center"
        ).pack(pady=10)

        self.status_label = ttk.Label(
            main_frame,
            text="Waiting for key press...",
            font=("Segoe UI", 11, "bold"),
            foreground="#0066cc"
        )
        self.status_label.pack(pady=10)

        button_frame = ttk.Frame(main_frame)
        button_frame.pack(pady=10)

        ttk.Button(
            button_frame,
            text="Cancel",
            command=self._on_cancel,
            width=15
        ).pack(side="left", padx=5)

    def _install_hook(self):
        """Install keyboard hook to capture keys."""
        CMPFUNC = ctypes.CFUNCTYPE(ctypes.c_long, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM)
        self.hook_proc = CMPFUNC(self._hook_callback)

        WH_KEYBOARD_LL = 13
        # Use NULL for module handle - works better with PyInstaller
        self.hook_id = ctypes.windll.user32.SetWindowsHookExA(
            WH_KEYBOARD_LL,
            self.hook_proc,
            None,  # NULL module handle for low-level hooks
            0
        )

    def _hook_callback(self, nCode, wParam, lParam):
        """Keyboard hook callback."""
        WM_KEYDOWN = 0x0100
        WM_SYSKEYDOWN = 0x0104

        if nCode >= 0 and wParam in (WM_KEYDOWN, WM_SYSKEYDOWN):
            from ..core.constants import SCAN_TO_CODE, SCAN_TO_CODE_EXT

            # Define KBDLLHOOKSTRUCT structure
            class KBDLLHOOKSTRUCT(ctypes.Structure):
                _fields_ = [
                    ("vkCode", wintypes.DWORD),
                    ("scanCode", wintypes.DWORD),
                    ("flags", wintypes.DWORD),
                    ("time", wintypes.DWORD),
                    ("dwExtraInfo", ctypes.POINTER(wintypes.ULONG))
                ]

            kb_struct = ctypes.cast(lParam, ctypes.POINTER(KBDLLHOOKSTRUCT)).contents
            scan_code = kb_struct.scanCode
            extended = (kb_struct.flags >> 0) & 0x1  # LLKHF_EXTENDED flag

            # Check modifiers
            VK_CONTROL = 0x11
            VK_SHIFT = 0x10
            VK_MENU = 0x12

            ctrl_pressed = (ctypes.windll.user32.GetKeyState(VK_CONTROL) & 0x8000) != 0
            shift_pressed = (ctypes.windll.user32.GetKeyState(VK_SHIFT) & 0x8000) != 0
            alt_pressed = (ctypes.windll.user32.GetKeyState(VK_MENU) & 0x8000) != 0

            # Get key code
            if extended:
                code = SCAN_TO_CODE_EXT.get(scan_code)
            else:
                code = SCAN_TO_CODE.get(scan_code)

            # Only accept F1-F12
            if code and code >= 59 and code <= 88:
                # Map scan code to F-key name
                f_keys = {
                    59: "F1", 60: "F2", 61: "F3", 62: "F4",
                    63: "F5", 64: "F6", 65: "F7", 66: "F8",
                    67: "F9", 68: "F10", 87: "F11", 88: "F12"
                }

                key_name = f_keys.get(code)
                if key_name:
                    self.captured_key = key_name
                    self.captured_modifiers = {
                        "ctrl": ctrl_pressed,
                        "shift": shift_pressed,
                        "alt": alt_pressed
                    }

                    # Build display string
                    parts = []
                    if ctrl_pressed:
                        parts.append("Ctrl")
                    if shift_pressed:
                        parts.append("Shift")
                    if alt_pressed:
                        parts.append("Alt")
                    parts.append(key_name)

                    display = "+".join(parts)
                    self.status_label.config(text=f"Captured: {display}")

                    # Auto-close after short delay
                    self.after(500, self._on_ok)

        return ctypes.windll.user32.CallNextHookEx(None, nCode, wParam, lParam)

    def _on_ok(self):
        """Accept the captured key."""
        if self.captured_key:
            # Build result tuple (display_string, modifiers, scan_code)
            parts = []
            if self.captured_modifiers["ctrl"]:
                parts.append("Ctrl")
            if self.captured_modifiers["shift"]:
                parts.append("Shift")
            if self.captured_modifiers["alt"]:
                parts.append("Alt")
            parts.append(self.captured_key)

            display_str = "+".join(parts)

            # Map F-key to scan code
            f_keys = {
                "F1": 59, "F2": 60, "F3": 61, "F4": 62,
                "F5": 63, "F6": 64, "F7": 65, "F8": 66,
                "F9": 67, "F10": 68, "F11": 87, "F12": 88
            }

            scan_code = f_keys.get(self.captured_key)

            self.result = (display_str, self.captured_modifiers, scan_code)

        self._cleanup()
        self.destroy()

    def _on_cancel(self):
        """Cancel key capture."""
        self.result = None
        self._cleanup()
        self.destroy()

    def _cleanup(self):
        """Remove keyboard hook."""
        if self.hook_id and IS_WINDOWS:
            ctypes.windll.user32.UnhookWindowsHookEx(self.hook_id)
            self.hook_id = None


class SettingsDialog(tk.Toplevel):
    """Settings dialog for hotkey configuration."""

    def __init__(self, parent, hotkey_config, on_save_callback):
        super().__init__(parent)
        self.title("KeyMimic Settings")
        self.transient(parent)
        self.resizable(False, False)

        self.hotkey_config = hotkey_config
        self.on_save_callback = on_save_callback  # Called when settings are saved
        self.temp_hotkeys = hotkey_config.get_all_hotkeys().copy()

        self._build_ui()

        # Center on screen
        self.update_idletasks()
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        window_width = 600
        window_height = 450  # Increased from 400 to show buttons
        x = (screen_width - window_width) // 2
        y = (screen_height - window_height) // 2
        self.geometry(f"{window_width}x{window_height}+{x}+{y}")

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
            text="Hotkeys work globally, even when KeyMimic is not focused.\nClick 'Change...' and press any key or combination (e.g., Shift+F12)",
            font=("Segoe UI", 9),
            foreground="gray",
            justify="center"
        )
        desc.pack(pady=(0, 20))

        # Hotkey configuration rows
        config_frame = ttk.Frame(main_frame)
        config_frame.pack(fill="x", pady=10)

        self.hotkey_labels = {}

        actions = [
            ("start_record", "Start Recording:"),
            ("stop_record", "Stop Recording:"),
            ("start", "Start Macro:"),
            ("stop", "Stop Macro:")
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

        # Mouse recording checkbox
        mouse_frame = ttk.Frame(main_frame)
        mouse_frame.pack(fill="x", pady=(20, 10))

        ttk.Separator(mouse_frame, orient="horizontal").pack(fill="x", pady=(0, 10))

        self.record_mouse_var = tk.BooleanVar(value=self.hotkey_config.record_mouse)

        mouse_check = ttk.Checkbutton(
            mouse_frame,
            text="Record mouse actions (clicks and movement) during keyboard recording",
            variable=self.record_mouse_var,
            style="TCheckbutton"
        )
        mouse_check.pack(anchor="w", padx=5)

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

        # Open key capture dialog
        current_key = self.temp_hotkeys[action]["key"]
        capture_dialog = KeyCaptureDialog(self, current_key)
        self.wait_window(capture_dialog)

        # Get result
        result = capture_dialog.result

        if result:
            key_str, modifiers, scan_code = result

            # Check for conflicts (comparing full hotkey string)
            for other_action, hotkey_info in self.temp_hotkeys.items():
                if other_action != action and hotkey_info.get("key") == key_str:
                    messagebox.showwarning(
                        "Conflict",
                        f"This hotkey is already assigned to {other_action.capitalize()}!"
                    )
                    return

            # Update temp config with modifiers
            self.temp_hotkeys[action] = {
                "key": key_str,
                "code": scan_code,
                "modifiers": modifiers  # {"ctrl": bool, "shift": bool, "alt": bool}
            }
            self.hotkey_labels[action].config(text=key_str)

    def _parse_hotkey(self, hotkey_str):
        """Parse hotkey string into components.

        Args:
            hotkey_str: String like "F12", "Shift+F12", "Ctrl+Alt+F1"

        Returns:
            Tuple of (display_string, modifiers_dict, scan_code) or None if invalid
        """
        parts = [p.strip() for p in hotkey_str.split("+")]

        modifiers = {"ctrl": False, "shift": False, "alt": False}
        key_name = None

        for part in parts:
            if part in ("CTRL", "CONTROL"):
                modifiers["ctrl"] = True
            elif part == "SHIFT":
                modifiers["shift"] = True
            elif part == "ALT":
                modifiers["alt"] = True
            elif part.startswith("F") and len(part) <= 3:  # F1-F12
                key_name = part
            else:
                return None  # Invalid part

        if not key_name:
            return None  # No main key found

        scan_code = self._key_name_to_code(key_name)
        if scan_code is None:
            return None

        # Build display string
        parts = []
        if modifiers["ctrl"]:
            parts.append("Ctrl")
        if modifiers["shift"]:
            parts.append("Shift")
        if modifiers["alt"]:
            parts.append("Alt")
        parts.append(key_name)

        display_str = "+".join(parts)

        return (display_str, modifiers, scan_code)

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
            "Reset all hotkeys to default values?\n\n"
            "Start Recording: F12\n"
            "Stop Recording: Shift+F12\n"
            "Start Macro: F11\n"
            "Stop Macro: Shift+F11"
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
                hotkey_info["code"],
                hotkey_info.get("modifiers", {"ctrl": False, "shift": False, "alt": False})
            )

        # Save mouse recording preference
        self.hotkey_config.set_record_mouse(self.record_mouse_var.get())

        # Call the callback to update UI
        if self.on_save_callback:
            self.on_save_callback()

        messagebox.showinfo("Saved", "Hotkey settings have been saved!")
        self.destroy()
