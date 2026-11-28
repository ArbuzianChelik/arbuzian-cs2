import ctypes
import struct
import time
from ctypes import wintypes

kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
ntdll = ctypes.WinDLL('ntdll', use_last_error=True)
psapi = ctypes.WinDLL('psapi', use_last_error=True)
user32 = ctypes.WinDLL('user32', use_last_error=True)

PROCESS_ALL_ACCESS = 0x1F0FFF
TH32CS_SNAPPROCESS = 0x02


class PROCESSENTRY32(ctypes.Structure):
    _fields_ = [
        ("dwSize", wintypes.DWORD), ("cntUsage", wintypes.DWORD),
        ("th32ProcessID", wintypes.DWORD),
        ("th32DefaultHeapID", ctypes.POINTER(ctypes.c_ulong)),
        ("th32ModuleID", wintypes.DWORD), ("cntThreads", wintypes.DWORD),
        ("th32ParentProcessID", wintypes.DWORD),
        ("pcPriClassBase", ctypes.c_long), ("dwFlags", wintypes.DWORD),
        ("szExeFile", ctypes.c_char * 260),
    ]


class MODULEINFO(ctypes.Structure):
    _fields_ = [
        ("lpBaseOfDll", ctypes.c_void_p),
        ("SizeOfImage", wintypes.DWORD),
        ("EntryPoint", ctypes.c_void_p),
    ]


kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
kernel32.OpenProcess.restype = wintypes.HANDLE
kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
kernel32.CloseHandle.restype = wintypes.BOOL
kernel32.CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
kernel32.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
kernel32.Process32First.argtypes = [wintypes.HANDLE, ctypes.POINTER(PROCESSENTRY32)]
kernel32.Process32First.restype = wintypes.BOOL
kernel32.Process32Next.argtypes = [wintypes.HANDLE, ctypes.POINTER(PROCESSENTRY32)]
kernel32.Process32Next.restype = wintypes.BOOL
kernel32.ReadProcessMemory.argtypes = [wintypes.HANDLE, wintypes.LPCVOID, wintypes.LPVOID,
                                        ctypes.c_size_t, ctypes.POINTER(ctypes.c_size_t)]
kernel32.ReadProcessMemory.restype = wintypes.BOOL

psapi.EnumProcessModules.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.HMODULE),
                                     wintypes.DWORD, ctypes.POINTER(wintypes.DWORD)]
psapi.EnumProcessModules.restype = wintypes.BOOL
psapi.GetModuleBaseNameW.argtypes = [wintypes.HANDLE, wintypes.HMODULE,
                                     wintypes.LPWSTR, wintypes.DWORD]
psapi.GetModuleBaseNameW.restype = wintypes.DWORD
psapi.GetModuleInformation.argtypes = [wintypes.HANDLE, wintypes.HMODULE,
                                       ctypes.POINTER(MODULEINFO), wintypes.DWORD]
psapi.GetModuleInformation.restype = wintypes.BOOL

ntdll.NtReadVirtualMemory.argtypes = [wintypes.HANDLE, wintypes.LPCVOID, wintypes.LPVOID,
                                      ctypes.c_size_t, ctypes.POINTER(ctypes.c_size_t)]
ntdll.NtReadVirtualMemory.restype = ctypes.c_long
ntdll.NtWriteVirtualMemory.argtypes = [wintypes.HANDLE, wintypes.LPVOID,
                                       wintypes.LPCVOID, ctypes.c_size_t,
                                       ctypes.POINTER(ctypes.c_size_t)]
ntdll.NtWriteVirtualMemory.restype = ctypes.c_long

user32.GetForegroundWindow.restype = wintypes.HWND
user32.FindWindowW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR]
user32.FindWindowW.restype = wintypes.HWND
user32.GetAncestor.argtypes = [wintypes.HWND, ctypes.c_uint]
user32.GetAncestor.restype = wintypes.HWND

_cs2_hwnd = [0]
_cs2_hwnd_ts = [0.0]


def _get_cs2_hwnd():
    now = time.time()
    if not _cs2_hwnd[0] or now - _cs2_hwnd_ts[0] > 2.0:
        _cs2_hwnd[0] = user32.FindWindowW(None, "Counter-Strike 2")
        _cs2_hwnd_ts[0] = now
    return _cs2_hwnd[0]


def is_game_foreground(window_title="Counter-Strike 2"):
    cs2 = _get_cs2_hwnd()
    if not cs2:
        return False
    fg = user32.GetForegroundWindow()
    if not fg:
        return False
    if fg == cs2:
        return True
    return user32.GetAncestor(fg, 2) == cs2


class Memory:
    def __init__(self, process_name: str):
        self.pid = self._get_pid(process_name)
        self.handle = kernel32.OpenProcess(PROCESS_ALL_ACCESS, False, self.pid)
        if not self.handle:
            raise RuntimeError(f"OpenProcess failed: {ctypes.get_last_error()}")
        self.client_base = self.get_module_base("client.dll")
        self.schemasystem_base = self.get_module_base("schemasystem.dll")
        try:
            self.engine2_base = self.get_module_base("engine2.dll")
        except RuntimeError:
            self.engine2_base = 0

    def _get_pid(self, name: str) -> int:
        snap = kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
        entry = PROCESSENTRY32()
        entry.dwSize = ctypes.sizeof(PROCESSENTRY32)
        if kernel32.Process32First(snap, ctypes.byref(entry)):
            while True:
                if entry.szExeFile.decode().lower() == name.lower():
                    kernel32.CloseHandle(snap)
                    return entry.th32ProcessID
                if not kernel32.Process32Next(snap, ctypes.byref(entry)):
                    break
        kernel32.CloseHandle(snap)
        raise RuntimeError(f"Process {name} not found")

    def get_module_base(self, module_name: str) -> int:
        h_mods = (wintypes.HMODULE * 1024)()
        needed = wintypes.DWORD()
        if not psapi.EnumProcessModules(self.handle, h_mods, ctypes.sizeof(h_mods),
                                        ctypes.byref(needed)):
            raise RuntimeError("EnumProcessModules failed")
        count = needed.value // ctypes.sizeof(wintypes.HMODULE)
        for i in range(count):
            buf = ctypes.create_unicode_buffer(260)
            psapi.GetModuleBaseNameW(self.handle, h_mods[i], buf, 260)
            if buf.value.lower() == module_name.lower():
                return h_mods[i]
        raise RuntimeError(f"Module {module_name} not found")

    def get_module_size(self, base: int) -> int:
        info = MODULEINFO()
        if not psapi.GetModuleInformation(self.handle, base, ctypes.byref(info),
                                          ctypes.sizeof(info)):
            raise RuntimeError("GetModuleInformation failed")
        return info.SizeOfImage

    def read(self, address: int, size: int) -> bytes:
        """Читает память. Лимиты мягкие — чтение само по себе безопасно."""
        if address <= 0 or size <= 0 or size > 0x10000000:  # 256 МБ максимум
            raise OSError(f"Bad read params: addr=0x{address:X} size={size}")
        buf = ctypes.create_string_buffer(size)
        bytes_read = ctypes.c_size_t(0)
        ok = kernel32.ReadProcessMemory(self.handle, ctypes.c_void_p(address),
                                        buf, size, ctypes.byref(bytes_read))
        if ok and bytes_read.value == size:
            return buf.raw
        status = ntdll.NtReadVirtualMemory(self.handle, ctypes.c_void_p(address),
                                           buf, size, ctypes.byref(bytes_read))
        if status == 0 and bytes_read.value == size:
            return buf.raw
        raise OSError(f"Read failed at 0x{address:X}")

    def write(self, address: int, data: bytes) -> bool:
        """Строгая валидация — именно запись вызывает краши при плохом адресе."""
        if address < 0x10000 or not data or len(data) > 0x1000:
            return False
        bytes_written = ctypes.c_size_t(0)
        status = ntdll.NtWriteVirtualMemory(
            self.handle, ctypes.c_void_p(address), data,
            len(data), ctypes.byref(bytes_written),
        )
        return status == 0 and bytes_written.value == len(data)

    def read_bytes(self, a, s): return self.read(a, s)
    def read_int(self, a):   return int.from_bytes(self.read(a, 4), 'little', signed=True)
    def read_uint(self, a):  return int.from_bytes(self.read(a, 4), 'little')
    def read_pointer(self, a): return int.from_bytes(self.read(a, 8), 'little')
    def read_float(self, a): return struct.unpack('<f', self.read(a, 4))[0]

    def read_vec3(self, a):
        return struct.unpack('<fff', self.read(a, 12))

    def read_string(self, a, n=128):
        data = self.read(a, n)
        end = data.find(b'\x00')
        return data[:end].decode('utf-8', errors='ignore') if end != -1 else data.decode('utf-8', errors='ignore')

    def write_float(self, a, v):
        return self.write(a, struct.pack('<f', v))

    def close(self):
        if self.handle:
            kernel32.CloseHandle(self.handle)