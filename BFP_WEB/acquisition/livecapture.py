"""
livecapture.py - Legal live browser data acquisition tool.
Manually executed only. No stealth or hidden collection.
Creates a forensic package ZIP of all browser artifacts.
"""

import os
import shutil
import zipfile
import logging
import datetime
import tempfile

from utils.browserdetector import detect_browsers, get_chromium_dbs, get_firefox_dbs
from utils.forensiccopy import forensic_copy

logger = logging.getLogger(__name__)


def capture_live_profile(profile: dict, output_dir: str,
                          progress_callback=None) -> dict:
    """
    Capture all artifacts from a live browser profile.
    Returns dict with captured files list and metadata.
    """
    os.makedirs(output_dir, exist_ok=True)
    captured = []
    errors = []
    browser = profile.get("browser", "")

    if browser == "Firefox":
        dbs = get_firefox_dbs(profile)
    else:
        dbs = get_chromium_dbs(profile)

    total = len([v for v in dbs.values() if v and os.path.exists(v)])
    done = 0

    for db_key, db_path in dbs.items():
        if not db_path or not os.path.exists(db_path):
            continue
        try:
            if os.path.isfile(db_path):
                dest = forensic_copy(db_path, output_dir)
                captured.append({"key": db_key, "source": db_path, "dest": dest})
            elif os.path.isdir(db_path):
                # Copy directory
                dest_dir = os.path.join(output_dir, db_key)
                if os.path.exists(dest_dir):
                    shutil.rmtree(dest_dir)
                shutil.copytree(db_path, dest_dir)
                captured.append({"key": db_key, "source": db_path, "dest": dest_dir})
        except Exception as e:
            errors.append({"key": db_key, "error": str(e)})
            logger.warning(f"Capture error for {db_key}: {e}")
        done += 1
        if progress_callback:
            progress_callback(done, total, db_key)

    return {"captured": captured, "errors": errors, "profile": profile}


def create_capture_package(profiles: list, output_zip: str,
                            progress_callback=None) -> bool:
    """
    Create a complete forensic capture package ZIP from selected profiles.
    """
    try:
        tmp_dir = tempfile.mkdtemp(prefix="bfp_capture_")
        manifest = {
            "tool": "Browser Forensics Pro",
            "capture_time": datetime.datetime.now().isoformat(),
            "profiles": [],
        }

        for i, profile in enumerate(profiles):
            profile_dir = os.path.join(tmp_dir, f"profile_{i}_{profile['name'].replace(' ', '_')}")
            os.makedirs(profile_dir, exist_ok=True)
            result = capture_live_profile(profile, profile_dir, progress_callback)
            manifest["profiles"].append({
                "name":     profile["name"],
                "browser":  profile["browser"],
                "path":     profile["path"],
                "captured": len(result["captured"]),
                "errors":   len(result["errors"]),
            })

        # Write manifest
        import json
        manifest_path = os.path.join(tmp_dir, "manifest.json")
        with open(manifest_path, "w") as f:
            json.dump(manifest, f, indent=2)

        # Create ZIP
        with zipfile.ZipFile(output_zip, "w", zipfile.ZIP_DEFLATED) as zf:
            for root, dirs, files in os.walk(tmp_dir):
                for fname in files:
                    fpath = os.path.join(root, fname)
                    arcname = os.path.relpath(fpath, tmp_dir)
                    zf.write(fpath, arcname)

        shutil.rmtree(tmp_dir, ignore_errors=True)
        logger.info(f"Capture package created: {output_zip}")
        return True
    except Exception as e:
        logger.error(f"Capture package error: {e}")
        return False


def load_capture_package(zip_path: str, extract_dir: str) -> dict:
    """
    Load a previously created capture package ZIP.
    Returns dict with extracted profile paths and manifest.
    """
    try:
        os.makedirs(extract_dir, exist_ok=True)
        with zipfile.ZipFile(zip_path, "r") as zf:
            zf.extractall(extract_dir)

        import json
        manifest_path = os.path.join(extract_dir, "manifest.json")
        if os.path.isfile(manifest_path):
            with open(manifest_path, "r") as f:
                manifest = json.load(f)
        else:
            manifest = {"profiles": []}

        # Build profile list from extracted dirs
        profiles = []
        for entry in os.scandir(extract_dir):
            if entry.is_dir() and entry.name.startswith("profile_"):
                profiles.append({
                    "name": entry.name,
                    "path": entry.path,
                    "browser": "Unknown",
                    "source": "Capture Package",
                })

        return {"manifest": manifest, "profiles": profiles, "extract_dir": extract_dir}
    except Exception as e:
        logger.error(f"Load capture package error: {e}")
        return {"manifest": {}, "profiles": [], "extract_dir": extract_dir}
