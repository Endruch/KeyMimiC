"""
Visual keyboard editor for generating macro code.
"""

import tkinter as tk
from tkinter import ttk


class VisualEditor(tk.Toplevel):
    """Visual keyboard editor with clickable keys."""

    def __init__(self, parent, callback):
        super().__init__(parent)
        self.title("Visual Keyboard Editor")
        self.transient(parent)
        self.callback = callback

        # Track modifier states
        self.shift_active = False
        self.ctrl_active = False
        self.alt_active = False

        self._build_ui()

        # Auto-size based on content and center
        self.update_idletasks()
        self.resizable(True, True)

        # Center on screen
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        window_width = 1100
        window_height = 600
        x = (screen_width - window_width) // 2
        y = (screen_height - window_height) // 2
        self.geometry(f"{window_width}x{window_height}+{x}+{y}")

    def _build_ui(self):
        """Build the visual editor UI."""
        main_frame = ttk.Frame(self, padding=10)
        main_frame.pack(fill="both", expand=True)

        # Title
        title = ttk.Label(
            main_frame,
            text="Click keys to add commands to your macro",
            font=("Segoe UI", 12, "bold")
        )
        title.pack(pady=(0, 10))

        # Instructions
        instructions = ttk.Label(
            main_frame,
            text="Toggle modifiers (Ctrl/Shift/Alt) to hold them. Click other keys to add press+release commands.",
            font=("Segoe UI", 9),
            foreground="gray"
        )
        instructions.pack(pady=(0, 10))

        # Keyboard container
        kb_frame = ttk.Frame(main_frame)
        kb_frame.pack(expand=True)

        # Row 1: Function keys
        row1 = ttk.Frame(kb_frame)
        row1.pack(pady=2)
        self._add_key(row1, "ESC", "esc", width=8)
        self._add_spacer(row1, 2)
        for i in range(1, 13):
            self._add_key(row1, f"F{i}", f"f{i}", width=8)
            if i in [4, 8]:
                self._add_spacer(row1, 2)

        # Row 2: Numbers
        row2 = ttk.Frame(kb_frame)
        row2.pack(pady=2)
        self._add_key(row2, "`", "`", width=8)
        for i in range(1, 10):
            self._add_key(row2, str(i), str(i), width=8)
        self._add_key(row2, "0", "0", width=8)
        self._add_key(row2, "-", "-", width=8)
        self._add_key(row2, "=", "=", width=8)
        self._add_key(row2, "BACK", "backspace", width=12)

        # Row 3: QWERTY
        row3 = ttk.Frame(kb_frame)
        row3.pack(pady=2)
        self._add_key(row3, "TAB", "tab", width=10)
        for ch in "QWERTYUIOP":
            self._add_key(row3, ch, ch.lower(), width=8)
        self._add_key(row3, "[", "[", width=8)
        self._add_key(row3, "]", "]", width=8)
        self._add_key(row3, "\\", "\\", width=8)

        # Row 4: ASDF
        row4 = ttk.Frame(kb_frame)
        row4.pack(pady=2)
        self._add_key(row4, "CAPS", "caps", width=12)
        for ch in "ASDFGHJKL":
            self._add_key(row4, ch, ch.lower(), width=8)
        self._add_key(row4, ";", ";", width=8)
        self._add_key(row4, "'", "'", width=8)
        self._add_key(row4, "ENTER", "enter", width=14)

        # Row 5: ZXCV
        row5 = ttk.Frame(kb_frame)
        row5.pack(pady=2)
        self.shift_btn = self._add_key(row5, "SHIFT", "shift", width=14, toggle=True)
        for ch in "ZXCVBNM":
            self._add_key(row5, ch, ch.lower(), width=8)
        self._add_key(row5, ",", ",", width=8)
        self._add_key(row5, ".", ".", width=8)
        self._add_key(row5, "/", "/", width=8)
        self._add_key(row5, "SHIFT", "rshift", width=14)

        # Row 6: Bottom row
        row6 = ttk.Frame(kb_frame)
        row6.pack(pady=2)
        self.ctrl_btn = self._add_key(row6, "CTRL", "ctrl", width=10, toggle=True)
        self._add_key(row6, "WIN", "win", width=10)
        self.alt_btn = self._add_key(row6, "ALT", "alt", width=10, toggle=True)
        self._add_key(row6, "SPACE", "space", width=50)
        self._add_key(row6, "ALT", "ralt", width=10)
        self._add_key(row6, "WIN", "rwin", width=10)
        self._add_key(row6, "MENU", "menu", width=10)
        self._add_key(row6, "CTRL", "rctrl", width=10)

        # Navigation cluster (on the right)
        nav_label = ttk.Label(main_frame, text="Navigation & Arrows", font=("Segoe UI", 9, "bold"))
        nav_label.pack(pady=(10, 5))

        nav_frame = ttk.Frame(main_frame)
        nav_frame.pack()

        # Insert/Delete/Home/End/PgUp/PgDn
        nav_row1 = ttk.Frame(nav_frame)
        nav_row1.pack()
        self._add_key(nav_row1, "INS", "insert", width=8)
        self._add_key(nav_row1, "HOME", "home", width=8)
        self._add_key(nav_row1, "PG UP", "pageup", width=8)

        nav_row2 = ttk.Frame(nav_frame)
        nav_row2.pack()
        self._add_key(nav_row2, "DEL", "delete", width=8)
        self._add_key(nav_row2, "END", "end", width=8)
        self._add_key(nav_row2, "PG DN", "pagedown", width=8)

        # Arrow keys
        self._add_spacer(nav_frame, 1)
        arrow_row1 = ttk.Frame(nav_frame)
        arrow_row1.pack()
        self._add_spacer(arrow_row1, 8)
        self._add_key(arrow_row1, "↑", "up", width=8)

        arrow_row2 = ttk.Frame(nav_frame)
        arrow_row2.pack()
        self._add_key(arrow_row2, "←", "left", width=8)
        self._add_key(arrow_row2, "↓", "down", width=8)
        self._add_key(arrow_row2, "→", "right", width=8)

        # Mouse actions
        mouse_label = ttk.Label(main_frame, text="Mouse Actions", font=("Segoe UI", 9, "bold"))
        mouse_label.pack(pady=(10, 5))

        mouse_frame = ttk.Frame(main_frame)
        mouse_frame.pack()
        self._add_mouse_btn(mouse_frame, "Left Click", "click()")
        self._add_mouse_btn(mouse_frame, "Right Click", "right_click()")

        # Sleep button
        sleep_frame = ttk.Frame(main_frame)
        sleep_frame.pack(pady=10)

        ttk.Label(sleep_frame, text="Add delay:", font=("Segoe UI", 10)).pack(side="left", padx=5)

        sleep_buttons = [
            ("0.1s", 0.1),
            ("0.5s", 0.5),
            ("1.0s", 1.0),
            ("2.0s", 2.0),
            ("Custom", None)
        ]

        for label, duration in sleep_buttons:
            btn = ttk.Button(
                sleep_frame,
                text=label,
                command=lambda d=duration: self._add_sleep(d),
                width=10
            )
            btn.pack(side="left", padx=3)

        # Close button
        close_btn = ttk.Button(
            main_frame,
            text="Close",
            command=self.destroy,
            width=20
        )
        close_btn.pack(pady=10)

    def _add_key(self, parent, label, key_name, width=6, toggle=False):
        """Add a clickable key button."""
        btn = tk.Button(
            parent,
            text=label,
            width=width,
            height=2,
            font=("Consolas", 9),
            relief="raised",
            bg="#f0f0f0",
            activebackground="#e0e0e0"
        )

        if toggle:
            # Toggle button for modifiers (new syntax: no parentheses/quotes)
            def on_click():
                if key_name == "shift":
                    self.shift_active = not self.shift_active
                    btn.config(bg="#4CAF50" if self.shift_active else "#f0f0f0")
                    if self.shift_active:
                        self.callback(f"press {key_name}")
                    else:
                        self.callback(f"release {key_name}")
                elif key_name == "ctrl":
                    self.ctrl_active = not self.ctrl_active
                    btn.config(bg="#4CAF50" if self.ctrl_active else "#f0f0f0")
                    if self.ctrl_active:
                        self.callback(f"press {key_name}")
                    else:
                        self.callback(f"release {key_name}")
                elif key_name == "alt":
                    self.alt_active = not self.alt_active
                    btn.config(bg="#4CAF50" if self.alt_active else "#f0f0f0")
                    if self.alt_active:
                        self.callback(f"press {key_name}")
                    else:
                        self.callback(f"release {key_name}")
        else:
            # Regular key (new syntax: no parentheses/quotes)
            def on_click():
                self.callback(f"press {key_name}")
                self.callback(f"sleep 0.5")
                self.callback(f"release {key_name}")

        btn.config(command=on_click)
        btn.pack(side="left", padx=1)
        return btn

    def _add_mouse_btn(self, parent, label, command):
        """Add a mouse action button."""
        def on_click():
            # Convert to new syntax: click instead of click()
            cmd_name = command.replace("()", "")
            self.callback(cmd_name)

        btn = tk.Button(
            parent,
            text=label,
            width=15,
            height=2,
            font=("Consolas", 9),
            relief="raised",
            bg="#e3f2fd",
            activebackground="#bbdefb",
            command=on_click
        )
        btn.pack(side="left", padx=5)

    def _add_spacer(self, parent, width):
        """Add a spacer."""
        spacer = ttk.Frame(parent, width=width * 10)
        spacer.pack(side="left")

    def _add_sleep(self, duration):
        """Add sleep command to macro."""
        from tkinter import simpledialog

        if duration is None:
            # Custom duration dialog
            duration = simpledialog.askfloat(
                "Custom Delay",
                "Enter delay duration in seconds:",
                minvalue=0.01,
                maxvalue=60.0,
                initialvalue=1.0
            )
            if duration is None:
                return  # Cancelled

        # Add sleep command
        command = f"sleep {duration}\n"
        self.callback(command)
