import tkinter as tk
import win32gui
import win32con
import time

class Overlay:
    def __init__(self, config_mgr=None):
        self.config_mgr = config_mgr
        self.running = True
        self._hwnd = 0
        self._game_hwnd = 0
        self._last_topmost = 0.0
        self._visible = False

        self.root = tk.Tk()
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.configure(bg="black")
        
        # Скрываем окно при старте, чтобы не было черного экрана
        self.root.withdraw()

        self.width = self.root.winfo_screenwidth()
        self.height = self.root.winfo_screenheight()
        self.root.geometry(f"{self.width}x{self.height}+0+0")

        self.canvas = tk.Canvas(self.root, bg="black", highlightthickness=0, bd=0)
        self.canvas.pack(fill="both", expand=True)

        self.root.update_idletasks()
        try:
            self.root.attributes("-transparentcolor", "black")
        except Exception:
            pass

        try:
            hwnd = win32gui.GetParent(self.canvas.winfo_id())
            self._hwnd = hwnd
            ex = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
            # Клик-сквозь и скрытие из панели задач
            ex = ex | win32con.WS_EX_TRANSPARENT | win32con.WS_EX_TOOLWINDOW
            win32gui.SetWindowLong(hwnd, win32con.GWL_EXSTYLE, ex)
        except Exception as e:
            print(f"[Overlay] hwnd setup: {e}")

        self.root.after(200, self._track_window)

    def _track_window(self):
        try:
            found = [None]
            def cb(hwnd, _):
                if win32gui.IsWindowVisible(hwnd):
                    if "Counter-Strike 2" in win32gui.GetWindowText(hwnd):
                        _, _, r, b = win32gui.GetClientRect(hwnd)
                        if r > 100 and b > 100:
                            found[0] = (hwnd, r, b)
                            return False
                return True

            try:
                win32gui.EnumWindows(cb, None)
            except Exception:
                pass

            if found[0]:
                hwnd, w, h = found[0]
                self._game_hwnd = hwnd
                if not self._visible:
                    self.root.deiconify()
                    self._visible = True
                if w != self.width or h != self.height:
                    self.width, self.height = w, h
                    self.root.geometry(f"{w}x{h}+0+0")
            else:
                if self._visible:
                    self.root.withdraw()
                    self._visible = False
        except Exception:
            pass

        now = time.time()
        if now - self._last_topmost > 0.8 and self._hwnd and self._visible:
            self._last_topmost = now
            try:
                win32gui.SetWindowPos(self._hwnd, win32con.HWND_TOPMOST, 0, 0, 0, 0,
                                      win32con.SWP_NOMOVE | win32con.SWP_NOSIZE | win32con.SWP_NOACTIVATE)
            except Exception:
                pass

        try:
            self.root.after(200, self._track_window)
        except Exception:
            pass

    def clear(self):
        self.canvas.delete("all")

    def box(self, x1, y1, x2, y2, color="#ff4040", thickness=2):
        self.canvas.create_rectangle(x1, y1, x2, y2, outline=color, width=thickness)

    def corner_box(self, x1, y1, x2, y2, color="#ff4040", thickness=2, length_ratio=0.25):
        w, h = x2 - x1, y2 - y1
        lw = max(4, int(min(w, h) * length_ratio))
        for cx, cy, sx, sy in ((x1, y1, 1, 1), (x2, y1, -1, 1),
                               (x1, y2, 1, -1), (x2, y2, -1, -1)):
            self.line(cx, cy, cx + sx * lw, cy, color, thickness)
            self.line(cx, cy, cx, cy + sy * lw, color, thickness)

    def rect_fill(self, x1, y1, x2, y2, color="#303030"):
        self.canvas.create_rectangle(x1, y1, x2, y2, fill=color, outline="")

    def text(self, x, y, text, color="#ffffff", size=10, anchor="nw", bold=False):
        font = ("Segoe UI", size, "bold" if bold else "normal")
        self.canvas.create_text(x, y, text=text, fill=color, anchor=anchor, font=font)

    def line(self, x1, y1, x2, y2, color="#ffffff", width=1):
        self.canvas.create_line(x1, y1, x2, y2, fill=color, width=width)

    def circle(self, cx, cy, r, color="#ffffff", width=1):
        self.canvas.create_oval(cx - r, cy - r, cx + r, cy + r, outline=color, width=width)

    def health_bar(self, x, y, w, h, health, fg="#30ff30"):
        health = max(0, min(100, health))
        self.canvas.create_rectangle(x - 1, y - 1, x + w + 1, y + h + 1, fill="#000000", outline="")
        self.canvas.create_rectangle(x, y, x + w, y + h, fill="#202020", outline="")
        filled = int(h * health / 100.0)
        if filled > 0:
            self.canvas.create_rectangle(x, y + h - filled, x + w, y + h, fill=fg, outline="")

    def start(self):
        try:
            self.root.mainloop()
        except KeyboardInterrupt:
            pass

    def stop(self):
        self.running = False
        try:
            self.root.quit()
        except Exception:
            pass