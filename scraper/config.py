import os

# Must match the quiz options in web/app/quiz/page.tsx
CATEGORIES = [
    "jazz_blues",
    "live_music",
    "food_markets",
    "culture",
    "bikes",
    "dance",
    "outdoor_music",
    "food_festivals",
    "car_shows",
    "outdoor_recreation",
    "arts",
    "dog_friendly",
    "family_friendly",
    "unusual",
]

# Simple keyword -> category mapping used to auto-tag events that don't come
# pre-categorized. Extend freely; matching is case-insensitive substring match
# against the event title + description (+ the source's own category names).
CATEGORY_KEYWORDS = {
    "jazz_blues": ["jazz", "blues", "big band", "bebop", "swing band", "jam session", "quartet",
                   "quintet", "trio", "organ trio", "scat", "harmonica", "juke joint", "go-go"],
    "live_music": ["live music", "concert", "band", "live performance", "open mic", "jam session",
                   "dj ", "dj set", "singer", "songwriter", "acoustic", "orchestra", "choir",
                   "porchfest", "porch fest", "busk", "music series", "recital", "sound bath"],
    "food_markets": ["farmers market", "farmers' market", "farmer's market", "food market",
                     "night market", "public market", "food hall", "makers market", "makers' market",
                     "flea market", "bazaar", "food truck", "food fest", "food festival", "tasting",
                     "crab feast", "oyster", "pop-up market", "popup market", "holiday market"],
    "culture": ["festival", "museum", "exhibit", "exhibition", "gallery", "lecture", "author talk",
                "book talk", "film screening", "screening", "poetry", "spoken word", "theatre",
                "theater", "heritage", "cultural", "culture", "history", "walking tour", "parade",
                "celebration", "block party", "art walk", "open studio", "storytelling", "comedy"],
    "bikes": ["bike", "cycling", "bicycle", "critical mass", "velodrome"],
    "dance": ["dance", "salsa", "swing night", "ballroom", "line dancing", "bachata", "lindy"],
    "outdoor_music": ["outdoor concert", "concert series", "amphitheater", "festival stage",
                      "concert in the park", "summer concert"],
    "food_festivals": ["food festival", "food truck", "tasting", "beer fest", "wine fest", "farmers market"],
    "car_shows": ["car show", "cars and coffee", "auto show", "classic cars"],
    "outdoor_recreation": ["hike", "kayak", "trail", "paddle", "outdoor rec", "park cleanup"],
    "arts": ["gallery", "art walk", "exhibit", "mural", "open studio", "theatre", "theater"],
    "dog_friendly": ["dog friendly", "dog-friendly", "dog park", "pup", "yappy hour"],
    "family_friendly": ["family friendly", "family-friendly", "kid friendly", "all ages", "family fun"],
    "unusual": ["oddities", "weird", "unusual", "offbeat", "bizarre"],
}

# Text that means "this is not a fun outing" even if a keyword above matched
# (e.g. Baltimore Public Markets also lists food-pantry distributions).
EXCLUDE_KEYWORDS = ["food pantry", "pop-up pantry", "people's pantry", "peoples pantry",
                    "vendor application", "vendor applications", "call for vendors", "volunteer orientation"]

BALTIMORE_LAT = 39.2904
BALTIMORE_LNG = -76.6122
RADIUS_MILES = 35  # what the public site keeps; personal alerts use PERSONAL_RADIUS_MILES

EVENTBRITE_TOKEN = os.environ.get("EVENTBRITE_TOKEN")
MEETUP_API_KEY = os.environ.get("MEETUP_API_KEY")

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")

# ---------------------------------------------------------------- event sources
# Websites running the WordPress "The Events Calendar" plugin. The scraper reads
# their built-in data feed (/wp-json/tribe/events/v1/events), falling back to the
# plugin's iCal export. `tags` are added to every event from that source.
# `local: True` = the site only lists Baltimore-area events, so an event with no
# address is still assumed nearby.
TRIBE_SOURCES = [
    {"name": "baltimore_jazz_alliance", "base_url": "https://www.baltimorejazz.com",
     "tags": ["jazz_blues", "live_music"], "local": False},
    {"name": "creative_alliance", "base_url": "https://creativealliance.org",
     "tags": ["culture"], "local": True},
    {"name": "baltimore_public_markets", "base_url": "https://baltimoremarkets.org",
     "tags": ["food_markets"], "local": True},
    {"name": "stages_music_arts", "base_url": "https://www.stagesmusicarts.com",
     "tags": [], "local": True},
]

# Any plain iCal (.ics) calendar link — e.g. a venue's public Google Calendar.
# Add entries in the same shape: {"name": ..., "url": ..., "tags": [...], "local": True}
ICAL_SOURCES = []

DAYS_AHEAD = 45  # how far into the future to collect events

# ------------------------------------------------------------- phone alerts
# Push notifications via the free ntfy app (ntfy.sh). Anyone can sign up on the
# website (/alerts); each subscriber gets a private random topic.
NTFY_SERVER = os.environ.get("NTFY_SERVER") or "https://ntfy.sh"
NTFY_TOKEN = os.environ.get("NTFY_TOKEN")          # optional: paid ntfy plan access token (higher limits)
NTFY_DAILY_LIMIT = int(os.environ.get("NTFY_DAILY_LIMIT") or 240)  # free ntfy.sh: keep under its daily cap
NTFY_BURST = 50                                    # sends before pacing kicks in
NTFY_PACE_SECONDS = 10.5                           # free ntfy.sh allows ~1 message / 10 s after a burst
SITE_URL = (os.environ.get("SITE_URL") or "https://b-more-social.vercel.app").rstrip("/")

# Your own feed: the NTFY_TOPIC secret is treated as a subscriber with these settings.
NTFY_TOPIC = os.environ.get("NTFY_TOPIC")
PERSONAL_RADIUS_MILES = 10
PERSONAL_CATEGORIES = ["jazz_blues", "live_music", "food_markets", "culture", "food_festivals",
                       "outdoor_music", "arts", "unusual"]

# Towns within roughly 10 miles of downtown, used when an event has an address
# but no map coordinates.
NEARBY_PLACES = [
    "baltimore", "towson", "catonsville", "dundalk", "essex", "parkville", "pikesville",
    "halethorpe", "arbutus", "lutherville", "timonium", "rosedale", "middle river",
    "brooklyn park", "glen burnie", "linthicum", "woodlawn", "gwynn oak", "windsor mill",
    "nottingham", "overlea", "perry hall", "edgemere", "sparrows point", "lansdowne",
    "elkridge", "ellicott city", "owings mills", "stevenson", "ruxton", "riderwood",
]

INSTANT_MAX_PER_RUN = 6        # owner: more than this in one run → one combined push
PUBLIC_INSTANT_MAX = 3         # everyone else
INSTANT_REPEAT_DAYS = 30       # a repeating event (weekly jam, Saturday market) pings once a month
WEEKLY_DAYS_AHEAD = 8
WEEKLY_EVERY_DAYS = 6.5        # the weekly job runs daily; each person gets one roundup per ~7 days
QUIET_HOURS = (22, 8)          # no instant pings 10 PM–8 AM; they wait for the next daytime run
