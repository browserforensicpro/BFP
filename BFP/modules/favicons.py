"""
favicons.py - Extract favicons from Chromium and Firefox.
Handles all schema versions including modern Chrome (icon_mapping table).
"""

import os
import logging
from utils.forensiccopy import open_readonly_copy, safe_query, table_exists, get_table_names
from utils.timeutils import webkit_to_str

logger = logging.getLogger(__name__)


def extract_chromium(dbs: dict) -> list:
    results = []
    db_path = dbs.get("Favicons", "")
    if not db_path or not os.path.isfile(db_path):
        logger.warning("Favicons DB not found")
        return results
    try:
        conn = open_readonly_copy(db_path)
        tables = get_table_names(conn)
        logger.info(f"Favicons DB tables: {tables}")

        # Modern Chrome: icon_mapping -> favicons -> favicon_bitmaps
        if "icon_mapping" in tables and "favicons" in tables:
            rows = safe_query(conn, """
                SELECT DISTINCT
                    im.page_url,
                    f.url          AS favicon_url,
                    fb.width,
                    fb.height,
                    COALESCE(length(fb.image_data), 0) AS data_size,
                    f.last_updated
                FROM icon_mapping im
                JOIN favicons f ON im.icon_id = f.id
                LEFT JOIN favicon_bitmaps fb ON f.id = fb.icon_id
                ORDER BY f.last_updated DESC
            """)
            for row in rows:
                results.append({
                    "page_url":     row[0] or "",
                    "favicon_url":  row[1] or "",
                    "width":        row[2] or 0,
                    "height":       row[3] or 0,
                    "data_size_b":  row[4] or 0,
                    "last_updated": webkit_to_str(row[5]) if row[5] else "N/A",
                })

        elif "favicons" in tables:
            rows = safe_query(conn, "SELECT url, COALESCE(last_updated,0) FROM favicons ORDER BY last_updated DESC")
            for row in rows:
                results.append({
                    "page_url":     "",
                    "favicon_url":  row[0] or "",
                    "width":        0,
                    "height":       0,
                    "data_size_b":  0,
                    "last_updated": webkit_to_str(row[1]) if row[1] else "N/A",
                })

        elif "favicon_bitmaps" in tables:
            rows = safe_query(conn, "SELECT icon_id, width, height, length(image_data), last_updated FROM favicon_bitmaps")
            for row in rows:
                results.append({
                    "page_url":     f"icon_id:{row[0]}",
                    "favicon_url":  "",
                    "width":        row[1] or 0,
                    "height":       row[2] or 0,
                    "data_size_b":  row[3] or 0,
                    "last_updated": webkit_to_str(row[4]) if row[4] else "N/A",
                })

        conn.close()
        logger.info(f"Favicons extracted: {len(results)}")
    except Exception as e:
        logger.error(f"Chromium favicons error: {e}")
    return results


def extract_firefox(dbs: dict) -> list:
    results = []
    db_path = dbs.get("Favicons", "")
    if not db_path or not os.path.isfile(db_path):
        return results
    try:
        conn = open_readonly_copy(db_path)
        if table_exists(conn, "moz_icons"):
            rows = safe_query(conn, "SELECT root, width, COALESCE(length(data),0), expire_ms FROM moz_icons ORDER BY width DESC")
            for row in rows:
                results.append({
                    "page_url":    "",
                    "favicon_url": row[0] or "",
                    "width":       row[1] or 0,
                    "height":      row[1] or 0,
                    "data_size_b": row[2] or 0,
                    "last_updated": str(row[3] or "N/A"),
                })
        conn.close()
    except Exception as e:
        logger.error(f"Firefox favicons error: {e}")
    return results
