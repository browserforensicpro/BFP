"""
timeutils.py - Timestamp conversion utilities for browser forensics.
Handles Chrome/Edge/Brave (WebKit epoch), Firefox (Unix µs), and standard Unix timestamps.

Timezone is configurable via TZ_OFFSET_HOURS (default IST = UTC+5.5).
Call set_timezone(offset_hours) to change globally.
"""

import datetime

# Chrome/Edge/Brave use WebKit epoch: Jan 1, 1601
WEBKIT_EPOCH = datetime.datetime(1601, 1, 1)
UNIX_EPOCH   = datetime.datetime(1970, 1, 1)

# Global timezone offset in hours — default IST = +5.5
_TZ_OFFSET_HOURS: float = 5.5
_TZ_LABEL: str = "IST"

KNOWN_TZ = {
    "IST":   5.5,
    "UTC":   0.0,
    "EST":  -5.0,
    "EDT":  -4.0,
    "CST":  -6.0,
    "CDT":  -5.0,
    "MST":  -7.0,
    "MDT":  -6.0,
    "PST":  -8.0,
    "PDT":  -7.0,
    "GMT":   0.0,
    "CET":   1.0,
    "EET":   2.0,
    "JST":   9.0,
    "AEST": 10.0,
}


def set_timezone(label: str) -> None:
    """Set the global timezone label. e.g. 'IST', 'UTC', 'PST'."""
    global _TZ_OFFSET_HOURS, _TZ_LABEL
    label = label.strip().upper()
    if label in KNOWN_TZ:
        _TZ_OFFSET_HOURS = KNOWN_TZ[label]
        _TZ_LABEL = label
    else:
        # Try parsing as numeric offset e.g. "+5.5" or "-8"
        try:
            _TZ_OFFSET_HOURS = float(label.replace("UTC","").replace("GMT","") or 0)
            _TZ_LABEL = f"UTC{_TZ_OFFSET_HOURS:+.1f}".replace(".0","")
        except ValueError:
            pass  # Ignore unknown


def get_timezone_label() -> str:
    return _TZ_LABEL


def get_timezone_offset() -> float:
    return _TZ_OFFSET_HOURS


# ── Raw datetime converters (always return UTC datetime) ──────────────────────

def webkit_to_datetime(webkit_ts: int) -> datetime.datetime:
    """Convert WebKit microsecond timestamp to UTC datetime."""
    try:
        return WEBKIT_EPOCH + datetime.timedelta(microseconds=int(webkit_ts))
    except Exception:
        return datetime.datetime(1970, 1, 1)


def unix_ms_to_datetime(unix_ms: int) -> datetime.datetime:
    """Convert Unix millisecond timestamp to UTC datetime."""
    try:
        return datetime.datetime.utcfromtimestamp(int(unix_ms) / 1000)
    except Exception:
        return datetime.datetime(1970, 1, 1)


def unix_us_to_datetime(unix_us: int) -> datetime.datetime:
    """Convert Unix microsecond timestamp to UTC datetime."""
    try:
        return datetime.datetime.utcfromtimestamp(int(unix_us) / 1_000_000)
    except Exception:
        return datetime.datetime(1970, 1, 1)


def unix_s_to_datetime(unix_s: int) -> datetime.datetime:
    """Convert Unix second timestamp to UTC datetime."""
    try:
        return datetime.datetime.utcfromtimestamp(int(unix_s))
    except Exception:
        return datetime.datetime(1970, 1, 1)


# ── Formatted string output (applies global timezone) ────────────────────────

def _apply_tz(dt: datetime.datetime) -> datetime.datetime:
    """Apply the global timezone offset to a UTC datetime."""
    if dt.year == 1970:
        return dt
    return dt + datetime.timedelta(hours=_TZ_OFFSET_HOURS)


def format_dt(dt: datetime.datetime) -> str:
    """Format a UTC datetime in the configured timezone."""
    try:
        if dt.year == 1970:
            return "N/A"
        local = _apply_tz(dt)
        fmt = "%d/%m/%Y, %I:%M:%S %p" if True else "%Y-%m-%d %H:%M:%S"
        return local.strftime(fmt) + f" {_TZ_LABEL}"
    except Exception:
        return "N/A"


def webkit_to_str(webkit_ts) -> str:
    return format_dt(webkit_to_datetime(webkit_ts))


def unix_ms_to_str(unix_ms) -> str:
    return format_dt(unix_ms_to_datetime(unix_ms))


def unix_us_to_str(unix_us) -> str:
    return format_dt(unix_us_to_datetime(unix_us))


def unix_s_to_str(unix_s) -> str:
    return format_dt(unix_s_to_datetime(unix_s))
