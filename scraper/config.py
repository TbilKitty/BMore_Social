import os

# Must match the quiz options in web/app/quiz/page.tsx
CATEGORIES = [
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
# against the event title + description.
CATEGORY_KEYWORDS = {
    "bikes": ["bike", "cycling", "bicycle", "critical mass", "velodrome"],
    "dance": ["dance", "salsa", "swing night", "ballroom", "line dancing"],
    "outdoor_music": ["outdoor concert", "concert series", "live music", "amphitheater", "festival stage"],
    "food_festivals": ["food festival", "food truck", "tasting", "beer fest", "wine fest", "farmers market"],
    "car_shows": ["car show", "cars and coffee", "auto show", "classic cars"],
    "outdoor_recreation": ["hike", "kayak", "trail", "paddle", "outdoor rec", "park cleanup"],
    "arts": ["gallery", "art walk", "exhibit", "mural", "open studio", "theatre", "theater"],
    "dog_friendly": ["dog friendly", "dog park", "pup", "yappy hour"],
    "family_friendly": ["family friendly", "kid friendly", "all ages", "family fun"],
    "unusual": ["oddities", "weird", "unusual", "offbeat", "bizarre"],
}

BALTIMORE_LAT = 39.2904
BALTIMORE_LNG = -76.6122
RADIUS_MILES = 35

EVENTBRITE_TOKEN = os.environ.get("EVENTBRITE_TOKEN")
MEETUP_API_KEY = os.environ.get("MEETUP_API_KEY")

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")
