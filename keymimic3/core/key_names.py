"""
Symbolic key names, aliases and the QWERTY layout used by the visual keyboard picker.
"""

from .constants import SCAN_CODES

# alias -> canonical internal id (every canonical id also maps to itself)
KEY_NAMES = {code: code for code in SCAN_CODES}

_ALIASES = {
    "ctrl": "lctrl",
    "control": "lctrl",
    "shift": "lshift",
    "alt": "lalt",
    "win": "lwin",
    "windows": "lwin",
    "cmd": "lwin",
    "esc": "esc",
    "escape": "esc",
    "del": "delete",
    "ins": "insert",
    "pgup": "pageup",
    "pgdn": "pagedown",
    "capslock": "caps",
    "-": "minus",
    "=": "equals",
    "[": "lbracket",
    "]": "rbracket",
    ";": "semicolon",
    "'": "quote",
    "`": "grave",
    "\\": "backslash",
    ",": "comma",
    ".": "period",
    "/": "slash",
}
KEY_NAMES.update(_ALIASES)

# Pretty display labels for keys whose canonical id isn't self-explanatory.
_DISPLAY_LABELS = {
    "lctrl": "Ctrl", "rctrl": "RCtrl",
    "lshift": "Shift", "rshift": "RShift",
    "lalt": "Alt", "ralt": "RAlt",
    "lwin": "Win", "rwin": "RWin",
    "esc": "Esc", "caps": "Caps",
    "enter": "Enter", "backspace": "Backspace",
    "space": "Space", "tab": "Tab",
    "minus": "-", "equals": "=",
    "lbracket": "[", "rbracket": "]",
    "semicolon": ";", "quote": "'", "grave": "`",
    "backslash": "\\", "comma": ",", "period": ".", "slash": "/",
    "up": "Up", "down": "Down", "left": "Left", "right": "Right",
    "pageup": "PgUp", "pagedown": "PgDn", "home": "Home", "end": "End",
    "insert": "Ins", "delete": "Del", "menu": "Menu",
    "numlock": "NumLock", "scrolllock": "ScrLk",
    "num_enter": "Num.Enter", "num_divide": "Num/", "num_multiply": "Num*",
    "num_minus": "Num-", "num_plus": "Num+", "num_decimal": "Num.",
}


def resolve_key(key):
    """
    Resolve a key name (or already-canonical id) to its canonical internal id.

    Raises:
        ValueError: if the key name is not recognized.
    """
    if isinstance(key, str):
        lookup = key.strip().lower()
        if lookup in KEY_NAMES:
            return KEY_NAMES[lookup]
    raise ValueError(f"Unknown key: {key!r}")


def get_key_display_name(code):
    """Return a short human-friendly label for a canonical internal key id."""
    if code in _DISPLAY_LABELS:
        return _DISPLAY_LABELS[code]
    if code.startswith("num") and code[3:].isdigit():
        return f"Num{code[3:]}"
    return code.upper()


# Rows of the visual QWERTY keyboard picker. Each entry is a canonical internal id.
KEYBOARD_LAYOUT = [
    ["esc", "f1", "f2", "f3", "f4", "f5", "f6", "f7", "f8", "f9", "f10", "f11", "f12"],
    ["grave", "1", "2", "3", "4", "5", "6", "7", "8", "9", "0", "minus", "equals", "backspace"],
    ["tab", "q", "w", "e", "r", "t", "y", "u", "i", "o", "p", "lbracket", "rbracket", "backslash"],
    ["caps", "a", "s", "d", "f", "g", "h", "j", "k", "l", "semicolon", "quote", "enter"],
    ["lshift", "z", "x", "c", "v", "b", "n", "m", "comma", "period", "slash", "rshift"],
    ["lctrl", "lwin", "lalt", "space", "ralt", "rwin", "menu", "rctrl"],
    ["insert", "delete", "home", "end", "pageup", "pagedown"],
    ["up", "down", "left", "right"],
    ["numlock", "num_divide", "num_multiply", "num_minus"],
    ["num7", "num8", "num9", "num_plus"],
    ["num4", "num5", "num6"],
    ["num1", "num2", "num3", "num_enter"],
    ["num0", "num_decimal"],
]
