"""
thumbnails.py - Extract Top Sites thumbnails and NTP tiles from browser profiles.
Handles multiple Chromium DB schemas.
"""

import os
import logging
from utils.forensiccopy import open_readonly_copy, safe_query, table_exists, get_table_names
from utils.timeutils import webkit_to_str

logger = logging.getLogger(__name__)


def extract_chromium(dbs: dict) -> list:
    results = []
    db_path = dbs.get("TopSites", "")
    if not db_path or not os.path.isfile(db_path):
        logger.warning(f"TopSites DB not found at: {db_path}")
        return results
    try:
        conn = open_readonly_copy(db_path)
        tables = get_table_names(conn)
        logger.info(f"TopSites tables: {tables}")

        # Modern Chrome schema: top_sites
        if "top_sites" in tables:
            rows = safe_query(conn, "SELECT url, url_rank, title, redirects FROM top_sites ORDER BY url_rank ASC")
            for row in rows:
                results.append({
                    "rank":          row[1] if row[1] is not None else 0,
                    "url":           row[0] or "",
                    "title":         row[2] or "",
                    "redirects":     row[3] or "",
                    "thumbnail":     "See Cache Gallery",
                    "last_updated":  "N/A",
                })

        # Older schema: thumbnails table (Chrome < 100)
        if "thumbnails" in tables:
            rows = safe_query(conn, """
                SELECT url, boring_score, good_clipping, at_top,
                       last_updated, length(thumbnail)
                FROM thumbnails
                ORDER BY last_updated DESC
            """)
            for row in rows:
                results.append({
                    "rank":          0,
                    "url":           row[0] or "",
                    "title":         "",
                    "redirects":     "",
                    "thumbnail":     f"Yes — {row[5]} bytes" if row[5] else "No",
                    "last_updated":  webkit_to_str(row[4]) if row[4] else "N/A",
                })

        # ntp_tiles table (some versions)
        if "ntp_tiles" in tables:
            rows = safe_query(conn, "SELECT url, title, source FROM ntp_tiles")
            for row in rows:
                results.append({
                    "rank":          0,
                    "url":           row[0] or "",
                    "title":         row[1] or "",
                    "redirects":     "",
                    "thumbnail":     f"Source: {row[2]}",
                    "last_updated":  "N/A",
                })

        conn.close()
        logger.info(f"Thumbnails extracted: {len(results)}")
    except Exception as e:
        logger.error(f"Chromium thumbnails error: {e}")
    return results
