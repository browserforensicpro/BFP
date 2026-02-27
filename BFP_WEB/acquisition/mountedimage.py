"""
mountedimage.py - Extract browser data from a mounted forensic image.
Auto-detects user profiles inside the mounted path.
"""

import os
import logging

logger = logging.getLogger(__name__)

# Relative paths to check inside a mounted image for browser data
CHROMIUM_RELATIVE = [
    r"Users\{user}\AppData\Local\Google\Chrome\User Data",
    r"Users\{user}\AppData\Local\Microsoft\Edge\User Data",
    r"Users\{user}\AppData\Local\BraveSoftware\Brave-Browser\User Data",
    r"Users\{user}\AppData\Local\Vivaldi\User Data",
    r"Users\{user}\AppData\Roaming\Opera Software\Opera Stable",
]
FIREFOX_RELATIVE = [
    r"Users\{user}\AppData\Roaming\Mozilla\Firefox\Profiles",
]


def discover_profiles_in_image(mount_path: str) -> list:
    """
    Given the root of a mounted forensic image, discover all browser profiles.
    Returns list of profile dicts compatible with the main tool.
    """
    profiles = []
    users_dir = os.path.join(mount_path, "Users")
    if not os.path.isdir(users_dir):
        # Try Linux-style path
        users_dir = mount_path

    user_names = []
    try:
        for entry in os.scandir(users_dir):
            if entry.is_dir() and entry.name not in (
                "Public", "Default", "Default User", "All Users", "desktop.ini"
            ):
                user_names.append(entry.name)
    except Exception as e:
        logger.warning(f"User scan error: {e}")
        user_names = [""]

    for user in user_names:
        # Chromium
        for rel_template in CHROMIUM_RELATIVE:
            rel = rel_template.replace("{user}", user)
            base = os.path.join(mount_path, rel)
            if not os.path.isdir(base):
                continue
            try:
                for entry in os.scandir(base):
                    if entry.is_dir() and (
                        entry.name == "Default" or entry.name.startswith("Profile ")
                    ):
                        history_db = os.path.join(entry.path, "History")
                        if os.path.isfile(history_db):
                            browser = _detect_browser_from_path(rel)
                            profiles.append({
                                "name":    f"{user} / {entry.name}",
                                "path":    entry.path,
                                "browser": browser,
                                "source":  "Forensic Image",
                                "user":    user,
                            })
            except Exception as e:
                logger.warning(f"Chromium image scan error: {e}")

        # Firefox
        for rel_template in FIREFOX_RELATIVE:
            rel = rel_template.replace("{user}", user)
            base = os.path.join(mount_path, rel)
            if not os.path.isdir(base):
                continue
            try:
                for entry in os.scandir(base):
                    if entry.is_dir():
                        places = os.path.join(entry.path, "places.sqlite")
                        if os.path.isfile(places):
                            profiles.append({
                                "name":    f"{user} / {entry.name}",
                                "path":    entry.path,
                                "browser": "Firefox",
                                "source":  "Forensic Image",
                                "user":    user,
                            })
            except Exception as e:
                logger.warning(f"Firefox image scan error: {e}")

    logger.info(f"Discovered {len(profiles)} profiles in image: {mount_path}")
    return profiles


def _detect_browser_from_path(path: str) -> str:
    path_lower = path.lower()
    if "chrome" in path_lower:  return "Chrome"
    if "edge" in path_lower:    return "Edge"
    if "brave" in path_lower:   return "Brave"
    if "vivaldi" in path_lower: return "Vivaldi"
    if "opera" in path_lower:   return "Opera"
    return "Chromium"
