"""
Windows SendInput wrapper for injecting keyboard and mouse events.

All ctypes/Windows API details live here. On non-Windows platforms every
function is a harmless no-op returning 0, so the rest of the app (model,
executor, GUI) can be imported and exercised on any OS.
"""

import ctypes

from .constants import IS_WINDOWS

if IS_WINDOWS:
    PUL = ctypes.POINTER(ctypes.c_ulong)

    class _KeyBdInput(ctypes.Structure):
        _fields_ = [
            ("wVk", ctypes.c_ushort),
            ("wScan", ctypes.c_ushort),
            ("dwFlags", ctypes.c_ulong),
            ("time", ctypes.c_ulong),
            ("dwExtraInfo", PUL),
        ]

    class _HardwareInput(ctypes.Structure):
        _fields_ = [
            ("uMsg", ctypes.c_ulong),
            ("wParamL", ctypes.c_short),
            ("wParamH", ctypes.c_ushort),
        ]

    class _MouseInput(ctypes.Structure):
        _fields_ = [
            ("dx", ctypes.c_long),
            ("dy", ctypes.c_long),
            ("mouseData", ctypes.c_ulong),
            ("dwFlags", ctypes.c_ulong),
            ("time", ctypes.c_ulong),
            ("dwExtraInfo", PUL),
        ]

    class _InputUnion(ctypes.Union):
        _fields_ = [("ki", _KeyBdInput), ("mi", _MouseInput), ("hi", _HardwareInput)]

    class _Input(ctypes.Structure):
        _fields_ = [("type", ctypes.c_ulong), ("ii", _InputUnion)]

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
        return ctypes.pointer(ctypes.c_ulong(0))

    def _send_input(*inputs):
        n = len(inputs)
        arr = (_Input * n)(*inputs)
        return ctypes.windll.user32.SendInput(n, ctypes.pointer(arr), ctypes.sizeof(_Input))


def send_key_down(scan_code, extended=False):
    """Inject a key-down event using a hardware scan code. Returns events sent (0/1)."""
    if not IS_WINDOWS:
        return 0
    flags = KEYEVENTF_SCANCODE | (KEYEVENTF_EXTENDEDKEY if extended else 0)
    ki = _KeyBdInput(0, scan_code, flags, 0, _extra_info())
    return _send_input(_Input(INPUT_KEYBOARD, _InputUnion(ki=ki)))


def send_key_up(scan_code, extended=False):
    """Inject a key-up event using a hardware scan code. Returns events sent (0/1)."""
    if not IS_WINDOWS:
        return 0
    flags = KEYEVENTF_SCANCODE | KEYEVENTF_KEYUP | (KEYEVENTF_EXTENDEDKEY if extended else 0)
    ki = _KeyBdInput(0, scan_code, flags, 0, _extra_info())
    return _send_input(_Input(INPUT_KEYBOARD, _InputUnion(ki=ki)))


def send_mouse_move_absolute(x, y):
    """Move the mouse to an absolute screen position. Returns events sent (0/1)."""
    if not IS_WINDOWS:
        return 0
    screen_w = ctypes.windll.user32.GetSystemMetrics(0)
    screen_h = ctypes.windll.user32.GetSystemMetrics(1)
    norm_x = int((x * 65536) / max(screen_w, 1))
    norm_y = int((y * 65536) / max(screen_h, 1))
    mi = _MouseInput(norm_x, norm_y, 0, MOUSEEVENTF_MOVE | MOUSEEVENTF_ABSOLUTE, 0, _extra_info())
    return _send_input(_Input(INPUT_MOUSE, _InputUnion(mi=mi)))


def send_mouse_move_relative(dx, dy):
    """
    Move the mouse by a relative offset. Returns events sent (0/1).

    Used specifically for movement recorded while a mouse button was held
    (see model.MousePathPoint) - many games switch to reading raw relative
    mouse input for camera look/aim while a button is held, often confining
    or hiding the OS cursor entirely, so an absolute move wouldn't land
    correctly (or at all) there; a relative delta matches what the game
    itself is reading.
    """
    if not IS_WINDOWS:
        return 0
    mi = _MouseInput(dx, dy, 0, MOUSEEVENTF_MOVE, 0, _extra_info())
    return _send_input(_Input(INPUT_MOUSE, _InputUnion(mi=mi)))


def send_mouse_button_down(button="left"):
    """Press (and hold) a mouse button at the current cursor position. Returns events sent (0/1)."""
    if not IS_WINDOWS:
        return 0
    flag = MOUSEEVENTF_RIGHTDOWN if button == "right" else MOUSEEVENTF_LEFTDOWN
    mi = _MouseInput(0, 0, 0, flag, 0, _extra_info())
    return _send_input(_Input(INPUT_MOUSE, _InputUnion(mi=mi)))


def send_mouse_button_up(button="left"):
    """Release a mouse button. Returns events sent (0/1)."""
    if not IS_WINDOWS:
        return 0
    flag = MOUSEEVENTF_RIGHTUP if button == "right" else MOUSEEVENTF_LEFTUP
    mi = _MouseInput(0, 0, 0, flag, 0, _extra_info())
    return _send_input(_Input(INPUT_MOUSE, _InputUnion(mi=mi)))


def get_mouse_position():
    """Return current (x, y) mouse position, or (0, 0) on non-Windows."""
    if not IS_WINDOWS:
        return (0, 0)

    class _POINT(ctypes.Structure):
        _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]

    pt = _POINT()
    ctypes.windll.user32.GetCursorPos(ctypes.byref(pt))
    return (pt.x, pt.y)


def is_cursor_visible() -> bool:
    """
    True if the OS cursor is currently shown, False if hidden.

    Used by Recorder to decide whether mouse movement should be captured as
    an absolute position or a relative delta: many games hide the cursor
    (and confine it, or read raw HID deltas directly) specifically while
    reading relative mouse input for camera look/aim, e.g. holding a button
    to aim - the cursor's absolute position during that time isn't
    meaningful, unlike an ordinary held-button drag (e.g. dragging an item
    in an inventory UI) where the cursor stays visible and tracked
    normally, and absolute coordinates are correct.
    """
    if not IS_WINDOWS:
        return True

    class _CursorInfo(ctypes.Structure):
        _fields_ = [
            ("cbSize", ctypes.c_uint32),
            ("flags", ctypes.c_uint32),
            ("hCursor", ctypes.c_void_p),
            ("ptScreenPos_x", ctypes.c_long),
            ("ptScreenPos_y", ctypes.c_long),
        ]

    CURSOR_SHOWING = 0x00000001
    info = _CursorInfo()
    info.cbSize = ctypes.sizeof(_CursorInfo)
    try:
        if not ctypes.windll.user32.GetCursorInfo(ctypes.byref(info)):
            return True  # query failed - default to the safer/previous behavior (absolute)
    except Exception:
        return True
    return bool(info.flags & CURSOR_SHOWING)
