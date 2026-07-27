"""
Clean SendInput wrapper for Windows input injection.

Provides functional interface for sending keyboard and mouse events.
All Windows API details are encapsulated here.
"""

import ctypes
import time

try:
    IS_WINDOWS = True
    import sys
    if not sys.platform.startswith('win'):
        IS_WINDOWS = False
except:
    IS_WINDOWS = False


if IS_WINDOWS:
    PUL = ctypes.POINTER(ctypes.c_ulong)

    class KeyBdInput(ctypes.Structure):
        _fields_ = [
            ("wVk", ctypes.c_ushort),
            ("wScan", ctypes.c_ushort),
            ("dwFlags", ctypes.c_ulong),
            ("time", ctypes.c_ulong),
            ("dwExtraInfo", PUL)
        ]

    class HardwareInput(ctypes.Structure):
        _fields_ = [
            ("uMsg", ctypes.c_ulong),
            ("wParamL", ctypes.c_short),
            ("wParamH", ctypes.c_ushort)
        ]

    class MouseInput(ctypes.Structure):
        _fields_ = [
            ("dx", ctypes.c_long),
            ("dy", ctypes.c_long),
            ("mouseData", ctypes.c_ulong),
            ("dwFlags", ctypes.c_ulong),
            ("time", ctypes.c_ulong),
            ("dwExtraInfo", PUL)
        ]

    class InputUnion(ctypes.Union):
        _fields_ = [("ki", KeyBdInput), ("mi", MouseInput), ("hi", HardwareInput)]

    class Input(ctypes.Structure):
        _fields_ = [("type", ctypes.c_ulong), ("ii", InputUnion)]

    # Constants
    INPUT_MOUSE = 0
    INPUT_KEYBOARD = 1

    KEYEVENTF_EXTENDEDKEY = 0x0001
    KEYEVENTF_KEYUP = 0x0002
    KEYEVENTF_SCANCODE = 0x0008

    MOUSEEVENTF_MOVE = 0x0001
    MOUSEEVENTF_LEFTDOWN = 0x0002
    MOUSEEVENTF_LEFTUP = 0x0004
    MOUSEEVENTF_RIGHTDOWN = 0x0008
    MOUSEEVENTF_RIGHTUP = 0x0010
    MOUSEEVENTF_ABSOLUTE = 0x8000

    def _extra_info():
        """Create extra info pointer for input structures."""
        return ctypes.pointer(ctypes.c_ulong(0))

    def _send_input(*inputs):
        """
        Send input events using SendInput API.

        Returns:
            Number of events successfully sent.
            If return value is 0, input was blocked (likely by privilege issues).
        """
        n = len(inputs)
        arr = (Input * n)(*inputs)
        result = ctypes.windll.user32.SendInput(n, ctypes.pointer(arr), ctypes.sizeof(Input))
        return result


def send_key_down(scan_code, extended=False):
    """
    Send key down event using hardware scan code.

    Args:
        scan_code: Hardware scan code (e.g., 0x1F for 'S' key)
        extended: True for extended keys (arrows, navigation, etc.)

    Returns:
        Number of events successfully injected (1 on success, 0 on failure)
    """
    if not IS_WINDOWS:
        return 0

    flags = KEYEVENTF_SCANCODE
    if extended:
        flags |= KEYEVENTF_EXTENDEDKEY

    ki = KeyBdInput(0, scan_code, flags, 0, _extra_info())
    inp = Input(INPUT_KEYBOARD, InputUnion(ki=ki))

    return _send_input(inp)


def send_key_up(scan_code, extended=False):
    """
    Send key up event using hardware scan code.

    Args:
        scan_code: Hardware scan code (e.g., 0x1F for 'S' key)
        extended: True for extended keys (arrows, navigation, etc.)

    Returns:
        Number of events successfully injected (1 on success, 0 on failure)
    """
    if not IS_WINDOWS:
        return 0

    flags = KEYEVENTF_SCANCODE | KEYEVENTF_KEYUP
    if extended:
        flags |= KEYEVENTF_EXTENDEDKEY

    ki = KeyBdInput(0, scan_code, flags, 0, _extra_info())
    inp = Input(INPUT_KEYBOARD, InputUnion(ki=ki))

    return _send_input(inp)


def send_mouse_move(dx, dy):
    """
    Move mouse by relative offset.

    Args:
        dx: Horizontal movement (pixels)
        dy: Vertical movement (pixels)

    Returns:
        Number of events successfully injected (1 on success, 0 on failure)
    """
    if not IS_WINDOWS:
        return 0

    mi = MouseInput(int(dx), int(dy), 0, MOUSEEVENTF_MOVE, 0, _extra_info())
    inp = Input(INPUT_MOUSE, InputUnion(mi=mi))

    return _send_input(inp)


def send_mouse_move_absolute(x, y):
    """
    Move mouse to absolute screen position.

    Args:
        x: Absolute X coordinate (pixels)
        y: Absolute Y coordinate (pixels)

    Returns:
        Number of events successfully injected (1 on success, 0 on failure)
    """
    if not IS_WINDOWS:
        return 0

    # Get screen dimensions
    screen_width = ctypes.windll.user32.GetSystemMetrics(0)
    screen_height = ctypes.windll.user32.GetSystemMetrics(1)

    # Convert to normalized coordinates (0-65535)
    # Windows uses 0-65535 for absolute positioning
    norm_x = int((x * 65536) / screen_width)
    norm_y = int((y * 65536) / screen_height)

    mi = MouseInput(norm_x, norm_y, 0, MOUSEEVENTF_MOVE | MOUSEEVENTF_ABSOLUTE, 0, _extra_info())
    inp = Input(INPUT_MOUSE, InputUnion(mi=mi))

    return _send_input(inp)


def get_mouse_position():
    """
    Get current mouse position.

    Returns:
        Tuple (x, y) of current mouse position, or (0, 0) on non-Windows
    """
    if not IS_WINDOWS:
        return (0, 0)

    class POINT(ctypes.Structure):
        _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]

    pt = POINT()
    ctypes.windll.user32.GetCursorPos(ctypes.byref(pt))
    return (pt.x, pt.y)


def send_mouse_click(button='left', duration=0.03):
    """
    Perform mouse click.

    Args:
        button: 'left' or 'right'
        duration: Time between down and up events (seconds)

    Returns:
        Tuple (down_result, up_result) - number of events injected for each
    """
    if not IS_WINDOWS:
        return (0, 0)

    if button == 'right':
        down_flag = MOUSEEVENTF_RIGHTDOWN
        up_flag = MOUSEEVENTF_RIGHTUP
    else:
        down_flag = MOUSEEVENTF_LEFTDOWN
        up_flag = MOUSEEVENTF_LEFTUP

    # Send down event
    mi_down = MouseInput(0, 0, 0, down_flag, 0, _extra_info())
    inp_down = Input(INPUT_MOUSE, InputUnion(mi=mi_down))
    down_result = _send_input(inp_down)

    # Wait
    time.sleep(duration)

    # Send up event
    mi_up = MouseInput(0, 0, 0, up_flag, 0, _extra_info())
    inp_up = Input(INPUT_MOUSE, InputUnion(mi=mi_up))
    up_result = _send_input(inp_up)

    return (down_result, up_result)
