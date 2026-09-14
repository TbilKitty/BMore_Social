import sys
from datetime import datetime, timezone

from supabase import create_client

from config import SUPABASE_URL, SUPABASE_SERVICE_KEY, RADIUS_MILES
from sources import eventbrite, meetup, template_html_source

# Register additional scraped sources here as you build them
# (e.g. from sources import visit_baltimore, bopa)
SOURCES = [
    eventbrite,
    meetup,
    template_html_source,  # inert until configured — see its module docstring
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


def upsert_events(client, events: list[dict]):
    if not events:
        print("[main] no events to upsert")
        return

    now = datetime.now(timezone.utc).isoformat()
    rows = []
    for e in events:
        row = dict(e)
        row["last_seen_at"] = now
        rows.append(row)

    # Upsert on dedupe_key: re-scraping the same event updates last_seen_at and
    # any changed fields (time moved, description edited) without duplicating it.
    result = client.table("events").upsert(rows, on_conflict="dedupe_key").execute()
    print(f"[main] upserted {len(result.data)} events")


def main():
    if not (SUPABASE_URL and SUPABASE_SERVICE_KEY):
        print("[main] SUPABASE_URL / SUPABASE_SERVICE_KEY not set — printing results instead of upserting")
        events = [e for e in collect_all_events() if within_radius(e)]
        for e in events[:10]:
            print(f"  - {e['title']} ({e['source']}) @ {e['start_time']}")
        print(f"[main] {len(events)} total events found (dry run, nothing written)")
        return

    client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
    events = [e for e in collect_all_events() if within_radius(e)]
    upsert_events(client, events)


if __name__ == "__main__":
    sys.exit(main())
