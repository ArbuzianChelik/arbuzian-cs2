import ctypes
import math
import time
import tkinter as tk
import os
import sys
import traceback

try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
except Exception:
    pass

try:
    ctypes.windll.winmm.timeBeginPeriod(1)
    _TIMER_1MS = True
except Exception:
    _TIMER_1MS = False

user32 = ctypes.WinDLL("user32")
VK_INSERT = 0x2D
VK_END = 0x23
VK_LBUTTON = 0x01
VK_MOUSE4 = 0x05

# ================= ЛОГИРОВАНИЕ (должно быть до импорта модулей) =================
LOG_FILE = "logs.txt"

class _Tee:
    """Дублирует весь stdout/stderr в файл с таймстампом по строкам."""
    def __init__(self, real, path):
        self._real = real
        self._path = path
        self._buf = ""

    def _emit(self, line):
        ts = time.strftime('%H:%M:%S')
        stamped = f"[{ts}] {line}"
        try:
            self._real.write(stamped)
        except Exception:
            pass
        try:
            with open(self._path, "a", encoding="utf-8") as f:
                f.write(stamped)
        except Exception:
            pass

    def write(self, s):
        if not s:
            return
        self._buf += s
        while "\n" in self._buf:
            line, self._buf = self._buf.split("\n", 1)
            self._emit(line + "\n")

    def flush(self):
        if self._buf:
            self._emit(self._buf)
            self._buf = ""
        try:
            self._real.flush()
        except Exception:
            pass

    def isatty(self):
        return False


def _install_tee():
    """Ставим Tee один раз. Повторный вызов безопасен."""
    if isinstance(sys.stdout, _Tee):
        return
    sys.stdout = _Tee(sys.__stdout__, LOG_FILE)
    sys.stderr = _Tee(sys.__stderr__, LOG_FILE)


_install_tee()
# ==============================================================================

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


def log(msg):
    """Просто print — TeeWriter добавит таймстамп и запишет в logs.txt."""
    print(msg)


def val(cfg, key):
    v = cfg[key]
    return v[1].get() if isinstance(v, tuple) else v.get()


def health_color(hp):
    p = max(0.0, min(1.0, hp / 100.0))
    return f"#{int(255 * min(1.0, 2 - 2 * p)):02X}{int(255 * min(1.0, 2 * p)):02X}50"


def team_color(team):
    return {2: "#ffb84d", 3: "#4a9eff"}.get(team, "#cccccc")


def darken_hex(hex_color, factor=0.5):
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


def read_view_angles(mem, offset):
    try:
        ptr = mem.read_pointer(mem.client_base + offset.dwViewAngles)
        if not ptr:
            return (0.0, 0.0)
        yaw = mem.read_float(ptr)
        pitch = mem.read_float(ptr + 4)
        if not (-720 <= yaw <= 720):
            yaw = 0.0
        if not (-180 <= pitch <= 180):
            pitch = 0.0
        return (yaw % 360.0, pitch)
    except OSError:
        return (0.0, 0.0)


def wait_for_process(name="cs2.exe", delay=2.0):
    log(f"[*] Ожидание {name}...")
    while True:
        try:
            mem = Memory(name)
            log(f"[+] PID {mem.pid}, client @ 0x{mem.client_base:X}")
            return mem
        except RuntimeError:
            time.sleep(delay)


def wait_for_offsets(mem, delay=1.0):
    log("[*] Оффсеты...")
    while True:
        try:
            off = GetOffsets(mem)
            log("[+] Offsets OK")
            return off
        except Exception as e:
            log(f"[!] {e}, retry...")
            time.sleep(delay)


def _dump_offsets(offset):
    """Пишет в лог ключевые оффсеты — полезно при диагностике."""
    for name in ("dwEntityList", "dwLocalPlayerPawn", "dwLocalPlayerController",
                 "dwViewMatrix", "dwViewAngles", "dwPlantedC4"):
        v = getattr(offset, name, None)
        if v is not None:
            log(f"[*] offset {name} = 0x{v:X}" if isinstance(v, int) else f"[*] offset {name} = {v!r}")


def main():
    log("=" * 60)
    log("[*] ARBUZIAN CS2 — External")
    log(f"[*] Python {sys.version.split()[0]}, cwd={os.getcwd()}")
    log("=" * 60)

    mem = wait_for_process()
    offset = wait_for_offsets(mem)
    _dump_offsets(offset)

    # === Инициализация модулей ===
    log("[*] Инициализация модулей...")
    esp = ESP(mem, offset)
    aimbot = Aimbot(mem, offset)
    silent = SilentAim(mem, offset)
    silent.start()
    triggerbot = Triggerbot(mem, offset)
    spinbot = Spinbot(mem, offset)
    bhop = Bhop(mem, offset)
    rcs = RecoilControl(mem, offset)

    # Создаем скрытое главное окно для Tkinter переменных
    root = tk.Tk()
    root.withdraw()

    log("[*] Создание конфига...")
    config = {
        # ── AIMBOT ──
        "Silent Aim": tk.BooleanVar(value=False),
        "360 Aim": tk.BooleanVar(value=False),
        "Silent FOV": ("slider", tk.DoubleVar(value=10.0), 1.0, 180.0),
        "Silent Hold (ms)": ("slider", tk.DoubleVar(value=18.0), 5.0, 50.0),
        "Silent Visibility": tk.BooleanVar(value=True),
        "Aimbot": tk.BooleanVar(value=False),
        "Aimbot Key": ("combo", tk.StringVar(value="Always"), ["Always", "LMB", "RMB"]),
        "Aimbot Hitbox": ("combo", tk.StringVar(value="Head"), ["Head", "Neck", "Chest", "Stomach"]),
        "Aimbot FOV": ("slider", tk.DoubleVar(value=15.0), 1.0, 90.0),
        "Aimbot Smooth": ("slider", tk.DoubleVar(value=8.0), 1.0, 30.0),
        "Aimbot Humanize": ("slider", tk.DoubleVar(value=0.0), 0.0, 1.0),
        "Aimbot Priority": ("combo", tk.StringVar(value="FOV"), ["FOV", "Distance", "Lowest HP"]),
        "Aimbot Visibility": tk.BooleanVar(value=True),
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
        "Spinbot Mode": ("combo", tk.StringVar(value="Spin"), ["Spin", "Jitter", "Random"]),
        "Jitter Range": ("slider", tk.DoubleVar(value=60.0), 10.0, 180.0),
        "Desync": tk.BooleanVar(value=False),
        "Desync Side": ("combo", tk.StringVar(value="Right"), ["Left", "Right", "Random"]),
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
        "Glow ESP": tk.BooleanVar(value=False),
        "Radar Hack": tk.BooleanVar(value=False),
        "No Flash": tk.BooleanVar(value=False),
        "FOV Circle": tk.BooleanVar(value=True),
        "ESP Debug": tk.BooleanVar(value=True),
    }

    log("[*] Загрузка профиля...")
    cfg_mgr = ConfigManager(config, folder="configs", default_name="default")
    cfg_mgr.load()

    log("[*] Инициализация оверлея...")
    try:
        overlay = Overlay(cfg_mgr)
    except TypeError:
        overlay = Overlay()

    log("[*] Создание меню...")
    menu = Menu(overlay.root, config, config_manager=cfg_mgr)

    overlay.root.protocol("WM_DELETE_WINDOW", overlay.root.quit)

    insert_prev = [False]
    fps_state = {"last": time.time(), "fps": 60.0}
    tick_count = [0]
    diag_count = [0]
    prev_fg = [None]
    prev_ent_count = [None]

    def tick(ov):
        # === INSERT ===
        state = user32.GetAsyncKeyState(VK_INSERT) & 0x8000 != 0
        if state and not insert_prev[0]:
            menu.toggle()
            log("[*] Menu toggled (INSERT)")
            try:
                menu.refresh_visibility()
            except Exception:
                pass
        insert_prev[0] = state

        # === END ===
        if user32.GetAsyncKeyState(VK_END) & 0x8000:
            log("[!] END pressed, exiting...")
            ov.root.quit()
            return

        now_t = time.time()
        dt = now_t - fps_state["last"]
        fps_state["last"] = now_t
        if dt > 0:
            fps_state["fps"] = 0.9 * fps_state["fps"] + 0.1 / dt

        fg_ok = is_game_foreground()
        if prev_fg[0] is None or prev_fg[0] != fg_ok:
            log(f"[*] foreground changed: {prev_fg[0]} -> {fg_ok}")
            prev_fg[0] = fg_ok

        esp.enable_no_flash = val(config, "No Flash")
        esp.skeleton_enabled = val(config, "ESP Skeleton")
        esp.enable_radar = val(config, "Radar Hack")
        esp.enable_glow = val(config, "Glow ESP")
        try:
            esp.update()
        except Exception as e:
            log(f"[!] ESP update error: {e}")
            log(traceback.format_exc())

        if hasattr(ov, 'width') and hasattr(ov, 'height'):
            W, H = ov.width, ov.height
        else:
            W = ov.root.winfo_screenwidth()
            H = ov.root.winfo_screenheight()

        # Смена количества сущностей — логируем всегда
        cur_count = len(esp.entities)
        if prev_ent_count[0] != cur_count:
            log(f"[*] entities: {prev_ent_count[0]} -> {cur_count}")
            prev_ent_count[0] = cur_count

        # Диагностика раз в ~секунду
        diag_count[0] += 1
        if diag_count[0] % 60 == 0:
            log(f"[diag] fg={fg_ok} pawn={'Y' if esp.local_pawn else 'N'} "
                f"entities={cur_count} bomb={'Y' if esp.bomb else 'N'} "
                f"W={W} H={H} fps={fps_state['fps']:.0f}")
            # Детально по ESP: адрес списка, структура, первая сущность
            try:
                el_off = getattr(offset, "dwEntityList", None)
                if el_off is not None:
                    el_ptr = mem.read_pointer(mem.client_base + el_off)
                    log(f"[diag/esp] dwEntityList@0x{el_off:X} -> el_ptr=0x{el_ptr:X}")
                struct = getattr(esp, "_struct", "<no attr>")
                log(f"[diag/esp] struct={struct}")
                if cur_count > 0:
                    e0 = esp.entities[0]
                    log(f"[diag/esp] first: team={e0.get('team')} "
                        f"hp={e0.get('health')} pos={e0.get('pos')} "
                        f"weapon={e0.get('weapon')!r} vis={e0.get('visible')}")
                else:
                    log("[diag/esp] entities empty — check esp._detect_structure() "
                        "and offsets dwEntityList")
            except Exception as ex:
                log(f"[diag/esp] error: {ex}")

        # ── AIMBOT ──
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

        draw = any(val(config, k) for k in (
            "ESP Box", "ESP Corner Box", "ESP Skeleton", "ESP Health", "ESP Name",
            "ESP Distance", "ESP Weapon", "ESP Tracer", "ESP Fill"
        ))
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
                base_col = team_color(e["team"])
                visible = e.get("visible", True)
                col = base_col if visible else darken_hex(base_col, 0.5)

                if val(config, "ESP Fill"):
                    fill = "#3a2010" if e["team"] == 2 else "#10243a"
                    ov.rect_fill(x1, y1, x2, y2, fill if visible else darken_hex(fill, 0.55))
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
                    ov.text(cx, y1 - 12, e["name"], "#fff" if visible else "#888", 10, anchor="n", bold=True)
                parts = []
                if val(config, "ESP Weapon") and e.get("weapon"):
                    parts.append(e["weapon"])
                if val(config, "ESP Distance"):
                    d = math.dist(e["pos"], esp.local_pos) * 0.0254
                    parts.append(f"{d:.0f}m")
                if parts:
                    ov.text(cx, y2 + 4, " | ".join(parts), "#ccc" if visible else "#666", 9, anchor="n")
                if val(config, "ESP Tracer"):
                    ov.line(W // 2, H, cx, (y1 + y2) // 2, col, 1)

        aimbot.enabled = val(config, "Aimbot")
        smooth_aimed = aimbot.update(esp.entities, esp.local_pawn, W, H)

        silent_busy = silent.is_active()
        if val(config, "Silent Aim"):
            silent.use_360 = val(config, "360 Aim")
            silent.visible_only = val(config, "Silent Visibility")
            silent.hold_s = val(config, "Silent Hold (ms)") / 1000.0
            silent.rcs_strength = val(config, "RCS Strength")
            silent.rcs_start_bullet = int(val(config, "RCS Start Bullet"))
            targets = []
            if silent.use_360:
                cur_yaw, cur_pitch = read_view_angles(mem, offset)
                eye = esp.local_eye
                for e in esp.entities:
                    if silent.visible_only and not e.get("visible"):
                        continue
                    tx, ty, tz = e["head_pos"]
                    dx_w = tx - eye[0]
                    dy_w = ty - eye[1]
                    dz_w = tz - eye[2]
                    horiz = math.hypot(dx_w, dy_w)
                    tgt_yaw = math.degrees(math.atan2(dy_w, dx_w)) % 360.0
                    tgt_pitch = -math.degrees(math.atan2(dz_w, horiz))
                    d_yaw = (tgt_yaw - cur_yaw + 180) % 360 - 180
                    d_pitch = tgt_pitch - cur_pitch
                    move_yaw = -d_yaw
                    move_pitch = d_pitch
                    dist = math.hypot(move_yaw, move_pitch)
                    if dist <= 180.0:
                        targets.append((move_yaw, move_pitch, dist))
            else:
                fov_limit = silent.fov
                for e in esp.entities:
                    if silent.visible_only and not e.get("visible"):
                        continue
                    yaw, pitch, dist = aimbot.angle_to(W, H, e["head_screen"])
                    if dist <= fov_limit:
                        targets.append((yaw, pitch, dist))
            sens = aimbot._sensitivity()
            punch = aimbot._get_punch(esp.local_pawn)
            shots = aimbot._shots_fired(esp.local_pawn)
            silent.publish(targets, sens, punch, shots, True, fg_ok)
        else:
            silent.publish([], 2.0, (0.0, 0.0), 0, False, fg_ok)

        if val(config, "Recoil Control") and not smooth_aimed and not silent_busy:
            rcs.smoothing = val(config, "RCS Smoothing")
            rcs.update(False)
        else:
            rcs.reset()

        triggerbot.enabled = val(config, "Triggerbot") and fg_ok
        if triggerbot.enabled:
            triggerbot.delay = val(config, "Trigger Delay (ms)") / 1000.0
            triggerbot.update(esp.local_team)

        spinbot_active = False
        if not silent_busy and not smooth_aimed:
            spin_hotkey = bool(user32.GetAsyncKeyState(VK_MOUSE4) & 0x8000)
            hotkey_mode = val(config, "Spinbot Hotkey")
            if val(config, "Spinbot"):
                spinbot.mode = val(config, "Spinbot Mode")
                spinbot.speed = val(config, "Spinbot Speed")
                spinbot.jitter_range = val(config, "Jitter Range")
                spinbot.update(hotkey_held=(spin_hotkey if hotkey_mode else True))
                spinbot_active = True

        if val(config, "Bhop"):
            bhop.autostrafe_strength = val(config, "Auto Strafe Strength")
            bhop.update(autostrafe=(val(config, "Auto Strafe") and not smooth_aimed and not silent_busy and not spinbot_active))

        cfg_mgr.autosave(interval=1.5)

        if val(config, "ESP Debug"):
            status = f"{fps_state['fps']:.0f} fps | enemies {len(esp.entities)}"
            status += f" | pawn {'Y' if esp.local_pawn else 'N'}"
            status += f" | fg {'Y' if fg_ok else 'N'}"
            status += f" | {W}x{H}"
            if silent_busy:
                status += f" | SILENT x{silent.snaps}"
            if smooth_aimed:
                status += " | AIM"
            ov.text(10, 10, status, "#22c55e", 11, bold=True)

    def tick_ui():
        try:
            state = user32.GetAsyncKeyState(VK_INSERT) & 0x8000 != 0
            if state and not insert_prev[0]:
                menu.toggle()
                try:
                    menu.refresh_visibility()
                except Exception:
                    pass
            insert_prev[0] = state

            tick_count[0] += 1
            if tick_count[0] % 3 == 0:
                try:
                    menu.refresh_visibility()
                except Exception:
                    pass
        except Exception as e:
            log(f"[!] UI tick error: {e}")
        try:
            overlay.root.after(50, tick_ui)
        except Exception:
            pass

    def _overlay_alive():
        try:
            return overlay.root.winfo_exists() != 0
        except Exception:
            return False

    def tick_loop():
        if not _overlay_alive():
            log("[*] Overlay window closed, tick loop stopped")
            return
        try:
            overlay.clear()
        except Exception as e:
            log(f"[!] Clear error: {e}")
            log(traceback.format_exc())
        try:
            tick(overlay)
        except Exception as e:
            log(f"[!] Tick error: {e}")
            log(traceback.format_exc())
        if not _overlay_alive():
            log("[*] Overlay window closed, tick loop stopped")
            return
        try:
            overlay.root.after(16, tick_loop)
        except Exception:
            pass

    log("[*] Запуск tick loop и mainloop...")
    overlay.root.after(16, tick_loop)

    try:
        overlay.start()
    except KeyboardInterrupt:
        log("[!] KeyboardInterrupt")
    finally:
        log("[*] Завершение сессии...")
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
        # Финальный flush, чтобы последние строки точно попали в файл
        try:
            sys.stdout.flush()
        except Exception:
            pass
        log("[*] Done.")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        log(f"\n[!] КРИТИЧЕСКАЯ ОШИБКА: {e}")
        log(traceback.format_exc())
        input("Нажми Enter для выхода...")