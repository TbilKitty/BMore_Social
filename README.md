# Baltimore Side Quest

Auto-scraped, quiz-matched event discovery for the Baltimore area — no social media required.

## How it works

1. **Scraper** (`/scraper`, Python) runs on a schedule via **GitHub Actions**, pulls events
   from local event calendars (and Meetup, if configured), dedupes and tags them, and saves the
   upcoming list to **Google Cloud Firestore**. Past events drop off automatically, so the
   database stays tiny.
2. **Web app** (`/web`, Next.js) is a public site: first-time visitors take a short interest
   quiz (stored in a cookie or account), then see a personalized feed with Match + Novelty
   scores. Every event has Save / Attended / Not for me buttons and Google/Apple/Outlook
   calendar links.
3. **Email digest**: a second scheduled GitHub Action reads Firestore for new
   high-match events per subscriber and sends a digest via **Resend**.

Everything is free-tier: GitHub Actions (scraping + email cron), Firestore (database, free
quota: 1 GiB stored, 50,000 reads and 20,000 writes a day),
Vercel (hosting, auto-deploys from your GitHub repo), Resend (100 emails/day free).

## Database (Google Firestore) — one-time setup

1. Go to **console.firebase.google.com**, sign in with your Google account, **Add project**
   (Google Analytics: off). Stay on the free **Spark** plan.
2. **Build → Firestore Database → Create database** → *Standard edition*, location
   `us-east4` (or any US region), **production mode**. Use the *(default)* database — named
   databases don't get the free quota. Production mode blocks all browser access, which is what
   we want: only the scraper and the website's server routes touch the data, with the key below.
3. **Project settings (gear) → Service accounts → Generate new private key**. A `.json` file
   downloads. Open it and copy **everything** in it.
4. **GitHub** → this repo → Settings → Secrets and variables → Actions → **New repository
   secret**: name `FIREBASE_SERVICE_ACCOUNT`, value = the whole JSON.
5. **Vercel** → the project → Settings → Environment Variables: add `FIREBASE_SERVICE_ACCOUNT`
   with the same JSON (all environments). Remove the old `NEXT_PUBLIC_SUPABASE_*` and
   `SUPABASE_*` variables. Redeploy.
6. **Move existing subscribers over** (only if you used Supabase before): Actions tab →
   *Move data from Supabase (one time)* → Run workflow. Then run *Scrape events* once.
7. After a few days of things working, delete the old Supabase project and the `SUPABASE_URL` /
   `SUPABASE_SERVICE_KEY` repo secrets.

Other optional secrets: `MEETUP_API_KEY`, `RESEND_API_KEY` + `DIGEST_FROM_EMAIL` (email digest),
`NTFY_TOPIC` (your own phone feed), `NTFY_TOKEN`. Repo variable `SITE_URL`.

### What's stored

| Collection | What | Grows? |
|---|---|---|
| `snapshot` | the upcoming events list, rewritten each scrape (~300 events per doc) | no |
| `push_subscribers` | one doc per phone subscriber, incl. their last 60 days of alert history | per person |
| `profiles` / `interactions` | quiz answers and Save / Attended / Not for me, per visitor | per person |
| `meta` | daily push-message count (ntfy's free cap) | one tiny doc a day |

## Phone alerts for everyone (ntfy)

Anyone can sign up at **/alerts**: pick interests, distance, free-only, and optional instant
pings. No account, email or phone number — each person gets a random ntfy topic to subscribe
to in the free ntfy app, plus a private "change or stop" link (/alerts/manage?token=…) that
lets them edit, pause, test or unsubscribe (which deletes their row).

- **Weekly** (`push_alerts.py --mode weekly`, run daily by the "Weekly roundups" workflow):
  everyone who's due gets ONE roundup message about every 7 days, grouped by interest, free
  events first, with "See all events" and "Change or stop alerts" buttons.
- **Instant** (opt-in, after each scrape): heads-up pings for new jazz/blues, free or pop-up
  music, and market events that match the person's interests. Quiet hours 10 PM–8 AM; a
  repeating event pings once a month; bursts are bundled into one message.
- **Limits:** the free ntfy.sh server allows ~60 messages then ~1 per 10 s and a daily cap.
  Sends are paced and stop at `NTFY_DAILY_LIMIT` (default 240); anyone missed goes out on the
  next day's run. For more subscribers, buy an ntfy plan and set `NTFY_TOKEN` + raise the limit.
- **Your own feed:** the `NTFY_TOPIC` secret is treated as a subscriber (instant on, the
  interests in `scraper/config.py`).

Setup: nothing beyond the Firestore steps above.

## Adding more local Baltimore sources

Sites that use the WordPress "The Events Calendar" plugin (look for `/events/` pages with
"« All Events" links) need no code: add them to `TRIBE_SOURCES` in `scraper/config.py`.
Any public iCal/Google Calendar link goes in `ICAL_SOURCES`.



`scraper/sources/template_html_source.py` is a working template using `requests` +
`BeautifulSoup`. Duplicate it per site (Visit Baltimore, BOPA, specific venues), point it
at the site's events page, and adjust the CSS selectors to match that site's HTML —
selectors WILL need hand-tuning per site since I can't browse live pages from here.
Register each new source in `scraper/main.py`'s `SOURCES` list.

## Customizing categories

Categories live in `scraper/config.py` (`CATEGORIES`) and must match the quiz options in
`web/app/quiz/page.tsx`. Current set: bikes, dance, outdoor_music, food_festivals,
car_shows, outdoor_recreation, arts, dog_friendly, family_friendly, unusual.

## Local dev

```
cd scraper && pip install -r requirements.txt && python main.py   # dry run without FIREBASE_SERVICE_ACCOUNT
python -m pytest tests                                            # offline tests
cd web && npm install && npm run dev                              # run the site locally
```
