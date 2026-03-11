"""
searches.py - Extract search terms from browser history URLs.
"""

import re
import logging
from urllib.parse import urlparse, parse_qs, unquote_plus

logger = logging.getLogger(__name__)

# Search engine patterns: (domain_fragment, query_param)
SEARCH_ENGINES = [
    ("google.",      "q"),
    ("bing.com",     "q"),
    ("yahoo.com",    "p"),
    ("duckduckgo",   "q"),
    ("baidu.com",    "wd"),
    ("yandex.",      "text"),
    ("ask.com",      "q"),
    ("ecosia.org",   "q"),
    ("startpage.com","query"),
    ("brave.com",    "q"),
    ("search.aol",   "q"),
    ("qwant.com",    "q"),
]


def extract_from_history(history_rows: list) -> list:
    """Extract search queries from history URL list."""
    results = []
    seen = set()
    for row in history_rows:
        url = row.get("url", "")
        visit_time = row.get("visit_time", "N/A")
        search_info = _parse_search_url(url)
        if search_info:
            key = (search_info["engine"], search_info["query"])
            if key not in seen:
                seen.add(key)
                search_info["visit_time"] = visit_time
                search_info["url"] = url
                results.append(search_info)
    return results


def _parse_search_url(url: str) -> dict:
    """Return search info dict if URL is a search query, else None."""
    try:
        parsed = urlparse(url)
        domain = parsed.netloc.lower()
        for engine_frag, param in SEARCH_ENGINES:
            if engine_frag in domain:
                qs = parse_qs(parsed.query)
                query_terms = qs.get(param, [])
                if query_terms:
                    return {
                        "engine": _engine_name(engine_frag),
                        "query":  unquote_plus(query_terms[0]),
                        "domain": domain,
                    }
    except Exception:
        pass
    return None


def _engine_name(frag: str) -> str:
    NAMES = {
        "google.":     "Google",
        "bing.com":    "Bing",
        "yahoo.com":   "Yahoo",
        "duckduckgo":  "DuckDuckGo",
        "baidu.com":   "Baidu",
        "yandex.":     "Yandex",
        "ask.com":     "Ask",
        "ecosia.org":  "Ecosia",
        "startpage":   "Startpage",
        "brave.com":   "Brave Search",
        "search.aol":  "AOL",
        "qwant.com":   "Qwant",
    }
    return NAMES.get(frag, frag)
