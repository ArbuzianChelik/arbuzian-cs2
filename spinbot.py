import time
import math
import ctypes
from ctypes import wintypes
from memory import is_game_foreground

user32 = ctypes.WinDLL("user32", use_last_error=True)

class Spinbot:
    MAX_DEG_PER_SEC = 720.0

    def __init__(self, mem, offset, speed=45.0, sens=2.0):
        self.mem = mem
        self.client = mem.client_base
        self.off = offset
        self.speed = speed
        self.sens = sens
        self.mode = "Spin"           # Spin / Jitter / Random / Desync
        self.jitter_range = 60.0
        self.desync_side = "Right"

        self._last = time.time()
        self._base_yaw = None       # «нулевой» yaw, от которого считаем спин
        self._phase = 0.0
        self._jitter_dir = 1
        self._desync_flip = False

    def _read_yaw(self):
        try:
            ptr = self.mem.read_pointer(self.client + self.off.dwViewAngles)
            if not ptr or ptr < 0x10000:
                return None
            yaw = self.mem.read_float(ptr + 0x20)
            if not (-180.5 <= yaw <= 180.5):
                return None
            return yaw % 360.0
        except OSError:
            return None

    def _write_yaw(self, yaw):
        yaw = ((yaw % 360.0) + 180.0) % 360.0 - 180.0

        # 1) СЕРВЕРНЫЕ углы — то, что видят другие
        pawn = self._get_local_pawn()
        if pawn and self.off.m_angEyeAngles:
            try:
                # m_angEyeAngles = {pitch@0, yaw@4, roll@8}
                self.mem.write_float(pawn + self.off.m_angEyeAngles + 4, yaw)
            except OSError:
                pass

        # 2) клиентские углы — для твоей камеры
        try:
            ptr = self.mem.read_pointer(self.client + self.off.dwViewAngles)
            if ptr and ptr >= 0x10000:
                for off in (0x20, 0x4CC, 0x574):
                    self.mem.write_float(ptr + off, yaw)
        except OSError:
            pass

    def _get_local_pawn(self):
        try:
            return self.mem.read_pointer(self.client + self.off.dwLocalPlayerPawn)
        except OSError:
            return None

    def update(self, desync=False, hotkey_held=True):
        if not is_game_foreground():
            self._last = time.time()
            self._base_yaw = None
            return
        if not hotkey_held and not desync:
            self._last = time.time()
            self._base_yaw = None
            return

        now = time.time()
        dt = min(now - self._last, 0.1)
        self._last = now
        if dt <= 0:
            return

        cur = self._read_yaw()
        if cur is None:
            return

        if self._base_yaw is None:
            self._base_yaw = cur

        if desync:
            self._do_desync(cur, dt)
        elif self.mode == "Spin":
            self._spin(cur, dt)
        elif self.mode == "Jitter":
            self._jitter(cur, dt)
        elif self.mode == "Random":
            self._random(cur, dt)

    def _spin(self, cur, dt):
        speed = min(self.speed, self.MAX_DEG_PER_SEC)
        self._phase = (self._phase + speed * dt) % 360.0
        self._write_yaw(self._phase)

    def _jitter(self, cur, dt):
        self._phase += dt
        if self._phase < 0.10:
            return
        self._phase = 0.0
        self._jitter_dir *= -1
        deg = min(self.jitter_range, 90.0) * self._jitter_dir
        self._write_yaw((self._base_yaw + deg) % 360.0)

    def _random(self, cur, dt):
        self._phase += dt
        if self._phase < 0.15:
            return
        self._phase = 0.0
        import random
        deg = random.uniform(-min(self.jitter_range, 90.0),
                             min(self.jitter_range, 90.0))
        self._write_yaw((self._base_yaw + deg) % 360.0)

    def _do_desync(self, cur, dt):
        self._phase += dt
        if self._phase < 0.15:
            return
        self._phase = 0.0
        if self.desync_side == "Left":
            deg = -min(self.jitter_range, 60.0)
        elif self.desync_side == "Right":
            deg = min(self.jitter_range, 60.0)
        else:
            import random
            deg = min(self.jitter_range, 60.0) * random.choice((-1, 1))
        self._write_yaw((self._base_yaw + deg) % 360.0)