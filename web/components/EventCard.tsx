"use client";

import { googleCalendarUrl, outlookCalendarUrl, buildIcsDataUrl } from "@/lib/calendar";
import { supabase, getOrCreateAnonId } from "@/lib/supabaseClient";

export default function EventCard({
  event,
  matchScore,
  noveltyScore,
  profileId,
}: {
  event: any;
  matchScore: number;
  noveltyScore: number;
  profileId: string | null;
}) {
  async function setStatus(status: "saved" | "attended" | "not_for_me") {
    if (!profileId) return;
    await supabase
      .from("interactions")
      .upsert({ profile_id: profileId, event_id: event.id, status }, { onConflict: "profile_id,event_id" });
  }

  return (
    <div className="border border-neutral-800 rounded-lg p-4 mb-4">
      <div className="flex justify-between items-start gap-2">
        <a href={event.source_url} target="_blank" rel="noreferrer" className="font-semibold text-lg hover:underline">
          {event.title}
        </a>
        <div className="text-xs text-neutral-400 whitespace-nowrap">
          Match {Math.round(matchScore * 100)}% · Novelty {Math.round(noveltyScore * 100)}%
        </div>
      </div>
      <div className="text-sm text-neutral-400 mt-1">
        {new Date(event.start_time).toLocaleString(undefined, {
          weekday: "short", month: "short", day: "numeric", hour: "numeric", minute: "2-digit",
        })}
        {event.venue_name ? ` · ${event.venue_name}` : ""}
      </div>
      <div className="flex flex-wrap gap-1 mt-2">
        {(event.categories || []).map((c: string) => (
          <span key={c} className="text-xs bg-neutral-800 rounded-full px-2 py-0.5">{c.replace("_", " ")}</span>
        ))}
      </div>

      <div className="flex flex-wrap gap-3 mt-3 text-sm">
        <a className="underline" href={googleCalendarUrl(event.title, event.start_time, event.end_time, event.venue_name)} target="_blank" rel="noreferrer">Google Cal</a>
        <a className="underline" href={outlookCalendarUrl(event.title, event.start_time, event.end_time, event.venue_name)} target="_blank" rel="noreferrer">Outlook</a>
        <a className="underline" href={buildIcsDataUrl(event.title, event.start_time, event.end_time, event.venue_name)} download={`${event.title}.ics`}>Apple / .ics</a>
      </div>

      <div className="flex gap-2 mt-3">
        <button onClick={() => setStatus("saved")} className="text-sm px-3 py-1 rounded bg-neutral-800 hover:bg-neutral-700">Save</button>
        <button onClick={() => setStatus("attended")} className="text-sm px-3 py-1 rounded bg-neutral-800 hover:bg-neutral-700">Attended</button>
        <button onClick={() => setStatus("not_for_me")} className="text-sm px-3 py-1 rounded bg-neutral-800 hover:bg-neutral-700">Not for me</button>
      </div>
    </div>
  );
}
