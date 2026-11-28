import json
import os
import glob
import time

class ConfigManager:
    def __init__(self, config, folder="configs", default_name="default"):
        self.config = config
        self.folder = folder
        os.makedirs(folder, exist_ok=True)
        self.current_name = default_name
        self._last_save = 0.0
        self._last_snapshot = None

    @property
    def path(self):
        return os.path.join(self.folder, f"{self.current_name}.json")

    def list_profiles(self):
        files = glob.glob(os.path.join(self.folder, "*.json"))
        return sorted(os.path.splitext(os.path.basename(f))[0] for f in files)

    def set_profile(self, name):
        self.current_name = name
        self._last_snapshot = None

    def _snapshot(self):
        data = {}
        for key, v in self.config.items():
            if isinstance(v, tuple) and v[0] in ("slider", "combo"):
                try: data[key] = v[1].get()
                except: pass
            elif hasattr(v, "get"):
                try: data[key] = v.get()
                except: pass
        return data

    def load(self):
        if not os.path.exists(self.path):
            print(f"[Config] {self.path} not found")
            return False
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            print(f"[Config] load failed: {e}")
            return False

        count = 0
        for key, value in data.items():
            if key not in self.config: continue
            v = self.config[key]
            try:
                if isinstance(v, tuple):
                    if v[0] == "slider": v[1].set(float(value))
                    elif v[0] == "combo": v[1].set(str(value))
                elif hasattr(v, "set"):
                    v.set(value)
                count += 1
            except: pass

        # ВАЖНО: обновляем снапшот, чтобы автосохранение не перезаписало только что загруженный конфиг
        self._last_snapshot = json.dumps(self._snapshot(), sort_keys=True)
        print(f"[Config] '{self.current_name}': loaded {count} keys")
        return True

    def save(self):
        data = self._snapshot()
        try:
            tmp = self.path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            os.replace(tmp, self.path)
            self._last_snapshot = json.dumps(data, sort_keys=True)
            print(f"[Config] '{self.current_name}': saved {len(data)} keys")
            return True
        except Exception as e:
            print(f"[Config] save failed: {e}")
            return False

    def autosave(self, interval=1.5):
        now = time.time()
        if now - self._last_save < interval: return
        data = self._snapshot()
        snap = json.dumps(data, sort_keys=True)
        if snap == self._last_snapshot: return
        self._last_save = now
        self.save()