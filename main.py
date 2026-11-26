import ctypes
import math
import time
import tkinter as tk
from glow import GlowController

try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
except Exception:
    pass

# КРИТИЧНО для точности silent aim: sleep(0.8ms) реально ~0.8ms, а не 15.6ms
try:
    ctypes.windll.winmm.timeBeginPeriod(1)
    _TIMER_1MS = True
except Exception:
    _TIMER_1MS = False

user32 = ctypes.WinDLL("user32")
VK_INSERT = 0x2D
VK_LBUTTON = 0x01
VK_MOUSE4 = 0x05

from memory import Memory, is_game_foreground
from offsets import GetOffsets
from esp import ESP, BONE_CONNECTIONS
from aimbot import Aimbot
from triggerbot import Triggerbot
from spinbot import Spinbot
from bhop import Bhop
from rcs import RecoilControl
from overlay import Overlay
from menu import Menu
from silent_aim import SilentAim
from config_manager import ConfigManager


def val(cfg, key):
    v = cfg.get(key)
    if v is None:
        return False
    return v[1].get() if isinstance(v, tuple) else v.get()


def health_color(hp):
    p = max(0.0, min(1.0, hp / 100.0))
    return f"#{int(255 * min(1.0, 2 - 2 * p)):02X}{int(255 * min(1.0, 2 * p)):02X}50"


def team_color(team):
    return {2: "#ffb84d", 3: "#4a9eff"}.get(team, "#cccccc")


def darken_hex(hex_color, factor=0.5):
    """Затемняет HEX-цвет. Возвращает исходный при ошибке."""
    h = hex_color.lstrip("#")
    if len(h) < 6:
        return hex_color
    try:
        r = int(h[0:2], 16)
        g = int(h[2:4], 16)
        b = int(h[4:6], 16)
    except ValueError:
        return hex_color
    return f"#{int(r*factor):02X}{int(g*factor):02X}{int(b*factor):02X}"


VIEW_ANGLES_QANGLE_OFFSET = 0x1C   # продублируй константу или импортни из silent_aim

def read_view_angles(mem, offset):
    try:
        ptr = mem.read_pointer(mem.client_base + offset.dwViewAngles)
        if not ptr or ptr < 0x10000:
            return (0.0, 0.0)
        pitch = mem.read_float(ptr + VIEW_ANGLES_QANGLE_OFFSET)
        yaw   = mem.read_float(ptr + VIEW_ANGLES_QANGLE_OFFSET + 4)
        if not (-89.5 <= pitch <= 89.5 and -180.5 <= yaw <= 180.5):
            return (0.0, 0.0)
        return (yaw % 360.0, pitch)
    except OSError:
        return (0.0, 0.0)

def wait_for_process(name="cs2.exe", delay=2.0):
    print(f"[*] Ожидание {name}...")
    while True:
        try:
            mem = Memory(name)
            print(f"[+] PID {mem.pid}, client @ 0x{mem.client_base:X}")
            return mem
        except RuntimeError:
            time.sleep(delay)


def wait_for_offsets(mem, delay=1.0):
    print("[*] Оффсеты...")
    while True:
        try:
            off = GetOffsets(mem)
            print("[+] Offsets OK")
            return off
        except Exception as e:
            print(f"[!] {e}, retry...")
            time.sleep(delay)


def main():
    print("[*] ARBUZIAN CS2")
    mem = wait_for_process()
    offset = wait_for_offsets(mem)

    esp = ESP(mem, offset)
    aimbot = Aimbot(mem, offset)
    silent = SilentAim(mem, offset)
    silent.start()
    triggerbot = Triggerbot(mem, offset)
    spinbot = Spinbot(mem, offset)
    bhop = Bhop(mem, offset)
    rcs = RecoilControl(mem, offset)
    glow = GlowController(mem, offset)
    overlay = Overlay()

    # ── временная диагностика m_angEyeAngles ──
    from offsets import DumpSchemas
    schema_buf = mem.read(mem.schemasystem_base,
                        mem.get_module_size(mem.schemasystem_base))
    diag_schemas = DumpSchemas(mem, mem.schemasystem_base,
                                mem.get_module_size(mem.schemasystem_base))
    print("[diag] ищу eye-angle поля:")
    for cls, fields in diag_schemas.items():
        for fname, foff in fields.items():
            low = fname.lower()
            if ("eyeangle" in low or "angEye" in fname
                    or "viewoffset" in low and "angle" in low):
                print(f"    {cls}.{fname} = 0x{foff:X}")

    config = {
        # ── AIMBOT ──
        "Silent Aim": tk.BooleanVar(value=False),
        "Silent FOV": ("slider", tk.DoubleVar(value=10.0), 1.0, 180.0),
        "Silent Hold (ms)": ("slider", tk.DoubleVar(value=18.0), 5.0, 50.0),
        "Silent Visibility": tk.BooleanVar(value=True),

        "Aimbot": tk.BooleanVar(value=False),
        "Aimbot Key": ("combo", tk.StringVar(value="Always"),
                        ["Always", "LMB", "RMB"]),
        "Aimbot Hitbox": ("combo", tk.StringVar(value="Head"),
                           ["Head", "Neck", "Chest", "Stomach"]),
        "Aimbot FOV": ("slider", tk.DoubleVar(value=15.0), 1.0, 90.0),
        "Aimbot Smooth": ("slider", tk.DoubleVar(value=8.0), 1.0, 30.0),
        "Aimbot Humanize": ("slider", tk.DoubleVar(value=0.0), 0.0, 1.0),
        "Aimbot Priority": ("combo", tk.StringVar(value="FOV"),
                             ["FOV", "Distance", "Lowest HP"]),
        "Aimbot Visibility": tk.BooleanVar(value=True),
        "Aimbot 360": tk.BooleanVar(value=False),

        "RCS Strength": ("slider", tk.DoubleVar(value=1.0), 0.0, 1.0),
        "RCS Start Bullet": ("slider", tk.DoubleVar(value=1), 1, 30),
        "Recoil Control": tk.BooleanVar(value=False),
        "RCS Smoothing": ("slider", tk.DoubleVar(value=1.5), 1.0, 5.0),

        "Triggerbot": tk.BooleanVar(value=False),
        "Trigger Delay (ms)": ("slider", tk.DoubleVar(value=50), 10, 500),

        # ── ANTI-AIM ──
        "Spinbot": tk.BooleanVar(value=False),
        "Spinbot Hotkey": tk.BooleanVar(value=True),
        "Spinbot Speed": ("slider", tk.DoubleVar(value=90.0), 10.0, 720.0),
        "Spinbot Mode": ("combo", tk.StringVar(value="Spin"),
                          ["Spin", "Jitter", "Random"]),
        "Jitter Range": ("slider", tk.DoubleVar(value=60.0), 10.0, 180.0),
        "Desync": tk.BooleanVar(value=False),
        "Desync Side": ("combo", tk.StringVar(value="Right"),
                         ["Left", "Right", "Random"]),

        # ── MOVEMENT ──
        "Bhop": tk.BooleanVar(value=False),
        "Bhop Hitchance": ("slider", tk.DoubleVar(value=85), 10, 100),
        "Bhop Delay (ms)": ("slider", tk.DoubleVar(value=0), 0, 30),
        "Auto Strafe": tk.BooleanVar(value=False),
        "Auto Strafe Strength": ("slider", tk.DoubleVar(value=6.0), 1.0, 20.0),

        # ── VISUALS ──
        "ESP Box": tk.BooleanVar(value=True),
        "ESP Corner Box": tk.BooleanVar(value=False),
        "ESP Skeleton": tk.BooleanVar(value=False),
        "ESP Health": tk.BooleanVar(value=True),
        "ESP Name": tk.BooleanVar(value=False),
        "ESP Distance": tk.BooleanVar(value=True),
        "ESP Weapon": tk.BooleanVar(value=True),
        "ESP Tracer": tk.BooleanVar(value=False),
        "ESP Fill": tk.BooleanVar(value=False),
        "Bomb ESP": tk.BooleanVar(value=True),
        "Radar Hack": tk.BooleanVar(value=False),
        "No Flash": tk.BooleanVar(value=False),
        "FOV Circle": tk.BooleanVar(value=True),
        "ESP Debug": tk.BooleanVar(value=True),
        "ESP Glow": tk.BooleanVar(value=False),
    }

    cfg_mgr = ConfigManager(config, folder="configs", name="default")
    cfg_mgr.load()

    menu = Menu(overlay.root, config,
                on_save=cfg_mgr.save, on_load=cfg_mgr.load)
    overlay.root.protocol("WM_DELETE_WINDOW", overlay.root.quit)

    VK_END = 0x23
    insert_prev = [False]
    fps_state = {"last": time.time(), "fps": 60.0}

    def tick(ov):
        # Аварийный выход по END
        if user32.GetAsyncKeyState(VK_END) & 0x8000:
            print("\n[!] END pressed, exiting...")
            ov.root.quit()
            return

        now_t = time.time()
        dt = now_t - fps_state["last"]
        fps_state["last"] = now_t
        if dt > 0:
            fps_state["fps"] = 0.9 * fps_state["fps"] + 0.1 / dt

        state = user32.GetAsyncKeyState(VK_INSERT) & 0x8000 != 0
        if state and not insert_prev[0]:
            menu.toggle()
        insert_prev[0] = state

        fg_ok = is_game_foreground()

        esp.enable_no_flash = val(config, "No Flash")
        esp.skeleton_enabled = val(config, "ESP Skeleton")
        esp.enable_radar = val(config, "Radar Hack")
        esp.update()
        glow.update(esp.entities,
                    esp.local_team,
                    val(config, "ESP Glow") and fg_ok)

        W, H = ov.width, ov.height
        aimbot.set_screen_aspect(W, H)
        aimbot.fov = val(config, "Aimbot FOV")
        aimbot.smooth = max(1.0, val(config, "Aimbot Smooth"))
        aimbot.humanize = val(config, "Aimbot Humanize")
        aimbot.rcs_strength = val(config, "RCS Strength")
        aimbot.rcs_start_bullet = int(val(config, "RCS Start Bullet"))
        aimbot.visibility_check = val(config, "Aimbot Visibility")
        aimbot.hitbox = val(config, "Aimbot Hitbox")
        aimbot.aim_key = val(config, "Aimbot Key")
        aimbot.target_priority = val(config, "Aimbot Priority")

        if val(config, "FOV Circle"):
            r = int(aimbot.fov_radius_px(H))
            ov.circle(W // 2, H // 2, max(2, r), "#22c55e", 1)

        if val(config, "Bomb ESP") and esp.bomb:
            bs = esp.world_to_screen(*esp.bomb["pos"])
            if bs:
                ov.circle(bs[0], bs[1], 22, "#ff4444", 2)
                ov.text(bs[0], bs[1] - 26, "BOMB", "#ff4444", 11, anchor="s", bold=True)

        # ── ESP ──
        draw = any(val(config, k) for k in (
            "ESP Box", "ESP Corner Box", "ESP Skeleton", "ESP Health",
            "ESP Name", "ESP Distance", "ESP Weapon", "ESP Tracer", "ESP Fill"))

        if draw:
            for e in esp.entities:
                hs, fs = e["head_screen"], e["screen"]
                y1, y2 = hs[1], fs[1]
                if y2 - y1 < 5:
                    continue
                bh = y2 - y1
                bw = max(25, int(bh * 0.45))
                cx = hs[0]
                x1, x2 = cx - bw // 2, cx + bw // 2

                # Цвет команды, но затемнённый если не видим
                base_col = team_color(e["team"])
                visible = e.get("visible", True)
                col = base_col if visible else darken_hex(base_col, 0.5)

                if val(config, "ESP Fill"):
                    fill = ("#3a2010" if e["team"] == 2 else "#10243a")
                    ov.rect_fill(x1, y1, x2, y2,
                                 fill if visible else darken_hex(fill, 0.55))

                if val(config, "ESP Corner Box"):
                    ov.corner_box(x1, y1, x2, y2, col, 2)
                elif val(config, "ESP Box"):
                    ov.box(x1, y1, x2, y2, col, 2)

                if val(config, "ESP Skeleton") and e["bone_screens"]:
                    bs = e["bone_screens"]
                    sk_col = col if visible else darken_hex(col, 0.55)
                    for a, b in BONE_CONNECTIONS:
                        if a in bs and b in bs:
                            ov.line(bs[a][0], bs[a][1], bs[b][0], bs[b][1], sk_col, 1)

                if val(config, "ESP Health"):
                    hp_col = health_color(e["health"])
                    if not visible:
                        hp_col = darken_hex(hp_col, 0.6)
                    ov.health_bar(x1 - 7, y1, 4, bh, e["health"], hp_col)

                if val(config, "ESP Name") and e["name"]:
                    ov.text(cx, y1 - 12, e["name"],
                            "#fff" if visible else "#888", 10, anchor="n", bold=True)

                parts = []
                if val(config, "ESP Weapon") and e.get("weapon"):
                    parts.append(e["weapon"])
                if val(config, "ESP Distance"):
                    d = math.dist(e["pos"], esp.local_pos) * 0.0254
                    parts.append(f"{d:.0f}m")
                if parts:
                    ov.text(cx, y2 + 4, " | ".join(parts),
                            "#ccc" if visible else "#666", 9, anchor="n")

                if val(config, "ESP Tracer"):
                    ov.line(W // 2, H, cx, (y1 + y2) // 2, col, 1)

        # ── SMOOTH AIMBOT ──
        aimbot.enabled = val(config, "Aimbot")
        smooth_aimed = aimbot.update(esp.entities, esp.local_pawn, W, H)

        if val(config, "360 Aim") and esp.entities:
            target = min(esp.entities,
                         key=lambda e: math.dist(e["head_pos"], esp.local_eye))
            aimbot.aim_at_360(esp.local_eye, target["head_pos"],
                              smooth=1.0)   # 1.0 = мгновенно, без интерполяции

        # ── SILENT AIM ──
        silent_busy = silent.is_active()
        if val(config, "Silent Aim"):
            silent.use_360 = val(config, "360 Aim")
            silent.visible_only = val(config, "Silent Visibility")
            silent.hold_s = val(config, "Silent Hold (ms)") / 1000.0
            silent.rcs_strength = val(config, "RCS Strength")
            silent.rcs_start_bullet = int(val(config, "RCS Start Bullet"))

            cur_yaw, cur_pitch = read_view_angles(mem, offset)
            eye = esp.local_eye
            targets = []

            for e in esp.entities:
                if silent.visible_only and not e.get("visible"):
                    continue
                tx, ty, tz = e["head_pos"]
                dx_w = tx - eye[0]
                dy_w = ty - eye[1]
                dz_w = tz - eye[2]

                horiz = math.hypot(dx_w, dy_w)
                if horiz < 1.0:
                    continue

                tgt_yaw = math.degrees(math.atan2(dy_w, dx_w)) % 360.0
                tgt_pitch = -math.degrees(math.atan2(dz_w, horiz))

                # приводим к [-180, 180] для корректного сравнения
                d_yaw = (tgt_yaw - cur_yaw + 180) % 360 - 180
                d_pitch = tgt_pitch - cur_pitch
                dist = math.hypot(d_yaw, d_pitch)

                limit = 180.0 if silent.use_360 else silent.fov
                if dist <= limit:
                    targets.append((tgt_yaw, tgt_pitch, dist))

            punch = aimbot._get_punch(esp.local_pawn)
            shots = aimbot._shots_fired(esp.local_pawn)
            silent.publish(targets, punch, shots, True, fg_ok)
        else:
            silent.publish([], (0.0, 0.0), 0, False, fg_ok)

        # ── RCS ──
        if val(config, "Recoil Control") and not smooth_aimed and not silent_busy:
            rcs.smoothing = val(config, "RCS Smoothing")
            rcs.update(False)
        else:
            rcs.reset()

        # ── TRIGGERBOT ──
        triggerbot.enabled = val(config, "Triggerbot") and fg_ok
        if triggerbot.enabled:
            triggerbot.delay = val(config, "Trigger Delay (ms)") / 1000.0
        triggerbot.update(esp.local_team)

        # ── ANTI-AIM ──
        spinbot_active = False
        if not silent_busy and not smooth_aimed:
            spin_hotkey = bool(user32.GetAsyncKeyState(VK_MOUSE4) & 0x8000)
            hotkey_mode = val(config, "Spinbot Hotkey")
            spinbot.desync_side = val(config, "Desync Side")
            if val(config, "Spinbot"):
                spinbot.mode = val(config, "Spinbot Mode")
                spinbot.speed = val(config, "Spinbot Speed")
                spinbot.jitter_range = val(config, "Jitter Range")
                spinbot.update(desync=False,
                                hotkey_held=(spin_hotkey if hotkey_mode else True))
                spinbot_active = True
            elif val(config, "Desync"):
                spinbot.jitter_range = val(config, "Jitter Range")
                spinbot.update(desync=True,
                                hotkey_held=(spin_hotkey if hotkey_mode else True))
                spinbot_active = True

        # ── BHOP ──
        if val(config, "Bhop"):
            bhop.autostrafe_strength = val(config, "Auto Strafe Strength")
            bhop.hitchance = val(config, "Bhop Hitchance") / 100.0
            bhop.delay = val(config, "Bhop Delay (ms)") / 1000.0
            bhop.update(autostrafe=(val(config, "Auto Strafe")
                                    and not smooth_aimed
                                    and not silent_busy
                                    and not spinbot_active))

        # ── AUTOSAVE ──
        cfg_mgr.autosave(interval=1.5)

        # ── DEBUG ──
        if val(config, "ESP Debug"):
            status = (f"{fps_state['fps']:.0f} fps | "
                      f"enemies {len(esp.entities)}")
            if silent_busy:
                status += f" | SILENT x{silent.snaps}"
            if smooth_aimed:
                status += " | AIM"
            if not fg_ok:
                status += " | PAUSED"
            ov.text(10, 10, status, "#22c55e", 11, bold=True)

    try:
        overlay.run(tick, interval=16)
    except KeyboardInterrupt:
        print("\n[!] Exit")
    finally:
        try:
            cfg_mgr.save()
        except Exception:
            pass
        silent.stop()
        if _TIMER_1MS:
            try:
                ctypes.windll.winmm.timeEndPeriod(1)
            except Exception:
                pass
        mem.close()


if __name__ == "__main__":
    main()