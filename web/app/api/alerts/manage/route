// The private "change or stop" link. Anyone holding the token can view/edit/delete
// that one subscription — nothing else.
//   GET    ?token=...                     current settings
//   PUT    { token, ...prefs, paused? }   save changes
//   POST   { token, action: "test" }      send a test notification
//   DELETE { token }                      unsubscribe (deletes everything about them)
import { NextResponse } from "next/server";
import { adminClient } from "@/lib/supabaseAdmin";
import { cleanPrefs, sendPush } from "@/lib/alerts";

export const dynamic = "force-dynamic";

const FIELDS = "id, topic, categories, free_only, radius_mi, instant, paused, last_test_at";

async function findByToken(token: unknown) {
  if (typeof token !== "string" || token.length < 20 || token.length > 100) return null;
  const { data } = await adminClient().from("push_subscribers").select(FIELDS).eq("manage_token", token).maybeSingle();
  return data;
}

const notFound = () =>
  NextResponse.json({ error: "This link isn't valid anymore — you may have already unsubscribed." }, { status: 404 });

async function readBody(req: Request): Promise<any> {
  try {
    return await req.json();
  } catch {
    return {};
  }
}

export async function GET(req: Request) {
  const sub = await findByToken(new URL(req.url).searchParams.get("token"));
  if (!sub) return notFound();
  const { id, last_test_at, ...visible } = sub as any;
  return NextResponse.json(visible);
}

export async function PUT(req: Request) {
  const body = await readBody(req);
  const sub = await findByToken(body.token);
  if (!sub) return notFound();
  const prefs = cleanPrefs(body);
  if (typeof prefs === "string") return NextResponse.json({ error: prefs }, { status: 400 });
  const { error } = await adminClient()
    .from("push_subscribers")
    .update({ ...prefs, paused: body.paused === true, updated_at: new Date().toISOString() })
    .eq("id", (sub as any).id);
  if (error) return NextResponse.json({ error: "Couldn't save. Please try again." }, { status: 500 });
  return NextResponse.json({ ok: true });
}

export async function POST(req: Request) {
  const body = await readBody(req);
  const sub: any = await findByToken(body.token);
  if (!sub) return notFound();
  if (body.action !== "test") return NextResponse.json({ error: "Unknown action" }, { status: 400 });
  if (sub.last_test_at && Date.now() - new Date(sub.last_test_at).getTime() < 60_000) {
    return NextResponse.json({ error: "One test per minute, please." }, { status: 429 });
  }
  const db = adminClient();
  await db.from("push_subscribers").update({ last_test_at: new Date().toISOString() }).eq("id", sub.id);
  const ok = await sendPush(sub.topic, "Test notification ✅", "Your Baltimore alerts are connected to this phone.", body.token);
  if (ok) await db.from("push_log").insert({ subscriber_id: sub.id, kind: "test" });
  return ok
    ? NextResponse.json({ ok: true })
    : NextResponse.json({ error: "The notification service didn't answer. Try again in a minute." }, { status: 502 });
}

export async function DELETE(req: Request) {
  const body = await readBody(req);
  const sub: any = await findByToken(body.token);
  if (!sub) return notFound();
  await sendPush(sub.topic, "You're unsubscribed", "No more Baltimore alerts will be sent. You can remove this topic from the ntfy app.");
  const { error } = await adminClient().from("push_subscribers").delete().eq("id", sub.id);
  if (error) return NextResponse.json({ error: "Couldn't unsubscribe. Please try again." }, { status: 500 });
  return NextResponse.json({ ok: true });
}
