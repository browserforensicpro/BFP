"""
cacherebuilder.py - Proper Chrome Cache v2 / Simple Cache parser + image extractor.
Supports both Chrome's blockfile cache and simple cache (Cache_Data folder).
"""
import os, struct, logging, shutil, hashlib
from pathlib import Path

logger = logging.getLogger(__name__)

IMG_SIGS = {
    b"\xff\xd8\xff": ".jpg",
    b"\x89PNG\r\n\x1a\n": ".png",
    b"GIF87a": ".gif",
    b"GIF89a": ".gif",
    b"RIFF": ".webp",      # RIFF....WEBP
    b"BM": ".bmp",
    b"\x00\x00\x01\x00": ".ico",
}
# WEBP must have WEBP at offset 8
def _is_webp(data: bytes, pos: int) -> bool:
    return len(data) >= pos + 12 and data[pos+8:pos+12] == b"WEBP"

def _is_valid_image(data: bytes, sig: bytes) -> bool:
    """Quick plausibility check: minimum size."""
    return len(data) >= 128

def list_cache_files(cache_dir: str) -> list:
    results = []
    if not os.path.isdir(cache_dir):
        return results
    try:
        for root, dirs, files in os.walk(cache_dir):
            for fname in files:
                fpath = os.path.join(root, fname)
                try:
                    sz = os.path.getsize(fpath)
                    mtime = os.path.getmtime(fpath)
                    import datetime
                    results.append({
                        "name":     fname,
                        "size":     _fmt(sz),
                        "modified": datetime.datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M"),
                        "_raw_size": sz,
                    })
                except Exception:
                    pass
    except Exception as e:
        logger.warning(f"Cache list error: {e}")
    return sorted(results, key=lambda x: x["_raw_size"], reverse=True)


def extract_cached_images(cache_dir: str, output_dir: str) -> list:
    """
    Scan all cache files for embedded image data.
    Chrome Simple Cache: files in Cache_Data/ named as hex hashes.
    Chrome Block Cache: f_000000 ... f_ffffff files.
    Also handles raw files that ARE images.
    """
    os.makedirs(output_dir, exist_ok=True)
    extracted = []
    seen_hashes = set()
    idx = 0

    if not os.path.isdir(cache_dir):
        return extracted

    all_files = []
    for root, dirs, files in os.walk(cache_dir):
        for fname in files:
            fpath = os.path.join(root, fname)
            try:
                sz = os.path.getsize(fpath)
                if 200 < sz < 15_000_000:   # skip tiny/huge
                    all_files.append(fpath)
            except Exception:
                pass

    logger.info(f"Cache image scan: {len(all_files)} files in {cache_dir}")

    for fpath in all_files:
        try:
            with open(fpath, "rb") as f:
                raw = f.read()

            # Skip obvious non-image cache metadata files
            if raw[:4] in (b"CHCK", b"SFCA", b"\xd8\x41\x0c\x00"):
                # Chrome cache entry header — skip header, scan body
                raw = raw[8192:] if len(raw) > 8192 else raw[256:]

            for sig, ext in IMG_SIGS.items():
                pos = 0
                while True:
                    pos = raw.find(sig, pos)
                    if pos == -1:
                        break

                    # Extra WEBP check
                    if sig == b"RIFF" and not _is_webp(raw, pos):
                        pos += 1; continue

                    chunk = raw[pos: pos + 10_000_000]
                    if len(chunk) < 128:
                        pos += 1; continue

                    # Deduplicate by hash of first 4KB
                    h = hashlib.md5(chunk[:4096]).hexdigest()
                    if h in seen_hashes:
                        pos += len(sig); continue
                    seen_hashes.add(h)

                    out_path = os.path.join(output_dir, f"img_{idx:05d}{ext}")
                    with open(out_path, "wb") as out:
                        out.write(chunk)

                    # Validate: try PIL open
                    try:
                        from PIL import Image
                        im = Image.open(out_path)
                        im.verify()
                        # Re-open after verify (verify closes it)
                        im = Image.open(out_path)
                        w, h2 = im.size
                        if w < 8 or h2 < 8:
                            os.remove(out_path)
                            pos += len(sig); continue
                        extracted.append(out_path)
                        idx += 1
                    except Exception:
                        # PIL not available or invalid — keep if reasonable size
                        if len(chunk) > 512:
                            extracted.append(out_path)
                            idx += 1
                        else:
                            try: os.remove(out_path)
                            except: pass

                    pos += len(sig)
                    if idx >= 500:   # cap at 500 images
                        break
                if idx >= 500:
                    break
            if idx >= 500:
                break
        except Exception as e:
            logger.debug(f"Cache scan [{fpath}]: {e}")

    logger.info(f"Extracted {len(extracted)} cached images")
    return extracted


def clear_least_used_cache(cache_dir: str, keep_pct: float = 0.3) -> dict:
    """
    Delete the least-used (smallest) cache files, keeping the top keep_pct by size.
    Only runs on explicit user request — never automatic.
    Returns: {deleted_count, freed_bytes, freed_str}
    """
    if not os.path.isdir(cache_dir):
        return {"deleted_count": 0, "freed_bytes": 0, "freed_str": "0 B"}

    files = []
    for root, dirs, fs in os.walk(cache_dir):
        for f in fs:
            fp = os.path.join(root, f)
            try:
                files.append((fp, os.path.getsize(fp)))
            except Exception:
                pass

    if not files:
        return {"deleted_count": 0, "freed_bytes": 0, "freed_str": "0 B"}

    # Sort ascending by size — delete the smallest (least-used)
    files.sort(key=lambda x: x[1])
    cutoff = int(len(files) * (1 - keep_pct))
    to_delete = files[:cutoff]

    deleted = 0; freed = 0
    for fp, sz in to_delete:
        try:
            os.remove(fp)
            deleted += 1; freed += sz
        except Exception:
            pass

    return {"deleted_count": deleted, "freed_bytes": freed, "freed_str": _fmt(freed)}


def clear_old_cache(cache_dir: str, days: int = 30) -> dict:
    """Delete cache files older than `days` days."""
    import datetime
    if not os.path.isdir(cache_dir):
        return {"deleted_count": 0, "freed_bytes": 0, "freed_str": "0 B"}
    cutoff = datetime.datetime.now() - datetime.timedelta(days=days)
    deleted = 0; freed = 0
    for root, dirs, files in os.walk(cache_dir):
        for f in files:
            fp = os.path.join(root, f)
            try:
                mtime = datetime.datetime.fromtimestamp(os.path.getmtime(fp))
                if mtime < cutoff:
                    sz = os.path.getsize(fp)
                    os.remove(fp)
                    deleted += 1; freed += sz
            except Exception:
                pass
    return {"deleted_count": deleted, "freed_bytes": freed, "freed_str": _fmt(freed)}


def clear_all_cache(cache_dir: str) -> dict:
    """Delete ALL cache files."""
    if not os.path.isdir(cache_dir):
        return {"deleted_count": 0, "freed_bytes": 0, "freed_str": "0 B"}
    deleted = 0; freed = 0
    for root, dirs, files in os.walk(cache_dir):
        for f in files:
            fp = os.path.join(root, f)
            try:
                sz = os.path.getsize(fp)
                os.remove(fp)
                deleted += 1; freed += sz
            except Exception:
                pass
    return {"deleted_count": deleted, "freed_bytes": freed, "freed_str": _fmt(freed)}


def _fmt(size: int) -> str:
    for u in ["B","KB","MB","GB"]:
        if size < 1024: return f"{size:.1f} {u}"
        size /= 1024
    return f"{size:.1f} TB"
