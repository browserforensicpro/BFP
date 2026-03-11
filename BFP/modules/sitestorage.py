"""
sitestorage.py - Extract Local Storage, IndexedDB info from browser profiles.
"""

import os
import logging
from utils.forensiccopy import open_readonly_copy, safe_query, table_exists

logger = logging.getLogger(__name__)


def extract_chromium(dbs: dict) -> list:
    """List Local Storage and IndexedDB origins/keys."""
    results = []
    ls_dir = dbs.get("LocalStorage", "")
    idb_dir = dbs.get("IndexedDB", "")

    # Local Storage - LevelDB files (list origins)
    if ls_dir and os.path.isdir(ls_dir):
        try:
            for f in os.listdir(ls_dir):
                fpath = os.path.join(ls_dir, f)
                if os.path.isfile(fpath):
                    size = os.path.getsize(fpath)
                    results.append({
                        "type":   "Local Storage",
                        "origin": f,
                        "key":    "",
                        "value":  f"[Binary LevelDB]",
                        "size":   _fmt_size(size),
                    })
        except Exception as e:
            logger.warning(f"LocalStorage list error: {e}")

    # IndexedDB - list database directories
    if idb_dir and os.path.isdir(idb_dir):
        try:
            for entry in os.scandir(idb_dir):
                if entry.is_dir():
                    size = _dir_size(entry.path)
                    results.append({
                        "type":   "IndexedDB",
                        "origin": entry.name,
                        "key":    "",
                        "value":  f"[IndexedDB dir]",
                        "size":   _fmt_size(size),
                    })
        except Exception as e:
            logger.warning(f"IndexedDB list error: {e}")

    return results


def extract_firefox(dbs: dict) -> list:
    results = []
    storage_dir = dbs.get("Storage", "")
    if not storage_dir or not os.path.isdir(storage_dir):
        return results
    try:
        for root, dirs, files in os.walk(storage_dir):
            for fname in files:
                if fname.endswith(".sqlite"):
                    fpath = os.path.join(root, fname)
                    size = os.path.getsize(fpath)
                    origin = os.path.basename(os.path.dirname(fpath))
                    results.append({
                        "type":   "Local Storage",
                        "origin": origin,
                        "key":    fname,
                        "value":  f"[SQLite]",
                        "size":   _fmt_size(size),
                    })
    except Exception as e:
        logger.error(f"Firefox site storage error: {e}")
    return results


def _fmt_size(b: int) -> str:
    if b < 1024: return f"{b} B"
    if b < 1048576: return f"{b/1024:.1f} KB"
    if b < 1073741824: return f"{b/1048576:.2f} MB"
    return f"{b/1073741824:.2f} GB"


def _dir_size(path: str) -> int:
    total = 0
    try:
        for root, dirs, files in os.walk(path):
            for f in files:
                try:
                    total += os.path.getsize(os.path.join(root, f))
                except Exception:
                    pass
    except Exception:
        pass
    return total
