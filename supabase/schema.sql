-- Baltimore Side Quest schema. Run this in the Supabase SQL editor.

create extension if not exists pgcrypto;

create table if not exists events (
  id uuid primary key default gen_random_uuid(),
  dedupe_key text unique not null,        -- normalized hash of title+venue+start_time
  source text not null,                   -- 'eventbrite' | 'meetup' | 'visit_baltimore' | ...
  source_url text not null,
  title text not null,
  description text,
  venue_name text,
  address text,
  lat double precision,
  lng double precision,
  distance_from_baltimore_mi numeric,
  start_time timestamptz not null,
  end_time timestamptz,
  categories text[] not null default '{}', -- subset of CATEGORIES in scraper/config.py
  is_recurring boolean default false,
  recurrence_group text,                  -- shared key for recurring instances, for dedupe
  raw jsonb,                              -- original scraped payload, for debugging
  first_seen_at timestamptz default now(),
  last_seen_at timestamptz default now()
);

create index if not exists events_start_time_idx on events (start_time);
create index if not exists events_categories_idx on events using gin (categories);

-- One row per visitor/subscriber. `user_id` is null for anonymous quiz-takers using a
-- cookie-stored `anon_id` instead; set once they optionally sign up via Supabase auth.
create table if not exists profiles (
  id uuid primary key default gen_random_uuid(),
  user_id uuid references auth.users(id),
  anon_id text unique,
  email text,
  email_subscribed boolean default false,
  category_weights jsonb not null default '{}', -- {"bikes": 0.8, "dance": 0.2, ...}
  radius_mi int default 35,
  created_at timestamptz default now()
);

create table if not exists interactions (
  id uuid primary key default gen_random_uuid(),
  profile_id uuid references profiles(id) on delete cascade,
  event_id uuid references events(id) on delete cascade,
  status text not null check (status in ('saved', 'attended', 'not_for_me')),
  created_at timestamptz default now(),
  unique (profile_id, event_id)
);

-- Row Level Security: events are public read; profiles/interactions are owner-only.
alter table events enable row level security;
create policy "events are publicly readable" on events for select using (true);

alter table profiles enable row level security;
create policy "profiles are self-access only" on profiles
  for all using (auth.uid() = user_id or user_id is null);

alter table interactions enable row level security;
create policy "interactions are self-access only" on interactions
  for all using (
    profile_id in (select id from profiles where auth.uid() = user_id or user_id is null)
  );
