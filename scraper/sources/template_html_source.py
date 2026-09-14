"""
Template for scraping a local Baltimore events page that doesn't have an API
(e.g. Visit Baltimore's events calendar, BOPA, a specific venue's site).

Duplicate this file per site (e.g. visit_baltimore.py, bopa.py), then:
  1. Set SOURCE_NAME and LISTING_URL below.
  2. Open the site's events page, use your browser's inspector to find the CSS
     selector wrapping each event card, and update select_event_cards().
  3. Update parse_card() field-by-field for that site's markup.
  4. Register the new module in scraper/main.py's SOURCES list.

Selectors here are placeholders — I can't browse live sites from this
environment, so this file WILL 404-safe (returns []) until you fill in real
selectors, rather than silently scraping garbage.
"""
import requests
from bs4 import BeautifulSoup
from dateutil import parser as dateparser

from dedupe import dedupe_key, distance_from_baltimore, auto_categorize

SOURCE_NAME = "template_html_source"
LISTING_URL = "https://example.com/events"  # <-- replace with real events page

# CSS selector for each event "card" on the listing page
CARD_SELECTOR = ".event-card"  # <-- replace


def select_event_cards(soup: BeautifulSoup):
    return soup.select(CARD_SELECTOR)


def parse_card(card) -> dict | None:
    try:
        title_el = card.select_one(".event-title")  # <-- replace
        link_el = card.select_one("a")               # <-- replace
        date_el = card.select_one(".event-date")      # <-- replace
        venue_el = card.select_one(".event-venue")    # <-- replace

        if not (title_el and link_el and date_el):
            return None

        title = title_el.get_text(strip=True)
        source_url = link_el.get("href")
        start_time = dateparser.parse(date_el.get_text(strip=True)).isoformat()
        venue_name = venue_el.get_text(strip=True) if venue_el else None

        return {
            "dedupe_key": dedupe_key(title, venue_name, start_time),
            "source": SOURCE_NAME,
            "source_url": source_url,
            "title": title,
            "description": None,
            "venue_name": venue_name,
            "address": None,
            "lat": None,
            "lng": None,
            "distance_from_baltimore_mi": distance_from_baltimore(None, None),
            "start_time": start_time,
            "end_time": None,
            "categories": auto_categorize(title),
            "is_recurring": False,
            "raw": {"html": str(card)[:2000]},
        }
    except Exception as e:
        print(f"[{SOURCE_NAME}] failed to parse a card: {e}")
        return None


def fetch():
    if LISTING_URL == "https://example.com/events":
        print(f"[{SOURCE_NAME}] not configured yet (placeholder URL), skipping")
        return []

    resp = requests.get(LISTING_URL, timeout=30, headers={"User-Agent": "BaltimoreSideQuest/1.0"})
    if resp.status_code != 200:
        print(f"[{SOURCE_NAME}] request failed: {resp.status_code}")
        return []

    soup = BeautifulSoup(resp.text, "html.parser")
    events = [parse_card(c) for c in select_event_cards(soup)]
    return [e for e in events if e]
