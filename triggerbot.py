import ctypes
import time
from ctypes import wintypes
from memory import is_game_foreground

user32 = ctypes.WinDLL('user32', use_last_error=True)
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
LMB_HOLD_S = 0.015  # 1 тик на 64Hz


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


class Triggerbot:
    def __init__(self, mem, offset):
        self.mem = mem
        self.client = mem.client_base
        self.off = offset
        self.enabled = False
        self.delay = 0.05
        self.last_shot = 0.0
        self._fire_release_at = 0.0

    def _resolve(self, el_ptr, idx):
        # Используем ту же схему, что и ESP (динамически определённую),
        # но для простоты оставляем старую — если ESP работает, эта тоже.
        try:
            chunk = self.mem.read_pointer(el_ptr + 0x10 + 8 * (idx >> 9))
            if not chunk:
                return 0
            return self.mem.read_pointer(chunk + 0x70 * (idx & 0x1FF))
        except OSError:
            return 0

    def _local_alive(self):
        try:
            pawn = self.mem.read_pointer(self.client + self.off.dwLocalPlayerPawn)
            if not pawn:
                return False
            hp = self.mem.read_int(pawn + self.off.m_iHealth)
            return hp > 0
        except OSError:
            return False

    def _is_enemy_visible_in_crosshair(self, local_team):
        try:
            pawn = self.mem.read_pointer(self.client + self.off.dwLocalPlayerPawn)
            if not pawn:
                return False
            handle = self.mem.read_uint(pawn + self.off.m_iIDEntIndex)
            if handle in (0, 0xFFFFFFFF):
                return False
            idx = handle & 0x7FFF
            if idx == 0:
                return False

            el_ptr = self.mem.read_pointer(self.client + self.off.dwEntityList)
            if not el_ptr:
                return False
            target = self._resolve(el_ptr, idx)
            if not target:
                return False

            health = self.mem.read_int(target + self.off.m_iHealth)
            team = self.mem.read_int(target + self.off.m_iTeamNum)
            if not (0 < health <= 100) or team == local_team:
                return False

            # Проверка m_bSpotted (общий флаг видимости)
            try:
                spotted_base = target + self.off.m_entitySpottedState
                spotted = self.mem.read_uint(spotted_base + self.off.m_bSpotted) & 0xFF
                return bool(spotted)
            except OSError:
                # Если не удалось прочитать — считаем, что видим (чтобы не блокировать)
                return True
        except OSError:
            return False

    def update(self, local_team):
        now = time.time()

        # Отпускаем кнопку
        if self._fire_release_at > 0 and now >= self._fire_release_at:
            up = INPUT(type=0, mi=MOUSEINPUT(dwFlags=MOUSEEVENTF_LEFTUP))
            user32.SendInput(1, ctypes.byref(up), ctypes.sizeof(INPUT))
            self._fire_release_at = 0.0
            self.last_shot = now
            return
        if self._fire_release_at > 0:
            return

        if not self.enabled or not is_game_foreground():
            return
        if not self._local_alive():
            return
        if now - self.last_shot < self.delay:
            return

        if self._is_enemy_visible_in_crosshair(local_team):
            down = INPUT(type=0, mi=MOUSEINPUT(dwFlags=MOUSEEVENTF_LEFTDOWN))
            user32.SendInput(1, ctypes.byref(down), ctypes.sizeof(INPUT))
            self._fire_release_at = now + LMB_HOLD_S