import sys
from datetime import datetime, timezone

from config import RADIUS_MILES
from db import get_store
from sources import meetup, tribe_events, ical_feeds

# Register additional scraped sources here as you build them.
# Eventbrite was removed: its public search API was shut down (every request 404s).
# To add a site that uses "The Events Calendar" WordPress plugin, or any public
# iCal feed, just add it to TRIBE_SOURCES / ICAL_SOURCES in config.py.
SOURCES = [
    tribe_events,
    ical_feeds,
    meetup,  # skips itself unless MEETUP_API_KEY is set
]


def collect_all_events() -> list[dict]:
    all_events = []
    for source in SOURCES:
        try:
            found = source.fetch()
            print(f"[main] {source.__name__.split('.')[-1]}: {len(found)} events")
            all_events.extend(found)
        except Exception as e:
            print(f"[main] source {source.__name__} raised: {e}")
    return all_events


def within_radius(event: dict) -> bool:
    # Events with unknown lat/lng (e.g. from HTML sources without geocoding) are
    # kept by default rather than dropped — better to show an unverified-distance
    # event than silently lose it. Tighten this if that gets noisy.
    dist = event.get("distance_from_baltimore_mi")
    return dist is None or dist <= RADIUS_MILES


def merge_duplicates(events: list[dict]) -> list[dict]:
    rows = {}
    for e in events:
        row = dict(e, id=e["dedupe_key"])
        prev = rows.get(row["dedupe_key"])
        if prev:  # same event from two calendars: keep one, merge their tags
            row["categories"] = sorted(set(prev["categories"]) | set(row["categories"]))
        rows[row["dedupe_key"]] = row
    return list(rows.values())


def build_snapshot(new_events: list[dict], previous: list[dict]) -> list[dict]:
    """This run's events, plus last run's upcoming events from any source that came back
    empty this time (a site being down for a day shouldn't wipe its listings)."""
    fresh = merge_duplicates(new_events)
    seen_sources = {e["source"] for e in new_events}
    have = {e["id"] for e in fresh}
    kept = [e for e in previous if e.get("source") not in seen_sources and e["id"] not in have]
    if kept:
        print(f"[main] kept {len(kept)} events from sources that returned nothing this run")
    return fresh + kept


def main():
    store = get_store()
    events = [e for e in collect_all_events() if within_radius(e)]
    if store is None:
        print("[main] FIREBASE_SERVICE_ACCOUNT not set — printing results instead of saving")
        for e in events[:10]:
            print(f"  - {e['title']} ({e['source']}) @ {e['start_time']}")
        print(f"[main] {len(events)} total events found (dry run, nothing written)")
        return

    now = datetime.now(timezone.utc).isoformat()
    previous = store.upcoming_events(now)
    snapshot = [e for e in build_snapshot(events, previous) if e["start_time"] >= now]
    n = store.replace_events(snapshot)
    print(f"[main] saved {n} upcoming events (past events drop off automatically)")


if __name__ == "__main__":
    sys.exit(main())
