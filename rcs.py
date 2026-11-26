import ctypes
from ctypes import wintypes
from memory import is_game_foreground

user32 = ctypes.WinDLL('user32', use_last_error=True)
MOUSEEVENTF_MOVE = 0x0001


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [("dx", wintypes.LONG), ("dy", wintypes.LONG),
                ("mouseData", wintypes.DWORD), ("dwFlags", wintypes.DWORD),
                ("time", wintypes.DWORD), ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong))]


class INPUT(ctypes.Structure):
    _fields_ = [("type", wintypes.DWORD), ("mi", MOUSEINPUT)]


user32.SendInput.argtypes = [wintypes.UINT, ctypes.POINTER(INPUT), ctypes.c_int]
user32.SendInput.restype = wintypes.UINT


def _send_move(dx, dy):
    ix, iy = int(dx), int(dy)
    if ix == 0 and iy == 0:
        return
    inp = INPUT(type=0, mi=MOUSEINPUT(dx=ix, dy=iy, dwFlags=MOUSEEVENTF_MOVE))
    user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT))


class RecoilControl:
    """Компенсация отдачи чтением aim-punch из m_pAimPunchServices.

    Логика полностью повторяет cs2py:
      count = *(uint*)(services + m_unpredictableBaseTick - 0x18)
      data  = *(ptr*)(services + m_unpredictableBaseTick - 0x18 + 0x08)
      punch = data[count - 1] (Vector3, 12 байт)
    """

    def __init__(self, mem, offset, smoothing=1.5):
        self.mem = mem
        self.client = mem.client_base
        self.off = offset
        self.smoothing = smoothing
        self.old_punch_x = 0.0
        self.old_punch_y = 0.0
        self._printed = False

    def _get_punch(self, pawn):
        try:
            services = self.mem.read_pointer(pawn + self.off.m_pAimPunchServices)
            if not services:
                return (0.0, 0.0)
            base = self.off.m_unpredictableBaseTick - 0x18
            count = self.mem.read_uint(services + base)
            data_ptr = self.mem.read_pointer(services + base + 0x08)

            if not (0 < count < 1000) or not data_ptr:
                if not self._printed:
                    self._printed = True
                    print(f"[RCS] punch buffer empty (count={count} data=0x{data_ptr:X})")
                return (0.0, 0.0)

            addr = data_ptr + (count - 1) * 12
            x, y, _ = self.mem.read_vec3(addr)
            return (x, y)
        except OSError:
            return (0.0, 0.0)

    def _sensitivity(self):
        try:
            base = self.mem.read_pointer(self.client + self.off.dwSensitivity)
            if not base:
                return 2.0
            s = self.mem.read_float(base + self.off.dwSensitivity_sensitivity)
            if 0.01 < s < 50.0:
                return s
        except OSError:
            pass
        return 2.0

    def reset(self):
        self.old_punch_x = 0.0
        self.old_punch_y = 0.0

    def update(self, aimbot_active):
        if not is_game_foreground():
            self.reset()
            return
        if aimbot_active:
            self.reset()
            return

        try:
            pawn = self.mem.read_pointer(self.client + self.off.dwLocalPlayerPawn)
            if not pawn:
                self.reset()
                return
            shots = self.mem.read_int(pawn + self.off.m_iShotsFired)
        except OSError:
            self.reset()
            return

        if not (1 < shots < 999999):
            self.reset()
            return

        punch_x, punch_y = self._get_punch(pawn)

        delta_x = (punch_x - self.old_punch_x) * -1.0
        delta_y = (punch_y - self.old_punch_y) * -1.0

        sens = self._sensitivity()
        move_x = (delta_y * 2.0 / sens) / -0.022
        move_y = (delta_x * 2.0 / sens) / 0.022

        smooth = max(1.0, min(float(self.smoothing), 5.0))
        _send_move(move_x / smooth, move_y / smooth)

        self.old_punch_x = punch_x
        self.old_punch_y = punch_y