import time
import threading
import ctypes
from ctypes import wintypes

user32 = ctypes.WinDLL('user32', use_last_error=True)
MOUSEEVENTF_MOVE = 0x0001
VK_LBUTTON = 0x01
M_YAW = 0.022


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [("dx", wintypes.LONG), ("dy", wintypes.LONG),
                ("mouseData", wintypes.DWORD), ("dwFlags", wintypes.DWORD),
                ("time", wintypes.DWORD), ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong))]


class INPUT(ctypes.Structure):
    _fields_ = [("type", wintypes.DWORD), ("mi", MOUSEINPUT)]


user32.SendInput.argtypes = [wintypes.UINT, ctypes.POINTER(INPUT), ctypes.c_int]
user32.SendInput.restype = wintypes.UINT


def _send_move(dx, dy):
    if dx == 0 and dy == 0:
        return
    inp = INPUT(type=0, mi=MOUSEINPUT(dx=int(dx), dy=int(dy), dwFlags=MOUSEEVENTF_MOVE))
    user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT))


class SilentAim:
    """
    Snap-silent на 1250Гц (требует timeBeginPeriod(1) в main).
    HOLD ~18мс = ~1.15 тика на 64Hz.
    Поддерживает 360° через world-angle дельты.
    """

    CHUNK = 5000

    def __init__(self, mem, offset):
        self.mem = mem
        self.client = mem.client_base
        self.off = offset
        self.fov = 15.0
        self.use_360 = False
        self.visible_only = True
        self.hold_s = 0.018
        self.rcs_strength = 1.0
        self.rcs_start_bullet = 1

        self._lock = threading.Lock()
        self._targets = []
        self._sens = 2.0
        self._punch = (0.0, 0.0)
        self._shots = 0
        self._enabled = False
        self._active_ok = False

        self._running = False
        self._thread = None
        self._active_until = 0.0
        self.snaps = 0

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        print("[Silent] worker @1250Hz (timeBeginPeriod(1))")

    def stop(self):
        self._running = False

    def is_active(self):
        return self._active_until > time.time()

    def publish(self, targets, sens, punch, shots, enabled, active_ok):
        with self._lock:
            self._targets = targets
            self._sens = sens
            self._punch = punch
            self._shots = shots
            self._enabled = enabled
            self._active_ok = active_ok

    def _send_fast(self, dx, dy):
        while dx or dy:
            sx = max(-self.CHUNK, min(self.CHUNK, dx))
            sy = max(-self.CHUNK, min(self.CHUNK, dy))
            _send_move(sx, sy)
            dx -= sx
            dy -= sy

    def _loop(self):
        prev_lmb = False
        total_dx = 0
        total_dy = 0

        while self._running:
            now = time.time()

            if self._active_until > 0 and now >= self._active_until:
                if total_dx or total_dy:
                    self._send_fast(-total_dx, -total_dy)
                total_dx = 0
                total_dy = 0
                self._active_until = 0.0

            lmb = bool(user32.GetAsyncKeyState(VK_LBUTTON) & 0x8000)
            pressed = lmb and not prev_lmb
            prev_lmb = lmb

            if pressed and self._active_until <= 0:
                with self._lock:
                    en = self._enabled
                    ok = self._active_ok
                    targets = self._targets
                    sens = self._sens
                    punch = self._punch
                    shots = self._shots
                    hold = self.hold_s
                    rcs = self.rcs_strength
                    rcs_start = self.rcs_start_bullet

                if en and ok and targets:
                    move_yaw, move_pitch, dist = min(targets, key=lambda t: t[2])

                    if shots >= rcs_start and rcs > 0.01:
                        px, py = punch
                        move_pitch -= px * rcs
                        move_yaw -= py * rcs

                    dx = int(round(move_yaw / (M_YAW * sens)))
                    dy = int(round(move_pitch / (M_YAW * sens)))
                    if dx or dy:
                        self._send_fast(dx, dy)
                        total_dx = dx
                        total_dy = dy
                        self._active_until = now + hold
                        self.snaps += 1

            time.sleep(0.0008)