"""
Any public iCal (.ics) calendar listed in config.ICAL_SOURCES — for example a
venue's public Google Calendar ("Settings → Integrate calendar → Public address
in iCal format"). Add a source by appending to ICAL_SOURCES; no code needed.
"""
from config import ICAL_SOURCES
from sources.tribe_events import fetch_ical


def fetch():
    events = []
    for src in ICAL_SOURCES:
        try:
            found = fetch_ical(src, src["url"])
            print(f"[ical] {src['name']}: {len(found)} events")
            events.extend(found)
        except Exception as ex:
            print(f"[ical] {src['name']} failed: {type(ex).__name__}: {ex}")
    return events
