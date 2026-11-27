import time
import random
import ctypes
from ctypes import wintypes
from memory import is_game_foreground

user32 = ctypes.WinDLL("user32", use_last_error=True)
MOUSEEVENTF_MOVE = 0x0001


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", wintypes.LONG), ("dy", wintypes.LONG),
        ("mouseData", wintypes.DWORD), ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD), ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong)),
    ]


class INPUT(ctypes.Structure):
    _fields_ = [("type", wintypes.DWORD), ("mi", MOUSEINPUT)]


user32.SendInput.argtypes = [wintypes.UINT, ctypes.POINTER(INPUT), ctypes.c_int]
user32.SendInput.restype = wintypes.UINT


class Spinbot:
    """
    Anti-aim через эмуляцию мыши. Безопасно (никаких записей в память).

    Modes:
      Spin   — непрерывное вращение (максимально заметно)
      Jitter — рывки влево-вправо каждые ~100мс (менее заметно)
      Random — случайные рывки каждые ~150мс
    """

    MAX_DEG_PER_SEC = 180.0
    MAX_CHUNK = 500

    def __init__(self, mem, offset, speed=45.0, sens=2.0):
        self.mem = mem
        self.client = mem.client_base
        self.off = offset

        self.speed = speed
        self.sens = sens
        self.mode = "Spin"
        self.jitter_range = 60.0

        self._last = time.time()
        self._acc = 0.0
        self._jitter_dir = 1

    def update(self, hotkey_held=True, desync=False):
        if not is_game_foreground() or (not hotkey_held and not desync):
            self._last = time.time()
            self._acc = 0.0
            return

        now = time.time()
        dt = min(now - self._last, 0.1)
        self._last = now
        if dt <= 0:
            return

        if desync:
            self._do_desync(dt)
        elif self.mode == "Spin":
            self._spin(dt)
        elif self.mode == "Jitter":
            self._jitter(dt)
        elif self.mode == "Random":
            self._random(dt)
            
    def _do_desync(self, dt):
        self._acc += dt
        if self._acc < 0.15:
            return
        self._acc = 0.0
        # Просто рывок в сторону (как Jitter, но с фиксированной стороной)
        deg = min(self.jitter_range, 60.0)
        counts = int(deg / (0.022 * self.sens))
        if counts:
            self._send_split(counts)

    def _jitter(self, dt):
        self._acc += dt
        if self._acc < 0.10:
            return
        self._acc = 0.0
        self._jitter_dir *= -1
        deg = min(self.jitter_range, 90.0) * self._jitter_dir
        counts = int(deg / (0.022 * self.sens))
        if counts:
            self._send_split(counts)

    def _random(self, dt):
        self._acc += dt
        if self._acc < 0.15:
            return
        self._acc = 0.0
        deg = random.uniform(-min(self.jitter_range, 90.0),
                             min(self.jitter_range, 90.0))
        counts = int(deg / (0.022 * self.sens))
        if counts:
            self._send_split(counts)

    def _send_split(self, counts):
        while abs(counts) > self.MAX_CHUNK:
            step = self.MAX_CHUNK if counts > 0 else -self.MAX_CHUNK
            self._send(step)
            counts -= step
        if counts:
            self._send(counts)

    def _send(self, counts):
        inp = INPUT(type=0, mi=MOUSEINPUT(dx=counts, dy=0, dwFlags=MOUSEEVENTF_MOVE))
        user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT))