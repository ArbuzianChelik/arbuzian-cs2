import json
import os
import time


class ConfigManager:
    def __init__(self, config, folder="configs", name="default"):
        self.config = config
        self.folder = folder
        self.path = os.path.join(folder, name + ".json")
        os.makedirs(folder, exist_ok=True)
        self._last_save = 0.0
        self._last_snapshot = None

    def _snapshot(self):
        data = {}
        for key, v in self.config.items():
            if isinstance(v, tuple):
                if v[0] in ("slider", "combo"):
                    try:
                        data[key] = v[1].get()
                    except Exception:
                        pass
            elif hasattr(v, "get"):
                try:
                    data[key] = v.get()
                except Exception:
                    pass
        return data

    def load(self):
        if not os.path.exists(self.path):
            print(f"[Config] '{self.path}' not found, using defaults")
            return False
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            print(f"[Config] load failed: {e}")
            return False

        count = 0
        for key, value in data.items():
            if key not in self.config:
                continue
            v = self.config[key]
            try:
                if isinstance(v, tuple):
                    if v[0] == "slider":
                        v[1].set(float(value))
                    elif v[0] == "combo":
                        v[1].set(str(value))
                elif hasattr(v, "set"):
                    v.set(value)
                count += 1
            except Exception:
                pass
        print(f"[Config] loaded {count} keys from {self.path}")
        return True

    def save(self):
        data = self._snapshot()
        try:
            tmp = self.path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            os.replace(tmp, self.path)
            print(f"[Config] saved {len(data)} keys to {self.path}")
            return True
        except Exception as e:
            print(f"[Config] save failed: {e}")
            return False

    def autosave(self, interval=1.5):
        now = time.time()
        if now - self._last_save < interval:
            return
        data = self._snapshot()
        snapshot = json.dumps(data, sort_keys=True)
        if snapshot == self._last_snapshot:
            return
        self._last_snapshot = snapshot
        self._last_save = now
        self.save()