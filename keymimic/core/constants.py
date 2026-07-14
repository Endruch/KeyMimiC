"""
Constants and scan code mappings for keyboard input.
"""

import sys

IS_WINDOWS = sys.platform.startswith("win")

# Scan code table mapping KeyMimiC codes to (hardware_scancode, extended_flag)
SCAN_CODES = {
    # Function row
    1: (0x01, False),  # ESC
    59: (0x3B, False), 60: (0x3C, False), 61: (0x3D, False), 62: (0x3E, False),
    63: (0x3F, False), 64: (0x40, False), 65: (0x41, False), 66: (0x42, False),
    67: (0x43, False), 68: (0x44, False), 87: (0x57, False), 88: (0x58, False),

    # Numbers row
    41: (0x29, False),  # ` ~
    2: (0x02, False), 3: (0x03, False), 4: (0x04, False), 5: (0x05, False),
    6: (0x06, False), 7: (0x07, False), 8: (0x08, False), 9: (0x09, False),
    10: (0x0A, False), 11: (0x0B, False),
    12: (0x0C, False), 13: (0x0D, False), 14: (0x0E, False),  # - = BACKSPACE

    # QWERTY row
    15: (0x0F, False),  # TAB
    16: (0x10, False), 17: (0x11, False), 18: (0x12, False), 19: (0x13, False),
    20: (0x14, False), 21: (0x15, False), 22: (0x16, False), 23: (0x17, False),
    24: (0x18, False), 25: (0x19, False), 26: (0x1A, False), 27: (0x1B, False),
    43: (0x2B, False),  # backslash

    # ASDF row
    58: (0x3A, False),  # CAPS LOCK
    30: (0x1E, False), 31: (0x1F, False), 32: (0x20, False), 33: (0x21, False),
    34: (0x22, False), 35: (0x23, False), 36: (0x24, False), 37: (0x25, False),
    38: (0x26, False), 39: (0x27, False), 40: (0x28, False),
    28: (0x1C, False),  # ENTER

    # ZXCV row
    42: (0x2A, False),  # LEFT SHIFT
    44: (0x2C, False), 45: (0x2D, False), 46: (0x2E, False), 47: (0x2F, False),
    48: (0x30, False), 49: (0x31, False), 50: (0x32, False), 51: (0x33, False),
    52: (0x34, False), 53: (0x35, False), 54: (0x36, False),  # RIGHT SHIFT

    # Bottom row
    29: (0x1D, False),  # LEFT CTRL
    91: (0x5B, True),   # LEFT WIN
    56: (0x38, False),  # LEFT ALT
    57: (0x39, False),  # SPACE
    100: (0x38, True),  # RIGHT ALT
    92: (0x5C, True),   # RIGHT WIN
    93: (0x5D, True),   # MENU
    97: (0x1D, True),   # RIGHT CTRL

    # Navigation cluster
    110: (0x52, True),  # INSERT
    111: (0x53, True),  # DELETE
    102: (0x47, True),  # HOME
    107: (0x4F, True),  # END
    104: (0x49, True),  # PAGE UP
    109: (0x51, True),  # PAGE DOWN
    70: (0x46, False),  # SCROLL LOCK

    # Arrows
    103: (0x48, True), 108: (0x50, True), 105: (0x4B, True), 106: (0x4D, True),

    # Numpad
    69: (0x45, False),  # NUM LOCK
    98: (0x35, True),   # NUMPAD /
    55: (0x37, False),  # NUMPAD *
    74: (0x4A, False),  # NUMPAD -
    71: (0x47, False), 72: (0x48, False), 73: (0x49, False),  # 7 8 9
    78: (0x4E, False),  # NUMPAD +
    75: (0x4B, False), 76: (0x4C, False), 77: (0x4D, False),  # 4 5 6
    79: (0x4F, False), 80: (0x50, False), 81: (0x51, False),  # 1 2 3
    96: (0x1C, True),   # NUMPAD ENTER
    82: (0x52, False),  # NUMPAD 0
    83: (0x53, False),  # NUMPAD .

    # Multimedia
    163: (0x19, True),  # NEXT TRACK
    165: (0x10, True),  # PREV TRACK
    164: (0x24, True),  # STOP
    162: (0x22, True),  # PLAY/PAUSE
    160: (0x20, True),  # MUTE
    176: (0x30, True),  # VOLUME UP
    174: (0x2E, True),  # VOLUME DOWN
}

# Reverse mappings for recorder
SCAN_TO_CODE = {v[0]: k for k, v in SCAN_CODES.items() if not v[1]}
SCAN_TO_CODE_EXT = {v[0]: k for k, v in SCAN_CODES.items() if v[1]}
