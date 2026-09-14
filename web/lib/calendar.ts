import { createEvent } from "ics";

export function googleCalendarUrl(title: string, start: string, end: string, location?: string) {
  const fmt = (iso: string) => new Date(iso).toISOString().replace(/[-:]|\.\d{3}/g, "");
  const params = new URLSearchParams({
    action: "TEMPLATE",
    text: title,
    dates: `${fmt(start)}/${fmt(end || start)}`,
    location: location || "",
  });
  return `https://calendar.google.com/calendar/render?${params.toString()}`;
}

export function outlookCalendarUrl(title: string, start: string, end: string, location?: string) {
  const params = new URLSearchParams({
    path: "/calendar/action/compose",
    rru: "addevent",
    subject: title,
    startdt: start,
    enddt: end || start,
    location: location || "",
  });
  return `https://outlook.live.com/calendar/0/deeplink/compose?${params.toString()}`;
}

// Apple Calendar has no web-add URL scheme; the standard approach is offering
// a downloadable .ics file, which macOS/iOS opens directly into Calendar.
export function buildIcsDataUrl(title: string, start: string, end: string, location?: string): string {
  const s = new Date(start);
  const e = new Date(end || start);
  const { value } = createEvent({
    title,
    start: [s.getFullYear(), s.getMonth() + 1, s.getDate(), s.getHours(), s.getMinutes()],
    end: [e.getFullYear(), e.getMonth() + 1, e.getDate(), e.getHours(), e.getMinutes()],
    location: location || "",
  });
  return `data:text/calendar;charset=utf8,${encodeURIComponent(value || "")}`;
}
