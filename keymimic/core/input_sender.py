"""
Low-level input sending via Windows SendInput API.
"""

import ctypes
import time
from .constants import IS_WINDOWS

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

    def _extra_info():
        return ctypes.pointer(ctypes.c_ulong(0))

    def _send(*inputs):
        n = len(inputs)
        arr = (Input * n)(*inputs)
        ctypes.windll.user32.SendInput(n, ctypes.pointer(arr), ctypes.sizeof(Input))


def key_down(scan, extended=False):
    """Send key down event."""
    if not IS_WINDOWS:
        return
    flags = KEYEVENTF_SCANCODE | (KEYEVENTF_EXTENDEDKEY if extended else 0)
    ki = KeyBdInput(0, scan, flags, 0, _extra_info())
    _send(Input(INPUT_KEYBOARD, InputUnion(ki=ki)))


def key_up(scan, extended=False):
    """Send key up event."""
    if not IS_WINDOWS:
        return
    flags = KEYEVENTF_SCANCODE | KEYEVENTF_KEYUP | (KEYEVENTF_EXTENDEDKEY if extended else 0)
    ki = KeyBdInput(0, scan, flags, 0, _extra_info())
    _send(Input(INPUT_KEYBOARD, InputUnion(ki=ki)))


def mouse_move(dx, dy):
    """Move mouse by relative offset."""
    if not IS_WINDOWS:
        return
    mi = MouseInput(int(dx), int(dy), 0, MOUSEEVENTF_MOVE, 0, _extra_info())
    _send(Input(INPUT_MOUSE, InputUnion(mi=mi)))


def mouse_click(right=False):
    """Perform mouse click."""
    if not IS_WINDOWS:
        return
    down = MOUSEEVENTF_RIGHTDOWN if right else MOUSEEVENTF_LEFTDOWN
    up = MOUSEEVENTF_RIGHTUP if right else MOUSEEVENTF_LEFTUP
    mi_down = MouseInput(0, 0, 0, down, 0, _extra_info())
    _send(Input(INPUT_MOUSE, InputUnion(mi=mi_down)))
    time.sleep(0.03)
    mi_up = MouseInput(0, 0, 0, up, 0, _extra_info())
    _send(Input(INPUT_MOUSE, InputUnion(mi=mi_up)))
