import ctypes
from ctypes import wintypes
import math
import time
from memory import is_game_foreground

user32 = ctypes.WinDLL("user32", use_last_error=True)
VK_SPACE = 0x20
VK_A = 0x41
VK_D = 0x44
FL_ONGROUND = 1

BTN_CLEAR = 0
BTN_JUMP  = 256
BTN_FORCE = 65537

# ── input structs для эмуляции A/D ──
MOUSEEVENTF_MOVE = 0x0001
KEYEVENTF_KEYUP = 0x0002

class MOUSEINPUT(ctypes.Structure):
    _fields_ = [("dx", wintypes.LONG), ("dy", wintypes.LONG),
                ("mouseData", wintypes.DWORD), ("dwFlags", wintypes.DWORD),
                ("time", wintypes.DWORD),
                ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong))]

class KEYBDINPUT(ctypes.Structure):
    _fields_ = [("wVk", wintypes.WORD), ("wScan", wintypes.WORD),
                ("dwFlags", wintypes.DWORD), ("time", wintypes.DWORD),
                ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong))]

class _INPUT_UNION(ctypes.Union):
    _fields_ = [("mi", MOUSEINPUT), ("ki", KEYBDINPUT)]

class INPUT_K(ctypes.Structure):
    _fields_ = [("type", wintypes.DWORD), ("u", _INPUT_UNION)]

user32.SendInput.argtypes = [wintypes.UINT,
                              ctypes.POINTER(INPUT_K),
                              ctypes.c_int]
user32.SendInput.restype = wintypes.UINT

def _key_event(vk, up=False):
    inp = INPUT_K(type=1,
                  u=_INPUT_UNION(ki=KEYBDINPUT(
                      wVk=vk, wScan=0,
                      dwFlags=KEYEVENTF_KEYUP if up else 0)))
    user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT_K))

class Bhop:
    def __init__(self, mem, offset):
        self.mem = mem
        self.client = mem.client_base
        self.off = offset
        self.autostrafe_strength = 8

    def _write(self, value):
        try:
            self.mem.write(self.client + self.off.ButtonJump,
                           value.to_bytes(4, "little", signed=False))
        except OSError:
            pass

    # ── rage autostrafe ──
    SV_AIRACCELERATE = 12.0        # дефолт CS2
    SV_AIR_MAX_WISHSPEED = 30.0    # дефолт CS2
    TICK_INTERVAL = 1.0 / 64.0     # при 128 тиках поставь 1/128
    SURFACE_FRICTION = 1.0

    def _read_velocity(self, pawn):
        try:
            vx = self.mem.read_float(pawn + self.off.m_vecVelocity)
            vy = self.mem.read_float(pawn + self.off.m_vecVelocity + 4)
            return vx, vy
        except OSError:
            return 0.0, 0.0

    def _read_view_yaw(self):
        try:
            ptr = self.mem.read_pointer(self.client + self.off.dwViewAngles)
            if not ptr:
                return 0.0
            # CS2 QAngle = (pitch, yaw, roll). yaw — ВТОРОЙ float.
            f0 = self.mem.read_float(ptr)       # pitch  [-89..89]
            f1 = self.mem.read_float(ptr + 4)   # yaw    [-180..180]
            if abs(f0) <= 89.5 and abs(f1) <= 180.5:
                return f1 % 360.0
            # fallback для старых сборок (yaw-first)
            if abs(f0) <= 180.5 and abs(f1) <= 89.5:
                return f0 % 360.0
            return f1 % 360.0 if abs(f1) <= 720 else 0.0
        except OSError:
            return 0.0

    @staticmethod
    def _norm180(a):
        return (a + 180.0) % 360.0 - 180.0

    def _read_sensitivity(self):
        try:
            base = self.mem.read_pointer(self.client + self.off.dwSensitivity)
            if base:
                s = self.mem.read_float(base + self.off.dwSensitivity_sensitivity)
                if 0.01 < s < 50.0:
                    return s
        except OSError:
            pass
        return 2.0

    def _autostrafe(self, pawn, autofly=False):
        # если игрок сам стрейфит — не мешаем
        if (bool(user32.GetAsyncKeyState(VK_A) & 0x8000) or
            bool(user32.GetAsyncKeyState(VK_D) & 0x8000)):
            return

        vx, vy = self._read_velocity(pawn)
        speed = math.hypot(vx, vy)
        if speed < 20.0:
            return

        vel_yaw = math.degrees(math.atan2(vy, vx))
        view_yaw = self._read_view_yaw()
        delta = ((vel_yaw - view_yaw + 180.0) % 360.0) - 180.0
        # delta > 0  → скорость СЛЕВА от прицела (в CS +yaw = влево)
        # delta < 0  → скорость СПРАВА от прицела

        if autofly:
            # доворачиваем прицел к скорости, но МАКСИМУМ ~2°/тик.
            # Это убирает спин: мы никогда не делаем флик.
            rot = max(-2.0, min(2.0, delta))
            if abs(rot) > 0.3:
                sens = self._read_sensitivity()
                m_yaw = 0.022
                dx = int(-rot / (m_yaw * sens))  # +yaw = мышь влево = отрицательный dx
                if dx != 0:
                    from aimbot import _send_move
                    _send_move(dx, 0)

            # всегда стрейфим в одну сторону (CCW) — так скорость растёт стабильно
            _key_event(VK_A, up=False)
            _key_event(VK_D, up=True)
        else:
            # key-only silent strafe с гистерезисом 5°:
            # переключаем A/D только когда скорость ушла с одной стороны прицела
            if delta > 5.0:
                self._strafe = 'A'   # скорость слева → продолжать влево
            elif delta < -5.0:
                self._strafe = 'D'   # скорость справа → продолжать вправо
            # иначе держим прошлый выбор — никакого флипа

            if self._strafe == 'A':
                _key_event(VK_A, up=False)
                _key_event(VK_D, up=True)
            elif self._strafe == 'D':
                _key_event(VK_D, up=False)
                _key_event(VK_A, up=True)

    def update(self, autostrafe=False):
        if not is_game_foreground():
            self._write(BTN_CLEAR)
            return

        space = bool(user32.GetAsyncKeyState(VK_SPACE) & 0x8000)
        if not space:
            self._write(BTN_CLEAR)
            return

        try:
            pawn = self.mem.read_pointer(self.client + self.off.dwLocalPlayerPawn)
            if not pawn:
                self._write(BTN_CLEAR)
                return
            flags = self.mem.read_uint(pawn + self.off.m_fFlags)
        except OSError:
            self._write(BTN_CLEAR)
            return

        on_ground = bool(flags & FL_ONGROUND)

        if on_ground:
            # ЕДИНСТВЕННОЕ место, где пишем прыжок.
            # BTN_FORCE несёт старший "force"-бит: CS2 обрабатывает его
            # даже если прошлый тик jump был зажат. Именно это даёт
            # мгновенный hop в момент приземления, а не "прыгнул один раз".
            self._write(BTN_FORCE)
            return

        # В воздухе — ОБЯЗАТЕЛЬНЫЙ release.
        # Без него игра видит "+jump held", edge-триггер не срабатывает
        # на следующем приземлении, и бхоп ломается после первого прыжка.
        self._write(BTN_CLEAR)

        if autostrafe:
            self._autostrafe(pawn, autofly=True)   # True → включает "полёт"
        else:
            _key_event(VK_A, up=True)
            _key_event(VK_D, up=True)