"""
downloads.py - Extract browser download history.
"""

import logging
from utils.forensiccopy import open_readonly_copy, safe_query, table_exists
from utils.timeutils import webkit_to_str, unix_us_to_str

logger = logging.getLogger(__name__)


def extract_chromium(dbs: dict) -> list:
    results = []
    db_path = dbs.get("History", "")
    if not db_path:
        return results
    try:
        conn = open_readonly_copy(db_path)
        if not table_exists(conn, "downloads"):
            conn.close()
            return results

        rows = safe_query(conn, """
            SELECT d.target_path, d.total_bytes, d.received_bytes,
                   d.start_time, d.end_time, d.state,
                   d.danger_type, d.interrupt_reason,
                   du.url
            FROM downloads d
            LEFT JOIN downloads_url_chains du ON d.id = du.id
            ORDER BY d.start_time DESC
        """)
        def _fmt_mb(b):
            if not b: return "0 B"
            b = int(b)
            if b < 1024: return f"{b} B"
            if b < 1048576: return f"{b/1024:.1f} KB"
            return f"{b/1048576:.2f} MB"
        for row in rows:
            results.append({
                "target_path":     row[0] or "",
                "total_size":      _fmt_mb(row[1]),
                "received_size":   _fmt_mb(row[2]),
                "start_time":      webkit_to_str(row[3]) if row[3] else "N/A",
                "end_time":        webkit_to_str(row[4]) if row[4] else "N/A",
                "state":           _decode_state(row[5]),
                "danger_type":     _decode_danger(row[6]),
                "interrupt_reason": str(row[7] or ""),
                "url":             row[8] or "",
            })
        conn.close()
    except Exception as e:
        logger.error(f"Chromium downloads error: {e}")
    return results


def extract_firefox(dbs: dict) -> list:
    results = []
    db_path = dbs.get("History", "")
    if not db_path:
        return results
    try:
        conn = open_readonly_copy(db_path)
        # Firefox downloads are in moz_annos
        if not table_exists(conn, "moz_annos"):
            conn.close()
            return results

        rows = safe_query(conn, """
            SELECT p.url, a.content, a.dateAdded
            FROM moz_places p
            JOIN moz_annos a ON p.id = a.place_id
            JOIN moz_anno_attributes at ON a.anno_attribute_id = at.id
            WHERE at.name = 'downloads/destinationFileName'
            ORDER BY a.dateAdded DESC
        """)
        for row in rows:
            results.append({
                "target_path":   row[1] or "",
                "url":           row[0] or "",
                "start_time":    unix_us_to_str(row[2]) if row[2] else "N/A",
                "total_size":    "N/A",
                "received_size": "N/A",
                "state":         "Complete",
                "danger_type":   "",
                "interrupt_reason": "",
                "end_time":      "N/A",
            })
        conn.close()
    except Exception as e:
        logger.error(f"Firefox downloads error: {e}")
    return results


def _decode_state(val) -> str:
    STATES = {0: "In Progress", 1: "Complete", 2: "Cancelled",
               3: "Interrupted", 4: "Async Pending"}
    try:
        return STATES.get(int(val), str(val))
    except Exception:
        return str(val or "")


def _decode_danger(val) -> str:
    DANGERS = {0: "Safe", 1: "Dangerous", 2: "Antivirus", 3: "Dangerous Host",
               4: "Uncommon", 5: "User Validated", 6: "Dangerous URL",
               7: "Dangerous Content", 8: "Maybe Dangerous", 9: "Allowlisted"}
    try:
        return DANGERS.get(int(val), str(val))
    except Exception:
        return str(val or "Safe")
