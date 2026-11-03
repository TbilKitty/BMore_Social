// The visitor's quiz answers, keyed by their anon_id cookie.
//   GET  → { profile, interactions }   (profile is null before the quiz)
//   PUT  { category_weights, radius_mi, email, email_subscribed }
import { NextResponse } from "next/server";
import { anonIdFrom, db } from "@/lib/db";

export const dynamic = "force-dynamic";

const CATEGORY_KEYS = new Set([
  "jazz_blues", "live_music", "food_markets", "culture", "bikes", "dance", "outdoor_music",
  "food_festivals", "car_shows", "outdoor_recreation", "arts", "dog_friendly", "family_friendly", "unusual",
]);

export async function GET(req: Request) {
  const anon = anonIdFrom(req);
  if (!anon) return NextResponse.json({ profile: null, interactions: [] });
  const store = db();
  const [doc, inter] = await Promise.all([
    store.collection("profiles").doc(anon).get(),
    store.collection("interactions").where("profile_id", "==", anon).get(),
  ]);
  if (!doc.exists) return NextResponse.json({ profile: null, interactions: [] });
  const interactions = inter.docs
    .map((d) => d.data())
    .sort((a, b) => String(a.created_at).localeCompare(String(b.created_at)))
    .map((d) => ({ event_id: d.event_id, status: d.status, categories: d.categories || [] }));
  return NextResponse.json({ profile: { id: anon, ...doc.data() }, interactions });
}

export async function PUT(req: Request) {
  const anon = anonIdFrom(req);
  if (!anon) return NextResponse.json({ error: "Missing visitor id" }, { status: 400 });
  const body = await req.json().catch(() => ({}));
  const weights: Record<string, number> = {};
  for (const [k, v] of Object.entries(body?.category_weights || {})) {
    const n = Number(v);
    if (CATEGORY_KEYS.has(k) && n >= 0 && n <= 1) weights[k] = n;
  }
  const radius = Math.min(35, Math.max(5, Number(body?.radius_mi) || 35));
  const email = typeof body?.email === "string" && /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(body.email) ? body.email.slice(0, 200) : null;
  const ref = db().collection("profiles").doc(anon);
  const existing = await ref.get();
  await ref.set({
    anon_id: anon,
    category_weights: weights,
    radius_mi: radius,
    email,
    email_subscribed: body?.email_subscribed === true && !!email,
    created_at: existing.exists ? existing.get("created_at") ?? new Date().toISOString() : new Date().toISOString(),
    updated_at: new Date().toISOString(),
  });
  return NextResponse.json({ ok: true });
}
