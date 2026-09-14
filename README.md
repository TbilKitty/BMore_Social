# Baltimore Side Quest

Auto-scraped, quiz-matched event discovery for the Baltimore area — no social media required.

## How it works

1. **Scraper** (`/scraper`, Python) runs on a schedule via **GitHub Actions**, pulls events
   from Eventbrite + Meetup APIs and any HTML sources you add, dedupes them, scores them
   against interest categories, and upserts them into **Supabase** (Postgres).
2. **Web app** (`/web`, Next.js) is a public site: first-time visitors take a short interest
   quiz (stored in a cookie or account), then see a personalized feed with Match + Novelty
   scores. Every event has Save / Attended / Not for me buttons and Google/Apple/Outlook
   calendar links.
3. **Email digest**: a second scheduled GitHub Action queries Supabase for new
   high-match events per subscriber and sends a digest via **Resend**.

Everything is free-tier: GitHub Actions (scraping + email cron), Supabase (DB + auth),
Vercel (hosting, auto-deploys from your GitHub repo), Resend (100 emails/day free).

## One-time setup

1. **Push this folder to a new GitHub repo.**
2. **Supabase**: create a free project at supabase.com → run `supabase/schema.sql` in the
   SQL editor → copy your Project URL and `service_role` key (scraper) and `anon` key (web).
3. **Eventbrite**: create a free API key at eventbrite.com/platform/api.
4. **Meetup**: create an OAuth client at meetup.com/api — the API now requires OAuth, see
   `scraper/sources/meetup.py` for the token-fetch flow.
5. **Resend**: create a free account at resend.com, verify a sending domain (or use their
   test domain while developing), copy your API key.
6. **GitHub repo secrets** (Settings → Secrets and variables → Actions), add:
   - `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`
   - `EVENTBRITE_TOKEN`
   - `MEETUP_API_KEY` (or OAuth creds per meetup.py)
   - `RESEND_API_KEY`
7. **Vercel**: import the repo, set the root directory to `web/`, add env vars
   `NEXT_PUBLIC_SUPABASE_URL` and `NEXT_PUBLIC_SUPABASE_ANON_KEY`. Deploy — you get a free
   `*.vercel.app` URL immediately, and can attach a custom domain for free in Vercel's
   Domains tab if you own one.
8. Merge to `main` — the scrape workflow runs on its schedule (default: daily 8am ET) and
   also on-demand from the Actions tab (`workflow_dispatch`).

## Adding more local Baltimore sources

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
cd scraper && pip install -r requirements.txt && python main.py   # test a scrape run
cd web && npm install && npm run dev                              # run the site locally
```
