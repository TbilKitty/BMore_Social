-- Phone alerts for everyone (ntfy). Run once in the Supabase SQL editor.
-- No names or emails: a subscriber is just a random ntfy topic + their interests.

create table if not exists push_subscribers (
  id uuid primary key default gen_random_uuid(),
  topic text unique not null,              -- random ntfy topic the person subscribes to in the app
  manage_token text unique not null,       -- secret in their "change or stop" link
  categories text[] not null default '{}', -- interests, from scraper/config.py CATEGORIES
  free_only boolean not null default false,
  radius_mi int not null default 10,
  instant boolean not null default false,  -- heads-up pings as new matches appear
  paused boolean not null default false,
  is_owner boolean not null default false, -- the site owner's own feed (NTFY_TOPIC secret)
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  last_weekly_at timestamptz,
  instant_seeded_at timestamptz,         -- set after the first quiet catch-up for instant alerts
  last_test_at timestamptz,
  signup_fingerprint text                   -- one-way hash of the sign-up IP, only to stop bulk fake sign-ups
);
create index if not exists push_subscribers_signup_idx on push_subscribers (signup_fingerprint, created_at);

create table if not exists push_log (
  id bigint generated always as identity primary key,
  subscriber_id uuid references push_subscribers(id) on delete cascade,
  event_id uuid references events(id) on delete cascade,
  title_key text,
  kind text not null,                      -- 'weekly' | 'instant' | 'seeded' | 'welcome' | 'test'
  sent_at timestamptz not null default now()
);
create index if not exists push_log_sub_idx on push_log (subscriber_id, sent_at);
create index if not exists push_log_day_idx on push_log (sent_at);

-- Private: no public read/write at all. The website's server routes and the
-- GitHub Actions sender use the service key, which bypasses these rules.
alter table push_subscribers enable row level security;
alter table push_log enable row level security;
