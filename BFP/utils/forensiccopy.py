"""
forensiccopy.py - Safe read-only forensic copy of SQLite databases.
Always copies DB + WAL + SHM to temp before opening.
Never modifies source files.
"""

import os
import shutil
import sqlite3
import tempfile
import logging

logger = logging.getLogger(__name__)


def forensic_copy(src_path: str, dest_dir: str = None) -> str:
    """
    Copy a SQLite database (plus WAL/SHM) to a temp directory.
    Returns path to the copied database file.
    """
    if not os.path.isfile(src_path):
        raise FileNotFoundError(f"Source DB not found: {src_path}")

    if dest_dir is None:
        dest_dir = tempfile.mkdtemp(prefix="bfp_")

    os.makedirs(dest_dir, exist_ok=True)
    base_name = os.path.basename(src_path)
    dest_path = os.path.join(dest_dir, base_name)

    # Copy main DB
    shutil.copy2(src_path, dest_path)
    logger.debug(f"Forensic copy: {src_path} → {dest_path}")

    # Copy WAL file if present
    wal_src = src_path + "-wal"
    if os.path.isfile(wal_src):
        shutil.copy2(wal_src, dest_path + "-wal")
        logger.debug(f"Copied WAL: {wal_src}")

    # Copy SHM file if present
    shm_src = src_path + "-shm"
    if os.path.isfile(shm_src):
        shutil.copy2(shm_src, dest_path + "-shm")
        logger.debug(f"Copied SHM: {shm_src}")

    return dest_path


def open_readonly_copy(db_path: str) -> sqlite3.Connection:
    """
    Make a forensic copy then open it in read-only mode.
    Returns sqlite3 Connection.
    """
    from config import TEMP_DIR
    copy_path = forensic_copy(db_path, TEMP_DIR)
    # Use URI mode for read-only
    uri = f"file:{copy_path}?mode=ro"
    conn = sqlite3.connect(uri, uri=True, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def safe_query(conn: sqlite3.Connection, sql: str, params=()):
    """Execute a query safely, returning list of Row objects or empty list."""
    try:
        cur = conn.cursor()
        cur.execute(sql, params)
        return cur.fetchall()
    except Exception as e:
        logger.warning(f"Query failed: {e}\nSQL: {sql}")
        return []


def get_table_names(conn: sqlite3.Connection):
    """Return list of table names in the database."""
    rows = safe_query(conn, "SELECT name FROM sqlite_master WHERE type='table'")
    return [r[0] for r in rows]


def table_exists(conn: sqlite3.Connection, table: str) -> bool:
    rows = safe_query(conn,
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,))
    return len(rows) > 0
