"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { supabase, getOrCreateAnonId } from "@/lib/supabaseClient";

// Must match scraper/config.py CATEGORIES
const CATEGORIES: [string, string][] = [
  ["bikes", "Biking"],
  ["dance", "Dance"],
  ["outdoor_music", "Outdoor music"],
  ["food_festivals", "Food festivals"],
  ["car_shows", "Car shows"],
  ["outdoor_recreation", "Outdoor recreation"],
  ["arts", "Arts"],
  ["dog_friendly", "Dog-friendly"],
  ["family_friendly", "Family-friendly"],
  ["unusual", "Unusual / offbeat"],
];

export default function Quiz() {
  const router = useRouter();
  const [weights, setWeights] = useState<Record<string, number>>(
    Object.fromEntries(CATEGORIES.map(([key]) => [key, 0.5]))
  );
  const [radius, setRadius] = useState(35);
  const [email, setEmail] = useState("");
  const [subscribe, setSubscribe] = useState(false);
  const [saving, setSaving] = useState(false);

  async function submit() {
    setSaving(true);
    const anonId = getOrCreateAnonId();
    await supabase.from("profiles").upsert(
      {
        anon_id: anonId,
        category_weights: weights,
        radius_mi: radius,
        email: subscribe ? email : null,
        email_subscribed: subscribe && !!email,
      },
      { onConflict: "anon_id" }
    );
    router.push("/");
  }

  return (
    <div>
      <h1 className="text-2xl font-bold mb-1">What are you into?</h1>
      <p className="text-neutral-400 mb-6">Slide each one — 0 means skip it, 1 means show me everything.</p>

      {CATEGORIES.map(([key, label]) => (
        <div key={key} className="mb-4">
          <div className="flex justify-between text-sm mb-1">
            <span>{label}</span>
            <span className="text-neutral-400">{Math.round(weights[key] * 100)}%</span>
          </div>
          <input
            type="range" min={0} max={1} step={0.05} value={weights[key]}
            onChange={(e) => setWeights({ ...weights, [key]: parseFloat(e.target.value) })}
            className="w-full"
          />
        </div>
      ))}

      <div className="mb-4">
        <label className="block text-sm mb-1">How far will you travel? ({radius} mi)</label>
        <input type="range" min={5} max={35} step={5} value={radius} onChange={(e) => setRadius(parseInt(e.target.value))} className="w-full" />
      </div>

      <div className="mb-6 border border-neutral-800 rounded-lg p-4">
        <label className="flex items-center gap-2 mb-2">
          <input type="checkbox" checked={subscribe} onChange={(e) => setSubscribe(e.target.checked)} />
          <span>Email me a weekly digest of new high-match events</span>
        </label>
        {subscribe && (
          <input
            type="email" placeholder="you@example.com" value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="w-full bg-neutral-900 border border-neutral-700 rounded px-3 py-2"
          />
        )}
      </div>

      <button
        onClick={submit} disabled={saving}
        className="px-4 py-2 rounded bg-white text-black font-medium disabled:opacity-50"
      >
        {saving ? "Saving..." : "See my matches"}
      </button>
    </div>
  );
}
