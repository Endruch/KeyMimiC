"""Thread-safe storage of named Script profiles for one thread panel."""

import json
import threading

from ..config.paths import PROFILES_DIR
from ..model import Script


class ProfileManager:
    """
    Manages Script profiles for one thread panel (persisted as
    `thread_<id>_profiles.json`, a dict of profile name -> script dict).

    Saving only ever happens when explicitly requested (add/rename/delete/
    update), never implicitly on profile switch - the old app used to
    silently rewrite the file on every switch, which could clobber data.
    """

    def __init__(self, thread_id):
        self.thread_id = thread_id
        self.profile_file = PROFILES_DIR / f"thread_{thread_id}_profiles.json"
        self._lock = threading.Lock()
        self._raw = self._load()

    def _load(self) -> dict:
        if self.profile_file.exists():
            try:
                with open(self.profile_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if data:
                    return data
            except Exception:
                pass
        return {"Profile 1": Script.empty("Profile 1").to_dict()}

    def _save(self):
        try:
            PROFILES_DIR.mkdir(parents=True, exist_ok=True)
            with open(self.profile_file, "w", encoding="utf-8") as f:
                json.dump(self._raw, f, ensure_ascii=False, indent=2)
        except Exception as exc:
            print(f"Error saving profiles for thread {self.thread_id}: {exc}")

    def get_profile_names(self):
        with self._lock:
            return list(self._raw.keys())

    def get_profile(self, name: str) -> Script:
        with self._lock:
            raw = self._raw.get(name)
        if raw is None:
            return Script.empty(name)
        return Script.from_dict(raw)

    def add_profile(self, name: str, script: Script):
        with self._lock:
            self._raw[name] = script.to_dict()
            self._save()

    def update_profile(self, name: str, script: Script):
        with self._lock:
            self._raw[name] = script.to_dict()
            self._save()

    def rename_profile(self, old_name: str, new_name: str) -> bool:
        with self._lock:
            if old_name not in self._raw or new_name in self._raw:
                return False
            self._raw[new_name] = self._raw.pop(old_name)
            self._save()
            return True

    def delete_profile(self, name: str) -> bool:
        with self._lock:
            if name not in self._raw or len(self._raw) <= 1:
                return False
            del self._raw[name]
            self._save()
            return True
