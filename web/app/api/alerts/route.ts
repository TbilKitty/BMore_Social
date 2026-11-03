// POST /api/alerts — create a phone-alert subscription. No name, email or phone number:
// the person gets a random ntfy topic to subscribe to, plus a private link to change or stop.
import { NextResponse } from "next/server";
import { randomBytes, createHash } from "crypto";
import { countSent, db, hashSalt } from "@/lib/db";
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

  const subs = db().collection("push_subscribers");

  // Stop bulk fake sign-ups (they'd eat the daily notification allowance meant for real people).
  const ip = (req.headers.get("x-forwarded-for") || "").split(",")[0].trim() || "unknown";
  const signup_fingerprint = createHash("sha256").update(ip + hashSalt().slice(-16)).digest("hex").slice(0, 32);
  const hourAgo = new Date(Date.now() - 3600_000).toISOString();
  const dayAgo = new Date(Date.now() - 86400_000).toISOString();
  try {
    const [fromHere, today] = await Promise.all([
      subs.where("signup_fingerprint", "==", signup_fingerprint).get(),
      subs.where("created_at", ">=", dayAgo).count().get(),
    ]);
    const mine = fromHere.docs.filter((d) => String(d.get("created_at") || "") >= hourAgo).length;
    if (mine >= 5) {
      return NextResponse.json({ error: "Too many sign-ups from this connection. Try again in an hour." }, { status: 429 });
    }
    if (today.data().count >= 300) {
      return NextResponse.json({ error: "Lots of sign-ups today! Please try again tomorrow." }, { status: 503 });
    }
  } catch (err) {
    console.error("alerts signup check failed", err);
    return NextResponse.json({ error: "Sign-up is temporarily unavailable. Please try again later." }, { status: 500 });
  }

  const topic = "bsq-" + randomBytes(9).toString("hex");
  const manage_token = randomBytes(24).toString("base64url");
  const now = new Date().toISOString();

  try {
    await subs.add({
      topic, manage_token, signup_fingerprint, ...prefs,
      paused: false, is_owner: false, created_at: now, updated_at: now,
    });
  } catch (err) {
    console.error("alerts signup failed", err);
    return NextResponse.json({ error: "Sign-up is temporarily unavailable. Please try again later." }, { status: 500 });
  }

  // Waits on the ntfy server (about 12 hours), so it shows up as soon as they subscribe in the app.
  const ok = await sendPush(
    topic,
    "You're signed up 🎉",
    "Your Baltimore picks will arrive here about once a week. Use the button below anytime to change your interests or stop.",
    manage_token
  );
  if (ok) await countSent().catch(() => null);

  return NextResponse.json({ topic, manage_url: manageUrl(manage_token) });
}
