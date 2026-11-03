"""Offline tests: python -m pytest tests  (run from the scraper folder)."""
import json
import os
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import dedupe
import main as scraper_main
from db import MemoryStore, compact
import push_alerts as pa
from ical import parse_ics
from sources import tribe_events

NOW = datetime.now(timezone.utc)


def iso(days, hour=23):
    return (NOW + timedelta(days=days)).replace(hour=hour, minute=0, second=0, microsecond=0)


# ------------------------------------------------------------------- tagging
def test_tagging_free_jazz_and_exclusions():
    c = dedupe.auto_categorize("Jazz Jam at Cat's Eye", "In-person, Indoor, No-cover")
    assert "jazz_blues" in c and "free" in c
    c = dedupe.auto_categorize("Gluten-free bake sale", "free parking available")
    assert "free" not in c
    c = dedupe.auto_categorize("The People's Pantry - Lexington Market", "fresh food", ["food_markets"])
    assert "food_markets" not in c
    c = dedupe.auto_categorize("Hampden Porchfest", "live music on porches all afternoon")
    assert {"live_music", "popup"} <= set(c)
    assert "live_music" not in dedupe.auto_categorize("Husband and wife cooking class", "")
    assert "free" in dedupe.auto_categorize("Concert", "", cost="Free")
    assert "free" not in dedupe.auto_categorize("Concert", "free drinks", cost="$15")


# -------------------------------------------------------------- tribe source
class FakeResp:
    def __init__(self, status, payload=None, text=""):
        self.status_code, self._payload, self.text = status, payload, text or json.dumps(payload or {})

    def json(self):
        return self._payload


def tribe_payload():
    s = iso(3).strftime("%Y-%m-%d %H:%M:%S")
    return {"total_pages": 1, "events": [
        {"id": 1, "title": "Free Jazz in the Park &amp; Friends", "description": "<p>Bring a chair</p>",
         "url": "https://x/1", "utc_start_date": s, "utc_end_date": s, "cost": "Free", "all_day": False,
         "venue": {"venue": "Patterson Park", "address": "27 S Patterson Park Ave", "city": "Baltimore",
                   "state": "MD", "zip": "21231"},
         "categories": [{"name": "Concert"}], "tags": []},
        {"id": 2, "title": "Big Band Night", "description": "", "url": "https://x/2", "utc_start_date": s,
         "cost": "$20", "venue": {"venue": "Blues Alley", "city": "Washington", "state": "DC", "zip": "20007"}},
        {"id": 3, "title": "", "url": "https://x/3", "utc_start_date": s},  # no title → dropped
    ]}


def test_tribe_rest(monkeypatch):
    monkeypatch.setattr(tribe_events.requests, "get", lambda *a, **k: FakeResp(200, tribe_payload()))
    src = {"name": "bja", "base_url": "https://b", "tags": ["jazz_blues", "live_music"], "local": False}
    evs = tribe_events.fetch_rest(src)
    assert len(evs) == 2
    first = evs[0]
    assert first["title"] == "Free Jazz in the Park & Friends"
    assert first["description"] == "Bring a chair"
    assert {"jazz_blues", "free"} <= set(first["categories"])
    assert first["start_time"].endswith("+00:00")
    assert pa.is_nearby(first) and not pa.is_nearby(evs[1], 35)  # DC show never counts as nearby


ICS = """BEGIN:VCALENDAR
BEGIN:VEVENT
UID:abc
DTSTART;TZID=America/New_York:{d}T190000
DTEND;TZID=America/New_York:{d}T210000
SUMMARY:Night Market\\, Station North
DESCRIPTION:Pop-up food vendors and a DJ. Free 
 entry.
LOCATION:Station North\\, Baltimore\\, MD 21202
URL:https://y/1
END:VEVENT
BEGIN:VEVENT
UID:old
DTSTART:20200101T120000Z
SUMMARY:Past event
END:VEVENT
END:VCALENDAR"""


def test_ical_fallback(monkeypatch):
    d = (NOW + timedelta(days=4)).strftime("%Y%m%d")
    text = ICS.format(d=d)
    parsed = parse_ics(text)
    assert parsed[0]["summary"] == "Night Market, Station North"
    assert parsed[0]["description"] == "Pop-up food vendors and a DJ. Free entry."
    monkeypatch.setattr(tribe_events.requests, "get", lambda *a, **k: FakeResp(200, text=text))
    evs = tribe_events.fetch_ical({"name": "cal", "base_url": "https://y", "tags": [], "local": True})
    assert len(evs) == 1  # past event skipped
    assert {"food_markets", "popup", "free"} <= set(evs[0]["categories"])


def test_rest_missing_falls_back(monkeypatch):
    calls = []

    def fake_get(url, **k):
        calls.append(url)
        if "wp-json" in url:
            return FakeResp(404, text='{"code":"rest_no_route"}')
        return FakeResp(200, text=ICS.format(d=(NOW + timedelta(days=2)).strftime("%Y%m%d")))
    monkeypatch.setattr(tribe_events.requests, "get", fake_get)
    monkeypatch.setattr(tribe_events, "TRIBE_SOURCES", [{"name": "s", "base_url": "https://s", "tags": [], "local": True}])
    assert len(tribe_events.fetch()) == 1 and any("ical=1" in c for c in calls)


# -------------------------------------------------------------------- alerts
def ev(i, title, cats, days=2, venue="Venue", address="Baltimore, MD 21201", dist=None, local=False):
    return {"id": f"id{i}", "title": title, "categories": cats, "start_time": iso(days).isoformat(),
            "venue_name": venue, "address": address, "distance_from_baltimore_mi": dist,
            "source_url": f"https://e/{i}", "description": "desc", "raw": {"local": local}}


EVENTS = [
    ev(1, "Free Jazz Jam – Nov 5", ["jazz_blues", "live_music", "free"]),
    ev(2, "Free Jazz Jam – Nov 12", ["jazz_blues", "live_music", "free"], days=9),  # same series
    ev(3, "Arena rock tour", ["live_music"]),
    ev(4, "Pop-up brass band", ["live_music", "popup"]),
    ev(5, "Saturday Farmers Market", ["food_markets"]),
    ev(6, "Museum lecture", ["culture", "free"]),
    ev(7, "Blues in Columbia", ["jazz_blues"], address="Columbia, MD 21044"),     # outer ring
    ev(8, "Car show", ["car_shows"]),
    ev(9, "Blues at Caton Castle", ["jazz_blues"], dist=4.2),
    ev(11, "Trail hike", ["outdoor_recreation"], dist=25),
]
ME = {"id": "me", "topic": "t-me", "manage_token": "tok", "categories": ["jazz_blues", "live_music", "food_markets",
      "culture"], "radius_mi": 10, "instant": True, "is_owner": True, "free_only": False}


def test_distance_rings():
    assert not pa.is_nearby(EVENTS[6], 10) and pa.is_nearby(EVENTS[6], 20)
    assert not pa.is_nearby(EVENTS[9], 20) and pa.is_nearby(EVENTS[9], 35)
    assert not pa.is_nearby({"address": "Blues Alley, Washington, DC 20007"}, 35)
    assert pa.is_nearby({"address": "861 Washington Blvd, Baltimore, MD 21230"}, 5)


def test_matching_per_person():
    outdoorsy = {"categories": ["outdoor_recreation", "car_shows"], "radius_mi": 35}
    assert [e["id"] for e in EVENTS if pa.matches(e, outdoorsy)] == ["id8", "id11"]
    free_culture = {"categories": ["culture"], "radius_mi": 10, "free_only": True}
    assert [e["id"] for e in EVENTS if pa.matches(e, free_culture)] == ["id6"]


def test_instant_picks():
    ids = [e["id"] for e in pa.pick_instant(EVENTS, ME, set(), set())]
    assert ids[0] == "id1" and set(ids) == {"id1", "id4", "id5", "id9"}   # id2 = repeat series, id3 paid arena
    k = pa.title_key(EVENTS[0])
    assert {e["id"] for e in pa.pick_instant(EVENTS, ME, {"id1"}, {k})} == {"id4", "id5", "id9"}


def test_messages():
    m = pa.instant_message(EVENTS[0], ME)
    assert m["title"].startswith("FREE jazz/blues:") and m["priority"] == 4 and m["click"] == "https://e/1"
    assert m["actions"][0]["url"].endswith("/alerts/manage?token=tok")
    assert pa.instant_message(EVENTS[3], ME)["title"].startswith("Pop-up live music:")
    w = pa.weekly_message([e for e in EVENTS if pa.matches(e, ME)], ME)
    assert w["title"] == "Your Baltimore week: 7 picks, 3 free"
    assert w["message"].startswith("🎷 Jazz & blues\n• FREE") and "Car show" not in w["message"]
    assert len(w["message"].encode()) <= 3800 and len(w["actions"]) == 2
    many = [ev(100 + i, f"Show number {chr(65 + i % 26)}{i}", ["live_music"], days=1 + i % 7) for i in range(80)]
    big = pa.weekly_message(many, {**ME, "categories": ["live_music"]})
    assert "more on the site" in big["message"] and len(big["message"].encode()) <= 3800


# ---------------------------------------------------------------- fake db
def FakeClient(events, subs):
    return MemoryStore(events, subs)


def capture(monkeypatch):
    sent = []
    monkeypatch.setattr(pa, "in_quiet_hours", lambda: False)
    monkeypatch.setattr(pa.Sender, "send", lambda self, topic, msg: (sent.append((topic, msg)), True)[1]
                        if self.remaining > 0 and not setattr(self, "remaining", self.remaining - 1) else False)
    return sent


def test_instant_flow(monkeypatch):
    sent = capture(monkeypatch)
    monkeypatch.setattr(pa, "NTFY_TOPIC", None)
    pub = {"id": "p1", "topic": "t-p1", "manage_token": "x", "categories": ["jazz_blues"], "radius_mi": 10,
           "instant": True, "paused": False}
    client = FakeClient(list(EVENTS), [dict(ME, paused=False), pub])
    pa.run_instant(client, dry_run=False)
    assert [t for t, _ in sent] == ["t-me"] and "alerts are on" in sent[0][1]["title"]  # owner hello, public silent
    sent.clear()
    pa.run_instant(client, dry_run=False)
    assert sent == []
    client.events.append(compact(ev(10, "Free Blues Picnic", ["jazz_blues", "free"], days=5)))
    pa.run_instant(client, dry_run=False)
    assert sorted(t for t, _ in sent) == ["t-me", "t-p1"]
    sent.clear()
    client.events += [compact(ev(20 + i, f"Pop-up show {chr(65 + i)}", ["live_music", "popup"])) for i in range(8)]
    pa.run_instant(client, dry_run=False)
    assert len(sent) == 1 and sent[0][1]["title"].startswith("8 new picks")   # bundled; jazz-only person skipped


def test_weekly_due_and_budget(monkeypatch):
    sent = capture(monkeypatch)
    monkeypatch.setattr(pa, "NTFY_TOPIC", None)
    monkeypatch.setattr(pa, "NTFY_DAILY_LIMIT", 3)
    long_ago = (NOW - timedelta(days=8)).isoformat()
    recent = (NOW - timedelta(days=2)).isoformat()
    subs = [dict(ME, paused=False, last_weekly_at=recent)] + [
        {"id": f"s{i}", "topic": f"t{i}", "manage_token": f"m{i}", "categories": ["jazz_blues"], "radius_mi": 10,
         "paused": i == 4, "last_weekly_at": long_ago if i % 2 else None} for i in range(6)]
    client = FakeClient(list(EVENTS), subs)
    pa.run_weekly(client, dry_run=False)
    assert len(sent) == 3 and "t-me" not in [t for t, _ in sent] and "t4" not in [t for t, _ in sent]
    first_batch = {t for t, _ in sent}
    sent.clear()
    client.count = 0                       # a new day
    pa.run_weekly(client, dry_run=False)
    assert {t for t, _ in sent} == {"t0", "t1", "t2", "t3", "t5"} - first_batch   # the rest, no repeats


def test_quiet_hours():
    tz = pa.LOCAL
    assert pa.in_quiet_hours(datetime(2026, 11, 2, 23, 0, tzinfo=tz))
    assert pa.in_quiet_hours(datetime(2026, 11, 2, 6, 30, tzinfo=tz))
    assert not pa.in_quiet_hours(datetime(2026, 11, 2, 12, 0, tzinfo=tz))


def test_sender_paces_after_burst(monkeypatch):
    naps = []
    monkeypatch.setattr(pa, "NTFY_BURST", 2)
    monkeypatch.setattr(pa.requests, "post", lambda *a, **k: FakeResp(200, {}))
    s = pa.Sender(0, dry_run=False, sleep=naps.append)
    for _ in range(4):
        s.send("t", {"title": "x", "message": "y"})
    assert naps == [pa.NTFY_PACE_SECONDS] * 2


def test_history_lives_on_subscriber(monkeypatch):
    capture(monkeypatch)
    monkeypatch.setattr(pa, "NTFY_TOPIC", None)
    client = FakeClient(list(EVENTS), [dict(ME, paused=False)])
    pa.run_instant(client, dry_run=False)
    sub = client.subs["me"]
    assert sub["instant_seeded_at"] and "id1" in sub["instant_sent"] and client.count == 1


def test_snapshot_keeps_listings_from_a_source_that_was_down():
    old = [dict(compact(ev(1, "Old jazz", ["jazz_blues"], days=3)), source="bja"),
           dict(compact(ev(2, "Old market", ["food_markets"], days=3)), source="markets")]
    new = [dict(ev(3, "New market", ["food_markets"]), source="markets", dedupe_key="k3"),
           dict(ev(3, "New market", ["culture"]), source="other", dedupe_key="k3")]
    snap = scraper_main.build_snapshot(new, old)
    ids = {e["id"] for e in snap}
    assert ids == {"k3", "id1"}                       # bja was down → kept; markets refreshed
    assert set(next(e for e in snap if e["id"] == "k3")["categories"]) == {"food_markets", "culture"}
    store = MemoryStore()
    store.replace_events(snap)
    assert [e["id"] for e in store.upcoming_events(NOW.isoformat())] and "raw" in store.events[0]


# ------------------------------------------------- Firestore adapter (fake SDK)
class _Snap:
    def __init__(self, id, data): self.id, self._d = id, data
    exists = property(lambda self: self._d is not None)
    def to_dict(self): return None if self._d is None else dict(self._d)


class _Doc:
    def __init__(self, db, col, id): self.db, self.col, self.id = db, col, id
    def set(self, data, merge=False): self.db.setdefault(self.col, {})[self.id] = data
    def update(self, vals): self.db[self.col][self.id].update(vals)
    def delete(self): self.db.get(self.col, {}).pop(self.id, None)
    def get(self): return _Snap(self.id, self.db.get(self.col, {}).get(self.id))


class _Col:
    def __init__(self, db, name, filters=()): self.db, self.name, self.filters = db, name, list(filters)
    def document(self, id=None): return _Doc(self.db, self.name, id or f"auto{len(self.db.get(self.name, {}))}")
    def list_documents(self): return [_Doc(self.db, self.name, k) for k in self.db.get(self.name, {})]
    def where(self, f, op, v): return _Col(self.db, self.name, self.filters + [(f, v)])
    def limit(self, n): return self
    def stream(self):
        return [_Snap(k, d) for k, d in self.db.get(self.name, {}).items()
                if all(d.get(f) == v for f, v in self.filters)]


class _Batch:
    def __init__(self): self.ops = []
    def set(self, ref, data): self.ops.append(lambda: ref.set(data))
    def delete(self, ref): self.ops.append(ref.delete)
    def commit(self): [op() for op in self.ops]


class _Client:
    def __init__(self): self.db = {}
    def collection(self, name): return _Col(self.db, name)
    def batch(self): return _Batch()


def test_firestore_store_roundtrip(monkeypatch):
    from db import FirestoreStore
    import db as dbmod
    monkeypatch.setattr(dbmod, "CHUNK_SIZE", 3)
    st = FirestoreStore(_Client())
    st.replace_events([ev(i, f"E{i}", ["culture"], days=1 + i) for i in range(7)])
    assert sorted(st.c.db["snapshot"]) == ["chunk-0", "chunk-1", "chunk-2"]
    assert len(st.upcoming_events(NOW.isoformat())) == 7
    st.replace_events([ev(1, "Only", ["culture"])])
    assert list(st.c.db["snapshot"]) == ["chunk-0"]              # stale chunks removed
    sid = st.add_subscriber({"topic": "t", "paused": False})
    st.update_subscriber(sid, {"instant": True})
    assert st.subscriber_with_topic("t")["instant"] and len(st.active_subscribers()) == 1
