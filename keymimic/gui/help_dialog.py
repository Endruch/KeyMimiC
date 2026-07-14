"""
Help dialog showing key code reference table.
"""

import tkinter as tk
from tkinter import ttk


class HelpDialog(tk.Toplevel):
    """Dialog showing key code reference."""

    def __init__(self, parent):
        super().__init__(parent)
        self.title("KeyMimic Help - Key Code Reference")
        self.geometry("900x700")
        self.transient(parent)

        self._build_ui()

        # Center on parent
        self.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() - self.winfo_width()) // 2
        y = parent.winfo_y() + (parent.winfo_height() - self.winfo_height()) // 2
        self.geometry(f"+{x}+{y}")

    def _build_ui(self):
        """Build the help dialog UI."""
        # Main container with scrollbar
        main_frame = ttk.Frame(self, padding=10)
        main_frame.pack(fill="both", expand=True)

        # Canvas with scrollbar
        canvas = tk.Canvas(main_frame, highlightthickness=0)
        scrollbar = ttk.Scrollbar(main_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # Title
        title = ttk.Label(
            scrollable_frame,
            text="KeyMimic Key Code Reference",
            font=("Segoe UI", 16, "bold")
        )
        title.pack(pady=(0, 10))

        # Description
        desc = ttk.Label(
            scrollable_frame,
            text="You can use either symbolic names (e.g., 's', 'ctrl') or numeric codes (e.g., 31, 29)",
            font=("Segoe UI", 10),
            foreground="gray"
        )
        desc.pack(pady=(0, 20))

        # Key categories
        self._add_section(scrollable_frame, "Function Keys", [
            ("F1-F12", "f1, f2, f3, ..., f12", "59-68, 87-88"),
            ("ESC", "esc, escape", "1"),
        ])

        self._add_section(scrollable_frame, "Letters (QWERTY Layout)", [
            ("Q-P", "q, w, e, r, t, y, u, i, o, p", "16-25"),
            ("A-L", "a, s, d, f, g, h, j, k, l", "30-38"),
            ("Z-M", "z, x, c, v, b, n, m", "44-50"),
        ])

        self._add_section(scrollable_frame, "Numbers", [
            ("1-0", "1, 2, 3, 4, 5, 6, 7, 8, 9, 0", "2-11"),
        ])

        self._add_section(scrollable_frame, "Modifier Keys", [
            ("Shift", "shift, lshift, rshift", "42, 54"),
            ("Ctrl", "ctrl, lctrl, rctrl, control", "29, 97"),
            ("Alt", "alt, lalt, ralt", "56, 100"),
            ("Win/Super", "win, lwin, rwin, windows", "91, 92"),
        ])

        self._add_section(scrollable_frame, "Special Keys", [
            ("Enter", "enter, return", "28"),
            ("Space", "space, spacebar", "57"),
            ("Tab", "tab", "15"),
            ("Backspace", "backspace", "14"),
            ("Caps Lock", "caps, capslock", "58"),
            ("Menu", "menu", "93"),
        ])

        self._add_section(scrollable_frame, "Symbols", [
            ("Tilde/Backtick", "`", "41"),
            ("Minus", "-, minus", "12"),
            ("Equals", "=, equals", "13"),
            ("Brackets", "[, ]", "26, 27"),
            ("Backslash", "\\, backslash", "43"),
            ("Semicolon", ";, semicolon", "39"),
            ("Quote", "', quote", "40"),
            ("Comma", ",, comma", "51"),
            ("Period", "., period", "52"),
            ("Slash", "/, slash", "53"),
        ])

        self._add_section(scrollable_frame, "Navigation", [
            ("Insert", "insert, ins", "110"),
            ("Delete", "delete, del", "111"),
            ("Home", "home", "102"),
            ("End", "end", "107"),
            ("Page Up", "pageup, pgup", "104"),
            ("Page Down", "pagedown, pgdn", "109"),
            ("Scroll Lock", "scrolllock", "70"),
        ])

        self._add_section(scrollable_frame, "Arrow Keys", [
            ("Up", "up, arrow_up", "103"),
            ("Down", "down, arrow_down", "108"),
            ("Left", "left, arrow_left", "105"),
            ("Right", "right, arrow_right", "106"),
        ])

        self._add_section(scrollable_frame, "Numpad", [
            ("Num Lock", "numlock", "69"),
            ("Numpad 0-9", "num0, num1, ..., num9", "82, 79-81, 75-77, 71-73"),
            ("Numpad Operators", "num/, num*, num-, num+", "98, 55, 74, 78"),
            ("Numpad Enter", "numenter", "96"),
            ("Numpad Dot", "num., numdot", "83"),
        ])

        self._add_section(scrollable_frame, "Multimedia", [
            ("Play/Pause", "play, playpause", "162"),
            ("Next Track", "next, nexttrack", "163"),
            ("Previous Track", "prev, prevtrack", "165"),
            ("Stop", "stop", "164"),
            ("Mute", "mute", "160"),
            ("Volume Up", "volup, volumeup", "176"),
            ("Volume Down", "voldown, volumedown", "174"),
        ])

        self._add_section(scrollable_frame, "Mouse Actions", [
            ("Left Click", "click(), mouse_left(), lclick()", ""),
            ("Right Click", "right_click(), mouse_right(), rclick()", ""),
            ("Mouse Move", "move(dx, dy)", ""),
        ])

        self._add_section(scrollable_frame, "Other Commands", [
            ("Press Key", "press('s') or press(31)", ""),
            ("Release Key", "release('s') or release(31)", ""),
            ("Sleep/Wait", "sleep(seconds)", ""),
            ("Log Message", "log('message')", ""),
        ])

        # Close button
        close_btn = ttk.Button(
            scrollable_frame,
            text="Close",
            command=self.destroy,
            width=20
        )
        close_btn.pack(pady=20)

        # Bind mouse wheel
        canvas.bind_all("<MouseWheel>", lambda e: canvas.yview_scroll(int(-1*(e.delta/120)), "units"))

    def _add_section(self, parent, title, items):
        """Add a section with key codes."""
        # Section frame
        section = ttk.LabelFrame(parent, text=title, padding=10)
        section.pack(fill="x", padx=5, pady=5)

        # Create table
        for key_name, symbolic, code in items:
            row = ttk.Frame(section)
            row.pack(fill="x", pady=2)

            ttk.Label(
                row,
                text=key_name,
                font=("Segoe UI", 10, "bold"),
                width=20
            ).pack(side="left", padx=5)

            ttk.Label(
                row,
                text=symbolic,
                font=("Consolas", 9),
                foreground="#0066cc",
                width=40
            ).pack(side="left", padx=5)

            if code:
                ttk.Label(
                    row,
                    text=f"Code: {code}",
                    font=("Consolas", 9),
                    foreground="gray",
                    width=20
                ).pack(side="left", padx=5)
