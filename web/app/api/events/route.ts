// GET /api/events?radius=35 — upcoming events within the radius (events with no known
// distance are included; the scraper only keeps Baltimore-area listings).
import { NextResponse } from "next/server";
import { upcomingEvents } from "@/lib/db";

export const dynamic = "force-dynamic";

export async function GET(req: Request) {
  const radius = Number(new URL(req.url).searchParams.get("radius")) || 35;
  try {
    const events = (await upcomingEvents())
      .filter((e) => e.distance_from_baltimore_mi == null || Number(e.distance_from_baltimore_mi) <= radius)
      .slice(0, 200);
    return NextResponse.json({ events });
  } catch (err) {
    console.error("events load failed", err);
    return NextResponse.json({ events: [], error: "Events are temporarily unavailable." }, { status: 500 });
  }
}
