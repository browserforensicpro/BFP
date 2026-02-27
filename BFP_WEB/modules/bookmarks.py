"""
bookmarks.py - Extract bookmarks from Chromium (JSON) and Firefox (SQLite).
"""

import os
import json
import logging
from utils.forensiccopy import open_readonly_copy, safe_query, table_exists
from utils.timeutils import webkit_to_str, unix_us_to_str

logger = logging.getLogger(__name__)


def extract_chromium(dbs: dict) -> list:
    """Parse Chromium Bookmarks JSON file."""
    results = []
    bm_path = dbs.get("Bookmarks", "")
    if not bm_path or not os.path.isfile(bm_path):
        return results
    try:
        with open(bm_path, "r", encoding="utf-8", errors="ignore") as f:
            data = json.load(f)
        roots = data.get("roots", {})
        for root_name, root_node in roots.items():
            if isinstance(root_node, dict):
                _walk_chromium_node(root_node, root_name, results)
    except Exception as e:
        logger.error(f"Chromium bookmarks error: {e}")
    return results


def _walk_chromium_node(node: dict, folder: str, results: list):
    """Recursively walk bookmark nodes."""
    node_type = node.get("type", "")
    if node_type == "url":
        results.append({
            "url":        node.get("url", ""),
            "title":      node.get("name", ""),
            "folder":     folder,
            "date_added": webkit_to_str(int(node["date_added"])) if node.get("date_added") else "N/A",
            "guid":       node.get("guid", ""),
        })
    elif node_type == "folder":
        folder_name = node.get("name", folder)
        for child in node.get("children", []):
            _walk_chromium_node(child, folder_name, results)
    else:
        for child in node.get("children", []):
            _walk_chromium_node(child, folder, results)


def extract_firefox(dbs: dict) -> list:
    results = []
    db_path = dbs.get("History", "")  # bookmarks are in places.sqlite
    if not db_path:
        return results
    try:
        conn = open_readonly_copy(db_path)
        if not table_exists(conn, "moz_bookmarks"):
            conn.close()
            return results

        rows = safe_query(conn, """
            SELECT p.url, b.title, b.dateAdded, b.lastModified,
                   f.title as folder
            FROM moz_bookmarks b
            JOIN moz_places p ON b.fk = p.id
            LEFT JOIN moz_bookmarks f ON b.parent = f.id
            WHERE b.type = 1
            ORDER BY b.dateAdded DESC
        """)
        for row in rows:
            results.append({
                "url":          row[0] or "",
                "title":        row[1] or "",
                "folder":       row[4] or "Bookmarks",
                "date_added":   unix_us_to_str(row[2]) if row[2] else "N/A",
                "date_modified": unix_us_to_str(row[3]) if row[3] else "N/A",
                "guid":         "",
            })
        conn.close()
    except Exception as e:
        logger.error(f"Firefox bookmarks error: {e}")
    return results
