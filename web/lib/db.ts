// SERVER ONLY. Google Cloud Firestore through the Firebase Admin SDK.
// The FIREBASE_SERVICE_ACCOUNT environment variable (Vercel → Settings → Environment Variables)
// holds the service-account JSON key. Never import this from a "use client" file.
import { cert, getApps, initializeApp } from "firebase-admin/app";
import { FieldValue, getFirestore, type Firestore } from "firebase-admin/firestore";

let cached: Firestore | null = null;

export function db(): Firestore {
  if (cached) return cached;
  if (!getApps().length) {
    const raw = process.env.FIREBASE_SERVICE_ACCOUNT;
    if (!raw) throw new Error("FIREBASE_SERVICE_ACCOUNT is not set in Vercel's environment variables");
    const sa = JSON.parse(raw);
    initializeApp({
      credential: cert({ projectId: sa.project_id, clientEmail: sa.client_email, privateKey: sa.private_key }),
    });
  }
  cached = getFirestore();
  return cached;
}

/** A per-deployment secret used to salt one-way hashes (sign-up rate limiting). */
export function hashSalt(): string {
  try {
    return JSON.parse(process.env.FIREBASE_SERVICE_ACCOUNT || "{}").private_key_id || "";
  } catch {
    return "";
  }
}

export type EventRow = {
  id: string;
  title: string;
  start_time: string;
  end_time?: string | null;
  categories: string[];
  distance_from_baltimore_mi?: number | null;
  [key: string]: any;
};

// The scraper rewrites the upcoming-events list (collection "snapshot") after each run.
// Cache it briefly so page views don't each spend Firestore reads.
let eventsCache: { at: number; events: EventRow[] } | null = null;
const CACHE_MS = 5 * 60 * 1000;

export async function upcomingEvents(): Promise<EventRow[]> {
  if (!eventsCache || Date.now() - eventsCache.at > CACHE_MS) {
    const snap = await db().collection("snapshot").get();
    const all: EventRow[] = [];
    snap.forEach((d) => all.push(...JSON.parse(d.get("events_json") || "[]")));
    all.sort((a, b) => a.start_time.localeCompare(b.start_time));
    eventsCache = { at: Date.now(), events: all };
  }
  const now = new Date().toISOString();
  return eventsCache.events.filter((e) => e.start_time >= now);
}

/** Counts push messages sent today, shared with the scraper's daily ntfy budget. */
export async function countSent(n = 1): Promise<void> {
  const day = new Date().toISOString().slice(0, 10);
  await db().collection("meta").doc(`ntfy-${day}`).set({ count: FieldValue.increment(n) }, { merge: true });
}

const ANON_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

/** The visitor's random id from the anon_id cookie (set by the browser), or null. */
export function anonIdFrom(req: Request): string | null {
  const m = (req.headers.get("cookie") || "").match(/(?:^|;\s*)anon_id=([^;]+)/);
  const id = m ? decodeURIComponent(m[1]) : "";
  return ANON_RE.test(id) ? id.toLowerCase() : null;
}
