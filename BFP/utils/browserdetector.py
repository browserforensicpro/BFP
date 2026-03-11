"""
browserdetector.py - Detect installed browsers and enumerate their profiles.
"""

import os
import json
import logging
from config import BROWSER_PATHS

logger = logging.getLogger(__name__)


def detect_browsers() -> dict:
    """
    Returns dict: { browser_name: [profile_paths, ...] }
    Only includes browsers that are actually installed.
    """
    found = {}
    for browser, base_paths in BROWSER_PATHS.items():
        for base in base_paths:
            if not os.path.isdir(base):
                continue
            profiles = _enumerate_profiles(browser, base)
            if profiles:
                found[browser] = profiles
    return found


def _enumerate_profiles(browser: str, base_path: str) -> list:
    """Enumerate profile directories for a given browser base path."""
    profiles = []

    if browser == "Firefox":
        # Firefox: each subfolder in Profiles directory IS a profile
        try:
            for entry in os.scandir(base_path):
                if entry.is_dir():
                    # Check for places.sqlite as indicator
                    places = os.path.join(entry.path, "places.sqlite")
                    if os.path.isfile(places):
                        profiles.append({
                            "name": entry.name,
                            "path": entry.path,
                            "browser": "Firefox",
                        })
        except Exception as e:
            logger.warning(f"Firefox profile scan error: {e}")
    else:
        # Chromium-based: profiles are "Default", "Profile 1", "Profile 2", etc.
        try:
            for entry in os.scandir(base_path):
                if not entry.is_dir():
                    continue
                name = entry.name
                if name in ("Default",) or name.startswith("Profile "):
                    history_db = os.path.join(entry.path, "History")
                    if os.path.isfile(history_db):
                        display_name = _get_profile_display_name(entry.path, name)
                        profiles.append({
                            "name": display_name,
                            "path": entry.path,
                            "browser": browser,
                        })
        except Exception as e:
            logger.warning(f"{browser} profile scan error: {e}")

    return profiles


def _get_profile_display_name(profile_path: str, fallback: str) -> str:
    """Try to read the human-readable profile name from Preferences JSON."""
    pref_file = os.path.join(profile_path, "Preferences")
    try:
        with open(pref_file, "r", encoding="utf-8", errors="ignore") as f:
            data = json.load(f)
        name = data.get("profile", {}).get("name", fallback)
        return f"{name} ({fallback})" if name != fallback else fallback
    except Exception:
        return fallback


def get_db_path(profile: dict, db_name: str) -> str:
    """Return full path to a DB file within a profile, or empty string."""
    path = os.path.join(profile["path"], db_name)
    return path if os.path.isfile(path) else ""


def get_chromium_dbs(profile: dict) -> dict:
    """Return dict of known Chromium DB paths for a profile."""
    p = profile["path"]
    dbs = {}
    candidates = {
        "History":       "History",
        "Cookies":       os.path.join("Network", "Cookies"),
        "Bookmarks":     "Bookmarks",
        "LoginData":     "Login Data",
        "WebData":       "Web Data",
        "Favicons":      "Favicons",
        "Sessions":      "Sessions",
        "TopSites":      "Top Sites",
        "VisitedLinks":  "Visited Links",
        "Preferences":   "Preferences",
        "Extensions":    os.path.join("Extensions"),
        "Cache":         os.path.join("Cache", "Cache_Data"),
        "LocalStorage":  os.path.join("Local Storage", "leveldb"),
        "IndexedDB":     "IndexedDB",
    }
    for key, rel in candidates.items():
        full = os.path.join(p, rel)
        dbs[key] = full if os.path.exists(full) else ""
    dbs["_profile_path"] = p
    return dbs


def get_firefox_dbs(profile: dict) -> dict:
    """Return dict of known Firefox DB paths for a profile."""
    p = profile["path"]
    dbs = {}
    candidates = {
        "History":    "places.sqlite",
        "Cookies":    "cookies.sqlite",
        "Logins":     "logins.json",
        "FormHistory":"formhistory.sqlite",
        "Favicons":   "favicons.sqlite",
        "Sessions":   "sessionstore.jsonlz4",
        "Permissions":"permissions.sqlite",
        "Storage":    "storage",
    }
    for key, rel in candidates.items():
        full = os.path.join(p, rel)
        dbs[key] = full if os.path.exists(full) else ""
    dbs["_profile_path"] = p
    return dbs
