// POST /api/alerts — create a phone-alert subscription. No name, email or phone number:
// the person gets a random ntfy topic to subscribe to, plus a private link to change or stop.
import { NextResponse } from "next/server";
import { randomBytes, createHash } from "crypto";
import { adminClient } from "@/lib/supabaseAdmin";
import { cleanPrefs, sendPush, manageUrl } from "@/lib/alerts";

export const dynamic = "force-dynamic";

export async function POST(req: Request) {
  let body: any;
  try {
    body = await req.json();
  } catch {
    return NextResponse.json({ error: "Bad request" }, { status: 400 });
  }
  if (body?.website) return NextResponse.json({ error: "Bad request" }, { status: 400 }); // bot honeypot

  const prefs = cleanPrefs(body);
  if (typeof prefs === "string") return NextResponse.json({ error: prefs }, { status: 400 });

  const db = adminClient();

  // Stop bulk fake sign-ups (they'd eat the daily notification allowance meant for real people).
  const ip = (req.headers.get("x-forwarded-for") || "").split(",")[0].trim() || "unknown";
  const signup_fingerprint = createHash("sha256")
    .update(ip + (process.env.SUPABASE_SERVICE_KEY || "").slice(-16))
    .digest("hex")
    .slice(0, 32);
  const hourAgo = new Date(Date.now() - 3600_000).toISOString();
  const dayAgo = new Date(Date.now() - 86400_000).toISOString();
  const [{ count: mine }, { count: today }] = await Promise.all([
    db.from("push_subscribers").select("id", { count: "exact", head: true })
      .eq("signup_fingerprint", signup_fingerprint).gte("created_at", hourAgo),
    db.from("push_subscribers").select("id", { count: "exact", head: true }).gte("created_at", dayAgo),
  ]);
  if ((mine ?? 0) >= 5) {
    return NextResponse.json({ error: "Too many sign-ups from this connection. Try again in an hour." }, { status: 429 });
  }
  if ((today ?? 0) >= 300) {
    return NextResponse.json({ error: "Lots of sign-ups today! Please try again tomorrow." }, { status: 503 });
  }

  const topic = "bsq-" + randomBytes(9).toString("hex");
  const manage_token = randomBytes(24).toString("base64url");

  const { data, error } = await db
    .from("push_subscribers")
    .insert({ topic, manage_token, signup_fingerprint, ...prefs })
    .select("id")
    .single();
  if (error || !data) {
    console.error("alerts signup failed", error);
    return NextResponse.json({ error: "Sign-up is temporarily unavailable. Please try again later." }, { status: 500 });
  }

  // Waits on the ntfy server (about 12 hours), so it shows up as soon as they subscribe in the app.
  const ok = await sendPush(
    topic,
    "You're signed up 🎉",
    "Your Baltimore picks will arrive here about once a week. Use the button below anytime to change your interests or stop.",
    manage_token
  );
  if (ok) await db.from("push_log").insert({ subscriber_id: data.id, kind: "welcome" });

  return NextResponse.json({ topic, manage_url: manageUrl(manage_token) });
}
