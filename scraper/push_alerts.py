"""
Phone alerts for everyone who signed up on the website (/alerts), plus the
site owner's own feed (NTFY_TOPIC secret). Delivered through the free ntfy app.

  python push_alerts.py --mode weekly    # run daily: anyone due gets ONE roundup message (~every 7 days)
  python push_alerts.py --mode instant   # run after each scrape: heads-up pings for people who opted in
  python push_alerts.py --mode test      # one test message to the owner's NTFY_TOPIC
  add --dry-run to print instead of sending

The free ntfy.sh server allows a burst of ~60 messages, then about 1 every
10 seconds, with a daily cap. Sends are paced, stop at NTFY_DAILY_LIMIT, and
anyone not reached today is picked up by tomorrow's run. Set NTFY_TOKEN (a paid
ntfy plan) and raise NTFY_DAILY_LIMIT if the list outgrows that.

Storage: scraper/db.py (Firestore)
"""
import argparse
import re
import secrets
import sys
import time
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import requests

from config import (NTFY_SERVER, NTFY_TOKEN, NTFY_TOPIC, NTFY_DAILY_LIMIT,
                    NTFY_BURST, NTFY_PACE_SECONDS, SITE_URL, PERSONAL_RADIUS_MILES, PERSONAL_CATEGORIES,
                    NEARBY_PLACES, INSTANT_MAX_PER_RUN, PUBLIC_INSTANT_MAX, INSTANT_REPEAT_DAYS,
                    WEEKLY_DAYS_AHEAD, WEEKLY_EVERY_DAYS, DAYS_AHEAD, QUIET_HOURS, HISTORY_DAYS)
from db import get_store
from dedupe import normalize_title

LOCAL = ZoneInfo("America/New_York")
ZIP_NEAR = re.compile(r"\b(212[0-3]\d|2128[46]|21252|21090|21061|21043|21093|21117|21075|21076)\b")
FAR_AWAY = re.compile(r"washington,? d\.?c|, ?dc\b|\bd\.c\.|virginia|\bva \d{5}|pennsylvania|\bpa \d{5}|delaware")
OUTER_RING = re.compile(r"columbia,? md|annapolis|frederick,? md|laurel,? md|bel air|silver spring|westminster|"
                        r"severna park|odenton|eldersburg|abingdon|hunt valley|cockeysville|reisterstown|"
                        r"\b2(10[0-9]\d|11\d\d)\b")

# Interest → section of the roundup
SECTIONS = [
    ("jazz", "🎷 Jazz & blues", {"jazz_blues"}),
    ("music", "🎶 Live music & dance", {"live_music", "outdoor_music", "dance"}),
    ("food", "🍎 Food & markets", {"food_markets", "food_festivals"}),
    ("culture", "🎭 Culture & arts", {"culture", "arts", "unusual"}),
    ("outside", "🌳 Outdoors & family", {"outdoor_recreation", "bikes", "dog_friendly", "family_friendly", "car_shows"}),
]
ALL_INTERESTS = set().union(*(s[2] for s in SECTIONS))


# ----------------------------------------------------------------- matching
def cats(e) -> set:
    return set(e.get("categories") or [])


def is_nearby(e, radius: int = PERSONAL_RADIUS_MILES) -> bool:
    d = e.get("distance_from_baltimore_mi")
    if d is not None:
        return float(d) <= radius
    where = f"{e.get('address') or ''} {e.get('venue_name') or ''}".lower()
    if where.strip():
        if FAR_AWAY.search(where):
            return False
        if OUTER_RING.search(where):
            return radius >= 20
        if ZIP_NEAR.search(where) or any(re.search(r"\b" + re.escape(p) + r"\b", where) for p in NEARBY_PLACES):
            return True
        return radius >= 35  # somewhere in Maryland we can't place
    return bool((e.get("raw") or {}).get("local"))


def section_of(e, interests=None) -> str | None:
    c = cats(e) & (set(interests) if interests else ALL_INTERESTS)
    for key, _, members in SECTIONS:
        if c & members:
            return key
    return None


def matches(e, sub) -> bool:
    if not is_nearby(e, sub.get("radius_mi") or PERSONAL_RADIUS_MILES):
        return False
    if sub.get("free_only") and "free" not in cats(e):
        return False
    return section_of(e, sub.get("categories") or []) is not None


def wants_instant(e) -> bool:
    c = cats(e)
    if "jazz_blues" in c:
        return True
    if c & {"live_music", "outdoor_music"} and c & {"free", "popup"}:
        return True
    if "food_markets" in c:
        return True
    if "popup" in c and c & {"culture", "arts", "food_festivals", "unusual"}:
        return True
    return False


def title_key(e) -> str:
    # strip dates/numbers so "Jazz Jam – Nov 5" and "Jazz Jam – Nov 12" count as one series
    t = normalize_title(e["title"])
    t = re.sub(r"\b(jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\b|\d+", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def sort_key(e):
    return ("free" not in cats(e), e["start_time"])


# --------------------------------------------------------------- formatting
def when(e) -> str:
    start = datetime.fromisoformat(e["start_time"].replace("Z", "+00:00")).astimezone(LOCAL)
    day = start.strftime("%a %b ") + str(start.day)
    if (e.get("raw") or {}).get("all_day"):
        return day
    return f"{day} · {start.strftime('%I:%M %p').lstrip('0').replace(':00', '')}"


def one_line(e) -> str:
    free = "FREE · " if "free" in cats(e) else ""
    venue = f" @ {e['venue_name']}" if e.get("venue_name") else ""
    return f"• {free}{when(e)} — {e['title']}{venue}"


def manage_url(sub) -> str:
    return f"{SITE_URL}/alerts/manage?token={sub['manage_token']}"


def actions(sub) -> list[dict]:
    return [{"action": "view", "label": "See all events", "url": SITE_URL},
            {"action": "view", "label": "Change or stop alerts", "url": manage_url(sub)}]


def instant_message(e, sub) -> dict:
    c = cats(e)
    sec = section_of(e, sub.get("categories")) or "culture"
    label = {"jazz": "jazz/blues", "music": "live music", "food": "food market",
             "culture": "event", "outside": "event"}[sec]
    if "popup" in c:
        label = "pop-up " + label
    label = ("FREE " + label) if "free" in c else label[0].upper() + label[1:]
    lines = [when(e)]
    if e.get("venue_name"):
        lines.append(e["venue_name"])
    if e.get("description"):
        lines.append(e["description"][:180] + ("…" if len(e["description"]) > 180 else ""))
    return {"title": f"{label}: {e['title']}"[:250], "message": "\n".join(lines), "click": e.get("source_url"),
            "tags": ["free"] if "free" in c else [],
            "priority": 4 if ("free" in c and "jazz_blues" in c) else 3,
            "actions": actions(sub)[1:]}


def weekly_message(events: list[dict], sub) -> dict | None:
    """ONE notification per person per week (keeps us inside ntfy's free limits)."""
    seen, by_sec = set(), {k: [] for k, _, _ in SECTIONS}
    for e in sorted(events, key=lambda x: x["start_time"]):
        k = (title_key(e), e["start_time"][:10])
        if k in seen:
            continue
        seen.add(k)
        by_sec[section_of(e, sub.get("categories"))].append(e)
    total = sum(len(v) for v in by_sec.values())
    if not total:
        return None
    n_free = sum(1 for v in by_sec.values() for e in v if "free" in cats(e))
    per_section = max(3, 20 // max(1, sum(1 for v in by_sec.values() if v)))
    parts = []
    for key, heading, _ in SECTIONS:
        items = sorted(by_sec[key], key=sort_key)
        if not items:
            continue
        lines = [heading] + [one_line(e) for e in items[:per_section]]
        if len(items) > per_section:
            lines.append(f"  …+{len(items) - per_section} more on the site")
        parts.append("\n".join(lines))
    body = "\n\n".join(parts)
    if len(body.encode()) > 3800:  # ntfy turns >4 KB into an attachment
        body = body.encode()[:3790].decode("utf-8", "ignore").rsplit("\n", 1)[0] + "\n…more on the site"
    free_txt = f", {n_free} free" if n_free else ""
    return {"title": f"Your Baltimore week: {total} pick{'s' if total != 1 else ''}{free_txt}",
            "message": body, "tags": ["calendar"], "actions": actions(sub)}


# ------------------------------------------------------------------ sending
class Sender:
    """Paces messages for ntfy's rate limit and stops at the daily budget."""

    def __init__(self, sent_today: int, dry_run: bool, sleep=time.sleep):
        self.remaining = max(0, NTFY_DAILY_LIMIT - sent_today)
        self.count, self.dry_run, self.sleep = 0, dry_run, sleep

    def send(self, topic: str, msg: dict) -> bool:
        if self.remaining <= 0:
            return False
        if self.count >= NTFY_BURST and not self.dry_run:
            self.sleep(NTFY_PACE_SECONDS)
        self.count += 1
        self.remaining -= 1
        if self.dry_run:
            print(f"--- PUSH to {topic[:6]}… (dry run) ---\n{msg['title']}\n{msg['message']}\n")
            return True
        headers = {"Authorization": f"Bearer {NTFY_TOKEN}"} if NTFY_TOKEN else {}
        payload = {"topic": topic, **{k: v for k, v in msg.items() if v}}
        for attempt in range(3):
            resp = requests.post(NTFY_SERVER.rstrip("/"), json=payload, headers=headers, timeout=30)
            if resp.status_code == 429:  # rate limited: back off and retry
                self.sleep(30 * (attempt + 1))
                continue
            if resp.status_code >= 300:
                print(f"[push] ntfy error {resp.status_code}: {resp.text[:200]}")
                return False
            return True
        self.remaining = 0  # still limited after retries: stop for today
        return False


# ---------------------------------------------------------------------- data
def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_events(store, days: int) -> list[dict]:
    now = datetime.now(timezone.utc)
    return store.upcoming_events(now.isoformat(), (now + timedelta(days=days)).isoformat())


def ensure_owner(store, dry_run) -> None:
    """The NTFY_TOPIC secret becomes a subscriber (instant on, your interests)."""
    if not NTFY_TOPIC or dry_run or store.subscriber_with_topic(NTFY_TOPIC):
        return
    store.add_subscriber({
        "topic": NTFY_TOPIC, "manage_token": secrets.token_urlsafe(24), "categories": PERSONAL_CATEGORIES,
        "radius_mi": PERSONAL_RADIUS_MILES, "instant": True, "is_owner": True, "paused": False,
        "free_only": False, "created_at": now_iso(),
    })


def pruned(history: dict | None, cutoff: str) -> dict:
    return {k: v for k, v in (history or {}).items() if v >= cutoff}


# ------------------------------------------------------------------- weekly
def is_due(sub, now=None) -> bool:
    last = sub.get("last_weekly_at")
    if not last:
        return True
    now = now or datetime.now(timezone.utc)
    return now - datetime.fromisoformat(last.replace("Z", "+00:00")) >= timedelta(days=WEEKLY_EVERY_DAYS)


def run_weekly(store, dry_run: bool, sleep=time.sleep) -> int:
    ensure_owner(store, dry_run)
    subs = [s for s in store.active_subscribers() if is_due(s)]
    subs.sort(key=lambda s: (not s.get("is_owner"), s.get("last_weekly_at") or ""))  # owner, then longest-waiting
    events = load_events(store, WEEKLY_DAYS_AHEAD)
    sender = Sender(store.sent_today(), dry_run, sleep)
    done = skipped_budget = 0
    now = datetime.now(timezone.utc).isoformat()
    for sub in subs:
        msg = weekly_message([e for e in events if matches(e, sub)], sub)
        if msg is None:
            msg = {"title": "Quiet week", "message": "Nothing matched your interests in the next 8 days. "
                   "Try adding interests or widening your distance.", "tags": ["zzz"], "actions": actions(sub)}
        if not sender.send(sub["topic"], msg):
            if sender.remaining <= 0:
                skipped_budget = len(subs) - done
                break
            continue
        done += 1
        if not dry_run:
            store.update_subscriber(sub["id"], {"last_weekly_at": now})
            store.add_sent(1)
    print(f"[push] weekly: sent {done} of {len(subs)} due"
          + (f"; {skipped_budget} wait for tomorrow (daily limit)" if skipped_budget else ""))
    return 0


# ------------------------------------------------------------------ instant
def in_quiet_hours(now_local=None) -> bool:
    h = (now_local or datetime.now(LOCAL)).hour
    start, end = QUIET_HOURS
    return h >= start or h < end


def pick_instant(events, sub, sent_event_ids: set, recent_title_keys: set) -> list[dict]:
    picks, seen = [], set()
    for e in sorted(events, key=sort_key):
        if e["id"] in sent_event_ids or not wants_instant(e) or not matches(e, sub):
            continue
        k = title_key(e)
        if k in recent_title_keys or k in seen:
            continue
        seen.add(k)
        picks.append(e)
    return picks


def run_instant(store, dry_run: bool, sleep=time.sleep) -> int:
    if in_quiet_hours() and not dry_run:
        print("[push] quiet hours — new picks wait for the next daytime run")
        return 0
    ensure_owner(store, dry_run)
    subs = [s for s in store.active_subscribers() if s.get("instant")]
    if not subs:
        print("[push] nobody has instant alerts on")
        return 0
    events = load_events(store, DAYS_AHEAD)
    now = datetime.now(timezone.utc)
    keep_since = (now - timedelta(days=HISTORY_DAYS)).isoformat()
    cutoff = (now - timedelta(days=INSTANT_REPEAT_DAYS)).isoformat()
    sender = Sender(store.sent_today(), dry_run, sleep)
    total = sent_msgs = 0
    for sub in sorted(subs, key=lambda s: not s.get("is_owner")):
        sent_events = pruned(sub.get("instant_sent"), keep_since)    # {event_id: when}
        sent_titles = pruned(sub.get("instant_titles"), keep_since)  # {series title: when}
        picks = pick_instant(events, sub, set(sent_events),
                             {k for k, v in sent_titles.items() if v >= cutoff})

        def remember(chosen):
            stamp = now.isoformat()
            for e in chosen:
                sent_events[e["id"]] = stamp
                sent_titles[title_key(e)] = stamp

        if not sub.get("instant_seeded_at"):
            # First run for this person: remember what's already out there instead of flooding them.
            if sub.get("is_owner") and picks:
                if sender.send(sub["topic"], {"title": "Baltimore alerts are on 🎷", "tags": ["tada"],
                               "message": f"{len(picks)} matching events are already on the calendar — they'll be "
                                          "in your weekly roundup. From now on you'll get a ping for each new one."}):
                    sent_msgs += 1
            remember(picks)
            if not dry_run:
                store.update_subscriber(sub["id"], {"instant_seeded_at": now.isoformat(),
                                                    "instant_sent": sent_events, "instant_titles": sent_titles})
            continue
        if not picks:
            continue
        limit = INSTANT_MAX_PER_RUN if sub.get("is_owner") else PUBLIC_INSTANT_MAX
        if len(picks) <= limit:
            done = [e for e in picks if sender.send(sub["topic"], instant_message(e, sub))]
            sent_msgs += len(done)
        else:
            lines = [one_line(e) for e in picks[:12]] + ([f"…and {len(picks) - 12} more"] if len(picks) > 12 else [])
            ok = sender.send(sub["topic"], {"title": f"{len(picks)} new picks around Baltimore",
                                            "message": "\n".join(lines), "tags": ["sparkles"], "actions": actions(sub)})
            done = picks if ok else []
            sent_msgs += 1 if ok else 0
        if done:
            remember(done)
            if not dry_run:
                store.update_subscriber(sub["id"], {"instant_sent": sent_events, "instant_titles": sent_titles})
        total += len(done)
        if sender.remaining <= 0:
            print("[push] daily limit reached; the rest go out next run")
            break
    if not dry_run:
        store.add_sent(sent_msgs)
    print(f"[push] instant: {total} events alerted across {len(subs)} subscribers")
    return 0


# --------------------------------------------------------------------- main
def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["instant", "weekly", "test"], required=True)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)

    if args.mode == "test":
        if not NTFY_TOPIC and not args.dry_run:
            print("[push] NTFY_TOPIC secret is not set in the repo's Actions secrets")
            return 1
        Sender(0, args.dry_run).send(NTFY_TOPIC or "dry-run", {
            "title": "Test from Baltimore Side Quest ✅", "message": "Your phone alerts are connected.",
            "tags": ["white_check_mark"]})
        return 0
    store = get_store()
    if store is None:
        print("[push] FIREBASE_SERVICE_ACCOUNT secret is not set")
        return 1
    return run_instant(store, args.dry_run) if args.mode == "instant" else run_weekly(store, args.dry_run)


if __name__ == "__main__":
    sys.exit(main())
