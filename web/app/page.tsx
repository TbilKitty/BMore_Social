"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { getOrCreateAnonId } from "@/lib/anon";
import { matchScore, noveltyScore } from "@/lib/scoring";
import EventCard from "@/components/EventCard";

export default function Home() {
  const [profile, setProfile] = useState<any>(null);
  const [events, setEvents] = useState<any[]>([]);
  const [recentCategories, setRecentCategories] = useState<string[][]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      getOrCreateAnonId();
      const me = await fetch("/api/profile").then((r) => r.json()).catch(() => ({ profile: null, interactions: [] }));
      const existing = me.profile;
      setProfile(existing);

      if (!existing) {
        setLoading(false);
        return;
      }

      const interactions: any[] = me.interactions || [];
      const seenIds = new Set(interactions.map((i) => i.event_id));
      const recent = interactions
        .filter((i) => i.status === "saved" || i.status === "attended")
        .map((i) => i.categories || [])
        .slice(-20);
      setRecentCategories(recent);

      const { events: upcoming } = await fetch(`/api/events?radius=${existing.radius_mi ?? 35}`)
        .then((r) => r.json())
        .catch(() => ({ events: [] }));

      const filtered = (upcoming || []).filter((e: any) => !seenIds.has(e.id));
      setEvents(filtered);
      setLoading(false);
    })();
  }, []);

  if (loading) return <p>Loading...</p>;

  if (!profile) {
    return (
      <div>
        <h1 className="text-2xl font-bold mb-2">Baltimore Side Quest</h1>
        <p className="text-neutral-400 mb-4">
          Auto-scraped things to do around Baltimore, matched to what you're actually into —
          no social media required.
        </p>
        <div className="flex flex-wrap gap-3">
          <Link href="/quiz" className="inline-block px-4 py-2 rounded bg-white text-black font-medium">
            Take the 60-second quiz to get started
          </Link>
          <Link href="/alerts" className="inline-block px-4 py-2 rounded border border-neutral-600">
            📲 Get weekly picks on your phone
          </Link>
        </div>
      </div>
    );
  }

  const weights = profile.category_weights || {};
  const scored = events
    .map((e) => ({ event: e, match: matchScore(e, weights), novelty: noveltyScore(e, recentCategories) }))
    .sort((a, b) => b.match - a.match);

  return (
    <div>
      <div className="flex justify-between items-center mb-4">
        <h1 className="text-2xl font-bold">Baltimore Side Quest</h1>
        <div className="flex gap-4 text-sm">
          <Link href="/alerts" className="underline">📲 Phone alerts</Link>
          <Link href="/quiz" className="underline text-neutral-400">Retake quiz</Link>
        </div>
      </div>
      {scored.length === 0 && <p className="text-neutral-400">No upcoming events yet — check back after the next scrape.</p>}
      {scored.map(({ event, match, novelty }) => (
        <EventCard key={event.id} event={event} matchScore={match} noveltyScore={novelty} profileId={profile.id} />
      ))}
    </div>
  );
}
