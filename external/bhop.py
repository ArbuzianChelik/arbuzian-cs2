import ctypes
import math
import random
import threading
import time
from ctypes import wintypes
from memory import is_game_foreground

user32 = ctypes.WinDLL("user32", use_last_error=True)

VK_SPACE = 0x20
FL_ONGROUND = 1

# Значения, которые понимает ButtonJump в CS2 (из старого рабочего кода)
BTN_CLEAR = 0
BTN_JUMP  = 256
BTN_FORCE = 65537

MOUSEEVENTF_MOVE    = 0x0001
KEYEVENTF_SCANCODE  = 0x0008
KEYEVENTF_KEYUP     = 0x0002

SCAN_A = 0x1E
SCAN_D = 0x20


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", wintypes.LONG), ("dy", wintypes.LONG),
        ("mouseData", wintypes.DWORD), ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD), ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong)),
    ]


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", wintypes.WORD), ("wScan", wintypes.WORD),
        ("dwFlags", wintypes.DWORD), ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong)),
    ]


class _INPUTunion(ctypes.Union):
    _fields_ = [("mi", MOUSEINPUT), ("ki", KEYBDINPUT)]


class INPUT(ctypes.Structure):
    _fields_ = [("type", wintypes.DWORD), ("u", _INPUTunion)]


user32.SendInput.argtypes = [wintypes.UINT, ctypes.POINTER(INPUT), ctypes.c_int]
user32.SendInput.restype = wintypes.UINT


def _send_move(dx, dy):
    if dx == 0 and dy == 0:
        return
    inp = INPUT(type=0)
    inp.u.mi = MOUSEINPUT(dx=int(dx), dy=int(dy), dwFlags=MOUSEEVENTF_MOVE)
    user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT))


def _send_scan(scan, keyup=False):
    inp = INPUT(type=1)
    inp.u.ki = KEYBDINPUT(
        wVk=0, wScan=scan,
        dwFlags=KEYEVENTF_SCANCODE | (KEYEVENTF_KEYUP if keyup else 0),
    )
    user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT))


class Bhop:
    def __init__(self, mem, offset):
        self.mem = mem
        self.client = mem.client_base
        self.off = offset
        self.autostrafe_strength = 8
        self._last_value = None

    def _write(self, value):
        if value == self._last_value:
            return
        self._last_value = value
        try:
            self.mem.write(self.client + self.off.ButtonJump,
                           value.to_bytes(4, "little", signed=False))
        except OSError:
            pass

    def update(self, autostrafe=False):
        # В меню / без фокуса — ничего не пишем
        if not is_game_foreground():
            return

        try:
            pawn = self.mem.read_pointer(self.client + self.off.dwLocalPlayerPawn)
            if not pawn:
                return
            hp = self.mem.read_int(pawn + self.off.m_iHealth)
            if not (0 < hp <= 100):
                return  # мёртв / не в матче
            flags = self.mem.read_uint(pawn + self.off.m_fFlags)
        except OSError:
            return

        space = bool(user32.GetAsyncKeyState(VK_SPACE) & 0x8000)
        on_ground = bool(flags & 1)

        if not space:
            self._write(0)
            return

        if on_ground:
            self._write(256)   # обычный jump
        else:
            self._write(65537) # force jump — держим в воздухе
            if autostrafe:
                a = bool(user32.GetAsyncKeyState(0x41) & 0x8000)
                d = bool(user32.GetAsyncKeyState(0x44) & 0x8000)
                if a != d:
                    from aimbot import _send_move
                    _send_move(-self.autostrafe_strength if a else self.autostrafe_strength, 0)