"""
Thread-safe profile management for storing and loading macros.
"""

import json
import threading
from pathlib import Path


# Profile storage directory
PROFILES_DIR = Path.home() / "Documents" / "KeyMimic" / "profiles"


class ProfileManager:
    """
    Manages macro profiles for a thread with thread-safety.

    Uses threading.Lock to prevent race conditions during file operations.
    """

    def __init__(self, thread_id):
        """
        Initialize profile manager for a thread.

        Args:
            thread_id: Thread identifier (1-4)
        """
        self.thread_id = thread_id
        self.profile_file = PROFILES_DIR / f"thread_{thread_id}_profiles.json"
        self._lock = threading.Lock()
        self.profiles = self._load()

    def _ensure_dir(self):
        """Ensure profiles directory exists."""
        try:
            PROFILES_DIR.mkdir(parents=True, exist_ok=True)
        except Exception:
            pass

    def _load(self):
        """
        Load profiles from JSON file.

        Returns:
            Dict mapping profile name to macro content
        """
        if self.profile_file.exists():
            try:
                with open(self.profile_file, 'r', encoding='utf-8') as f:
                    profiles = json.load(f)
                    # Ensure at least one profile exists
                    if not profiles:
                        return {"Profile 1": "# Empty macro\n"}
                    return profiles
            except Exception:
                pass

        return {"Profile 1": "# Empty macro\n"}

    def _save(self):
        """
        Save profiles to JSON file (internal, assumes lock is held).
        """
        self._ensure_dir()
        try:
            with open(self.profile_file, 'w', encoding='utf-8') as f:
                json.dump(self.profiles, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Error saving profiles: {e}")

    def save(self):
        """Save profiles to JSON file (thread-safe)."""
        with self._lock:
            self._save()

    def add_profile(self, name, content):
        """
        Add a new profile (thread-safe).

        Args:
            name: Profile name
            content: Macro content
        """
        with self._lock:
            self.profiles[name] = content
            self._save()

    def rename_profile(self, old_name, new_name):
        """
        Rename a profile (thread-safe).

        Args:
            old_name: Current profile name
            new_name: New profile name

        Returns:
            True if successful, False otherwise
        """
        with self._lock:
            if old_name in self.profiles:
                self.profiles[new_name] = self.profiles.pop(old_name)
                self._save()
                return True
            return False

    def delete_profile(self, name):
        """
        Delete a profile (thread-safe).

        Args:
            name: Profile name to delete

        Returns:
            True if successful, False otherwise
        """
        with self._lock:
            # Ensure at least one profile remains
            if name in self.profiles and len(self.profiles) > 1:
                del self.profiles[name]
                self._save()
                return True
            return False

    def get_profile(self, name):
        """
        Get profile content (thread-safe).

        Args:
            name: Profile name

        Returns:
            Profile content string, or empty string if not found
        """
        with self._lock:
            return self.profiles.get(name, "")

    def update_profile(self, name, content):
        """
        Update profile content (thread-safe).

        Args:
            name: Profile name
            content: New macro content
        """
        with self._lock:
            self.profiles[name] = content
            self._save()

    def get_profile_names(self):
        """
        Get list of all profile names (thread-safe).

        Returns:
            List of profile names
        """
        with self._lock:
            return list(self.profiles.keys())
