import os
import sys
import subprocess
import tkinter as tk
import customtkinter as ctk
import psutil
import time

ctk.set_appearance_mode("dark")

ACCENT = "#22c55e"
ACCENT_DIM = "#166534"
ACCENT_HOVER = "#4ade80"
BG = "#080f08"
CARD = "#0f1a10"
BORDER = "#1e2e20"
TEXT = "#e8f5e8"
SUBTEXT = "#7a8f7a"

def center_window(window, width, height):
    x = (window.winfo_screenwidth() // 2) - (width // 2)
    y = (window.winfo_screenheight() // 2) - (height // 2)
    window.geometry(f"{width}x{height}+{x}+{y}")

class Loader:
    def __init__(self):
        self.root = ctk.CTk()
        self.root.title("Arbuzian Loader")
        self.root.configure(fg_color=BG)
        self.root.resizable(False, False)
        center_window(self.root, 480, 420)

        self.proc_ext = None
        self.proc_int = None

        self._build()
        self.root.mainloop()

    def _build(self):
        ctk.CTkLabel(self.root, text="🍉 ARBUZIAN",
                     font=ctk.CTkFont("Segoe UI Emoji", 32, "bold"),
                     text_color=ACCENT).pack(pady=(30, 2))
        ctk.CTkLabel(self.root, text="CS2 Cheat Loader",
                     font=ctk.CTkFont("Segoe UI", 13),
                     text_color=SUBTEXT).pack(pady=(0, 20))

        card = ctk.CTkFrame(self.root, fg_color=CARD, corner_radius=12,
                            border_width=1, border_color=BORDER)
        card.pack(fill="x", padx=40, pady=8)

        # --- External ---
        self.btn_ext = ctk.CTkButton(
            card, text="🚀 Launch External", font=ctk.CTkFont("Segoe UI", 15, "bold"),
            fg_color=ACCENT_DIM, hover_color=ACCENT, height=50, corner_radius=8,
            command=self.launch_ext
        )
        self.btn_ext.pack(fill="x", padx=16, pady=(16, 10))

        # --- Internal ---
        self.btn_int = ctk.CTkButton(
            card, text="🔧 Inject Internal (C++)", font=ctk.CTkFont("Segoe UI", 15, "bold"),
            fg_color="#1a1a1a", hover_color="#2a2a2a", text_color=SUBTEXT,
            height=50, corner_radius=8, command=self.launch_int
        )
        self.btn_int.pack(fill="x", padx=16, pady=(0, 10))

        # --- Kill Switch ---
        self.btn_kill = ctk.CTkButton(
            card, text="⛔ Stop / Unload All", font=ctk.CTkFont("Segoe UI", 14, "bold"),
            fg_color="#4a1515", hover_color="#7a2020", text_color="#ff8888",
            height=40, corner_radius=8, command=self.kill_all
        )
        self.btn_kill.pack(fill="x", padx=16, pady=(5, 16))

        self.status_lbl = ctk.CTkLabel(self.root, text="Ready", text_color=SUBTEXT)
        self.status_lbl.pack(side="bottom", pady=10)

        # Автообновление статуса процессов
        self.update_status()

    def launch_ext(self):
        if self.proc_ext and self.proc_ext.poll() is None:
            return
        try:
            self.proc_ext = subprocess.Popen(
                [sys.executable, "main.py"], cwd="external",
                creationflags=subprocess.CREATE_NO_WINDOW
            )
        except Exception as e:
            self.status_lbl.configure(text=f"Error: {e}", text_color="red")

    def launch_int(self):
        # Проверяем, запущен ли инжектор
        if self.proc_int and self.proc_int.poll() is None:
            return
        path = os.path.join("internal", "injector.py")
        if not os.path.exists(path):
            self.status_lbl.configure(text="Internal not compiled yet!", text_color="orange")
            return
        try:
            self.proc_int = subprocess.Popen(
                [sys.executable, "injector.py"], cwd="internal",
                creationflags=subprocess.CREATE_NO_WINDOW
            )
        except Exception as e:
            self.status_lbl.configure(text=f"Error: {e}", text_color="red")

    def kill_all(self):
        # 1. Убиваем экстернал
        if self.proc_ext and self.proc_ext.poll() is None:
            self.proc_ext.terminate()
            self.proc_ext = None

        # 2. Убиваем инжектор
        if self.proc_int and self.proc_int.poll() is None:
            self.proc_int.terminate()
            self.proc_int = None

        # 3. Выгружаем DLL из CS2 (ищем по имени процесса)
        for proc in psutil.process_iter(['name']):
            if proc.info['name'] == 'cs2.exe':
                try:
                    # Отправляем сигнал выгрузки через нажатие END (как в экстернале)
                    # Или принудительно убиваем CS2, если это тест
                    pass
                except Exception:
                    pass

        self.status_lbl.configure(text="All processes stopped", text_color=ACCENT)

    def update_status(self):
        ext_alive = self.proc_ext and self.proc_ext.poll() is None
        int_alive = self.proc_int and self.proc_int.poll() is None

        if ext_alive and int_alive:
            self.status_lbl.configure(text="● External + Internal Running", text_color=ACCENT)
        elif ext_alive:
            self.status_lbl.configure(text="● External Running", text_color=ACCENT)
        elif int_alive:
            self.status_lbl.configure(text="● Internal Injected", text_color=ACCENT)
        else:
            self.status_lbl.configure(text="Ready", text_color=SUBTEXT)

        self.root.after(1000, self.update_status)

if __name__ == "__main__":
    Loader()