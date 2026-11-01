"""Minimal iCalendar (.ics) reader: enough to pull VEVENTs out of a public
calendar feed without adding a dependency."""
import re
from datetime import datetime, date, timezone
from zoneinfo import ZoneInfo

LOCAL_TZ = ZoneInfo("America/New_York")


def _unfold(text: str) -> list[str]:
    lines = []
    for raw in text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        if raw.startswith((" ", "\t")) and lines:
            lines[-1] += raw[1:]
        else:
            lines.append(raw)
    return lines


def _unescape(v: str) -> str:
    return (v.replace("\\n", "\n").replace("\\N", "\n").replace("\\,", ",")
             .replace("\\;", ";").replace("\\\\", "\\"))


def parse_dt(value: str, params: dict) -> tuple[str | None, bool]:
    """Returns (ISO-8601 UTC string, all_day)."""
    value = value.strip()
    try:
        if params.get("VALUE") == "DATE" or re.fullmatch(r"\d{8}", value):
            d = datetime.strptime(value[:8], "%Y%m%d").replace(hour=12, tzinfo=LOCAL_TZ)
            return d.astimezone(timezone.utc).isoformat(), True
        if value.endswith("Z"):
            d = datetime.strptime(value, "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)
        else:
            tz = LOCAL_TZ
            if params.get("TZID"):
                try:
                    tz = ZoneInfo(params["TZID"].strip('"'))
                except Exception:
                    tz = LOCAL_TZ
            d = datetime.strptime(value[:15], "%Y%m%dT%H%M%S").replace(tzinfo=tz)
        return d.astimezone(timezone.utc).isoformat(), False
    except ValueError:
        return None, False


def parse_ics(text: str) -> list[dict]:
    """Each event: {summary, description, location, url, start, end, all_day, geo, categories, uid}."""
    events, cur = [], None
    for line in _unfold(text):
        if line == "BEGIN:VEVENT":
            cur = {"categories": []}
            continue
        if line == "END:VEVENT":
            if cur and cur.get("start"):
                events.append(cur)
            cur = None
            continue
        if cur is None or ":" not in line:
            continue
        head, value = line.split(":", 1)
        name, *param_parts = head.split(";")
        params = dict(p.split("=", 1) for p in param_parts if "=" in p)
        name = name.upper()
        if name == "SUMMARY":
            cur["summary"] = _unescape(value)
        elif name == "DESCRIPTION":
            cur["description"] = _unescape(value)
        elif name == "LOCATION":
            cur["location"] = _unescape(value)
        elif name == "URL":
            cur["url"] = value.strip()
        elif name == "UID":
            cur["uid"] = value.strip()
        elif name == "DTSTART":
            cur["start"], cur["all_day"] = parse_dt(value, params)
        elif name == "DTEND":
            cur["end"], _ = parse_dt(value, params)
        elif name == "GEO":
            try:
                lat, lng = value.split(";")
                cur["geo"] = (float(lat), float(lng))
            except ValueError:
                pass
        elif name == "CATEGORIES":
            cur["categories"] += [_unescape(c).strip() for c in re.split(r"(?<!\\),", value) if c.strip()]
    return events
