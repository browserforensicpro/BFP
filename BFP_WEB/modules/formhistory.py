"""
formhistory.py - Extract autofill form history from browsers.
"""

import logging
from utils.forensiccopy import open_readonly_copy, safe_query, table_exists
from utils.timeutils import webkit_to_str, unix_us_to_str

logger = logging.getLogger(__name__)


def extract_chromium(dbs: dict) -> list:
    results = []
    db_path = dbs.get("WebData", "")
    if not db_path:
        return results
    try:
        conn = open_readonly_copy(db_path)
        if table_exists(conn, "autofill"):
            rows = safe_query(conn, """
                SELECT name, value, count, date_created, date_last_used
                FROM autofill
                ORDER BY count DESC
            """)
            for row in rows:
                results.append({
                    "name":           row[0] or "",
                    "value":          row[1] or "",
                    "count":          row[2] or 0,
                    "date_created":   webkit_to_str(row[3] * 1_000_000) if row[3] else "N/A",
                    "date_last_used": webkit_to_str(row[4] * 1_000_000) if row[4] else "N/A",
                    "type":           "Text Field",
                })

        # Also extract autofill_profile (address data)
        if table_exists(conn, "autofill_profiles"):
            rows2 = safe_query(conn, """
                SELECT full_name, email, phone_number, company_name,
                       street_address, city, state, zipcode, country_code
                FROM autofill_profiles
            """)
            for row in rows2:
                results.append({
                    "name":           "Address Profile",
                    "value":          " | ".join(filter(None, [
                                          row[0], row[1], row[2], row[3],
                                          row[4], row[5], row[6], row[7], row[8]
                                      ])),
                    "count":          0,
                    "date_created":   "N/A",
                    "date_last_used": "N/A",
                    "type":           "Address",
                })
        conn.close()
    except Exception as e:
        logger.error(f"Chromium form history error: {e}")
    return results


def extract_firefox(dbs: dict) -> list:
    results = []
    db_path = dbs.get("FormHistory", "")
    if not db_path:
        return results
    try:
        conn = open_readonly_copy(db_path)
        if not table_exists(conn, "moz_formhistory"):
            conn.close()
            return results

        rows = safe_query(conn, """
            SELECT fieldname, value, timesUsed, firstUsed, lastUsed
            FROM moz_formhistory
            ORDER BY timesUsed DESC
        """)
        for row in rows:
            results.append({
                "name":           row[0] or "",
                "value":          row[1] or "",
                "count":          row[2] or 0,
                "date_created":   unix_us_to_str(row[3]) if row[3] else "N/A",
                "date_last_used": unix_us_to_str(row[4]) if row[4] else "N/A",
                "type":           "Text Field",
            })
        conn.close()
    except Exception as e:
        logger.error(f"Firefox form history error: {e}")
    return results
