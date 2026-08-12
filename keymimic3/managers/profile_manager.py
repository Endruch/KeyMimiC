"""
Stores Script profiles as individual JSON files, one file per profile,
directly under `PROFILES_DIR` (`Documents/KeyMimic v3/profiles/`) - rather
than one shared file holding every profile as a dict. This means Delete in
the app really deletes a real file (not just an entry out of a shared
blob), and moving a profile to another machine is just copying its one
file into the same folder there.

Each file's content is `{"name": <display name>, "script": <Script.to_dict()>}`.
The filename is a sanitized version of the name (for a readable
Explorer/Finder listing), but `"name"` inside the file is always the
source of truth - sanitization can collide or strip characters, and a file
copied in from another machine or renamed by hand should still show up
under its real name.

Saving only ever happens when explicitly requested (add/rename/delete/
update), never implicitly on profile switch - the old app used to silently
rewrite the file on every switch, which could clobber data.
"""

import json
import re
import threading
from pathlib import Path

from ..config.paths import PROFILES_DIR
from ..model import Script

_INVALID_FILENAME_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def _sanitize_filename(name: str) -> str:
    """Turn a profile name into a filesystem-safe filename stem (Windows-legal)."""
    cleaned = _INVALID_FILENAME_CHARS.sub("_", name).strip(" .")
    return cleaned or "profile"


class ProfileManager:
    def __init__(self, thread_id):
        self.thread_id = thread_id
        self.profiles_dir = PROFILES_DIR
        self._lock = threading.Lock()
        with self._lock:
            self.profiles_dir.mkdir(parents=True, exist_ok=True)
            self._migrate_old_shared_file_locked()
            if not self._all_files_locked():
                self._write(self._path_for("Profile 1"), "Profile 1", Script.empty("Profile 1"))

    # -- one-time migration from the old single-shared-file format ----------

    def _migrate_old_shared_file_locked(self):
        """
        Older versions stored every profile for this panel in one file,
        `thread_<id>_profiles.json` (a dict of name -> script dict). If that
        file is still here and nothing has been migrated yet, split it into
        individual profile files so existing recordings aren't silently
        dropped by the format change, then delete it - no leftover backup
        file for the user to have to identify and clean up by hand later.
        """
        old_file = self.profiles_dir / f"thread_{self.thread_id}_profiles.json"
        if not old_file.exists() or self._all_files_locked():
            return
        try:
            raw = json.loads(old_file.read_text(encoding="utf-8"))
            for name, script_dict in raw.items():
                self._write(self._path_for(name), name, Script.from_dict(script_dict))
            old_file.unlink()
        except Exception as exc:
            print(f"Error migrating old profile file '{old_file}': {exc}")

    # -- filesystem helpers ---------------------------------------------------

    def _path_for(self, name: str) -> Path:
        """A filename for `name` that doesn't collide with an already-taken
        sanitized name (append _2, _3, ... as needed)."""
        stem = _sanitize_filename(name)
        candidate = self.profiles_dir / f"{stem}.json"
        n = 2
        while candidate.exists():
            candidate = self.profiles_dir / f"{stem}_{n}.json"
            n += 1
        return candidate

    def _write(self, path: Path, name: str, script: Script):
        try:
            path.write_text(
                json.dumps({"name": name, "script": script.to_dict()}, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception as exc:
            print(f"Error saving profile '{name}': {exc}")

    def _read(self, path: Path) -> dict:
        """Parsed {"name":.., "script":..} content, or None if `path` isn't
        a valid profile file (malformed JSON, a stray unrelated file, an
        un-migrated old-format file, etc.) - such files are silently
        ignored rather than crashing or polluting the profile list."""
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, dict) and "name" in data and "script" in data:
                return data
        except Exception:
            pass
        return None

    def _all_files_locked(self):
        """(path, parsed_content) for every valid profile file, oldest first."""
        files = sorted(self.profiles_dir.glob("*.json"), key=lambda p: p.stat().st_mtime)
        result = []
        for f in files:
            data = self._read(f)
            if data is not None:
                result.append((f, data))
        return result

    def _find_locked(self, name: str):
        for path, data in self._all_files_locked():
            if data["name"] == name:
                return path, data
        return None, None

    # -- public interface (unchanged from the old shared-file version) ------

    def get_profile_names(self):
        with self._lock:
            names = [data["name"] for _, data in self._all_files_locked()]
        return names or ["Profile 1"]

    def get_profile(self, name: str) -> Script:
        with self._lock:
            _, data = self._find_locked(name)
        if data is None:
            return Script.empty(name)
        try:
            return Script.from_dict(data["script"])
        except (AttributeError, TypeError, KeyError) as exc:
            # A malformed or foreign-format entry shouldn't crash the whole
            # app on startup - fall back to an empty script and keep going.
            print(f"Error loading profile '{name}' for thread {self.thread_id}: {exc}")
            return Script.empty(name)

    def add_profile(self, name: str, script: Script):
        with self._lock:
            self._write(self._path_for(name), name, script)

    def update_profile(self, name: str, script: Script):
        with self._lock:
            path, _ = self._find_locked(name)
            self._write(path or self._path_for(name), name, script)

    def rename_profile(self, old_name: str, new_name: str) -> bool:
        with self._lock:
            old_path, data = self._find_locked(old_name)
            if old_path is None or self._find_locked(new_name)[0] is not None:
                return False
            script = Script.from_dict(data["script"])
            new_path = self._path_for(new_name)
            self._write(new_path, new_name, script)
            if new_path != old_path:
                old_path.unlink(missing_ok=True)
            return True

    def delete_profile(self, name: str) -> bool:
        with self._lock:
            files = self._all_files_locked()
            if len(files) <= 1:
                return False
            path, data = self._find_locked(name)
            if path is None:
                return False
            path.unlink(missing_ok=True)
            return True
