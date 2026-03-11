"""
categorizer.py - Categorize URLs into predefined categories.
"""

from config import URL_CATEGORIES


def categorize_url(url: str) -> str:
    """Return category string for a given URL."""
    url_lower = url.lower()
    for category, keywords in URL_CATEGORIES.items():
        for kw in keywords:
            if kw in url_lower:
                return category
    return "General"


def categorize_history(history_rows: list) -> list:
    """Add 'category' field to each history row."""
    result = []
    for row in history_rows:
        row = dict(row)
        row["category"] = categorize_url(row.get("url", ""))
        result.append(row)
    return result


def get_category_summary(history_rows: list) -> dict:
    """Return dict of {category: count}."""
    from collections import Counter
    cats = [categorize_url(row.get("url", "")) for row in history_rows]
    return dict(Counter(cats))
