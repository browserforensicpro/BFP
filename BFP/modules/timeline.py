"""
timeline.py — Timeline analytics with IST conversion, 12-hour AM/PM format.
IST = UTC + 5:30

Reads _visit_timestamps list from each history row (set by history.py).
Falls back to visit_time_raw if _visit_timestamps is empty.
"""
import logging
from collections import defaultdict
from urllib.parse import urlparse
from utils.timeutils import webkit_to_datetime, unix_us_to_datetime
import datetime

logger = logging.getLogger(__name__)
IST_OFFSET = datetime.timedelta(hours=5, minutes=30)


def _to_ist(dt: datetime.datetime) -> datetime.datetime:
    return dt + IST_OFFSET


def _fmt12(dt: datetime.datetime) -> str:
    return dt.strftime("%Y-%m-%d %I:%M:%S %p IST")


def build_timeline(history_rows: list, browser: str = "chromium") -> dict:
    hourly  = defaultdict(int)   # IST hour (0-23) → count
    daily   = defaultdict(int)   # "YYYY-MM-DD" → count
    domains = defaultdict(int)
    pages   = defaultdict(lambda: {"title": "", "count": 0})
    entries = []

    is_ff = browser.lower() == "firefox"

    def _parse_ts(raw_ts):
        """Convert raw timestamp to IST datetime."""
        if not raw_ts:
            return None
        try:
            ts = int(raw_ts)
            if ts <= 0:
                return None
            utc_dt = unix_us_to_datetime(ts) if is_ff else webkit_to_datetime(ts)
            return _to_ist(utc_dt)
        except Exception:
            return None

    for row in history_rows:
        url   = row.get("url", "")
        title = row.get("title", "")

        # Use all individual visit timestamps if available (more accurate)
        ts_list = row.get("_visit_timestamps") or []
        if not ts_list:
            # Fallback: use visit_time_raw (just the last visit)
            raw = row.get("_visit_time_raw", row.get("visit_time_raw", 0))
            if raw:
                ts_list = [raw]

        # Aggregate domain/page counts based on visit_count (accurate total)
        if url:
            domain = _extract_domain(url)
            vc = int(row.get("visit_count", 0) or len(ts_list) or 1)
            if domain:
                domains[domain] += vc
            pages[url]["title"] = title
            pages[url]["count"] += vc

        # Build hourly/daily from actual timestamps
        for raw_ts in ts_list:
            ist_dt = _parse_ts(raw_ts)
            if not ist_dt:
                continue
            hourly[ist_dt.hour] += 1
            daily[ist_dt.strftime("%Y-%m-%d")] += 1
            if url:
                entries.append({
                    "datetime_ist": _fmt12(ist_dt),
                    "hour_ist":     ist_dt.hour,
                    "date_ist":     ist_dt.strftime("%Y-%m-%d"),
                    "url":          url,
                    "title":        title,
                })

    # Sort entries newest first, cap at 500
    entries.sort(key=lambda x: x["datetime_ist"], reverse=True)

    top_domains = sorted(
        [{"domain": d, "count": c} for d, c in domains.items()],
        key=lambda x: x["count"], reverse=True
    )[:50]

    top_pages = sorted(
        [{"url": u, "title": d["title"], "count": d["count"]} for u, d in pages.items()],
        key=lambda x: x["count"], reverse=True
    )[:100]

    return {
        "hourly":       dict(sorted(hourly.items())),
        "daily":        dict(sorted(daily.items())),
        "top_domains":  top_domains,
        "top_pages":    top_pages,
        "total_visits": sum(hourly.values()),
        "entries":      entries[:500],
    }


def _extract_domain(url: str) -> str:
    try:
        d = urlparse(url).netloc
        return d[4:] if d.startswith("www.") else d
    except Exception:
        return ""
