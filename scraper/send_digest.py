"""
Weekly email digest: for each subscribed profile, find events in the next 14
days with a match_score >= 0.6 that the profile hasn't already saved/attended/
dismissed, and email them via Resend. Run on its own GitHub Actions schedule
(see .github/workflows/digest.yml), separate from the scrape job so a slow
scrape never delays mail.
"""
import os
from datetime import datetime, timedelta, timezone

import requests
from supabase import create_client

from config import SUPABASE_URL, SUPABASE_SERVICE_KEY

RESEND_API_KEY = os.environ.get("RESEND_API_KEY")
FROM_EMAIL = os.environ.get("DIGEST_FROM_EMAIL", "digest@yourdomain.com")
MATCH_THRESHOLD = 0.6


def match_score(event_categories: list[str], weights: dict) -> float:
    if not event_categories:
        return 0.3
    scores = [weights.get(c, 0) for c in event_categories]
    return sum(scores) / len(scores) if scores else 0.3


def build_digest_html(events: list[dict]) -> str:
    items = "".join(
        f'<li><a href="{e["source_url"]}">{e["title"]}</a> — '
        f'{e["start_time"][:10]}{" @ " + e["venue_name"] if e.get("venue_name") else ""}</li>'
        for e in events
    )
    return f"<p>New events matched to your interests:</p><ul>{items}</ul>"


def send_email(to_email: str, html: str):
    resp = requests.post(
        "https://api.resend.com/emails",
        headers={"Authorization": f"Bearer {RESEND_API_KEY}", "Content-Type": "application/json"},
        json={
            "from": FROM_EMAIL,
            "to": [to_email],
            "subject": "Your Baltimore Side Quest picks this week",
            "html": html,
        },
        timeout=30,
    )
    if resp.status_code >= 300:
        print(f"[digest] send failed for {to_email}: {resp.status_code} {resp.text[:200]}")


def main():
    if not (SUPABASE_URL and SUPABASE_SERVICE_KEY and RESEND_API_KEY):
        print("[digest] missing SUPABASE_URL / SUPABASE_SERVICE_KEY / RESEND_API_KEY, aborting")
        return

    client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

    now = datetime.now(timezone.utc)
    horizon = (now + timedelta(days=14)).isoformat()
    events = client.table("events").select("*") \
        .gte("start_time", now.isoformat()).lte("start_time", horizon).execute().data

    profiles = client.table("profiles").select("*").eq("email_subscribed", True).execute().data

    for profile in profiles:
        if not profile.get("email"):
            continue

        seen_ids = {
            i["event_id"] for i in
            client.table("interactions").select("event_id").eq("profile_id", profile["id"]).execute().data
        }
        weights = profile.get("category_weights") or {}

        candidates = [e for e in events if e["id"] not in seen_ids]
        scored = [(e, match_score(e["categories"], weights)) for e in candidates]
        top = [e for e, score in scored if score >= MATCH_THRESHOLD]
        top.sort(key=lambda e: e["start_time"])

        if not top:
            continue

        send_email(profile["email"], build_digest_html(top[:10]))
        print(f"[digest] sent {len(top[:10])} events to {profile['email']}")


if __name__ == "__main__":
    main()
