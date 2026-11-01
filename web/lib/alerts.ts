// Shared by the alert pages and API routes. Interest keys must match scraper/config.py CATEGORIES.
export const INTERESTS: { key: string; label: string; emoji: string }[] = [
  { key: "jazz_blues", label: "Jazz & blues", emoji: "🎷" },
  { key: "live_music", label: "Live music & pop-up shows", emoji: "🎶" },
  { key: "food_markets", label: "Food & farmers markets", emoji: "🍎" },
  { key: "culture", label: "Festivals, culture & history", emoji: "🎭" },
  { key: "arts", label: "Art, galleries & theater", emoji: "🎨" },
  { key: "dance", label: "Dancing", emoji: "💃" },
  { key: "food_festivals", label: "Food festivals & tastings", emoji: "🦀" },
  { key: "outdoor_music", label: "Outdoor concerts", emoji: "🎪" },
  { key: "outdoor_recreation", label: "Hikes, paddling & outdoors", emoji: "🌳" },
  { key: "bikes", label: "Biking", emoji: "🚲" },
  { key: "family_friendly", label: "Family-friendly", emoji: "👨‍👩‍👧" },
  { key: "dog_friendly", label: "Dog-friendly", emoji: "🐕" },
  { key: "car_shows", label: "Car shows", emoji: "🚗" },
  { key: "unusual", label: "Weird & offbeat", emoji: "🦄" },
];

export const RADII = [5, 10, 20, 35];

export type AlertPrefs = {
  categories: string[];
  free_only: boolean;
  radius_mi: number;
  instant: boolean;
};

export const DEFAULT_PREFS: AlertPrefs = { categories: [], free_only: false, radius_mi: 10, instant: false };

const KEYS = new Set(INTERESTS.map((i) => i.key));

/** Validates untrusted input from a form; returns clean prefs or an error message. */
export function cleanPrefs(body: any): AlertPrefs | string {
  const categories = Array.isArray(body?.categories)
    ? Array.from(new Set(body.categories.filter((c: unknown) => typeof c === "string" && KEYS.has(c)))) as string[]
    : [];
  if (categories.length === 0) return "Pick at least one interest.";
  const radius = Number(body?.radius_mi);
  return {
    categories,
    free_only: body?.free_only === true,
    radius_mi: RADII.includes(radius) ? radius : 10,
    instant: body?.instant === true,
  };
}

export const NTFY_SERVER = (process.env.NTFY_SERVER || "https://ntfy.sh").replace(/\/$/, "");

export function siteUrl(): string {
  return (process.env.SITE_URL || process.env.NEXT_PUBLIC_SITE_URL || "https://b-more-social.vercel.app").replace(/\/$/, "");
}

export function manageUrl(token: string): string {
  return `${siteUrl()}/alerts/manage?token=${encodeURIComponent(token)}`;
}

/** Sends one ntfy message. Server-side only. */
export async function sendPush(topic: string, title: string, message: string, token?: string): Promise<boolean> {
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (process.env.NTFY_TOKEN) headers.Authorization = `Bearer ${process.env.NTFY_TOKEN}`;
  const actions = token ? [{ action: "view", label: "Change or stop alerts", url: manageUrl(token) }] : undefined;
  try {
    const res = await fetch(NTFY_SERVER, {
      method: "POST",
      headers,
      body: JSON.stringify({ topic, title, message, tags: ["wave"], actions }),
    });
    return res.ok;
  } catch {
    return false;
  }
}
