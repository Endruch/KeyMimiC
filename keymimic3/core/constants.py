"""
Hardware scan code tables (Windows "Set 1" scan codes).

Internal key identifiers are plain lowercase strings (e.g. "a", "f1", "lctrl").
SCAN_CODES maps an internal id to (scan_code, extended) used by SendInput.
SCAN_TO_CODE / SCAN_TO_CODE_EXT map a raw scan code back to an internal id,
used by the low-level hooks when decoding a captured key event.
"""

import sys

IS_WINDOWS = sys.platform.startswith("win")

# internal_id -> (scan_code, extended)
SCAN_CODES = {
    # Row 1
    "esc": (0x01, False),
    "1": (0x02, False),
    "2": (0x03, False),
    "3": (0x04, False),
    "4": (0x05, False),
    "5": (0x06, False),
    "6": (0x07, False),
    "7": (0x08, False),
    "8": (0x09, False),
    "9": (0x0A, False),
    "0": (0x0B, False),
    "minus": (0x0C, False),
    "equals": (0x0D, False),
    "backspace": (0x0E, False),

    # Row 2
    "tab": (0x0F, False),
    "q": (0x10, False),
    "w": (0x11, False),
    "e": (0x12, False),
    "r": (0x13, False),
    "t": (0x14, False),
    "y": (0x15, False),
    "u": (0x16, False),
    "i": (0x17, False),
    "o": (0x18, False),
    "p": (0x19, False),
    "lbracket": (0x1A, False),
    "rbracket": (0x1B, False),
    "enter": (0x1C, False),

    # Row 3
    "lctrl": (0x1D, False),
    "a": (0x1E, False),
    "s": (0x1F, False),
    "d": (0x20, False),
    "f": (0x21, False),
    "g": (0x22, False),
    "h": (0x23, False),
    "j": (0x24, False),
    "k": (0x25, False),
    "l": (0x26, False),
    "semicolon": (0x27, False),
    "quote": (0x28, False),
    "grave": (0x29, False),

    # Row 4
    "lshift": (0x2A, False),
    "backslash": (0x2B, False),
    "z": (0x2C, False),
    "x": (0x2D, False),
    "c": (0x2E, False),
    "v": (0x2F, False),
    "b": (0x30, False),
    "n": (0x31, False),
    "m": (0x32, False),
    "comma": (0x33, False),
    "period": (0x34, False),
    "slash": (0x35, False),
    "rshift": (0x36, False),

    # Row 5 (bottom)
    "lalt": (0x38, False),
    "space": (0x39, False),
    "caps": (0x3A, False),

    # Function keys
    "f1": (0x3B, False),
    "f2": (0x3C, False),
    "f3": (0x3D, False),
    "f4": (0x3E, False),
    "f5": (0x3F, False),
    "f6": (0x40, False),
    "f7": (0x41, False),
    "f8": (0x42, False),
    "f9": (0x43, False),
    "f10": (0x44, False),
    "f11": (0x57, False),
    "f12": (0x58, False),

    "numlock": (0x45, False),
    "scrolllock": (0x46, False),

    # Numpad
    "num0": (0x52, False),
    "num1": (0x4F, False),
    "num2": (0x50, False),
    "num3": (0x51, False),
    "num4": (0x4B, False),
    "num5": (0x4C, False),
    "num6": (0x4D, False),
    "num7": (0x47, False),
    "num8": (0x48, False),
    "num9": (0x49, False),
    "num_decimal": (0x53, False),
    "num_multiply": (0x37, False),
    "num_minus": (0x4A, False),
    "num_plus": (0x4E, False),

    # Extended keys (E0 prefix)
    "rctrl": (0x1D, True),
    "ralt": (0x38, True),
    "num_enter": (0x1C, True),
    "num_divide": (0x35, True),
    "home": (0x47, True),
    "up": (0x48, True),
    "pageup": (0x49, True),
    "left": (0x4B, True),
    "right": (0x4D, True),
    "end": (0x4F, True),
    "down": (0x50, True),
    "pagedown": (0x51, True),
    "insert": (0x52, True),
    "delete": (0x53, True),
    "lwin": (0x5B, True),
    "rwin": (0x5C, True),
    "menu": (0x5D, True),
}

SCAN_TO_CODE = {}
SCAN_TO_CODE_EXT = {}
for _internal_id, (_scan, _ext) in SCAN_CODES.items():
    if _ext:
        SCAN_TO_CODE_EXT[_scan] = _internal_id
    else:
        SCAN_TO_CODE[_scan] = _internal_id
del _internal_id, _scan, _ext
