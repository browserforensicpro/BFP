"""
vssrecovery.py - Multi-artifact deleted record recovery from SQLite WAL files.
Recovers: History, Downloads, Cookies, Logins, Form History, Bookmarks.
WAL recovery works without admin. VSS requires Windows admin.
"""
import os, re, logging, tempfile, shutil, sqlite3
logger = logging.getLogger(__name__)

# ── DB targets: key -> (db_key, sql, field_map) ─────────────────────────────
RECOVERY_TARGETS = {
    "history": {
        "db_key": "History",
        "queries": [
            ("urls",   "SELECT url, title, visit_count, last_visit_time, hidden FROM urls",
             ["url","title","visit_count","last_visit","hidden"]),
        ],
    },
    "downloads": {
        "db_key": "History",
        "queries": [
            ("downloads", "SELECT tab_url, target_path, total_bytes, state, start_time FROM downloads",
             ["url","target_path","total_bytes","state","start_time"]),
        ],
    },
    "cookies": {
        "db_key": "Cookies",
        "queries": [
            ("cookies", "SELECT host_key, name, path, expires_utc, is_secure, is_httponly FROM cookies",
             ["host","name","path","expires","secure","httponly"]),
        ],
    },
    "logins": {
        "db_key": "LoginData",
        "queries": [
            ("logins", "SELECT origin_url, username_value, date_created FROM logins",
             ["origin_url","username","date_created"]),
        ],
    },
    "formhistory": {
        "db_key": "WebData",
        "queries": [
            ("autofill", "SELECT name, value, count, date_created FROM autofill",
             ["field","value","count","date_created"]),
        ],
    },
    "bookmarks_raw": {
        "db_key": "History",
        "queries": [],  # bookmarks are JSON, handled separately
    },
}


def extract_all_deleted(dbs: dict) -> list:
    """
    Main entry: scan WAL files for ALL artifact types.
    Returns list of dicts with _artifact_type key for grouping.
    """
    all_results = []
    for artifact_key, cfg in RECOVERY_TARGETS.items():
        if not cfg["queries"]:
            continue
        db_path = dbs.get(cfg["db_key"], "")
        if not db_path or not os.path.isfile(db_path):
            continue
        results = _recover_from_db(db_path, cfg["queries"], artifact_key)
        all_results.extend(results)

    # Raw WAL binary scan for URLs from any DB
    raw_urls = _raw_wal_scan_all(dbs)
    all_results.extend(raw_urls)

    logger.info(f"WAL recovery total: {len(all_results)} records")
    return all_results


def extract_wal_deleted(db_path: str) -> list:
    """Legacy entry point: recover history from single DB."""
    if not db_path or not os.path.isfile(db_path):
        return []
    # Build a minimal dbs dict
    dbs = {"History": db_path}
    return extract_all_deleted(dbs)


def _recover_from_db(db_path: str, queries: list, artifact_type: str) -> list:
    """Open DB (with WAL auto-applied) and run recovery queries."""
    results = []
    try:
        from utils.forensiccopy import forensic_copy
        from utils.timeutils import webkit_to_str
        from config import TEMP_DIR

        copy_path = forensic_copy(db_path, TEMP_DIR)
        if not copy_path or not os.path.isfile(copy_path):
            return results

        conn = sqlite3.connect(copy_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()

        for (table, sql, fields) in queries:
            try:
                cur.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,))
                if not cur.fetchone():
                    continue
                cur.execute(sql)
                rows = cur.fetchall()
                for row in rows:
                    rec = {"_artifact_type": artifact_type,
                           "recovery_source": "WAL / Live DB"}
                    for i, field in enumerate(fields):
                        val = row[i] if i < len(row) else ""
                        # Convert timestamps
                        if field in ("last_visit", "start_time", "date_created") and val:
                            try:
                                rec[field] = webkit_to_str(int(val))
                                rec[field + "_raw"] = str(val)
                            except:
                                rec[field] = str(val)
                        else:
                            rec[field] = str(val) if val is not None else ""
                    results.append(rec)
            except Exception as e:
                logger.debug(f"Recovery query [{table}]: {e}")

        conn.close()
    except Exception as e:
        logger.error(f"DB recovery [{artifact_type}]: {e}")
    return results


def _raw_wal_scan_all(dbs: dict) -> list:
    """Scan all WAL files for deleted URL/email/path patterns."""
    results = []
    seen = set()
    db_keys = ["History", "Cookies", "LoginData", "WebData", "Favicons"]

    url_pat   = re.compile(rb'https?://[a-zA-Z0-9\-._~:/?#\[\]@!$&\'()*+,;=%]{8,512}')
    email_pat = re.compile(rb'[a-zA-Z0-9._%+\-]{2,40}@[a-zA-Z0-9.\-]{2,40}\.[a-zA-Z]{2,6}')
    path_pat  = re.compile(rb'[A-Za-z]:\\[^"\x00\r\n]{8,200}')

    for key in db_keys:
        db_path = dbs.get(key, "")
        if not db_path or not os.path.isfile(db_path):
            continue
        wal_path = db_path + "-wal"
        if not os.path.isfile(wal_path):
            continue
        try:
            with open(wal_path, "rb") as f:
                data = f.read()

            for pat, ftype in [(url_pat,"url"),(email_pat,"email"),(path_pat,"filepath")]:
                for m in pat.findall(data):
                    try:
                        val = m.decode("utf-8", errors="ignore").rstrip(".,;)'\"")
                        if val in seen or len(val) < 8:
                            continue
                        seen.add(val)
                        rec = {
                            "_artifact_type": "raw_wal",
                            "type":           ftype,
                            "value":          val,
                            "source_db":      os.path.basename(db_path),
                            "recovery_source": "RAW WAL BINARY SCAN (Deleted)",
                        }
                        # For URLs also set 'url' for compatibility
                        if ftype == "url":
                            rec["url"] = val
                        results.append(rec)
                    except:
                        pass
        except Exception as e:
            logger.debug(f"WAL scan [{key}]: {e}")

    return results
