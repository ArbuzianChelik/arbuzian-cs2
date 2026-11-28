import time

TEAM_GLOW = {
    2: (255, 170, 60),   # T
    3: (60, 160, 255),   # CT
    0: (255, 60, 60),    # unknown
}


def pack_color(r, g, b, a=255):
    return (a << 24) | (b << 16) | (g << 8) | r


class GlowController:
    def __init__(self, mem, offset):
        self.mem = mem
        self.off = offset
        self._enabled = set()
        self._last_update = 0.0

    def _w(self, addr, value, signed=False):
        """Безопасная запись 4 байт."""
        if addr < 0x10000:
            return
        try:
            self.mem.write(addr, value.to_bytes(4, "little", signed=signed))
        except OSError:
            pass

    def _set(self, pawn, team):
        base = pawn + self.off.m_Glow
        if base < 0x10000:
            return
        r, g, b = TEAM_GLOW.get(team, TEAM_GLOW[0])

        self._w(base + self.off.m_iGlowType, 3, signed=True)
        self._w(base + self.off.m_glowColorOverride, pack_color(r, g, b))
        self._w(base + self.off.m_bGlowing, 1, signed=True)

    def _clear(self, pawn):
        base = pawn + self.off.m_Glow
        if base < 0x10000:
            return
        self._w(base + self.off.m_bGlowing, 0, signed=True)

    def update(self, entities, local_team, enabled):
        now = time.time()
        if now - self._last_update < 0.1:  # throttle 10 Гц
            return
        self._last_update = now

        if not enabled:
            for addr in self._enabled:
                self._clear(addr)
            self._enabled.clear()
            return

        current = set()
        for e in entities:
            if e.get("team") == local_team:
                continue
            addr = e.get("addr")
            if not addr:
                continue
            current.add(addr)
            self._set(addr, e.get("team", 0))

        # Сброс glow у тех, кто исчез
        for addr in self._enabled - current:
            self._clear(addr)
        self._enabled = current