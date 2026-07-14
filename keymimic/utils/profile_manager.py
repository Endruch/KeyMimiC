"""
Profile management for storing and loading macros.
"""

import os
import json


PROFILES_DIR = os.path.join(os.path.expanduser("~"), "Documents", "KeyMimic", "profiles")


def ensure_profiles_dir():
    """Ensure profiles directory exists."""
    try:
        os.makedirs(PROFILES_DIR, exist_ok=True)
    except Exception:
        pass


class ProfileManager:
    """Manages macro profiles for a thread."""

    def __init__(self, thread_id):
        self.thread_id = thread_id
        self.profile_file = os.path.join(PROFILES_DIR, f"thread_{thread_id}_profiles.json")
        self.profiles = self.load_profiles()

    def load_profiles(self):
        """Load profiles from JSON file."""
        if os.path.exists(self.profile_file):
            try:
                with open(self.profile_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception:
                pass
        return {"Profile 1": "# Empty macro\n"}

    def save_profiles(self):
        """Save profiles to JSON file."""
        ensure_profiles_dir()
        try:
            with open(self.profile_file, 'w', encoding='utf-8') as f:
                json.dump(self.profiles, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Error saving profiles: {e}")

    def add_profile(self, name, content):
        """Add a new profile."""
        self.profiles[name] = content
        self.save_profiles()

    def rename_profile(self, old_name, new_name):
        """Rename a profile."""
        if old_name in self.profiles:
            self.profiles[new_name] = self.profiles.pop(old_name)
            self.save_profiles()
            return True
        return False

    def delete_profile(self, name):
        """Delete a profile."""
        if name in self.profiles and len(self.profiles) > 1:
            del self.profiles[name]
            self.save_profiles()
            return True
        return False

    def get_profile(self, name):
        """Get profile content."""
        return self.profiles.get(name, "")

    def update_profile(self, name, content):
        """Update profile content."""
        self.profiles[name] = content
        self.save_profiles()
