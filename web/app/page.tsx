"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { supabase, getOrCreateAnonId } from "@/lib/supabaseClient";
import { matchScore, noveltyScore } from "@/lib/scoring";
import EventCard from "@/components/EventCard";

export default function Home() {
  const [profile, setProfile] = useState<any>(null);
  const [events, setEvents] = useState<any[]>([]);
  const [recentCategories, setRecentCategories] = useState<string[][]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      const anonId = getOrCreateAnonId();
      const { data: existing } = await supabase.from("profiles").select("*").eq("anon_id", anonId).maybeSingle();
      setProfile(existing);

      if (!existing) {
        setLoading(false);
        return;
      }

      const { data: interactions } = await supabase
        .from("interactions")
        .select("event_id, status, events(categories)")
        .eq("profile_id", existing.id);

      const seenIds = new Set((interactions || []).map((i: any) => i.event_id));
      const recent = (interactions || [])
        .filter((i: any) => i.status === "saved" || i.status === "attended")
        .map((i: any) => i.events?.categories || [])
        .slice(-20);
      setRecentCategories(recent);

      const { data: upcoming } = await supabase
        .from("events")
        .select("*")
        .gte("start_time", new Date().toISOString())
        .lte("distance_from_baltimore_mi", existing.radius_mi ?? 35)
        .order("start_time", { ascending: true })
        .limit(200);

      const filtered = (upcoming || []).filter((e) => !seenIds.has(e.id));
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
        <Link href="/quiz" className="inline-block px-4 py-2 rounded bg-white text-black font-medium">
          Take the 60-second quiz to get started
        </Link>
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
        <Link href="/quiz" className="text-sm underline text-neutral-400">Retake quiz</Link>
      </div>
      {scored.length === 0 && <p className="text-neutral-400">No upcoming events yet — check back after the next scrape.</p>}
      {scored.map(({ event, match, novelty }) => (
        <EventCard key={event.id} event={event} matchScore={match} noveltyScore={novelty} profileId={profile.id} />
      ))}
    </div>
  );
}
