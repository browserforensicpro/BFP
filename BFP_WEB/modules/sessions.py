"""
sessions.py - Extract and parse session data from browsers.
Chromium: Scans Sessions/ folder + reads SNSS header for tab/window info.
Firefox: Reads sessionstore.jsonlz4 with LZ4 decompression.
"""

import os
import json
import struct
import logging
from utils.timeutils import webkit_to_str, unix_s_to_str, unix_ms_to_str

logger = logging.getLogger(__name__)

# SNSS magic bytes for Chromium session files
SNSS_MAGIC = b"SNSS"


def extract_chromium(dbs: dict) -> list:
    """Extract session data from Chrome Sessions/ folder."""
    results = []
    profile_path = dbs.get("_profile_path", "")

    # dbs["Sessions"] is the Sessions directory path
    sessions_dir = dbs.get("Sessions", "")

    search_dirs = []
    if sessions_dir and os.path.isdir(sessions_dir):
        search_dirs.append(sessions_dir)
    if profile_path:
        s = os.path.join(profile_path, "Sessions")
        if os.path.isdir(s) and s not in search_dirs:
            search_dirs.append(s)
        # Also check directly in profile root
        search_dirs.append(profile_path)

    session_file_names = [
        "Current Session", "Current Tabs",
        "Last Session", "Last Tabs",
        "Tabs",
    ]

    found_files = set()
    for d in search_dirs:
        if not os.path.isdir(d):
            continue
        for name in session_file_names:
            fp = os.path.join(d, name)
            if os.path.isfile(fp) and fp not in found_files:
                found_files.add(fp)
        # Also scan for any SNSS file
        try:
            for f in os.listdir(d):
                fp = os.path.join(d, f)
                if os.path.isfile(fp) and fp not in found_files:
                    try:
                        with open(fp, "rb") as fh:
                            magic = fh.read(4)
                        if magic == SNSS_MAGIC:
                            found_files.add(fp)
                    except Exception:
                        pass
        except Exception:
            pass

    for sf in found_files:
        try:
            size = os.path.getsize(sf)
            mtime = os.path.getmtime(sf)
            tabs_count, windows_count = _parse_snss_header(sf)
            results.append({
                "file":           os.path.basename(sf),
                "full_path":      sf,
                "size":           _fmt_size(size),
                "modified":       unix_s_to_str(int(mtime)),
                "format":         "SNSS (Binary)",
                "windows":        windows_count,
                "tabs":           tabs_count,
                "note":           "Chrome session binary — tabs/windows parsed from header",
            })
        except Exception as e:
            logger.warning(f"Session file error {sf}: {e}")

    logger.info(f"Sessions found: {len(results)}")
    return results


def _parse_snss_header(path: str):
    """Parse SNSS file to count windows and tabs (best-effort)."""
    tabs_count = 0
    windows_count = 0
    try:
        with open(path, "rb") as f:
            magic = f.read(4)
            if magic != SNSS_MAGIC:
                return 0, 0
            version = struct.unpack("<I", f.read(4))[0]
            # Scan for command type bytes that indicate tabs (type 1) and windows (type 0)
            data = f.read(65536)  # Read first 64KB for quick scan
            # Command size is little-endian 2 bytes, then 1 byte type, then 1 byte id
            i = 0
            while i < len(data) - 4:
                try:
                    cmd_size = struct.unpack_from("<H", data, i)[0]
                    if cmd_size < 2 or cmd_size > 4096:
                        i += 1
                        continue
                    cmd_type = data[i + 2]
                    if cmd_type == 1:
                        windows_count += 1
                    elif cmd_type == 2:
                        tabs_count += 1
                    i += cmd_size + 2
                except Exception:
                    i += 1
    except Exception:
        pass
    return tabs_count, windows_count


def _fmt_size(b) -> str:
    if not b or b == "": return ""
    try:
        b = int(b)
        if b < 1024: return f"{b} B"
        if b < 1048576: return f"{b/1024:.1f} KB"
        if b < 1073741824: return f"{b/1048576:.2f} MB"
        return f"{b/1073741824:.2f} GB"
    except Exception:
        return str(b)


def extract_firefox(dbs: dict) -> list:
    results = []
    profile_path = dbs.get("_profile_path", "")
    session_path = dbs.get("Sessions", "")

    # Check multiple possible session file locations
    candidates = []
    if session_path and os.path.isfile(session_path):
        candidates.append(session_path)
    if profile_path:
        for name in ["sessionstore.jsonlz4", "sessionstore-backups",
                     "recovery.jsonlz4", "previous.jsonlz4"]:
            fp = os.path.join(profile_path, name)
            if os.path.isfile(fp):
                candidates.append(fp)
        backup_dir = os.path.join(profile_path, "sessionstore-backups")
        if os.path.isdir(backup_dir):
            for f in os.listdir(backup_dir):
                candidates.append(os.path.join(backup_dir, f))

    for sf in candidates:
        try:
            size = os.path.getsize(sf)
            mtime = os.path.getmtime(sf)
            tabs, windows, urls = _parse_firefox_session(sf)
            entry = {
                "file":       os.path.basename(sf),
                "full_path":  sf,
                "size":       _fmt_size(size),
                "modified":   unix_s_to_str(int(mtime)),
                "format":     "LZ4 JSON",
                "windows":    windows,
                "tabs":       tabs,
                "note":       f"Firefox session — {len(urls)} URLs recovered",
            }
            results.append(entry)
            # Add individual tab URLs as sub-records
            for url_info in urls[:200]:
                results.append({
                    "file":       f"  └ TAB",
                    "full_path":  url_info.get("url", ""),
                    "size":       "",
                    "modified":   url_info.get("title", ""),
                    "format":     "Tab Entry",
                    "windows":    url_info.get("index", ""),
                    "tabs":       "",
                    "note":       url_info.get("url", ""),
                })
        except Exception as e:
            logger.warning(f"Firefox session error {sf}: {e}")

    return results


def _parse_firefox_session(path: str):
    """Parse Firefox .jsonlz4 session file. Returns (tabs_count, windows_count, url_list)."""
    tabs_count = 0
    windows_count = 0
    urls = []
    try:
        with open(path, "rb") as f:
            header = f.read(8)
            data = f.read()

        # Try LZ4 decompression
        try:
            import lz4.block
            json_bytes = lz4.block.decompress(data, uncompressed_size=len(data) * 10)
        except Exception:
            # Try without lz4: some Firefox files are plain JSON
            json_bytes = data
            if header != b"mozLz40\x00":
                json_bytes = header + data

        session = json.loads(json_bytes.decode("utf-8", errors="ignore"))
        windows = session.get("windows", [])
        windows_count = len(windows)
        for win in windows:
            for tab in win.get("tabs", []):
                tabs_count += 1
                entries = tab.get("entries", [])
                idx = tab.get("index", 1)
                if entries:
                    entry_idx = min(idx - 1, len(entries) - 1)
                    entry = entries[entry_idx] if entry_idx >= 0 else entries[-1]
                    urls.append({
                        "url":   entry.get("url", ""),
                        "title": entry.get("title", ""),
                        "index": f"Win {windows.index(win)+1}",
                    })
    except Exception as e:
        logger.debug(f"Session parse error: {e}")
    return tabs_count, windows_count, urls
