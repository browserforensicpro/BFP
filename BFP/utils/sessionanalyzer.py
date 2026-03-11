"""
sessionanalyzer.py - Analyze browser sessions, detect incognito usage,
validate session tokens, and infer browser open/close times.
"""

import os
import re
import json
import logging
import datetime

logger = logging.getLogger(__name__)


def analyze_sessions(session_data: list, history_data: list) -> dict:
    """
    Compare session timestamps vs history timestamps.
    Detect possible gaps indicating incognito or deleted history.
    Returns analysis dict.
    """
    report = {
        "total_sessions": len(session_data),
        "gaps_detected": [],
        "incognito_suspected": False,
        "notes": [],
    }

    # Sort history by timestamp
    try:
        hist_times = sorted([
            row.get("visit_time_raw", 0) for row in history_data
            if row.get("visit_time_raw", 0) > 0
        ])
        if len(hist_times) > 1:
            # Look for gaps > 4 hours with no history
            for i in range(1, len(hist_times)):
                gap = hist_times[i] - hist_times[i - 1]
                gap_hours = gap / 3_600_000_000  # microseconds to hours
                if gap_hours > 4:
                    report["gaps_detected"].append({
                        "gap_hours": round(gap_hours, 2),
                        "from_ts": hist_times[i - 1],
                        "to_ts": hist_times[i],
                    })
    except Exception as e:
        logger.warning(f"Session gap analysis error: {e}")

    if len(report["gaps_detected"]) > 0:
        report["incognito_suspected"] = True
        report["notes"].append(
            f"{len(report['gaps_detected'])} history gaps detected (>4h). "
            "Possible incognito or deleted history periods."
        )

    return report


def validate_session_tokens(cookies: list) -> list:
    """
    Scan cookies for session tokens and flag suspicious ones.
    Returns list of flagged cookies with notes.
    """
    SESSION_NAMES = {
        "PHPSESSID", "JSESSIONID", "ASP.NET_SessionId", "SESSIONID",
        "session", "sess", "token", "auth", "jwt", "access_token",
    }
    flagged = []
    for cookie in cookies:
        name = str(cookie.get("name", "")).upper()
        for sess_name in SESSION_NAMES:
            if sess_name.upper() in name:
                flagged.append({
                    "name": cookie.get("name"),
                    "host": cookie.get("host_key", cookie.get("host", "")),
                    "value_len": len(str(cookie.get("value", ""))),
                    "expires": cookie.get("expires_utc", ""),
                    "note": "Session/auth token detected",
                })
                break
    return flagged


def detect_browser_times(history_data: list) -> dict:
    """
    Infer browser open/close times from first/last history entries per day.
    """
    from utils.timeutils import webkit_to_datetime, format_dt
    daily = {}

    for row in history_data:
        ts_raw = row.get("visit_time_raw", 0)
        if not ts_raw:
            continue
        try:
            dt = webkit_to_datetime(ts_raw)
            day = dt.strftime("%Y-%m-%d")
            if day not in daily:
                daily[day] = {"first": dt, "last": dt}
            else:
                if dt < daily[day]["first"]:
                    daily[day]["first"] = dt
                if dt > daily[day]["last"]:
                    daily[day]["last"] = dt
        except Exception:
            pass

    result = []
    for day, times in sorted(daily.items()):
        duration = times["last"] - times["first"]
        result.append({
            "date": day,
            "first_visit": format_dt(times["first"]),
            "last_visit":  format_dt(times["last"]),
            "active_duration": str(duration).split(".")[0],
        })
    return result
