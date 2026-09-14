import hashlib
import math
import re

from config import CATEGORY_KEYWORDS, BALTIMORE_LAT, BALTIMORE_LNG


def normalize_title(title: str) -> str:
    t = title.lower().strip()
    t = re.sub(r"[^a-z0-9 ]", "", t)
    t = re.sub(r"\s+", " ", t)
    return t


def dedupe_key(title: str, venue_name: str, start_time_iso: str) -> str:
    """Hash of normalized title + venue + date (not exact time, so a venue's own
    listing and an aggregator's listing of the same event still collide even if
    one has slightly different HH:MM)."""
    date_part = start_time_iso[:10]  # YYYY-MM-DD
    raw = f"{normalize_title(title)}|{normalize_title(venue_name or '')}|{date_part}"
    return hashlib.sha256(raw.encode()).hexdigest()


def haversine_miles(lat1, lng1, lat2, lng2) -> float:
    r = 3958.8  # earth radius, miles
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def distance_from_baltimore(lat, lng) -> float | None:
    if lat is None or lng is None:
        return None
    return round(haversine_miles(BALTIMORE_LAT, BALTIMORE_LNG, lat, lng), 1)


def auto_categorize(title: str, description: str = "") -> list[str]:
    text = f"{title} {description or ''}".lower()
    return [cat for cat, keywords in CATEGORY_KEYWORDS.items() if any(k in text for k in keywords)]
