"""
history.py - Extract browser history from Chromium and Firefox databases.

Design:
  - Display table: ONE row per unique URL (deduplicated), with aggregated visit_count.
  - Timeline: Each unique visit timestamp is stored in _visit_timestamps list on the URL row.
  - The timeline module iterates _visit_timestamps to build the hourly/daily charts.
"""

import logging
from utils.forensiccopy import open_readonly_copy, safe_query, table_exists
from utils.timeutils import webkit_to_str, unix_us_to_str, webkit_to_datetime

logger = logging.getLogger(__name__)


def extract_chromium(dbs: dict) -> list:
    """
    Extract Chromium history — ONE row per unique URL.
    Individual visit timestamps stored in _visit_timestamps for timeline use.
    """
    results = []
    db_path = dbs.get("History", "")
    if not db_path:
        return results
    try:
        conn = open_readonly_copy(db_path)
        if not table_exists(conn, "urls"):
            conn.close()
            return results

        # ── Step 1: URL summary table — one row per URL ──────────────────
        url_rows = safe_query(conn, """
            SELECT u.id, u.url, u.title, u.visit_count,
                   u.last_visit_time, u.typed_count, u.hidden
            FROM urls u
            ORDER BY u.last_visit_time DESC
        """)

        # Index by url id for fast lookup
        url_map = {}
        for row in url_rows:
            url_map[row[0]] = {
                "url":              row[1] or "",
                "title":            row[2] or "",
                "visit_count":      row[3] or 0,
                "last_visit":       webkit_to_str(row[4]) if row[4] else "N/A",
                "_last_visit_raw":   row[4] or 0,
                "typed_count":      row[5] or 0,
                "hidden":           "Yes" if row[6] else "No",
                "visit_time":       webkit_to_str(row[4]) if row[4] else "N/A",
                "_visit_time_raw":   row[4] or 0,   # timeline uses last_visit as fallback
                "_visit_timestamps": [],            # filled in step 2
            }

        # ── Step 2: Individual visit timestamps — for timeline only ───────
        if url_map:
            visit_rows = safe_query(conn, """
                SELECT url, visit_time, transition
                FROM visits
                ORDER BY visit_time DESC
            """)
            for vrow in visit_rows:
                uid = vrow[0]
                if uid in url_map:
                    url_map[uid]["_visit_timestamps"].append(vrow[1] or 0)

            # Set visit_time_raw to the most recent visit timestamp (for timeline)
            for uid, rec in url_map.items():
                if rec["_visit_timestamps"]:
                    latest = max(rec["_visit_timestamps"])
                    rec["_visit_time_raw"] = latest
                    rec["visit_time"] = webkit_to_str(latest)

        conn.close()
        results = list(url_map.values())
        # Sort by last_visit_raw descending
        results.sort(key=lambda x: x["_last_visit_raw"], reverse=True)

    except Exception as e:
        logger.error(f"Chromium history error: {e}", exc_info=True)
    return results


def extract_firefox(dbs: dict) -> list:
    """
    Extract Firefox history — ONE row per unique URL.
    """
    results = []
    db_path = dbs.get("History", "")
    if not db_path:
        return results
    try:
        conn = open_readonly_copy(db_path)
        if not table_exists(conn, "moz_places"):
            conn.close()
            return results

        # ── Step 1: URL summary — one row per unique URL ──────────────────
        url_rows = safe_query(conn, """
            SELECT p.id, p.url, p.title, p.visit_count,
                   p.last_visit_date, p.typed, p.hidden
            FROM moz_places p
            WHERE p.url IS NOT NULL
            ORDER BY p.last_visit_date DESC
        """)

        url_map = {}
        for row in url_rows:
            url_map[row[0]] = {
                "url":              row[1] or "",
                "title":            row[2] or "",
                "visit_count":      row[3] or 0,
                "last_visit":       unix_us_to_str(row[4]) if row[4] else "N/A",
                "_last_visit_raw":   row[4] or 0,
                "typed_count":      row[5] or 0,
                "hidden":           "Yes" if row[6] else "No",
                "visit_time":       unix_us_to_str(row[4]) if row[4] else "N/A",
                "_visit_time_raw":   row[4] or 0,
                "_visit_timestamps": [],
            }

        # ── Step 2: Individual visit timestamps ────────────────────────────
        if url_map:
            visit_rows = safe_query(conn, """
                SELECT place_id, visit_date, visit_type
                FROM moz_historyvisits
                ORDER BY visit_date DESC
            """)
            for vrow in visit_rows:
                pid = vrow[0]
                if pid in url_map:
                    url_map[pid]["_visit_timestamps"].append(vrow[1] or 0)

            for pid, rec in url_map.items():
                if rec["_visit_timestamps"]:
                    latest = max(rec["_visit_timestamps"])
                    rec["_visit_time_raw"] = latest
                    rec["visit_time"] = unix_us_to_str(latest)

        conn.close()
        results = list(url_map.values())
        results.sort(key=lambda x: x["_last_visit_raw"], reverse=True)

    except Exception as e:
        logger.error(f"Firefox history error: {e}", exc_info=True)
    return results


def _decode_transition(val) -> str:
    """Decode Chromium page transition type."""
    if val is None:
        return ""
    TYPES = {
        0: "LINK", 1: "TYPED", 2: "AUTO_BOOKMARK", 3: "AUTO_SUBFRAME",
        4: "MANUAL_SUBFRAME", 5: "GENERATED", 6: "AUTO_TOPLEVEL",
        7: "FORM_SUBMIT", 8: "RELOAD", 9: "KEYWORD", 10: "KEYWORD_GENERATED",
    }
    core = int(val) & 0xFF
    return TYPES.get(core, f"TYPE_{core}")
