"""
sitesettings.py - Extract site-specific permissions and settings.
"""

import logging
from utils.forensiccopy import open_readonly_copy, safe_query, table_exists
from utils.timeutils import webkit_to_str

logger = logging.getLogger(__name__)


def extract_chromium(dbs: dict) -> list:
    results = []
    db_path = dbs.get("History", "")  # permissions in Preferences JSON
    # Content settings are in Preferences JSON
    prefs_path = dbs.get("Preferences", "")
    if prefs_path:
        import json, os
        try:
            with open(prefs_path, "r", encoding="utf-8", errors="ignore") as f:
                prefs = json.load(f)
            content_settings = prefs.get("profile", {}).get("content_settings", {})
            exceptions = content_settings.get("exceptions", {})
            for perm_type, sites in exceptions.items():
                if isinstance(sites, dict):
                    for site, setting in sites.items():
                        results.append({
                            "permission": perm_type,
                            "site":       site,
                            "setting":    str(setting.get("setting", setting)) if isinstance(setting, dict) else str(setting),
                            "last_modified": webkit_to_str(
                                setting.get("last_modified", 0)) if isinstance(setting, dict) else "N/A",
                        })
        except Exception as e:
            logger.warning(f"Site settings error: {e}")
    return results


def extract_firefox(dbs: dict) -> list:
    results = []
    db_path = dbs.get("Permissions", "")
    if not db_path:
        return results
    try:
        conn = open_readonly_copy(db_path)
        if table_exists(conn, "moz_perms"):
            rows = safe_query(conn, """
                SELECT origin, type, permission, expireType, expireTime, modificationTime
                FROM moz_perms
                ORDER BY modificationTime DESC
            """)
            for row in rows:
                results.append({
                    "permission":    row[1] or "",
                    "site":          row[0] or "",
                    "setting":       str(row[2] or ""),
                    "last_modified": str(row[5] or ""),
                })
        conn.close()
    except Exception as e:
        logger.error(f"Firefox site settings error: {e}")
    return results
