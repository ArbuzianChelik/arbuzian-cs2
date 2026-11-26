import time
import threading
import ctypes
from ctypes import wintypes

user32 = ctypes.WinDLL('user32', use_last_error=True)
VK_LBUTTON = 0x01
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
MOUSEEVENTF_MOVE = 0x0001
M_YAW = 0.022

VIEW_ANGLES_QANGLE_OFFSET = 0x1C
VIEW_ANGLES_MIRRORS = (0x4C8, 0x570)


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [("dx", wintypes.LONG), ("dy", wintypes.LONG),
                ("mouseData", wintypes.DWORD), ("dwFlags", wintypes.DWORD),
                ("time", wintypes.DWORD),
                ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong))]


class INPUT(ctypes.Structure):
    _fields_ = [("type", wintypes.DWORD), ("mi", MOUSEINPUT)]


user32.SendInput.argtypes = [wintypes.UINT, ctypes.POINTER(INPUT), ctypes.c_int]
user32.SendInput.restype = wintypes.UINT


def _send_move_split(dx, dy, chunk=1000):
    """Большой флик разбиваем на чанки — CS2 клампит дельту за один SendInput."""
    while dx or dy:
        cx = max(-chunk, min(chunk, int(dx)))
        cy = max(-chunk, min(chunk, int(dy)))
        if cx == 0 and cy == 0:
            break
        inp = INPUT(type=0, mi=MOUSEINPUT(dx=cx, dy=cy,
                                           dwFlags=MOUSEEVENTF_MOVE))
        user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT))
        dx -= cx
        dy -= cy
        if dx or dy:
            time.sleep(0.001)


def _send_click(down):
    inp = INPUT(type=0, mi=MOUSEINPUT(
        dwFlags=MOUSEEVENTF_LEFTDOWN if down else MOUSEEVENTF_LEFTUP))
    user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT))


class SilentAim:
    """
    Mouse-flick silent: на LMB-down edge делает флик на цель, стреляет,
    откатывает мышь. Отдельный клик — гарантирует, что пуля летит в цель,
    даже если пользовательский LMB уже был обработан клиентом.
    """
    def __init__(self, mem, offset):
        self.mem = mem
        self.client = mem.client_base
        self.off = offset

        # параметры — выставляются из main.py перед publish
        self.fov = 15.0
        self.use_360 = False
        self.visible_only = True
        self.hold_s = 0.020
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

        self._restore_at = 0.0
        self._pending_reverse = (0, 0)
        self._armed = True          # ждём отпускания LMB после выстрела
        self.snaps = 0

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        print("[Silent] worker @1250Hz (mouse-flick mode)")

    def stop(self):
        self._running = False

    def is_active(self):
        return self._restore_at > time.time()

    def publish(self, targets, sens, punch, shots, enabled, active_ok=True):
        with self._lock:
            self._targets = targets
            self._sens = sens if sens > 0.1 else 2.0
            self._punch = punch
            self._shots = shots
            self._enabled = enabled
            self._active_ok = active_ok

    def _read_angles(self):
        try:
            ptr = self.mem.read_pointer(self.client + self.off.dwViewAngles)
            if not ptr or ptr < 0x10000:
                return None
            pitch = self.mem.read_float(ptr + VIEW_ANGLES_QANGLE_OFFSET)
            yaw = self.mem.read_float(ptr + VIEW_ANGLES_QANGLE_OFFSET + 4)
            if not (-89.5 <= pitch <= 89.5 and -180.5 <= yaw <= 180.5):
                return None
            return yaw, pitch
        except OSError:
            return None

    def _loop(self):
        prev_lmb = False
        while self._running:
            now = time.time()

            # восстановление камеры после hold
            if self._restore_at > 0 and now >= self._restore_at:
                rx, ry = self._pending_reverse
                if rx or ry:
                    _send_move_split(rx, ry)
                self._restore_at = 0.0
                self._pending_reverse = (0, 0)

            lmb = bool(user32.GetAsyncKeyState(VK_LBUTTON) & 0x8000)
            pressed = lmb and not prev_lmb
            released = not lmb and prev_lmb
            prev_lmb = lmb

            if released:
                self._armed = True

            if pressed and self._armed and self._restore_at <= 0:
                with self._lock:
                    en = self._enabled
                    ok = self._active_ok
                    targets = list(self._targets)
                    punch = self._punch
                    shots = self._shots
                    hold = self.hold_s
                    rcs = self.rcs_strength
                    rcs_start = self.rcs_start_bullet
                    sens = self._sens

                if en and ok and targets:
                    yaw, pitch, _ = min(targets, key=lambda t: t[2])

                    if shots >= rcs_start and rcs > 0.01:
                        px, py = punch
                        pitch -= px * rcs
                        yaw -= py * rcs

                    saved = self._read_angles()
                    if saved:
                        cur_yaw, cur_pitch = saved
                        d_yaw = (yaw - cur_yaw + 180) % 360 - 180
                        d_pitch = pitch - cur_pitch

                        mx = int(-d_yaw / (M_YAW * sens))
                        my = int(d_pitch / (M_YAW * sens))

                        if mx or my:
                            # 1) отпускаем пользовательский LMB — мы сами выстрелим
                            _send_click(False)
                            # 2) флик на цель
                            _send_move_split(mx, my)
                            # 3) выстрел
                            _send_click(True)
                            _send_click(False)
                            # 4) откат — с задержкой, чтобы клиент успел отправить
                            #    usercmd на сервер с нашими углами
                            self._pending_reverse = (-mx, -my)
                            self._restore_at = now + hold
                            self._armed = False
                            self.snaps += 1

            time.sleep(0.0008)