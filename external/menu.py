import ctypes
from ctypes import wintypes
import tkinter as tk
import customtkinter as ctk
import os
import subprocess

ctk.set_appearance_mode("dark")

ACCENT = "#22c55e"
ACCENT_HOVER = "#4ade80"
ACCENT_DIM = "#166534"
BG = "#080f08"
CARD = "#0f1a10"
CARD_HOVER = "#152016"
BORDER = "#1e2e20"
TEXT = "#e8f5e8"
SUBTEXT = "#7a8f7a"
SIDEBAR_W = 140

DESCRIPTIONS = {
    "Silent Aim": {"en": "Snap only on shot (miss on semi-auto)", "ru": "Снап только на выстреле"},
    "360 Aim": {"en": "Aim behind you (world angle)", "ru": "Наводит и за спиной"},
    "Aimbot": {"en": "Smooth aimbot via mouse emulation", "ru": "Плавный аимбот через эмуляцию мыши"},
    "Aimbot FOV": {"en": "Max angular distance to target", "ru": "Макс. угол до цели, градусы"},
    "Aimbot Smooth": {"en": "Higher = slower (more human)", "ru": "Больше = плавнее"},
    "Aimbot Humanize": {"en": "Adds random jitter", "ru": "Случайный джиттер"},
    "Aimbot Visibility": {"en": "Skip targets behind walls", "ru": "Пропускать цели за стенами"},
    "Aimbot Priority": {"en": "Target selection logic", "ru": "Логика выбора цели"},
    "Aimbot Key": {"en": "When to activate aimbot", "ru": "Когда активировать"},
    "Aimbot Hitbox": {"en": "Which bone to aim at", "ru": "В какую кость целиться"},
    "RCS Strength": {"en": "0=off, 1=full", "ru": "0=выкл, 1=полная"},
    "RCS Start Bullet": {"en": "Start compensation after N-th bullet", "ru": "Начать с N-й пули"},
    "Recoil Control": {"en": "Standalone recoil compensation", "ru": "Компенсация отдачи"},
    "RCS Smoothing": {"en": "Higher = smoother", "ru": "Больше = плавнее"},
    "Triggerbot": {"en": "Auto-fire when crosshair on enemy", "ru": "Авто-стрельба при наведении"},
    "Trigger Delay (ms)": {"en": "Cooldown between shots", "ru": "Кулдаун между выстрелами"},
    "Spinbot": {"en": "Rotate your view constantly (HvH)", "ru": "Вращение камеры (HvH)"},
    "Spinbot Speed": {"en": "Rotation speed", "ru": "Скорость вращения"},
    "Spinbot Mode": {"en": "Spin / Jitter / Random", "ru": "Режим вращения"},
    "Jitter Range": {"en": "Max yaw deviation", "ru": "Макс. отклонение"},
    "Spinbot Hotkey": {"en": "Requires Mouse4", "ru": "Требует Mouse4"},
    "Desync": {"en": "Quick yaw flips", "ru": "Быстрые флипы"},
    "Bhop": {"en": "Auto-jump on landing", "ru": "Авто-прыжок"},
    "Bhop Hitchance": {"en": "Chance to register each jump", "ru": "Шанс регистрации"},
    "Bhop Delay (ms)": {"en": "Delay between jumps", "ru": "Задержка"},
    "Auto Strafe": {"en": "Auto air-strafe", "ru": "Авто-стрейф"},
    "Auto Strafe Strength": {"en": "Mouse counts per frame", "ru": "Пикселей за кадр"},
    "ESP Box": {"en": "Draw 2D box", "ru": "Рисовать 2D-бокс"},
    "ESP Corner Box": {"en": "Stylized corners", "ru": "Угловой бокс"},
    "ESP Skeleton": {"en": "Draw bones", "ru": "Скелет"},
    "ESP Health": {"en": "Health bar", "ru": "Полоска здоровья"},
    "ESP Name": {"en": "Player name", "ru": "Имя игрока"},
    "ESP Distance": {"en": "Distance in meters", "ru": "Расстояние"},
    "ESP Weapon": {"en": "Active weapon", "ru": "Оружие"},
    "ESP Tracer": {"en": "Line to enemy", "ru": "Линия к врагу"},
    "ESP Fill": {"en": "Filled rectangle", "ru": "Заливка"},
    "Bomb ESP": {"en": "Show C4", "ru": "Показать C4"},
    "Radar Hack": {"en": "Force radar (writes to mem)", "ru": "Радар (запись)"},
    "No Flash": {"en": "Disable flash (writes to mem)", "ru": "Без флешки (запись)"},
    "Glow ESP": {"en": "Outline glow (writes to mem)", "ru": "Свечение (запись)"},
    "FOV Circle": {"en": "Draw aimbot FOV circle", "ru": "Круг FOV"},
    "ESP Debug": {"en": "Stats on top-left", "ru": "Статистика слева"},
}

# ВОЗВРАЩЕНЫ ИКОНКИ
TABS = {
    "Aimbot": {
        "icon": "🎯",
        "sections": {
            "SILENT AIM": {"parent": "Silent Aim", "items": ["Silent Aim", "360 Aim", "Silent FOV", "Silent Hold (ms)", "Silent Visibility"]},
            "SMOOTH AIM": {"parent": "Aimbot", "items": ["Aimbot", "Aimbot Key", "Aimbot Hitbox", "Aimbot FOV", "Aimbot Smooth", "Aimbot Humanize", "Aimbot Priority", "Aimbot Visibility"]},
            "RECOIL": {"parent": "Recoil Control", "items": ["Recoil Control", "RCS Smoothing", "RCS Strength", "RCS Start Bullet"]},
            "TRIGGER": {"parent": "Triggerbot", "items": ["Triggerbot", "Trigger Delay (ms)"]},
        },
    },
    "Anti-Aim": {
        "icon": "🔄",
        "sections": {
            "SPINBOT": {"parent": "Spinbot", "items": ["Spinbot", "Spinbot Hotkey", "Spinbot Speed", "Spinbot Mode", "Jitter Range"]},
            "DESYNC": {"parent": "Desync", "items": ["Desync", "Desync Side"]},
        },
    },
    "Movement": {
        "icon": "🏃",
        "sections": {
            "BHOP": {"parent": "Bhop", "items": ["Bhop", "Bhop Hitchance", "Bhop Delay (ms)", "Auto Strafe", "Auto Strafe Strength"]},
        },
    },
    "Visuals": {
        "icon": "👁",
        "sections": {
            "PLAYER ESP": {"parent": "ESP Box", "items": ["ESP Box", "ESP Corner Box", "ESP Skeleton", "ESP Health", "ESP Name", "ESP Distance", "ESP Weapon", "ESP Tracer", "ESP Fill"]},
            "OTHER": {"parent": None, "items": ["Bomb ESP", "Glow ESP", "Radar Hack", "No Flash"]},
            "OVERLAY": {"parent": None, "items": ["FOV Circle", "ESP Debug"]},
        },
    },
}


class Tooltip:
    _current = None

    def __init__(self, widget, get_text, delay=350):
        self.widget = widget
        self.get_text = get_text
        self.delay = delay
        self._after_id = None
        self._top = None
        widget.bind("<Enter>", self._on_enter, add="+")
        widget.bind("<Leave>", self._on_leave, add="+")
        widget.bind("<ButtonPress>", self._on_leave, add="+")

    def _on_enter(self, _e=None):
        self._after_id = self.widget.after(self.delay, self._show)

    def _on_leave(self, _e=None):
        if self._after_id:
            self.widget.after_cancel(self._after_id)
            self._after_id = None
        self._hide()

    def _show(self):
        self._hide()
        text = self.get_text()
        if not text:
            return
        x = self.widget.winfo_rootx() + 20
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 5
        self._top = tk.Toplevel(self.widget)
        self._top.wm_overrideredirect(True)
        self._top.wm_attributes("-topmost", True)
        self._top.geometry(f"+{x}+{y}")
        tk.Label(
            self._top, text=text, justify="left", bg="#0f1a10", fg="#e8f5e8",
            font=("Segoe UI", 10), padx=10, pady=6, wraplength=280,
            bd=1, relief="solid",
        ).pack()
        Tooltip._current = self._top

    def _hide(self):
        if self._top:
            try:
                self._top.destroy()
            except Exception:
                pass
            self._top = None
            Tooltip._current = None


class Menu:
    W, H = 740, 780
    START_X, START_Y = 40, 40
    SLIDE_PX = 60

    def __init__(self, master, config, config_manager=None):
        self.root = ctk.CTkToplevel(master)
        self.root.title("ARBUZIAN // CS2")
        self.root.attributes("-topmost", True)
        self.root.configure(fg_color=BG)
        self.root.withdraw()

        self.config = config
        self.cfg_mgr = config_manager
        self.lang = tk.StringVar(value="en")
        self._animating = False
        self._visible = False
        self._current_cat = list(TABS.keys())[0]
        self._children_frames = {}

        self._build()
        self.root.update_idletasks()

        try:
            raw = self.root.winfo_id()
            user32 = ctypes.WinDLL("user32", use_last_error=True)
            user32.GetAncestor.argtypes = [wintypes.HWND, ctypes.c_uint]
            user32.GetAncestor.restype = wintypes.HWND
            hwnd = user32.GetAncestor(wintypes.HWND(raw), 2) or raw
            dwmapi = ctypes.WinDLL("dwmapi", use_last_error=True)
            for attr, value in ((20, 1), (38, 2)):
                try:
                    v = ctypes.c_int(value)
                    dwmapi.DwmSetWindowAttribute(wintypes.HWND(hwnd), ctypes.c_int(attr), ctypes.byref(v), ctypes.sizeof(v))
                except Exception:
                    pass
        except Exception:
            pass

    def _t(self, key):
        d = DESCRIPTIONS.get(key)
        return d.get(self.lang.get(), d.get("en", "")) if d else ""

    def _set_geom(self, y, alpha):
        self.root.geometry(f"{self.W}x{self.H}+{self.START_X}+{int(y)}")
        self.root.attributes("-alpha", max(0.0, min(1.0, alpha)))

    def _animate_in(self):
        if self._animating:
            return
        self._animating = True
        self._set_geom(self.START_Y + self.SLIDE_PX, 0.0)
        self.root.deiconify()
        self._anim_in_tick(0.0)

    def _anim_in_tick(self, t):
        t += 0.08
        if t >= 1.0:
            self._set_geom(self.START_Y, 1.0)
            self._animating = False
            return
        self._set_geom(self.START_Y + self.SLIDE_PX * (1.0 - t), t)
        self.root.after(14, lambda: self._anim_in_tick(t))

    def _animate_out(self):
        if self._animating:
            return
        self._animating = True
        self._anim_out_tick(1.0)

    def _anim_out_tick(self, t):
        t -= 0.10
        if t <= 0.0:
            self.root.attributes("-alpha", 0.0)
            self.root.withdraw()
            self._animating = False
            return
        self._set_geom(self.START_Y + self.SLIDE_PX * (1.0 - t), t)
        self.root.after(12, lambda: self._anim_out_tick(t))

    def _build(self):
        header = ctk.CTkFrame(self.root, fg_color="transparent", height=48)
        header.pack(fill="x", padx=18, pady=(14, 0))
        ctk.CTkLabel(header, text=" ARBUZIAN", font=ctk.CTkFont("Segoe UI Emoji", 20, "bold"), text_color=ACCENT).pack(side="left")
        ctk.CTkLabel(header, text="CS2 // HvH", font=ctk.CTkFont("Segoe UI", 10), text_color=SUBTEXT).pack(side="left", padx=(10, 0))
        ctk.CTkLabel(header, text="INSERT", font=ctk.CTkFont("Segoe UI", 9, "bold"), text_color=SUBTEXT).pack(side="right")

        footer = ctk.CTkFrame(self.root, fg_color="transparent", height=42)
        footer.pack(fill="x", side="bottom", padx=14, pady=(0, 12))

        # --- Кнопка открытия логов ---
        self.logs_btn = ctk.CTkButton(
            footer, text="📄 LOGS", width=70, height=28,
            fg_color=CARD, hover_color=ACCENT_DIM,
            text_color=TEXT, command=self.open_logs
        )
        self.logs_btn.pack(side="left", padx=(0, 8))

        ctk.CTkSegmentedButton(
            footer, values=["EN", "RU"],
            command=lambda v: self.lang.set(v.lower()),
            selected_color=ACCENT_DIM, unselected_color=CARD,
            text_color=TEXT, height=28,
        ).pack(side="right", padx=(8, 0))

        self._config_combo = ctk.CTkOptionMenu(
            footer, values=self._profile_names(), command=self._on_profile_switch,
            fg_color=CARD, button_color=ACCENT_DIM, button_hover_color=ACCENT,
            width=140, height=28,
        )
        self._config_combo.pack(side="right", padx=4)

        ctk.CTkButton(footer, text="💾", width=34, height=28, fg_color=CARD, hover_color=ACCENT_DIM, command=self._on_save).pack(side="right", padx=4)
        ctk.CTkButton(footer, text="+", width=34, height=28, fg_color=CARD, hover_color=ACCENT_DIM, command=self._on_new_profile).pack(side="right", padx=4)

        body = ctk.CTkFrame(self.root, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=14, pady=12)

        sidebar = ctk.CTkFrame(body, fg_color=CARD, width=SIDEBAR_W, corner_radius=10, border_width=1, border_color=BORDER)
        sidebar.pack(side="left", fill="y", padx=(0, 10))
        sidebar.pack_propagate(False)

        self.cat_buttons = {}
        for cat_name, info in TABS.items():
            btn = ctk.CTkButton(
                sidebar, text=f"{info['icon']} {cat_name}",
                font=ctk.CTkFont("Segoe UI", 13, "bold"), anchor="w",
                fg_color="transparent", hover_color=CARD_HOVER, text_color=TEXT,
                height=40, corner_radius=8,
                command=lambda c=cat_name: self._switch_category(c),
            )
            btn.pack(fill="x", padx=8, pady=(8, 2))
            self.cat_buttons[cat_name] = btn

        self.content = ctk.CTkFrame(body, fg_color="transparent")
        self.content.pack(side="left", fill="both", expand=True)

        self.cat_frames = {}
        for cat_name, info in TABS.items():
            scroll = ctk.CTkScrollableFrame(
                self.content, fg_color=CARD, corner_radius=10,
                border_width=1, border_color=BORDER,
                scrollbar_button_color="#1e2e20",
            )
            self._fill_category(scroll, info["sections"])
            self.cat_frames[cat_name] = scroll

        self._switch_category(self._current_cat)
        self.refresh_visibility()

    def _profile_names(self):
        if not self.cfg_mgr:
            return ["default"]
        names = self.cfg_mgr.get_profiles() or ["default"]
        if self.cfg_mgr.current_name not in names:
            names.insert(0, self.cfg_mgr.current_name)
        return names

    def _on_profile_switch(self, name):
        if not self.cfg_mgr:
            return
        self.cfg_mgr.set_profile(name)
        self.cfg_mgr.load()
        self.refresh_visibility()

    def _on_save(self):
        if self.cfg_mgr:
            self.cfg_mgr.save()

    def _on_new_profile(self):
        if not self.cfg_mgr:
            return
        dlg = ctk.CTkInputDialog(text="Profile name:", title="New Config")
        name = dlg.get_input()
        if not name:
            return
        self.cfg_mgr.set_profile(name.strip())
        self.cfg_mgr.save()
        self._config_combo.configure(values=self._profile_names())
        self._config_combo.set(self.cfg_mgr.current_name)

    def open_logs(self):
        log_path = os.path.abspath("logs.txt")
        if not os.path.exists(log_path):
            with open(log_path, "w", encoding="utf-8") as f:
                f.write("[INFO] Логи инициализированы.\n")
        try:
            subprocess.Popen(["notepad.exe", log_path])
        except Exception as e:
            print(f"Не удалось открыть логи: {e}")

    def _switch_category(self, cat_name):
        self._current_cat = cat_name
        for name, frame in self.cat_frames.items():
            if name == cat_name:
                frame.pack(fill="both", expand=True)
            else:
                frame.pack_forget()
        for name, btn in self.cat_buttons.items():
            btn.configure(
                fg_color=ACCENT_DIM if name == cat_name else "transparent",
                text_color=ACCENT if name == cat_name else TEXT,
            )

    def _fill_category(self, parent, sections):
        for section_name, info in sections.items():
            parent_key = info.get("parent")
            items = info.get("items", [])
            if not items:
                continue

            ctk.CTkLabel(
                parent, text=section_name,
                font=ctk.CTkFont("Segoe UI", 10, "bold"),
                text_color=SUBTEXT, anchor="w",
            ).pack(fill="x", padx=14, pady=(14, 6))

            child_container = None
            parent_card = None

            for idx, key in enumerate(items):
                if key not in self.config:
                    continue
                v = self.config[key]
                is_parent_item = (parent_key and key == parent_key)

                target_parent = parent
                if parent_key and not is_parent_item and child_container is not None:
                    target_parent = child_container

                if isinstance(v, tuple) and v[0] == "slider":
                    card = self._slider(target_parent, key, v)
                elif isinstance(v, tuple) and v[0] == "combo":
                    card = self._combo(target_parent, key, v)
                elif hasattr(v, "get"):
                    card = self._switch(target_parent, key, v)
                else:
                    continue

                if is_parent_item:
                    card.pack(fill="x", padx=10, pady=3)
                    parent_card = card
                    child_container = ctk.CTkFrame(parent, fg_color="transparent")
                    self._children_frames[parent_key] = (child_container, parent_card, [])
                    if hasattr(v, "trace_add"):
                        v.trace_add("write", lambda *_: self.refresh_visibility())
                else:
                    card.pack(fill="x", padx=10, pady=3)
                    if parent_key and child_container is not None:
                        self._children_frames[parent_key][2].append(card)

    def _attach_tooltip(self, widget, key):
        if widget is not None:
            Tooltip(widget, lambda k=key: self._t(k))

    def _switch(self, parent, label, var):
        card = ctk.CTkFrame(parent, fg_color="#0c1410", corner_radius=8)
        
        # Желтая пометка для функций, которым лучше работать в Internal
        display_label = label
        if label in ["Silent Aim", "No Flash", "Radar Hack", "Glow ESP", "Bhop", "Spinbot", "Desync", "Aimbot",]:
            display_label = f"⚠️ {label}"

        sw = ctk.CTkSwitch(
            card, text=display_label, variable=var,
            font=ctk.CTkFont("Segoe UI", 12),
            progress_color=ACCENT, button_color="#2a3a2a",
            button_hover_color="#4a5a4a", text_color=TEXT,
        )
        sw.pack(fill="x", padx=12, pady=8)
        self._attach_tooltip(sw, label) # В тултип передаем оригинальное название
        return card

    def _slider(self, parent, label, tup):
        _, var, from_, to = tup
        card = ctk.CTkFrame(parent, fg_color="#0c1410", corner_radius=8)
        top = ctk.CTkFrame(card, fg_color="transparent")
        top.pack(fill="x", padx=12, pady=(8, 0))
        lbl = ctk.CTkLabel(top, text=label, font=ctk.CTkFont("Segoe UI", 11), text_color=TEXT)
        lbl.pack(side="left")
        val_lbl = ctk.CTkLabel(top, text=f"{var.get():.1f}", font=ctk.CTkFont("Segoe UI", 11, "bold"), text_color=ACCENT)
        val_lbl.pack(side="right")

        def on_change(v):
            val_lbl.configure(text=f"{float(v):.1f}")

        sl = ctk.CTkSlider(
            card, from_=from_, to=to, variable=var, command=on_change,
            progress_color=ACCENT, button_color=ACCENT,
            button_hover_color=ACCENT_HOVER, fg_color="#1a2a1a",
        )
        sl.pack(fill="x", padx=12, pady=(4, 10))
        self._attach_tooltip(sl, label)
        self._attach_tooltip(lbl, label)
        return card

    def _combo(self, parent, label, tup):
        _, var, values = tup
        card = ctk.CTkFrame(parent, fg_color="#0c1410", corner_radius=8)
        lbl = ctk.CTkLabel(card, text=label, font=ctk.CTkFont("Segoe UI", 11), text_color=TEXT)
        lbl.pack(anchor="w", padx=12, pady=(8, 0))
        combo = ctk.CTkOptionMenu(
            card, values=values, variable=var,
            fg_color="#1a2a1a", button_color="#2a3a2a",
            button_hover_color=ACCENT, dropdown_fg_color="#0f1a10",
            text_color=TEXT,
        )
        combo.pack(fill="x", padx=12, pady=(4, 10))
        self._attach_tooltip(combo, label)
        self._attach_tooltip(lbl, label)
        return card

    def refresh_visibility(self):
        for parent_key, (container, parent_card, child_cards) in self._children_frames.items():
            if parent_key not in self.config:
                continue
            try:
                is_on = bool(self.config[parent_key].get())
            except Exception:
                is_on = True

            container.pack(fill="x", padx=(30, 10), pady=(0, 5), after=parent_card)
            for card in child_cards:
                self._set_card_enabled(card, is_on)

    def _set_card_enabled(self, card, enabled):
        card.configure(fg_color="#0c1410" if enabled else "#080f08")
        self._set_nested_widgets(card, enabled)

    def _set_nested_widgets(self, parent, enabled):
        for widget in parent.winfo_children():
            if isinstance(widget, ctk.CTkSwitch):
                widget.configure(
                    state="normal" if enabled else "disabled",
                    text_color=TEXT if enabled else SUBTEXT,
                    progress_color=ACCENT if enabled else ACCENT_DIM,
                    button_color="#2a3a2a" if enabled else "#1a241a",
                    button_hover_color="#4a5a4a" if enabled else "#1a241a",
                )
            elif isinstance(widget, ctk.CTkSlider):
                widget.configure(
                    state="normal" if enabled else "disabled",
                    progress_color=ACCENT if enabled else ACCENT_DIM,
                    button_color=ACCENT if enabled else "#365036",
                    button_hover_color=ACCENT_HOVER if enabled else "#365036",
                )
            elif isinstance(widget, ctk.CTkOptionMenu):
                widget.configure(
                    state="normal" if enabled else "disabled",
                    text_color=TEXT if enabled else SUBTEXT,
                    fg_color="#1a2a1a" if enabled else "#152016",
                    button_color="#2a3a2a" if enabled else "#1e2e20",
                    button_hover_color=ACCENT if enabled else "#1e2e20",
                )
            elif isinstance(widget, ctk.CTkLabel):
                if not hasattr(widget, "_enabled_text_color"):
                    widget._enabled_text_color = widget.cget("text_color")
                widget.configure(
                    text_color=widget._enabled_text_color if enabled else SUBTEXT
                )
            if widget.winfo_children():
                self._set_nested_widgets(widget, enabled)

    def show(self):
        if self._visible or self._animating:
            return
        self._visible = True
        self.refresh_visibility()
        self._animate_in()

    def hide(self):
        if not self._visible or self._animating:
            return
        self._visible = False
        self._animate_out()

    def toggle(self):
        if self._visible:
            self.hide()
        else:
            self.show()