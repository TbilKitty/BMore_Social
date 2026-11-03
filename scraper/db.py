"""
Storage for Baltimore Side Quest: Google Cloud Firestore (free tier).

Layout (kept deliberately tiny so it never outgrows the free 1 GiB):

  snapshot/{chunk-N}       the upcoming events list, rewritten by each scrape, ~300 events per doc.
                           There is no ever-growing events table: old events simply drop out.
  push_subscribers/{id}    one doc per phone subscriber. Instant-alert history lives inside the
                           doc (instant_sent / instant_titles maps, pruned to 60 days).
  profiles/{anon_id}       quiz answers per visitor
  interactions/{anon_id}__{event_id}   Save / Attended / Not for me
  meta/ntfy-YYYY-MM-DD     how many push messages went out that day (ntfy free cap)

Credentials: the FIREBASE_SERVICE_ACCOUNT secret holds the service-account JSON key.
"""
import json
import os
from datetime import datetime, timezone

CHUNK_SIZE = 300
DESC_CHARS = 400


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def compact(e: dict) -> dict:
    """What the site and alerts need from an event, nothing more."""
    raw = e.get("raw") or {}
    return {
        "id": e.get("id") or e["dedupe_key"],
        "source": e.get("source"),
        "source_url": e.get("source_url"),
        "title": e.get("title"),
        "description": (e.get("description") or "")[:DESC_CHARS],
        "venue_name": e.get("venue_name"),
        "address": e.get("address"),
        "lat": e.get("lat"),
        "lng": e.get("lng"),
        "distance_from_baltimore_mi": e.get("distance_from_baltimore_mi"),
        "start_time": e["start_time"],
        "end_time": e.get("end_time"),
        "categories": e.get("categories") or [],
        "raw": {"local": bool(raw.get("local")), "all_day": bool(raw.get("all_day"))},
    }


class FirestoreStore:
    def __init__(self, client=None):
        if client is None:
            from google.cloud import firestore
            from google.oauth2 import service_account
            info = json.loads(os.environ["FIREBASE_SERVICE_ACCOUNT"])
            creds = service_account.Credentials.from_service_account_info(info)
            client = firestore.Client(project=info["project_id"], credentials=creds)
        self.c = client

    # ---------------------------------------------------------------- events
    def replace_events(self, events: list[dict]) -> int:
        events = sorted((compact(e) for e in events), key=lambda e: e["start_time"])
        chunks = [events[i:i + CHUNK_SIZE] for i in range(0, len(events), CHUNK_SIZE)] or [[]]
        col = self.c.collection("snapshot")
        old = {d.id for d in col.list_documents()}
        batch = self.c.batch()
        stamp = utc_now().isoformat()
        for n, chunk in enumerate(chunks):
            # Stored as one JSON string: a single un-indexed field, so a big list never hits index limits.
            batch.set(col.document(f"chunk-{n}"), {"events_json": json.dumps(chunk), "n": n, "updated_at": stamp})
        for doc_id in old - {f"chunk-{n}" for n in range(len(chunks))}:
            batch.delete(col.document(doc_id))
        batch.commit()
        return len(events)

    def upcoming_events(self, start_iso: str, end_iso: str | None = None) -> list[dict]:
        out = []
        for d in self.c.collection("snapshot").stream():
            out.extend(json.loads((d.to_dict() or {}).get("events_json") or "[]"))
        out = [e for e in out if e["start_time"] >= start_iso and (end_iso is None or e["start_time"] <= end_iso)]
        return sorted(out, key=lambda e: e["start_time"])

    # ----------------------------------------------------------- subscribers
    def active_subscribers(self) -> list[dict]:
        q = self.c.collection("push_subscribers").where("paused", "==", False)
        return [{**d.to_dict(), "id": d.id} for d in q.stream()]

    def subscriber_with_topic(self, topic: str) -> dict | None:
        for d in self.c.collection("push_subscribers").where("topic", "==", topic).limit(1).stream():
            return {**d.to_dict(), "id": d.id}
        return None

    def add_subscriber(self, row: dict) -> str:
        ref = self.c.collection("push_subscribers").document()
        ref.set(row)
        return ref.id

    def update_subscriber(self, sub_id: str, vals: dict) -> None:
        self.c.collection("push_subscribers").document(sub_id).update(vals)

    # ------------------------------------------------------- daily send count
    def sent_today(self) -> int:
        snap = self.c.collection("meta").document("ntfy-" + utc_now().strftime("%Y-%m-%d")).get()
        return int((snap.to_dict() or {}).get("count", 0)) if snap.exists else 0

    def add_sent(self, n: int) -> None:
        if n <= 0:
            return
        from google.cloud import firestore
        self.c.collection("meta").document("ntfy-" + utc_now().strftime("%Y-%m-%d")).set(
            {"count": firestore.Increment(n)}, merge=True)

    # ---------------------------------------------------------- email digest
    def email_profiles(self) -> list[dict]:
        q = self.c.collection("profiles").where("email_subscribed", "==", True)
        return [{**d.to_dict(), "id": d.id} for d in q.stream()]

    def interacted_event_ids(self, profile_id: str) -> set:
        q = self.c.collection("interactions").where("profile_id", "==", profile_id)
        return {(d.to_dict() or {}).get("event_id") for d in q.stream()}


class MemoryStore:
    """Same interface, in memory. Used by the tests and --dry-run without credentials."""

    def __init__(self, events=None, subs=None):
        self.events = [compact(e) for e in (events or [])]
        self.subs = {s["id"]: dict(s) for s in (subs or [])}
        self.count = 0
        self.profiles, self.interactions = {}, []

    def replace_events(self, events):
        self.events = sorted((compact(e) for e in events), key=lambda e: e["start_time"])
        return len(self.events)

    def upcoming_events(self, start_iso, end_iso=None):
        return [dict(e) for e in self.events
                if e["start_time"] >= start_iso and (end_iso is None or e["start_time"] <= end_iso)]

    def active_subscribers(self):
        return [dict(s) for s in self.subs.values() if not s.get("paused")]

    def subscriber_with_topic(self, topic):
        return next((dict(s) for s in self.subs.values() if s.get("topic") == topic), None)

    def add_subscriber(self, row):
        sid = f"s{len(self.subs)}"
        self.subs[sid] = {**row, "id": sid}
        return sid

    def update_subscriber(self, sub_id, vals):
        self.subs[sub_id].update(vals)

    def sent_today(self):
        return self.count

    def add_sent(self, n):
        self.count += n

    def email_profiles(self):
        return [p for p in self.profiles.values() if p.get("email_subscribed")]

    def interacted_event_ids(self, profile_id):
        return {i["event_id"] for i in self.interactions if i["profile_id"] == profile_id}


def get_store():
    """FirestoreStore when the secret is set, else None."""
    if not os.environ.get("FIREBASE_SERVICE_ACCOUNT"):
        return None
    return FirestoreStore()
