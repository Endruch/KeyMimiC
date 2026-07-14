"""
Key name mappings for user-friendly macro writing.
Allows using press('s') instead of press(31).
"""

# Mapping from friendly names to scan codes
KEY_NAMES = {
    # Letters
    'q': 16, 'w': 17, 'e': 18, 'r': 19, 't': 20, 'y': 21, 'u': 22, 'i': 23, 'o': 24, 'p': 25,
    'a': 30, 's': 31, 'd': 32, 'f': 33, 'g': 34, 'h': 35, 'j': 36, 'k': 37, 'l': 38,
    'z': 44, 'x': 45, 'c': 46, 'v': 47, 'b': 48, 'n': 49, 'm': 50,

    # Numbers
    '1': 2, '2': 3, '3': 4, '4': 5, '5': 6, '6': 7, '7': 8, '8': 9, '9': 10, '0': 11,

    # Function keys
    'f1': 59, 'f2': 60, 'f3': 61, 'f4': 62, 'f5': 63, 'f6': 64,
    'f7': 65, 'f8': 66, 'f9': 67, 'f10': 68, 'f11': 87, 'f12': 88,

    # Special keys
    'esc': 1, 'escape': 1,
    'tab': 15,
    'caps': 58, 'capslock': 58,
    'shift': 42, 'lshift': 42, 'rshift': 54,
    'ctrl': 29, 'lctrl': 29, 'rctrl': 97, 'control': 29,
    'alt': 56, 'lalt': 56, 'ralt': 100,
    'space': 57, 'spacebar': 57,
    'enter': 28, 'return': 28,
    'backspace': 14,
    'win': 91, 'lwin': 91, 'rwin': 92, 'windows': 91,
    'menu': 93,

    # Symbols
    'tilde': 41, '`': 41,
    'minus': 12, '-': 12,
    'equals': 13, '=': 13,
    'lbracket': 26, '[': 26,
    'rbracket': 27, ']': 27,
    'backslash': 43, '\\': 43,
    'semicolon': 39, ';': 39,
    'quote': 40, "'": 40,
    'comma': 51, ',': 51,
    'period': 52, '.': 52,
    'slash': 53, '/': 53,

    # Navigation
    'insert': 110, 'ins': 110,
    'delete': 111, 'del': 111,
    'home': 102,
    'end': 107,
    'pageup': 104, 'pgup': 104,
    'pagedown': 109, 'pgdn': 109,
    'scrolllock': 70,

    # Arrows
    'up': 103, 'arrow_up': 103,
    'down': 108, 'arrow_down': 108,
    'left': 105, 'arrow_left': 105,
    'right': 106, 'arrow_right': 106,

    # Numpad
    'numlock': 69,
    'num0': 82, 'num1': 79, 'num2': 80, 'num3': 81,
    'num4': 75, 'num5': 76, 'num6': 77,
    'num7': 71, 'num8': 72, 'num9': 73,
    'numslash': 98, 'num/': 98,
    'numstar': 55, 'num*': 55,
    'numminus': 74, 'num-': 74,
    'numplus': 78, 'num+': 78,
    'numenter': 96,
    'numdot': 83, 'num.': 83,

    # Multimedia
    'next': 163, 'nexttrack': 163,
    'prev': 165, 'prevtrack': 165,
    'stop': 164,
    'play': 162, 'playpause': 162,
    'mute': 160,
    'volup': 176, 'volumeup': 176,
    'voldown': 174, 'volumedown': 174,
}

# Reverse mapping for display
CODE_TO_NAME = {v: k for k, v in KEY_NAMES.items()}

# Mouse action aliases
MOUSE_ACTIONS = {
    'mouse_left': 'click',
    'mouse_right': 'right_click',
    'left_click': 'click',
    'lclick': 'click',
    'rclick': 'right_click',
}


def resolve_key(key):
    """
    Resolve a key name to its scan code.

    Args:
        key: Either an integer scan code or a string key name

    Returns:
        int: The scan code

    Raises:
        ValueError: If the key name is not recognized
    """
    if isinstance(key, int):
        return key

    if isinstance(key, str):
        key_lower = key.lower()
        if key_lower in KEY_NAMES:
            return KEY_NAMES[key_lower]

        try:
            return int(key)
        except ValueError:
            raise ValueError(f"Unknown key name: '{key}'")

    raise ValueError(f"Invalid key type: {type(key)}")


def get_key_display_name(code):
    """Get a friendly display name for a scan code."""
    if code in CODE_TO_NAME:
        return CODE_TO_NAME[code].upper()
    return f"CODE_{code}"
