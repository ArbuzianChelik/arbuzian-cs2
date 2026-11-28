import json
import os
import tkinter as tk

class ConfigManager:
    def __init__(self, config_dict, folder="configs", default_name="default"):
        self.config = config_dict
        self.folder = folder
        self.default_name = default_name
        self.current_name = default_name
        self._last_snapshot = {}

        if not os.path.exists(self.folder):
            os.makedirs(self.folder)

        # Восстанавливаем последний активный профиль
        last_profile_path = os.path.join(self.folder, "last_profile.txt")
        if os.path.exists(last_profile_path):
            try:
                with open(last_profile_path, "r", encoding="utf-8") as f:
                    last_name = f.read().strip()
                if last_name and os.path.exists(os.path.join(self.folder, f"{last_name}.json")):
                    self.current_name = last_name
            except Exception:
                pass

    def _var_to_value(self, var):
        """Конвертирует tk.Variable в обычное значение."""
        if isinstance(var, tk.BooleanVar):
            return var.get()
        if isinstance(var, tk.DoubleVar):
            return var.get()
        if isinstance(var, tk.IntVar):
            return var.get()
        if isinstance(var, tk.StringVar):
            return var.get()
        return var

    def _value_to_var(self, key, value):
        """Конвертирует значение обратно в tk.Variable (сохраняя тип)."""
        old = self.config.get(key)
        if isinstance(old, tuple):
            # ("slider", var, from, to) или ("combo", var, values)
            _, var, *rest = old
            var.set(value)
            return (old[0], var, *rest)
        elif isinstance(old, tk.BooleanVar):
            old.set(value)
            return old
        elif isinstance(old, (tk.DoubleVar, tk.IntVar, tk.StringVar)):
            old.set(value)
            return old
        # Если ключа не было — создаём BooleanVar по умолчанию
        return tk.BooleanVar(value=bool(value))

    def load(self):
        path = os.path.join(self.folder, f"{self.current_name}.json")
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                for key, val in data.items():
                    if key in self.config:
                        self.config[key] = self._value_to_var(key, val)
                self._snapshot()
                print(f"[Config] Loaded profile: {self.current_name}")
                return
            except Exception as e:
                print(f"[Config] Load error: {e}")
        # Если файла нет — создаём дефолтный
        self.save()

    def _snapshot(self):
        snap = {}
        for key, var in self.config.items():
            if isinstance(var, tuple):
                snap[key] = self._var_to_value(var[1])
            else:
                snap[key] = self._var_to_value(var)
        self._last_snapshot = snap
        return snap

    def save(self):
        path = os.path.join(self.folder, f"{self.current_name}.json")
        try:
            data = self._snapshot()
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4)
            print(f"[Config] Saved profile: {self.current_name}")
        except Exception as e:
            print(f"[Config] Save error: {e}")

    def set_profile(self, name):
        # Сохраняем текущий перед переключением
        self.save()
        self.current_name = name
        self.load()
        # Запоминаем имя профиля
        try:
            last_profile_path = os.path.join(self.folder, "last_profile.txt")
            with open(last_profile_path, "w", encoding="utf-8") as f:
                f.write(name)
        except Exception:
            pass

    def get_profiles(self):
        profiles = []
        if os.path.exists(self.folder):
            for f in os.listdir(self.folder):
                if f.endswith(".json"):
                    profiles.append(f[:-5])
        if self.default_name not in profiles:
            profiles.append(self.default_name)
        return sorted(profiles)

    def autosave(self, interval=2.0):
        snap = self._snapshot()
        if snap != self._last_snapshot:
            self.save()
            self._last_snapshot = snap