// POST { event_id, status, categories } — Save / Attended / Not for me, for this visitor.
import { NextResponse } from "next/server";
import { anonIdFrom, db } from "@/lib/db";

export const dynamic = "force-dynamic";

const STATUSES = new Set(["saved", "attended", "not_for_me"]);

export async function POST(req: Request) {
  const anon = anonIdFrom(req);
  const body = await req.json().catch(() => ({}));
  const eventId = typeof body?.event_id === "string" ? body.event_id : "";
  if (!anon || !/^[A-Za-z0-9_-]{1,128}$/.test(eventId) || !STATUSES.has(body?.status)) {
    return NextResponse.json({ error: "Bad request" }, { status: 400 });
  }
  const store = db();
  if (!(await store.collection("profiles").doc(anon).get()).exists) {
    return NextResponse.json({ error: "Take the quiz first" }, { status: 400 });
  }
  const categories = Array.isArray(body.categories)
    ? body.categories.filter((c: unknown) => typeof c === "string").slice(0, 20)
    : [];
  await store.collection("interactions").doc(`${anon}__${eventId}`).set({
    profile_id: anon, event_id: eventId, status: body.status, categories, created_at: new Date().toISOString(),
  });
  return NextResponse.json({ ok: true });
}
