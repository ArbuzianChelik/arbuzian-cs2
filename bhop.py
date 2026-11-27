import ctypes
import math
import threading
import time
from ctypes import wintypes
from memory import is_game_foreground

user32 = ctypes.WinDLL("user32", use_last_error=True)

VK_SPACE = 0x20
FL_ONGROUND = 1
IN_JUMP = 2            # правильное значение IN_JUMP в CS2

MOUSEEVENTF_MOVE = 0x0001


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", wintypes.LONG),
        ("dy", wintypes.LONG),
        ("mouseData", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong)),
    ]


class INPUT(ctypes.Structure):
    _fields_ = [("type", wintypes.DWORD), ("mi", MOUSEINPUT)]


user32.SendInput.argtypes = [wintypes.UINT, ctypes.POINTER(INPUT), ctypes.c_int]
user32.SendInput.restype = wintypes.UINT


def _send_move(dx, dy):
    if dx == 0 and dy == 0:
        return
    inp = INPUT(type=0, mi=MOUSEINPUT(dx=int(dx), dy=int(dy), dwFlags=MOUSEEVENTF_MOVE))
    user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT))


class Bhop:
    def __init__(self, mem, offset):
        self.mem = mem
        self.client = mem.client_base
        self.off = offset

        self.autostrafe_strength = 6.0
        self.hitchance = 0.85
        self.delay = 0.0
        self.autostrafe = False

        self._last_update_ts = 0.0
        self._running = False
        self._thread = None

    # ---------- публичный интерфейс ----------
    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False

    def update(self, autostrafe=False):
        """
        Вызывается из tick(), когда Bhop включён в конфиге.
        Сам поток уже крутится (start() в __init__ через _ensure_thread).
        Timestamp используется, чтобы понять: если update() не звали > 0.5с,
        значит фича выключена — надо перестать прыгать.
        """
        self._last_update_ts = time.time()
        self.autostrafe = autostrafe
        self._ensure_thread()

    # ---------- внутреннее ----------
    def _ensure_thread(self):
        if not (self._thread and self._thread.is_alive()):
            self.start()

    def _write_jump(self, value):
        try:
            self.mem.write(
                self.client + self.off.ButtonJump,
                value.to_bytes(4, "little", signed=False),
            )
        except OSError:
            pass

    def _read_flags(self, pawn):
        try:
            return self.mem.read_uint(pawn + self.off.m_fFlags)
        except OSError:
            return 0

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
            yaw = self.mem.read_float(ptr + 4)
            if abs(yaw) <= 180.5:
                return yaw % 360.0
            return 0.0
        except OSError:
            return 0.0

    def _autostrafe(self, pawn):
        vx, vy = self._read_velocity(pawn)
        if math.hypot(vx, vy) < 1.0:
            return
        vel_yaw = math.degrees(math.atan2(vy, vx)) % 360.0
        cur_yaw = self._read_view_yaw()
        left_yaw = (vel_yaw + 90.0) % 360.0
        right_yaw = (vel_yaw - 90.0) % 360.0
        d_left = abs((left_yaw - cur_yaw + 180) % 360 - 180)
        d_right = abs((right_yaw - cur_yaw + 180) % 360 - 180)
        target_yaw = left_yaw if d_left < d_right else right_yaw
        delta = (target_yaw - cur_yaw + 180) % 360 - 180
        delta = max(-self.autostrafe_strength, min(self.autostrafe_strength, delta))
        counts = int(delta / (0.022 * 2.0))
        if counts:
            _send_move(counts, 0)

    def _loop(self):
        try:
            ctypes.windll.winmm.timeBeginPeriod(1)
        except Exception:
            pass

        while self._running:
            active = (time.time() - self._last_update_ts) < 0.5

            if not active or not is_game_foreground():
                self._write_jump(0)
                time.sleep(0.002)
                continue

            if not (user32.GetAsyncKeyState(VK_SPACE) & 0x8000):
                self._write_jump(0)
                time.sleep(0.002)
                continue

            try:
                pawn = self.mem.read_pointer(self.client + self.off.dwLocalPlayerPawn)
            except OSError:
                pawn = 0

            if not pawn:
                self._write_jump(0)
                time.sleep(0.002)
                continue

            flags = self._read_flags(pawn)
            on_ground = bool(flags & FL_ONGROUND)

            if on_ground:
                self._write_jump(IN_JUMP)
            else:
                self._write_jump(0)

            if self.autostrafe:
                self._autostrafe(pawn)

            time.sleep(0.001)

        try:
            ctypes.windll.winmm.timeEndPeriod(1)
        except Exception:
            pass