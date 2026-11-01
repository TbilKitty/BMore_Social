import hashlib
import math
import re

from config import CATEGORY_KEYWORDS, EXCLUDE_KEYWORDS, BALTIMORE_LAT, BALTIMORE_LNG


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


def _has_word(text: str, phrase: str) -> bool:
    """Whole-word match, so "band" doesn't fire on "husband" or "dj" on "adjust"."""
    phrase = phrase.strip().lower()
    return re.search(r"(?<![a-z0-9])" + re.escape(phrase) + r"(?![a-z0-9])", text) is not None


def auto_categorize(title: str, description: str = "", extra_tags=None, cost: str | None = None) -> list[str]:
    """Categories from keywords, plus any tags the source itself guarantees
    (e.g. everything on the jazz calendar is jazz). Adds the special tags
    "free" and "popup" so alerts can find free and pop-up events."""
    text = f"{title} {description or ''}".lower()
    cats = [cat for cat, keywords in CATEGORY_KEYWORDS.items() if any(_has_word(text, k) for k in keywords)]
    for t in extra_tags or []:
        if t not in cats:
            cats.append(t)
    if is_excluded(text):
        # Pantry distributions etc. stay listed but never count as a food market / fun pick.
        cats = [c for c in cats if c not in ("food_markets", "food_festivals")]
    if (is_free(text, cost) if cost else is_free(text)) and "free" not in cats:
        cats.append("free")
    if is_popup(text) and "popup" not in cats:
        cats.append("popup")
    return cats


def is_excluded(text: str) -> bool:
    text = text.lower()
    return any(k in text for k in EXCLUDE_KEYWORDS)


# "free" that does NOT mean free admission
_NOT_ADMISSION = re.compile(
    r"(gluten|sugar|dairy|smoke|alcohol|barrier|nut|cruelty|fragrance|scent|toll|hands|carefree|hassle|fee)[- ]free"
    r"|free (parking|wifi|wi-fi|shipping|refills?|swag|gift|t-shirt|drink with|appetizer)"
    r"|feel free|free to (join|bring|reach|contact|come)|free will"
)
_FREE = re.compile(r"(?<![a-z])(free|no[- ]cover|no charge|pay what you (can|wish)|\$0(\.00)?)(?![a-z])")


def is_free(text: str, cost: str | None = None) -> bool:
    if cost is not None and str(cost).strip():
        c = str(cost).lower()
        return bool(re.search(r"free|no cover|^\$?0(\.00)?$|donation", c))
    t = _NOT_ADMISSION.sub(" ", text.lower())
    return _FREE.search(t) is not None


_POPUP = re.compile(r"pop[- ]?up|block party|porch ?fest|busk|street (fair|festival|party)|night market|sidewalk|flash mob|open air|open-air")


def is_popup(text: str) -> bool:
    return _POPUP.search(text.lower()) is not None
