"""
Eventbrite source. Uses Eventbrite's public search API.

NOTE: Eventbrite deprecated open public search for most API keys in 2020; if your
token can't hit /events/search, fall back to their venue/organizer endpoints for
specific Baltimore organizers you care about, or to their public iCal feeds where
available. Left as a single well-documented attempt point — adjust the endpoint
here if Eventbrite returns a 403 for your key.
"""
import requests

from config import EVENTBRITE_TOKEN, BALTIMORE_LAT, BALTIMORE_LNG, RADIUS_MILES
from dedupe import dedupe_key, distance_from_baltimore, auto_categorize

BASE_URL = "https://www.eventbriteapi.com/v3/events/search/"


def fetch():
    if not EVENTBRITE_TOKEN:
        print("[eventbrite] no EVENTBRITE_TOKEN set, skipping")
        return []

    headers = {"Authorization": f"Bearer {EVENTBRITE_TOKEN}"}
    params = {
        "location.latitude": BALTIMORE_LAT,
        "location.longitude": BALTIMORE_LNG,
        "location.within": f"{RADIUS_MILES}mi",
        "expand": "venue",
    }

    events = []
    resp = requests.get(BASE_URL, headers=headers, params=params, timeout=30)
    if resp.status_code != 200:
        print(f"[eventbrite] request failed: {resp.status_code} {resp.text[:200]}")
        return []

    for e in resp.json().get("events", []):
        title = e.get("name", {}).get("text", "")
        description = e.get("description", {}).get("text", "") or ""
        venue = e.get("venue") or {}
        venue_name = venue.get("name")
        lat = float(venue["latitude"]) if venue.get("latitude") else None
        lng = float(venue["longitude"]) if venue.get("longitude") else None
        start = e.get("start", {}).get("utc")
        end = e.get("end", {}).get("utc")

        if not start:
            continue

        events.append({
            "dedupe_key": dedupe_key(title, venue_name, start),
            "source": "eventbrite",
            "source_url": e.get("url"),
            "title": title,
            "description": description,
            "venue_name": venue_name,
            "address": venue.get("address", {}).get("localized_address_display"),
            "lat": lat,
            "lng": lng,
            "distance_from_baltimore_mi": distance_from_baltimore(lat, lng),
            "start_time": start,
            "end_time": end,
            "categories": auto_categorize(title, description),
            "is_recurring": False,
            "raw": e,
        })

    return events
