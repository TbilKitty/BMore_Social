"""
ONE-TIME: copy subscribers, quiz profiles and saved events from the old Supabase
database into Firestore. Events themselves are not copied — the next scrape
rebuilds them.

Run it from GitHub: Actions → "Move data from Supabase (one time)" → Run workflow.
Needs secrets SUPABASE_URL, SUPABASE_SERVICE_KEY (old) and FIREBASE_SERVICE_ACCOUNT (new).
Safe to run more than once: it overwrites the same documents.
Reading still works while Supabase is in read-only mode.
"""
import os
import sys
from datetime import datetime, timedelta, timezone

import requests

from config import HISTORY_DAYS
from db import FirestoreStore

URL = (os.environ.get("SUPABASE_URL") or "").rstrip("/")
KEY = os.environ.get("SUPABASE_SERVICE_KEY") or ""
PAGE = 1000


def fetch(table: str, params: dict) -> list[dict]:
    rows, offset = [], 0
    headers = {"apikey": KEY, "Authorization": f"Bearer {KEY}"}
    while True:
        resp = requests.get(f"{URL}/rest/v1/{table}", headers=headers, timeout=60,
                            params={**params, "limit": PAGE, "offset": offset})
        if resp.status_code == 402:
            sys.exit("Supabase is blocking API reads for going over the limit (402). "
                     "Export the push_subscribers table as CSV from the Supabase dashboard instead.")
        if resp.status_code >= 300:
            sys.exit(f"Supabase {table}: {resp.status_code} {resp.text[:300]}")
        batch = resp.json()
        rows += batch
        if len(batch) < PAGE:
            return rows
        offset += PAGE


def write_all(client, collection: str, docs: dict[str, dict]) -> None:
    items = list(docs.items())
    for i in range(0, len(items), 400):
        batch = client.batch()
        for doc_id, data in items[i:i + 400]:
            batch.set(client.collection(collection).document(doc_id), data)
        batch.commit()
    print(f"[migrate] {collection}: {len(docs)} documents")


def main():
    if not (URL and KEY and os.environ.get("FIREBASE_SERVICE_ACCOUNT")):
        sys.exit("Need SUPABASE_URL, SUPABASE_SERVICE_KEY and FIREBASE_SERVICE_ACCOUNT secrets.")
    client = FirestoreStore().c
    since = (datetime.now(timezone.utc) - timedelta(days=HISTORY_DAYS)).isoformat()

    # Phone subscribers, with their recent instant-alert history folded in
    subs = {s["id"]: s for s in fetch("push_subscribers", {"select": "*", "order": "id"})}
    log = fetch("push_log", {"select": "subscriber_id,title_key,sent_at,events(dedupe_key)", "order": "id",
                             "kind": "in.(instant,seeded)", "sent_at": f"gte.{since}"})
    docs = {}
    for sid, s in subs.items():
        mine = [r for r in log if r["subscriber_id"] == sid]
        docs[sid] = {
            **{k: s.get(k) for k in ("topic", "manage_token", "categories", "free_only", "radius_mi", "instant",
                                     "created_at", "updated_at", "last_weekly_at", "instant_seeded_at",
                                     "last_test_at", "signup_fingerprint")},
            "paused": bool(s.get("paused")), "is_owner": bool(s.get("is_owner")),
            "instant_sent": {r["events"]["dedupe_key"]: r["sent_at"] for r in mine if r.get("events")},
            "instant_titles": {r["title_key"]: r["sent_at"] for r in mine if r.get("title_key")},
        }
    write_all(client, "push_subscribers", docs)

    # Quiz profiles (keyed by the visitor's cookie id) and their saved / attended / not-for-me picks
    profiles = fetch("profiles", {"select": "*", "order": "id"})
    by_id = {p["id"]: p["anon_id"] for p in profiles if p.get("anon_id")}
    write_all(client, "profiles", {p["anon_id"]: {
        "anon_id": p["anon_id"], "email": p.get("email"), "email_subscribed": bool(p.get("email_subscribed")),
        "category_weights": p.get("category_weights") or {}, "radius_mi": p.get("radius_mi") or 35,
        "created_at": p.get("created_at")} for p in profiles if p.get("anon_id")})

    inter = fetch("interactions", {"select": "profile_id,event_id,status,created_at,events(dedupe_key,categories)",
                                   "order": "id"})
    idocs = {}
    for r in inter:
        anon = by_id.get(r["profile_id"])
        if not anon:
            continue
        ev = r.get("events") or {}
        eid = ev.get("dedupe_key") or r["event_id"]
        idocs[f"{anon}__{eid}"] = {"profile_id": anon, "event_id": eid, "status": r["status"],
                                   "categories": ev.get("categories") or [], "created_at": r.get("created_at")}
    write_all(client, "interactions", idocs)
    print("[migrate] done. Next: run the 'Scrape events' workflow once to fill in events.")


if __name__ == "__main__":
    main()
