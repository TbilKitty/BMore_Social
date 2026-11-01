"""
Reads event calendars from websites that use the WordPress plugin "The Events
Calendar" (Baltimore Jazz Alliance, Creative Alliance, Baltimore Public
Markets, Stages Music Arts, ...). Sites are listed in config.TRIBE_SOURCES.

For each site it tries the plugin's built-in JSON feed first
(/wp-json/tribe/events/v1/events) and falls back to the iCal export
(/events/?ical=1). Every site is independent: one failing never stops the rest.
"""
import html
import re
from datetime import datetime, timedelta, timezone

import requests
from bs4 import BeautifulSoup

from config import TRIBE_SOURCES, DAYS_AHEAD
from dedupe import dedupe_key, distance_from_baltimore, auto_categorize
from ical import parse_ics

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; BaltimoreSideQuest/1.0; +https://github.com/TbilKitty/BMore_Social)",
    "Accept": "application/json, text/calendar;q=0.9, */*;q=0.8",
}
MAX_PAGES = 10


def clean_html(value) -> str:
    if not value:
        return ""
    text = BeautifulSoup(html.unescape(str(value)), "html.parser").get_text(" ", strip=True)
    return re.sub(r"\s+", " ", text).strip()


def _utc_iso(value: str | None) -> str | None:
    """Tribe's utc_start_date looks like '2026-11-05 23:00:00'."""
    if not value:
        return None
    try:
        return datetime.strptime(value[:19], "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc).isoformat()
    except ValueError:
        return None


def _float(v):
    try:
        return float(v) if v not in (None, "") else None
    except (TypeError, ValueError):
        return None


def build_event(src: dict, *, title, description, url, start, end, venue_name, address,
                lat, lng, cost=None, source_categories=(), raw=None) -> dict | None:
    title = clean_html(title)
    if not (title and start and url):
        return None
    description = clean_html(description)
    cat_text = " ".join(source_categories)
    return {
        "dedupe_key": dedupe_key(title, venue_name, start),
        "source": src["name"],
        "source_url": url,
        "title": title[:300],
        "description": description[:4000],
        "venue_name": venue_name,
        "address": address,
        "lat": lat,
        "lng": lng,
        "distance_from_baltimore_mi": distance_from_baltimore(lat, lng),
        "start_time": start,
        "end_time": end,
        "categories": auto_categorize(title, f"{description} {cat_text}", src.get("tags"), cost),
        "is_recurring": False,
        "raw": raw or {},
    }


def from_rest(src: dict, e: dict) -> dict | None:
    venue = e.get("venue") if isinstance(e.get("venue"), dict) else {}
    parts = [venue.get("address"), venue.get("city"), venue.get("state") or venue.get("province"), venue.get("zip")]
    address = ", ".join(p for p in parts if p) or None
    lat = _float(venue.get("geo_lat") or venue.get("latitude"))
    lng = _float(venue.get("geo_lng") or venue.get("longitude"))
    cats = [c.get("name", "") for c in (e.get("categories") or []) if isinstance(c, dict)]
    cats += [t.get("name", "") for t in (e.get("tags") or []) if isinstance(t, dict)]
    return build_event(
        src,
        title=e.get("title"), description=e.get("description") or e.get("excerpt"),
        url=e.get("url"), start=_utc_iso(e.get("utc_start_date")), end=_utc_iso(e.get("utc_end_date")),
        venue_name=clean_html(venue.get("venue")) or None, address=address, lat=lat, lng=lng,
        cost=clean_html(e.get("cost")) or None, source_categories=cats,
        raw={"id": e.get("id"), "cost": e.get("cost"), "categories": cats, "venue": venue,
             "all_day": bool(e.get("all_day")), "local": src.get("local", False)},
    )


def fetch_rest(src: dict) -> list[dict] | None:
    """None = the feed isn't available (caller falls back to iCal)."""
    url = src["base_url"].rstrip("/") + "/wp-json/tribe/events/v1/events"
    now = datetime.now(timezone.utc)
    params = {
        "start_date": now.strftime("%Y-%m-%d 00:00:00"),
        "end_date": (now + timedelta(days=DAYS_AHEAD)).strftime("%Y-%m-%d 23:59:59"),
        "per_page": 50,
    }
    out = []
    for page in range(1, MAX_PAGES + 1):
        params["page"] = page
        resp = requests.get(url, params=params, headers=HEADERS, timeout=30)
        if resp.status_code == 404 and page == 1:
            body = resp.text[:300]
            if "rest_no_route" in body or "<html" in body.lower():
                return None  # plugin feed not exposed
            return []  # feed exists, just no events in range
        if resp.status_code != 200:
            if page == 1:
                print(f"[{src['name']}] JSON feed returned {resp.status_code}")
                return None
            break
        try:
            data = resp.json()
        except ValueError:
            return None if page == 1 else out
        for e in data.get("events", []):
            ev = from_rest(src, e)
            if ev:
                out.append(ev)
        if page >= int(data.get("total_pages") or 1):
            break
    return out


def fetch_ical(src: dict, url: str | None = None) -> list[dict]:
    url = url or src["base_url"].rstrip("/") + "/events/?ical=1"
    resp = requests.get(url, headers=HEADERS, timeout=30)
    if resp.status_code != 200 or "BEGIN:VCALENDAR" not in resp.text[:2000]:
        print(f"[{src['name']}] iCal feed unavailable ({resp.status_code})")
        return []
    now = datetime.now(timezone.utc).isoformat()
    out = []
    for e in parse_ics(resp.text):
        if e["start"] < now:
            continue
        lat, lng = e.get("geo", (None, None))
        location = e.get("location") or ""
        venue_name = location.split(",")[0].strip() or None
        ev = build_event(
            src, title=e.get("summary"), description=e.get("description"),
            url=e.get("url") or src.get("url") or src.get("base_url"), start=e["start"], end=e.get("end"),
            venue_name=venue_name, address=location or None, lat=lat, lng=lng,
            source_categories=e.get("categories", []),
            raw={"uid": e.get("uid"), "categories": e.get("categories"), "all_day": e.get("all_day", False),
                 "local": src.get("local", False)},
        )
        if ev:
            out.append(ev)
    return out


def fetch():
    events = []
    for src in TRIBE_SOURCES:
        try:
            found = fetch_rest(src)
            how = "JSON feed"
            if found is None:
                found = fetch_ical(src)
                how = "iCal"
            print(f"[tribe] {src['name']}: {len(found)} events via {how}")
            events.extend(found)
        except Exception as ex:  # one bad site never sinks the run
            print(f"[tribe] {src['name']} failed: {type(ex).__name__}: {ex}")
    return events
