import ctypes
from ctypes import wintypes
import customtkinter as ctk

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

SIDEBAR_W = 130

TABS = {
    "Aimbot": {
        "icon": "🎯",
        "sections": {
            "SILENT AIM": ["Silent Aim", "360 Aim", "Silent FOV", "Silent Hold (ms)", "Silent Visibility"],
            "SMOOTH AIM": ["Aimbot", "Aimbot Key", "Aimbot Hitbox", "Aimbot FOV",
                           "Aimbot Smooth", "Aimbot Humanize", "Aimbot Priority",
                           "Aimbot Visibility"],
            "RECOIL": ["RCS Strength", "RCS Start Bullet", "Recoil Control", "RCS Smoothing"],
            "TRIGGER": ["Triggerbot", "Trigger Delay (ms)"],
        },
        
    },
    "Anti-Aim": {
        "icon": "💥",
        "sections": {
            "SPINBOT": ["Spinbot", "Spinbot Hotkey", "Spinbot Speed",
                        "Spinbot Mode", "Jitter Range"],
            "DESYNC": ["Desync", "Desync Side"],
        },
    },
    "Movement": {
        "icon": "🦘",
        "sections": {
            "BHOP": ["Bhop", "Bhop Hitchance", "Bhop Delay (ms)"],
            "STRAFE": ["Auto Strafe", "Auto Strafe Strength"],
        },
    },
    "Visuals": {
        "icon": "👁",
        "sections": {
            "PLAYER ESP": ["ESP Box", "ESP Corner Box", "ESP Skeleton", "ESP Health",
                           "ESP Name", "ESP Distance", "ESP Weapon", "ESP Tracer", "ESP Fill"],
            "OTHER ESP": ["Bomb ESP", "Radar Hack", "No Flash"],
            "OVERLAY": ["FOV Circle", "ESP Debug"],
            "PLAYER GLOW": ["ESP Glow"],
        },
    },
}


def _try_mica(hwnd, dark=True):
    try:
        dwmapi = ctypes.WinDLL("dwmapi", use_last_error=True)
        def _set(attr, value):
            try:
                v = ctypes.c_int(value)
                dwmapi.DwmSetWindowAttribute(
                    wintypes.HWND(hwnd), ctypes.c_int(attr),
                    ctypes.byref(v), ctypes.sizeof(v))
            except Exception:
                pass
        _set(20, 1 if dark else 0)
        _set(38, 2)
    except Exception:
        pass


class Menu:
    W, H = 720, 760
    START_X, START_Y = 40, 40
    SLIDE_PX = 60

    def __init__(self, master, config, on_save=None, on_load=None):
        self.root = ctk.CTkToplevel(master)
        self.root.title("ARBUZIAN // CS2")
        self.root.attributes("-topmost", True)
        self.root.configure(fg_color=BG)
        self.root.withdraw()

        self.config = config
        self.on_save = on_save
        self.on_load = on_load
        self._animating = False
        self._visible = False           # ← НОВОЕ: единственный источник правды
        self._current_cat = list(TABS.keys())[0]

        self._build()
        self.root.update_idletasks()
        try:
            raw = self.root.winfo_id()
            user32 = ctypes.WinDLL("user32", use_last_error=True)
            user32.GetAncestor.argtypes = [wintypes.HWND, ctypes.c_uint]
            user32.GetAncestor.restype = wintypes.HWND
            hwnd = user32.GetAncestor(wintypes.HWND(raw), 2) or raw
            _try_mica(hwnd, dark=True)
        except Exception:
            pass

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
        ctk.CTkLabel(header, text="🍉 ARBUZIAN",
                     font=ctk.CTkFont("Segoe UI Emoji", 20, "bold"),
                     text_color=ACCENT).pack(side="left")
        ctk.CTkLabel(header, text="CS2 // HvH",
                     font=ctk.CTkFont("Segoe UI", 10),
                     text_color=SUBTEXT).pack(side="left", padx=(10, 0))
        ctk.CTkLabel(header, text="INSERT",
                     font=ctk.CTkFont("Segoe UI", 9, "bold"),
                     text_color=SUBTEXT).pack(side="right")

        # Footer с кнопками конфига
        footer = ctk.CTkFrame(self.root, fg_color="transparent", height=42)
        footer.pack(fill="x", side="bottom", padx=14, pady=(0, 12))
        ctk.CTkButton(footer, text="💾 Save", command=self._safe_save,
                      fg_color=CARD, hover_color=ACCENT_DIM, text_color=ACCENT,
                      width=120, height=32,
                      font=ctk.CTkFont("Segoe UI", 12, "bold")
                      ).pack(side="left", padx=(0, 8))
        ctk.CTkButton(footer, text="📂 Load", command=self._safe_load,
                      fg_color=CARD, hover_color=ACCENT_DIM, text_color=ACCENT,
                      width=120, height=32,
                      font=ctk.CTkFont("Segoe UI", 12, "bold")
                      ).pack(side="left")

        body = ctk.CTkFrame(self.root, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=14, pady=12)

        sidebar = ctk.CTkFrame(body, fg_color=CARD, width=SIDEBAR_W,
                                corner_radius=10, border_width=1,
                                border_color=BORDER)
        sidebar.pack(side="left", fill="y", padx=(0, 10))
        sidebar.pack_propagate(False)

        self.cat_buttons = {}
        for cat_name, info in TABS.items():
            btn = ctk.CTkButton(
                sidebar, text=f"{info['icon']}   {cat_name}",
                font=ctk.CTkFont("Segoe UI", 13, "bold"),
                anchor="w", fg_color="transparent",
                hover_color=CARD_HOVER, text_color=TEXT,
                height=40, corner_radius=8,
                command=lambda c=cat_name: self._switch_category(c))
            btn.pack(fill="x", padx=8, pady=(8, 2))
            self.cat_buttons[cat_name] = btn

        self.content = ctk.CTkFrame(body, fg_color="transparent")
        self.content.pack(side="left", fill="both", expand=True)

        self.cat_frames = {}
        for cat_name, info in TABS.items():
            scroll = ctk.CTkScrollableFrame(
                self.content, fg_color=CARD, corner_radius=10,
                border_width=1, border_color=BORDER,
                scrollbar_button_color="#1e2e20")
            self._fill_category(scroll, info["sections"])
            self.cat_frames[cat_name] = scroll

        self._switch_category(self._current_cat)

    def _switch_category(self, cat_name):
        self._current_cat = cat_name
        for name, frame in self.cat_frames.items():
            if name == cat_name:
                frame.pack(fill="both", expand=True)
            else:
                frame.pack_forget()
        for name, btn in self.cat_buttons.items():
            btn.configure(fg_color=ACCENT_DIM if name == cat_name else "transparent",
                          text_color=ACCENT if name == cat_name else TEXT)

    def _fill_category(self, parent, sections):
        for section_name, keys in sections.items():
            if not keys:
                continue
            ctk.CTkLabel(parent, text=section_name,
                         font=ctk.CTkFont("Segoe UI", 10, "bold"),
                         text_color=SUBTEXT, anchor="w",
                         ).pack(fill="x", padx=14, pady=(14, 6))
            for key in keys:
                if key not in self.config:
                    continue
                v = self.config[key]
                if isinstance(v, tuple) and v[0] == "slider":
                    self._slider(parent, key, v)
                elif isinstance(v, tuple) and v[0] == "combo":
                    self._combo(parent, key, v)
                elif hasattr(v, "get"):
                    self._switch(parent, key, v)

    def _switch(self, parent, label, var):
        card = ctk.CTkFrame(parent, fg_color="#0c1410", corner_radius=8)
        card.pack(fill="x", padx=10, pady=3)
        ctk.CTkSwitch(card, text=label, variable=var,
                      font=ctk.CTkFont("Segoe UI", 12),
                      progress_color=ACCENT, button_color="#2a3a2a",
                      button_hover_color="#4a5a4a", text_color=TEXT,
                      ).pack(fill="x", padx=12, pady=8)

    def _slider(self, parent, label, tup):
        _, var, from_, to = tup
        card = ctk.CTkFrame(parent, fg_color="#0c1410", corner_radius=8)
        card.pack(fill="x", padx=10, pady=3)
        top = ctk.CTkFrame(card, fg_color="transparent")
        top.pack(fill="x", padx=12, pady=(8, 0))
        ctk.CTkLabel(top, text=label, font=ctk.CTkFont("Segoe UI", 11),
                     text_color=TEXT).pack(side="left")
        val_lbl = ctk.CTkLabel(top, text=f"{var.get():.1f}",
                               font=ctk.CTkFont("Segoe UI", 11, "bold"),
                               text_color=ACCENT)
        val_lbl.pack(side="right")
        state = {"shown": float(var.get()), "target": float(var.get())}

        def animate():
            s, t = state["shown"], state["target"]
            if abs(s - t) < 0.05:
                state["shown"] = t
                val_lbl.configure(text=f"{t:.1f}")
                return
            state["shown"] = s + (t - s) * 0.25
            val_lbl.configure(text=f"{state['shown']:.1f}")
            val_lbl.after(16, animate)

        def on_change(v):
            state["target"] = float(v)
            val_lbl.after(1, animate)

        ctk.CTkSlider(card, from_=from_, to=to, variable=var, command=on_change,
                      progress_color=ACCENT, button_color=ACCENT,
                      button_hover_color=ACCENT_HOVER, fg_color="#1a2a1a",
                      ).pack(fill="x", padx=12, pady=(4, 10))

    def _combo(self, parent, label, tup):
        _, var, values = tup
        card = ctk.CTkFrame(parent, fg_color="#0c1410", corner_radius=8)
        card.pack(fill="x", padx=10, pady=3)
        ctk.CTkLabel(card, text=label, font=ctk.CTkFont("Segoe UI", 11),
                     text_color=TEXT).pack(anchor="w", padx=12, pady=(8, 0))
        ctk.CTkOptionMenu(card, values=values, variable=var,
                          fg_color="#1a2a1a", button_color="#2a3a2a",
                          button_hover_color=ACCENT, dropdown_fg_color="#0f1a10",
                          text_color=TEXT,
                          ).pack(fill="x", padx=12, pady=(4, 10))

    def _safe_save(self):
        if self.on_save:
            self.on_save()

    def _safe_load(self):
        if self.on_load:
            self.on_load()

    def show(self):
        if self._visible or self._animating:
            return
        self._visible = True
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