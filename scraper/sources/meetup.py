"""
Meetup source. Meetup's public API now requires OAuth2 (client credentials flow
won't work for GraphQL search; you need a Meetup Pro OAuth consumer + a member
token). This is the friction point most likely to need hand-fixing:

  1. Create an OAuth client at https://www.meetup.com/api/oauth/list/
  2. Follow Meetup's docs to get a long-lived access token for your account
  3. Set MEETUP_API_KEY in repo secrets to that access token

Uses Meetup's GraphQL API (recommended over the old REST endpoints, which are
being sunset).
"""
import requests

from config import MEETUP_API_KEY, BALTIMORE_LAT, BALTIMORE_LNG, RADIUS_MILES
from dedupe import dedupe_key, distance_from_baltimore, auto_categorize

GRAPHQL_URL = "https://api.meetup.com/gql"

QUERY = """
query($lat: Float!, $lon: Float!, $radius: Int!) {
  keywordSearch(filter: {
    query: "",
    lat: $lat, lon: $lon, radius: $radius,
    source: EVENTS
  }) {
    edges {
      node {
        result {
          ... on Event {
            title
            description
            eventUrl
            dateTime
            endTime
            venue { name address lat lng }
          }
        }
      }
    }
  }
}
"""


def fetch():
    if not MEETUP_API_KEY:
        print("[meetup] no MEETUP_API_KEY set, skipping")
        return []

    headers = {"Authorization": f"Bearer {MEETUP_API_KEY}", "Content-Type": "application/json"}
    variables = {"lat": BALTIMORE_LAT, "lon": BALTIMORE_LNG, "radius": RADIUS_MILES}

    resp = requests.post(GRAPHQL_URL, headers=headers, json={"query": QUERY, "variables": variables}, timeout=30)
    if resp.status_code != 200:
        print(f"[meetup] request failed: {resp.status_code} {resp.text[:200]}")
        return []

    events = []
    edges = resp.json().get("data", {}).get("keywordSearch", {}).get("edges", [])
    for edge in edges:
        node = edge.get("node", {}).get("result", {})
        if not node or "title" not in node:
            continue

        title = node.get("title", "")
        description = node.get("description", "") or ""
        venue = node.get("venue") or {}
        start = node.get("dateTime")
        if not start:
            continue

        lat, lng = venue.get("lat"), venue.get("lng")

        events.append({
            "dedupe_key": dedupe_key(title, venue.get("name"), start),
            "source": "meetup",
            "source_url": node.get("eventUrl"),
            "title": title,
            "description": description,
            "venue_name": venue.get("name"),
            "address": venue.get("address"),
            "lat": lat,
            "lng": lng,
            "distance_from_baltimore_mi": distance_from_baltimore(lat, lng),
            "start_time": start,
            "end_time": node.get("endTime"),
            "categories": auto_categorize(title, description),
            "is_recurring": False,
            "raw": node,
        })

    return events
