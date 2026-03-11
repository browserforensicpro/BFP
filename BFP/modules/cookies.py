"""
cookies.py - Extract browser cookies from Chromium and Firefox.
Handles both old and new Chromium cookie DB schemas (Network/Cookies path fix).
"""

import os
import logging
from utils.forensiccopy import open_readonly_copy, safe_query, table_exists
from utils.timeutils import webkit_to_str, unix_s_to_str, unix_us_to_str

logger = logging.getLogger(__name__)


def extract_chromium(dbs: dict, profile_path: str = "") -> list:
    """
    Extract cookies from Chromium. Tries Network/Cookies first, then Cookies.
    """
    results = []

    # Try multiple cookie DB locations (fix for Profile 2+ no-cookie issue)
    candidates = []
    if dbs.get("Cookies"):
        candidates.append(dbs["Cookies"])
    # Also try direct path
    if profile_path:
        for rel in [os.path.join("Network", "Cookies"), "Cookies"]:
            full = os.path.join(profile_path, rel)
            if os.path.isfile(full) and full not in candidates:
                candidates.append(full)

    db_path = ""
    for c in candidates:
        if os.path.isfile(c):
            db_path = c
            break

    if not db_path:
        logger.info("No Cookies DB found for this profile.")
        return results

    try:
        conn = open_readonly_copy(db_path)

        # Determine schema - newer Chrome uses 'cookies' table
        if table_exists(conn, "cookies"):
            table = "cookies"
        elif table_exists(conn, "meta"):
            table = "cookies"
        else:
            conn.close()
            return results

        # Try new schema first
        try:
            rows = safe_query(conn, f"""
                SELECT host_key, name, path, expires_utc,
                       is_secure, is_httponly, last_access_utc,
                       has_expires, is_persistent, priority,
                       source_scheme, length(encrypted_value)
                FROM {table}
                ORDER BY host_key, name
            """)
            for row in rows:
                results.append({
                    "host_key":      row[0] or "",
                    "name":          row[1] or "",
                    "path":          row[2] or "",
                    "expires":       webkit_to_str(row[3]) if row[3] else "Session",
                    "secure":        "Yes" if row[4] else "No",
                    "httponly":      "Yes" if row[5] else "No",
                    "last_access":   webkit_to_str(row[6]) if row[6] else "N/A",
                    "has_expires":   "Yes" if row[7] else "No",
                    "persistent":    "Yes" if row[8] else "No",
                    "priority":      str(row[9] or ""),
                    "source_scheme": str(row[10] or ""),
                    "encrypted_len": row[11] or 0,
                    "value":         "[ENCRYPTED]",
                })
        except Exception:
            # Fallback: minimal query
            rows = safe_query(conn, f"SELECT host_key, name, path FROM {table}")
            for row in rows:
                results.append({
                    "host_key": row[0] or "",
                    "name":     row[1] or "",
                    "path":     row[2] or "",
                    "expires": "", "secure": "", "httponly": "",
                    "last_access": "", "has_expires": "",
                    "persistent": "", "priority": "",
                    "source_scheme": "", "encrypted_len": 0,
                    "value": "[N/A]",
                })
        conn.close()
    except Exception as e:
        logger.error(f"Chromium cookies error: {e}")
    return results


def extract_firefox(dbs: dict) -> list:
    results = []
    db_path = dbs.get("Cookies", "")
    if not db_path:
        return results
    try:
        conn = open_readonly_copy(db_path)
        if not table_exists(conn, "moz_cookies"):
            conn.close()
            return results

        rows = safe_query(conn, """
            SELECT host, name, path, expiry, isSecure, isHttpOnly,
                   lastAccessed, creationTime, value
            FROM moz_cookies
            ORDER BY host, name
        """)
        for row in rows:
            results.append({
                "host_key":      row[0] or "",
                "name":          row[1] or "",
                "path":          row[2] or "",
                "expires":       unix_s_to_str(row[3]) if row[3] else "Session",
                "secure":        "Yes" if row[4] else "No",
                "httponly":      "Yes" if row[5] else "No",
                "last_access":   unix_us_to_str(row[6]) if row[6] else "N/A",
                "has_expires":   "Yes" if row[3] else "No",
                "persistent":    "Yes" if row[3] else "No",
                "priority":      "",
                "source_scheme": "",
                "encrypted_len": 0,
                "value":         (row[8] or "")[:80],
            })
        conn.close()
    except Exception as e:
        logger.error(f"Firefox cookies error: {e}")
    return results
