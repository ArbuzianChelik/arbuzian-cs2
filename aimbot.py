import math
import random
import time
import ctypes
from ctypes import wintypes
from memory import is_game_foreground

user32 = ctypes.WinDLL('user32', use_last_error=True)
MOUSEEVENTF_MOVE = 0x0001
VK_LBUTTON = 0x01
VK_RBUTTON = 0x02

DEFAULT_VFOV = 73.74
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


class Aimbot:
    HITBOX_TO_BONE = {
        "Head": "head",
        "Neck": "neck_0",
        "Chest": "spine_2",
        "Stomach": "pelvis",
    }

    def __init__(self, mem, offset):
        self.mem = mem
        self.client = mem.client_base
        self.off = offset

        self.enabled = False
        self.fov = 15.0
        self.smooth = 8.0
        self.humanize = 0.0
        self.rcs_strength = 1.0
        self.rcs_start_bullet = 1
        self.visibility_check = True
        self.hitbox = "Head"
        self.aim_key = "Always"
        self.target_priority = "FOV"

        self.vfov = DEFAULT_VFOV
        self._acc_x = 0.0
        self._acc_y = 0.0
        self._humanize_skip_until = 0.0

        # ── target lock state ──
        self._last_target_pos = None       # (x,y) экранных координат последней цели
        self._last_lock_time = 0.0
        self._lock_frames = 0
        self._LOCK_MATCH_PX = 70.0         # допуск "это та же цель"
        self._LOCK_GRACE_S = 0.15          # сколько терпим потерю цели

    def set_screen_aspect(self, width, height):
        if height <= 0:
            return
        aspect = width / height
        if abs(aspect - 16/9) < 0.01:
            self.vfov = DEFAULT_VFOV
        else:
            hfov_43 = 90.0
            hfov = 2 * math.degrees(math.atan(
                math.tan(math.radians(hfov_43 / 2)) * (aspect / (4/3))))
            self.vfov = 2 * math.degrees(math.atan(
                math.tan(math.radians(hfov / 2)) / aspect))

    def fov_radius_px(self, screen_h):
        return (math.tan(math.radians(self.fov))
                / math.tan(math.radians(self.vfov / 2))
                * screen_h / 2)

    def angle_to(self, screen_w, screen_h, point_screen):
        tan_v = math.tan(math.radians(self.vfov / 2))
        aspect = screen_w / screen_h
        tan_h = tan_v * aspect
        dx = point_screen[0] - screen_w / 2.0
        dy = point_screen[1] - screen_h / 2.0
        yaw = math.degrees(math.atan(2 * dx / screen_w * tan_h))
        pitch = math.degrees(math.atan(2 * dy / screen_h * tan_v))
        return yaw, pitch, math.hypot(yaw, pitch)

    def _sensitivity(self):
        try:
            base = self.mem.read_pointer(self.client + self.off.dwSensitivity)
            if base:
                s = self.mem.read_float(base + self.off.dwSensitivity_sensitivity)
                if 0.01 < s < 50.0:
                    return s
        except OSError:
            pass
        return 2.0

    def _get_punch(self, local_pawn):
        if not local_pawn:
            return (0.0, 0.0)
        try:
            services = self.mem.read_pointer(local_pawn + self.off.m_pAimPunchServices)
            if not services:
                return (0.0, 0.0)
            base = self.off.m_unpredictableBaseTick - 0x18
            count = self.mem.read_uint(services + base)
            data_ptr = self.mem.read_pointer(services + base + 0x08)
            if not (0 < count < 1000) or not data_ptr:
                return (0.0, 0.0)
            addr = data_ptr + (count - 1) * 12
            x, y, _ = self.mem.read_vec3(addr)
            return (x, y)
        except OSError:
            return (0.0, 0.0)

    def _shots_fired(self, local_pawn):
        if not local_pawn:
            return 0
        try:
            return self.mem.read_int(local_pawn + self.off.m_iShotsFired)
        except OSError:
            return 0

    def _aim_key_held(self):
        if self.aim_key == "LMB":
            return bool(user32.GetAsyncKeyState(VK_LBUTTON) & 0x8000)
        if self.aim_key == "RMB":
            return bool(user32.GetAsyncKeyState(VK_RBUTTON) & 0x8000)
        return True

    def _get_hitbox_screen(self, e):
        bone = self.HITBOX_TO_BONE.get(self.hitbox, "head")
        bs = e.get("bone_screens") or {}
        return bs.get(bone) or e["head_screen"]

    def _same_target(self, screen_pos):
        if self._last_target_pos is None or not screen_pos:
            return False
        dx = screen_pos[0] - self._last_target_pos[0]
        dy = screen_pos[1] - self._last_target_pos[1]
        return dx * dx + dy * dy < self._LOCK_MATCH_PX * self._LOCK_MATCH_PX

    def _pick_target(self, entities, screen_w, screen_h):
        now = time.time()
        in_grace = (now - self._last_lock_time) < self._LOCK_GRACE_S
        best = None
        best_score = 1e18
        for e in entities:
            hs = self._get_hitbox_screen(e)
            if not hs:
                continue

            sticky = in_grace and self._same_target(hs)

            if self.visibility_check and not e.get("visible", True):
                continue

            yaw, pitch, dist = self.angle_to(screen_w, screen_h, hs)

            # FOV hysteresis: текущей цели прощаем +8° (но не больше 35%)
            fov_limit = self.fov + (min(self.fov * 0.35, 8.0) if sticky else 0.0)
            if dist > fov_limit:
                continue

            if self.target_priority == "Distance":
                score = e["screen"][1]
            elif self.target_priority == "Lowest HP":
                score = e.get("health", 100)
            else:
                score = dist

            # sticky-бонус: не переключаемся, пока другая цель не будет
            # в 2.5 раза ближе к прицелу
            if sticky:
                score *= 0.4

            if score < best_score:
                best_score = score
                best = (e, yaw, pitch, dist, hs)
        return best

    def update(self, entities, local_pawn, screen_w, screen_h):
        if not self.enabled or not is_game_foreground():
            self.reset_acc()
            self._lock_frames = 0
            self._last_target_pos = None
            return False
        if not self._aim_key_held():
            self.reset_acc()
            self._lock_frames = 0
            self._last_target_pos = None
            return False

        picked = self._pick_target(entities, screen_w, screen_h)
        if not picked:
            locked_target_hidden = (
                self.visibility_check
                and any(
                    not e.get("visible", True)
                    and self._same_target(self._get_hitbox_screen(e))
                    for e in entities
                )
            )
            if locked_target_hidden:
                self.reset_acc()
                self._lock_frames = 0
                self._last_target_pos = None
                self._last_lock_time = 0.0
                return False

            # кратковременная потеря (флейк raycast / цель на границе FOV) —
            # НЕ сбрасываем аккумулятор и счётчик кадров, чтобы при повторном
            # захвате сразу продолжить движение, а не «догонять» с нуля
            if (time.time() - self._last_lock_time) > self._LOCK_GRACE_S:
                self.reset_acc()
                self._lock_frames = 0
                self._last_target_pos = None
            return False

        target, yaw, pitch, dist, hs = picked

        # смена цели — не тащим суб-пиксельный остаток со старой
        if not self._same_target(hs) and self._lock_frames > 0:
            self._acc_x = 0.0
            self._acc_y = 0.0
            self._lock_frames = 0
        self._last_target_pos = hs
        self._last_lock_time = time.time()
        self._lock_frames += 1

        # RCS
        shots = self._shots_fired(local_pawn)
        if shots >= self.rcs_start_bullet and self.rcs_strength > 0.01:
            px, py = self._get_punch(local_pawn)
            pitch -= px * self.rcs_strength
            yaw -= py * self.rcs_strength

        now = time.time()
        if self.humanize > 0.01 and now < self._humanize_skip_until:
            return False
        if self.humanize > 0.01 and random.random() < self.humanize * 0.08:
            self._humanize_skip_until = now + random.uniform(0.005, 0.02)

        # быстрый старт: первые кадры после захвата двигаемся агрессивно,
        # затем плавно выходим на пользовательский smooth
        if self._lock_frames <= 2:
            eff_smooth = max(1.0, self.smooth * 0.25)
        elif self._lock_frames <= 5:
            eff_smooth = max(1.0, self.smooth * 0.6)
        else:
            eff_smooth = self.smooth

        sens = self._sensitivity()
        self._acc_x += yaw / (M_YAW * sens) / eff_smooth
        self._acc_y += pitch / (M_YAW * sens) / eff_smooth

        ix = int(self._acc_x)
        iy = int(self._acc_y)
        self._acc_x -= ix
        self._acc_y -= iy

        if ix or iy:
            _send_move(ix, iy)
        return True

    def reset_acc(self):
        self._acc_x = 0.0
        self._acc_y = 0.0

    def aim_at_360(self, eye_pos, target_pos, smooth=1.0):
        if not is_game_foreground():
            return False

        dx = target_pos[0] - eye_pos[0]
        dy = target_pos[1] - eye_pos[1]
        dz = target_pos[2] - eye_pos[2]

        horiz = math.hypot(dx, dy)
        target_yaw = math.degrees(math.atan2(dy, dx)) % 360.0
        target_pitch = -math.degrees(math.atan2(dz, horiz))

        cur_yaw, cur_pitch = self._read_view_angles()

        d_yaw = (target_yaw - cur_yaw + 180) % 360 - 180
        d_pitch = target_pitch - cur_pitch

        sens = self._sensitivity()
        m_yaw = 0.022

        # Переводим углы в движение мыши.
        # Знак yaw инвертирован: в CS2 положительный yaw = влево, а MoveInput dx > 0 = вправо.
        move_x = -d_yaw / (m_yaw * sens) / smooth
        move_y = d_pitch / (m_yaw * sens) / smooth

        _send_move(move_x, move_y)
        return True

    def _read_view_angles(self):
        """Читает текущие углы из dwViewAngles."""
        try:
            ptr = self.mem.read_pointer(self.client + self.off.dwViewAngles)
            if not ptr:
                return (0.0, 0.0)
            yaw = self.mem.read_float(ptr)
            pitch = self.mem.read_float(ptr + 4)
            if not (-720 <= yaw <= 720):
                yaw = 0.0
            if not (-180 <= pitch <= 180):
                pitch = 0.0
            return (yaw % 360.0, pitch)
        except OSError:
            return (0.0, 0.0)