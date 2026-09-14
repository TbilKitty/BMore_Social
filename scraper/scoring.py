"""
Match and novelty scores are computed on the web app side at request time (they
depend on the specific visitor's quiz weights + interaction history, which live
in Supabase, not in the scraper). This module is imported there conceptually —
mirrored in web/lib/scoring.ts for the Next.js API routes.

Kept here as the single documented source of truth for the formula:

match_score(event, profile) =
    avg(profile.category_weights[c] for c in event.categories) if event.categories else 0.3
    # events with no auto-detected category still show up, just lower-confidence

novelty_score(event, profile) =
    1.0 minus the fraction of the visitor's last 20 saved/attended events that
    share ANY category with this event. A visitor who's saved ten dance-night
    listings gets a low novelty score on an eleventh; a first-ever car show gets
    a high one. Purely category-based, no ML — easy to reason about and tune.
"""
