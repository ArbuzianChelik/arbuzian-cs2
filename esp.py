import struct
import time

BONES = {
    "pelvis": 1, "spine_2": 2, "spine_1": 4, "neck_0": 6, "head": 7,
    "arm_upper_L": 9, "arm_lower_L": 10, "hand_L": 11,
    "arm_upper_R": 13, "arm_lower_R": 14, "hand_R": 15,
    "leg_upper_L": 17, "leg_lower_L": 18, "ankle_L": 19,
    "leg_upper_R": 20, "leg_lower_R": 21, "ankle_R": 22,
}
BONE_CONNECTIONS = [
    ("head", "neck_0"), ("neck_0", "spine_1"), ("spine_1", "spine_2"), ("spine_2", "pelvis"),
    ("pelvis", "leg_upper_L"), ("leg_upper_L", "leg_lower_L"), ("leg_lower_L", "ankle_L"),
    ("pelvis", "leg_upper_R"), ("leg_upper_R", "leg_lower_R"), ("leg_lower_R", "ankle_R"),
    ("spine_2", "arm_upper_L"), ("arm_upper_L", "arm_lower_L"), ("arm_lower_L", "hand_L"),
    ("spine_2", "arm_upper_R"), ("arm_upper_R", "arm_lower_R"), ("arm_lower_R", "hand_R"),
]
BONE_READ_SIZE = (max(BONES.values()) + 1) * 32

WEAPON_NAMES = {
    1: "Deagle", 2: "Dual Berettas", 3: "Five-SeveN", 4: "Glock-18",
    7: "AK-47", 8: "AUG", 9: "AWP", 10: "FAMAS", 11: "G3SG1",
    13: "Galil", 14: "M249", 16: "M4A4", 17: "MAC-10",
    19: "P90", 23: "MP5-SD", 24: "UMP-45", 25: "XM1014",
    26: "PP-Bizon", 27: "MAG-7", 28: "Negev", 29: "Sawed-Off",
    30: "Tec-9", 31: "Zeus", 32: "P2000", 33: "MP7", 34: "MP9",
    35: "Nova", 36: "P250", 38: "SCAR-20", 39: "SG 553", 40: "SSG 08",
    60: "M4A1-S", 61: "USP-S", 63: "CZ75-Auto", 64: "R8",
}


class ESP:
    def __init__(self, mem, offset):
        self.mem = mem
        self.client = mem.client_base
        self.off = offset
        self.view_matrix = None
        self.local_team = 0
        self.local_pos = (0.0, 0.0, 0.0)
        self.local_eye = (0.0, 0.0, 0.0)   # НОВОЕ
        self.local_pawn = 0
        self.entities = []
        self._struct = None
        self._vis_logged = False
        self._weapon_cache = {}

        self._cached_local_index = 0
        self._cached_ctrl_ptr = 0
        self._cache_ts = 0.0

        self._el_ptr = 0
        self._el_ts = 0.0

        self._last_no_flash = 0.0

        self.enable_no_flash = False
        self.skeleton_enabled = False
        self.bomb = None
        self.enable_radar = False

    def _read_view_matrix(self):
        data = self.mem.read(self.client + self.off.dwViewMatrix, 64)
        self.view_matrix = list(struct.unpack("<16f", data))

    def world_to_screen(self, x, y, z):
        m = self.view_matrix
        if not m:
            return None
        w = m[12] * x + m[13] * y + m[14] * z + m[15]
        if w < 0.01:
            return None
        xs = (m[0] * x + m[1] * y + m[2] * z + m[3]) / w
        ys = (m[4] * x + m[5] * y + m[6] * z + m[7]) / w
        return (int((xs + 1) * 960), int((1 - ys) * 540))

    def _resolve(self, el_ptr, idx, combo):
        chunk_base, stride, deref = combo
        try:
            chunk = self.mem.read_pointer(el_ptr + chunk_base + 8 * (idx >> 9))
            if not chunk or chunk < 0x10000:
                return 0
            entry = chunk + stride * (idx & 0x1FF)
            if deref:
                entry = self.mem.read_pointer(entry)
                if not entry or entry < 0x10000:
                    return 0
            return entry
        except OSError:
            return 0

    def _get_entity(self, el_ptr, idx):
        if self._struct is None:
            return 0
        return self._resolve(el_ptr, idx, self._struct)

    def _get_el_ptr(self):
        now = time.time()
        if self._el_ptr and now - self._el_ts < 0.5:
            return self._el_ptr
        self._el_ptr = self.mem.read_pointer(self.client + self.off.dwEntityList)
        self._el_ts = now
        return self._el_ptr

    def _resolve_handle(self, el_ptr, handle):
        if handle == 0 or handle == 0xFFFFFFFF:
            return 0
        idx = handle & 0x7FFF
        if idx == 0:
            return 0
        return self._get_entity(el_ptr, idx)

    def _detect_structure(self, el_ptr):
        combos = [
            (0x10, 0x70, True), (0x10, 0x70, False),
            (0x10, 0x78, True), (0x10, 0x78, False),
        ]
        for combo in combos:
            hits = 0
            for idx in range(1, 17):
                addr = self._resolve(el_ptr, idx, combo)
                if not addr:
                    continue
                try:
                    team = self.mem.read_int(addr + self.off.m_iTeamNum)
                except OSError:
                    continue
                if team not in (1, 2, 3):
                    continue
                hp = self.mem.read_int(addr + self.off.m_iHealth)
                if 0 < hp <= 100:
                    hits += 1
                    continue
                handle = self.mem.read_uint(addr + self.off.m_hPlayerPawn)
                if handle == 0 or handle == 0xFFFFFFFF:
                    continue
                pawn = self._resolve(el_ptr, handle & 0x7FFF, combo)
                if not pawn:
                    continue
                hp = self.mem.read_int(pawn + self.off.m_iHealth)
                if 0 < hp <= 100:
                    hits += 1
            if hits >= 2:
                print(f"[ESP] entity list OK: 0x{combo[0]:X}/{combo[1]:X}/{combo[2]}")
                return combo
        print("[ESP] WARNING: entity list structure not detected")
        return None

    def _read_bones(self, pawn, full=False):
        try:
            scene = self.mem.read_pointer(pawn + self.off.m_pGameSceneNode)
            if not scene:
                return None
            matrix = self.mem.read_pointer(
                scene + self.off.m_modelState + self.off.m_boneArray
            )
            if not matrix:
                return None
            if full:
                raw = self.mem.read(matrix, BONE_READ_SIZE)
                return {name: struct.unpack_from("<fff", raw, idx * 32)
                        for name, idx in BONES.items()}
            head_off = BONES["head"] * 32
            raw = self.mem.read(matrix + head_off, 12)
            return {"head": struct.unpack("<fff", raw)}
        except OSError:
            return None

    def _find_local_index(self, el_ptr):
        now = time.time()
        try:
            ctrl = self.mem.read_pointer(self.client + self.off.dwLocalPlayerController)
            if not ctrl:
                return 0
            if ctrl == self._cached_ctrl_ptr and now - self._cache_ts < 1.0:
                return self._cached_local_index
            for i in range(1, 65):
                if self._get_entity(el_ptr, i) == ctrl:
                    self._cached_local_index = i
                    self._cached_ctrl_ptr = ctrl
                    self._cache_ts = now
                    return i
        except OSError:
            pass
        return 0

    def _check_visible(self, pawn):
        """Сначала m_bSpotted (общий флаг), потом маска — чтобы не залипало."""
        try:
            base = pawn + self.off.m_entitySpottedState
            spotted = self.mem.read_uint(base + self.off.m_bSpotted) & 0xFF
            if spotted == 0:
                return False
            if 1 <= self.local_index <= 64:
                if self.local_index <= 32:
                    mask = self.mem.read_uint(base + self.off.m_bSpottedByMask)
                    bit = 1 << (self.local_index - 1)
                else:
                    mask = self.mem.read_uint(base + self.off.m_bSpottedByMask + 4)
                    bit = 1 << (self.local_index - 33)
                return bool(mask & bit)
            return True
        except OSError:
            return False

    def _apply_radar(self, pawn):
        """Пишет m_bSpotted=1 через NtWriteVirtualMemory. Маску не трогаем."""
        try:
            base = pawn + self.off.m_entitySpottedState
            old = self.mem.read_uint(base + self.off.m_bSpotted) & 0xFF
            if old == 0:
                self.mem.write(base + self.off.m_bSpotted, b'\x01')
        except OSError:
            pass

    def _safe_no_flash(self):
        """Пишем m_flFlashMaxAlpha = 0 раз в 500 мс, с проверкой адреса."""
        now = time.time()
        if now - self._last_no_flash < 0.5:
            return
        self._last_no_flash = now
        if not self.local_pawn:
            return
        addr = self.local_pawn + self.off.m_flFlashMaxAlpha
        if addr < 0x10000:
            return
        try:
            cur = self.mem.read_float(addr)
            if cur > 0.01:
                self.mem.write_float(addr, 0.0)
        except OSError:
            pass

    def _get_weapon_name(self, pawn):
        now = time.time()
        cached = self._weapon_cache.get(pawn)
        if cached and now - cached[1] < 0.5:
            return cached[0]
        name = ""
        try:
            ws = self.mem.read_pointer(pawn + self.off.m_pWeaponServices)
            if ws:
                h = self.mem.read_uint(ws + self.off.m_hActiveWeapon)
                if h not in (0, 0xFFFFFFFF):
                    el_ptr = self._get_el_ptr()
                    if el_ptr and self._struct is not None:
                        weapon = self._resolve_handle(el_ptr, h)
                        if weapon:
                            idx = self.mem.read_uint(
                                weapon + self.off.m_AttributeManager
                                + self.off.m_Item + self.off.m_iItemDefinitionIndex
                            ) & 0xFFFF
                            name = WEAPON_NAMES.get(idx, "")
        except OSError:
            pass
        self._weapon_cache[pawn] = (name, now)
        return name

    def _read_bomb(self):
        try:
            c4 = self.mem.read_pointer(self.client + self.off.dwPlantedC4)
            if not c4:
                return None
            if self.mem.read_uint(c4 + self.off.m_bBombDefused) & 0xFF:
                return None
            return {"pos": self.mem.read_vec3(c4 + self.off.m_vOldOrigin)}
        except OSError:
            return None

    def _add(self, pawn, hp):
            try:
                team = self.mem.read_int(pawn + self.off.m_iTeamNum)
                if team == self.local_team or team == 0:
                    return
                pos = self.mem.read_vec3(pawn + self.off.m_vOldOrigin)

                bones = self._read_bones(pawn, full=self.skeleton_enabled)
                head_pos = bones["head"] if bones and "head" in bones \
                    else (pos[0], pos[1], pos[2] + 72.0)
                s = self.world_to_screen(*pos)
                hs = self.world_to_screen(*head_pos)
                if not s or not hs:
                    return
                bone_screens = {}
                if bones:
                    for name, p in bones.items():
                        sp = self.world_to_screen(*p)
                        if sp:
                            bone_screens[name] = sp

                if self.enable_radar:
                    self._apply_radar(pawn)

                self.entities.append({
                    "addr": pawn,
                    "pos": pos, "head_pos": head_pos,
                    "screen": s, "head_screen": hs,
                    "bones": bones, "bone_screens": bone_screens,
                    "health": hp, "team": team, "name": "",
                    "weapon": self._get_weapon_name(pawn),
                    "visible": self._check_visible(pawn),
                })
            except OSError:
                pass

    def update(self):
        try:
            self._read_view_matrix()
        except OSError:
            return

        try:
            self.local_pawn = self.mem.read_pointer(
                self.client + self.off.dwLocalPlayerPawn
            )
            if not self.local_pawn:
                self.entities = []
                return
            self.local_team = self.mem.read_int(self.local_pawn + self.off.m_iTeamNum)
            self.local_pos = self.mem.read_vec3(self.local_pawn + self.off.m_vOldOrigin)

            try:
                voff = self.mem.read_vec3(self.local_pawn + self.off.m_vecViewOffset)
                if not (-100 < voff[0] < 100 and -100 < voff[1] < 100
                        and -100 < voff[2] < 200):
                    voff = (0.0, 0.0, 64.0)
                self.local_eye = (self.local_pos[0] + voff[0],
                                  self.local_pos[1] + voff[1],
                                  self.local_pos[2] + voff[2])
            except OSError:
                self.local_eye = (self.local_pos[0], self.local_pos[1],
                                  self.local_pos[2] + 64.0)

            if self.enable_no_flash:
                self._safe_no_flash()
        except OSError:
            self.entities = []
            return

        el_ptr = self._get_el_ptr()
        if not el_ptr:
            self.entities = []
            return

        if self._struct is None:
            self._struct = self._detect_structure(el_ptr)
            if self._struct is None:
                self.entities = []
                return

        self.local_index = self._find_local_index(el_ptr)

        self.entities = []
        for i in range(1, 65):
            try:
                ent = self._get_entity(el_ptr, i)
                if not ent:
                    continue
                hp = self.mem.read_int(ent + self.off.m_iHealth)
                if 0 < hp <= 100:
                    self._add(ent, hp)
                    continue
                handle = self.mem.read_uint(ent + self.off.m_hPlayerPawn)
                if handle == 0 or handle == 0xFFFFFFFF:
                    continue
                pawn = self._resolve_handle(el_ptr, handle)
                if not pawn:
                    continue
                hp = self.mem.read_int(pawn + self.off.m_iHealth)
                if 0 < hp <= 100:
                    self._add(pawn, hp)
            except OSError:
                continue

        if len(self._weapon_cache) > 256:
            self._weapon_cache.clear()

        self.bomb = self._read_bomb()