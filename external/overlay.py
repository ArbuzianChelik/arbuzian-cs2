import ctypes
import math
from ctypes import wintypes
import tkinter as tk

user32 = ctypes.WinDLL('user32', use_last_error=True)

user32.GetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int]
user32.GetWindowLongW.restype = ctypes.c_long
user32.SetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_long]
user32.SetWindowLongW.restype = ctypes.c_long
user32.SetWindowPos.argtypes = [wintypes.HWND, wintypes.HWND,
                                ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
                                ctypes.c_uint]
user32.SetWindowPos.restype = wintypes.BOOL
user32.GetAncestor.argtypes = [wintypes.HWND, ctypes.c_uint]
user32.GetAncestor.restype = wintypes.HWND
user32.FindWindowW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR]
user32.FindWindowW.restype = wintypes.HWND
user32.SetForegroundWindow.argtypes = [wintypes.HWND]
user32.SetForegroundWindow.restype = wintypes.BOOL

GWL_EXSTYLE = -20
WS_EX_LAYERED = 0x00080000
WS_EX_TRANSPARENT = 0x00000020
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_NOACTIVATE = 0x08000000

SWP_NOSIZE = 0x0001
SWP_NOMOVE = 0x0002
SWP_NOZORDER = 0x0004
SWP_NOACTIVATE = 0x0010
SWP_FRAMECHANGED = 0x0020

GA_ROOT = 2

TRANSPARENT_COLOR = "#010203"


def get_cs2_client_rect():
    try:
        hwnd = user32.FindWindowW(None, "Counter-Strike 2")
        if not hwnd:
            return None
        rect = wintypes.RECT()
        if not user32.GetClientRect(hwnd, ctypes.byref(rect)):
            return None
        pt = wintypes.POINT(0, 0)
        user32.ClientToScreen(hwnd, ctypes.byref(pt))
        return (pt.x, pt.y, rect.right, rect.bottom)
    except Exception:
        return None


class Overlay:
    def __init__(self):
        self.root = tk.Tk()
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        try:
            self.root.attributes("-transparentcolor", TRANSPARENT_COLOR)
        except tk.TclError:
            self.root.attributes("-alpha", 0.85)
        self.root.configure(bg=TRANSPARENT_COLOR)
        self.root.geometry("1920x1080+0+0")

        self.canvas = tk.Canvas(self.root, bg=TRANSPARENT_COLOR,
                                highlightthickness=0, width=1920, height=1080)
        self.canvas.pack(fill="both", expand=True)

        self.root.update_idletasks()

        raw = self.root.winfo_id()
        hwnd = user32.GetAncestor(raw, GA_ROOT)
        if not hwnd:
            hwnd = raw
        self._hwnd = hwnd

        style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
        new_style = (style | WS_EX_LAYERED | WS_EX_TRANSPARENT
                     | WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE)
        user32.SetWindowLongW(hwnd, GWL_EXSTYLE, new_style)

        user32.SetWindowPos(hwnd, 0, 0, 0, 0, 0,
                            SWP_NOMOVE | SWP_NOSIZE | SWP_NOZORDER
                            | SWP_NOACTIVATE | SWP_FRAMECHANGED)

        try:
            game = user32.FindWindowW(None, "Counter-Strike 2")
            if game:
                user32.SetForegroundWindow(game)
        except Exception:
            pass

        self.width = 1920
        self.height = 1080
        self._last_rect = None
        self._callback = None
        self._interval = 16

        # Даём игре время инициализироваться, прежде чем цепляться
        self.root.withdraw()   # ← скрыть пока игра не появится
        self.root.after(2000, self._try_show)

    def _try_show(self):
        from external.overlay import get_cs2_client_rect
        if get_cs2_client_rect():
            self._track_window()
            self.root.deiconify()
        else:
            self.root.after(2000, self._try_show)
            
    def _track_window(self):
        r = get_cs2_client_rect()
        if not r:
            return
        x, y, w, h = r
        if w <= 1 or h <= 1 or self._last_rect == r:
            return
        self._last_rect = r
        self.width, self.height = w, h
        self.canvas.config(width=w, height=h)
        self.root.geometry(f"{w}x{h}+{x}+{y}")

    def clear(self):
        self.canvas.delete("all")

    def box(self, x1, y1, x2, y2, color="#ff4040", thickness=2):
        self.canvas.create_rectangle(x1, y1, x2, y2, outline=color, width=thickness)

    def corner_box(self, x1, y1, x2, y2, color="#ff4040", thickness=2, length_ratio=0.25):
        w, h = x2 - x1, y2 - y1
        lw = max(4, int(min(w, h) * length_ratio))
        for cx, cy, sx, sy in ((x1, y1, 1, 1), (x2, y1, -1, 1),
                               (x1, y2, 1, -1), (x2, y2, -1, -1)):
            self.canvas.create_line(cx, cy, cx + sx * lw, cy, fill=color, width=thickness)
            self.canvas.create_line(cx, cy, cx, cy + sy * lw, fill=color, width=thickness)

    def rect_fill(self, x1, y1, x2, y2, color="#303030"):
        self.canvas.create_rectangle(x1, y1, x2, y2, fill=color, outline="")

    def text(self, x, y, text, color="#ffffff", size=10, anchor="nw", bold=False):
        font = ("Segoe UI", size, "bold" if bold else "normal")
        self.canvas.create_text(x + 1, y + 1, text=text, fill="#000000",
                                anchor=anchor, font=font)
        self.canvas.create_text(x, y, text=text, fill=color, anchor=anchor, font=font)

    def line(self, x1, y1, x2, y2, color="#ffffff", width=1):
        self.canvas.create_line(x1, y1, x2, y2, fill=color, width=width)

    def circle(self, cx, cy, r, color="#ffffff", width=1):
        self.canvas.create_oval(cx - r, cy - r, cx + r, cy + r,
                                outline=color, width=width)

    def health_bar(self, x, y, w, h, health, fg="#30ff30"):
        health = max(0, min(100, health))
        self.canvas.create_rectangle(x - 1, y - 1, x + w + 1, y + h + 1,
                                     fill="#000000", outline="")
        self.canvas.create_rectangle(x, y, x + w, y + h, fill="#202020", outline="")
        filled = int(h * health / 100.0)
        if filled > 0:
            self.canvas.create_rectangle(x, y + h - filled, x + w, y + h,
                                         fill=fg, outline="")

    def radar(self, cx, cy, size, entities, local_pos, scale=4.0):
        """
        Квадратный север-вверх радар как в CS2.
        Враги — красные, союзники — зелёные, ты — ярко-зелёная точка в центре.
        scale: пикселей на метр (4.0 → ±size/4 метров вокруг)
        """
        self.canvas.create_rectangle(
            cx - size, cy - size, cx + size, cy + size,
            fill="#0a1410", outline="#22c55e", width=2,
        )
        for i in (1, 2, 3):
            s = size * i / 4
            self.canvas.create_line(cx - s, cy - size, cx - s, cy + size,
                                     fill="#1a3a20")
            self.canvas.create_line(cx + s, cy - size, cx + s, cy + size,
                                     fill="#1a3a20")
            self.canvas.create_line(cx - size, cy - s, cx + size, cy - s,
                                     fill="#1a3a20")
            self.canvas.create_line(cx - size, cy + s, cx + size, cy + s,
                                     fill="#1a3a20")

        for e in entities:
            rx = (e["pos"][0] - local_pos[0]) * 0.0254
            ry = (e["pos"][1] - local_pos[1]) * 0.0254
            px = cx + rx * scale
            py = cy - ry * scale
            if abs(px - cx) < size - 2 and abs(py - cy) < size - 2:
                color = "#4ade80" if e.get("is_teammate") else "#ff4444"
                self.canvas.create_oval(px - 3, py - 3, px + 3, py + 3,
                                         fill=color, outline="#0a1410")

        # центр = ты
        self.canvas.create_oval(cx - 4, cy - 4, cx + 4, cy + 4,
                                 fill="#22c55e", outline="#0a1410")

    def run(self, callback, interval=16):
        self._callback = callback
        self._interval = interval
        self.root.after(interval, self._tick)
        self.root.mainloop()

    def _tick(self):
        try:
            self._track_window()
            self.clear()
            if self._callback:
                self._callback(self)
        except Exception as e:
            print(f"[!] Overlay tick error: {e}")
        self.root.after(self._interval, self._tick)