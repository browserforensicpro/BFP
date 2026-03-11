"""
cache.py - List and manage cache files from browser profiles.
"""

import os
import shutil
import logging
from utils.cacherebuilder import list_cache_files, extract_cached_images
from config import TEMP_DIR

logger = logging.getLogger(__name__)


def get_cache_list(dbs: dict) -> list:
    """List all cache files with size info."""
    cache_dir = dbs.get("Cache", "")
    if not cache_dir or not os.path.isdir(cache_dir):
        return []
    return list_cache_files(cache_dir)


def get_cached_images(dbs: dict) -> list:
    """Extract cached images to temp dir and return their paths."""
    cache_dir = dbs.get("Cache", "")
    if not cache_dir or not os.path.isdir(cache_dir):
        return []
    out_dir = os.path.join(TEMP_DIR, "cached_images")
    return extract_cached_images(cache_dir, out_dir)


def get_cache_stats(dbs: dict) -> dict:
    """Return cache statistics."""
    files = get_cache_list(dbs)
    total_size = sum(f["size"] for f in files)
    return {
        "file_count": len(files),
        "total_size": total_size,
        "total_size_str": _format_size(total_size),
    }


def _format_size(size: int) -> str:
    for unit in ["B", "KB", "MB", "GB"]:
        if size < 1024:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} TB"
