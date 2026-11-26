import struct
import time
from memory import is_game_foreground

class VisualSpin:
    """Пишет углы в m_angEyeAngles. Камера остаётся ровной, модель крутится."""
    def __init__(self, mem, offset, speed=45.0):
        self.mem = mem
        self.client = mem.client_base
        self.off = offset
        self.speed = speed
        self._last = time.time()
        self._yaw = 0.0

    def update(self, enabled=True):
        if not enabled or not is_game_foreground():
            self._last = time.time()
            return

        now = time.time()
        dt = min(now - self._last, 0.1)
        self._last = now
        if dt <= 0:
            return

        self._yaw = (self._yaw + self.speed * dt) % 360.0

        try:
            pawn = self.mem.read_pointer(self.client + self.off.dwLocalPlayerPawn)
            if not pawn:
                return
            addr = pawn + self.off.m_angEyeAngles
            # m_angEyeAngles — это Vector2 (yaw, pitch), 8 байт.
            # Мы меняем только yaw (первые 4 байта), оставляя pitch как есть.
            self.mem.write(addr, struct.pack("<f", self._yaw))
        except OSError:
            pass