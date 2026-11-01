"use client";

import { useState } from "react";
import Link from "next/link";
import AlertPrefsForm from "@/components/AlertPrefsForm";
import { AlertPrefs, DEFAULT_PREFS } from "@/lib/alerts";

const APP_STORE = "https://apps.apple.com/app/ntfy/id1625396347";
const PLAY_STORE = "https://play.google.com/store/apps/details?id=io.heckel.ntfy";

function CopyBox({ value, label }: { value: string; label: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <div className="flex gap-2 items-stretch my-2">
      <code className="flex-1 bg-neutral-900 border border-neutral-700 rounded px-3 py-2 break-all text-sm">{value}</code>
      <button
        type="button"
        onClick={async () => {
          await navigator.clipboard.writeText(value);
          setCopied(true);
          setTimeout(() => setCopied(false), 2000);
        }}
        className="px-3 rounded bg-white text-black text-sm font-medium"
        aria-label={`Copy ${label}`}
      >
        {copied ? "Copied" : "Copy"}
      </button>
    </div>
  );
}

export default function AlertsSignup() {
  const [prefs, setPrefs] = useState<AlertPrefs>(DEFAULT_PREFS);
  const [honeypot, setHoneypot] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [done, setDone] = useState<{ topic: string; manage_url: string } | null>(null);

  async function submit() {
    setBusy(true);
    setError("");
    const res = await fetch("/api/alerts", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ...prefs, website: honeypot }),
    });
    const json = await res.json().catch(() => ({}));
    setBusy(false);
    if (!res.ok) return setError(json.error || "Something went wrong. Please try again.");
    setDone(json);
    window.scrollTo(0, 0);
  }

  if (done) {
    return (
      <div>
        <h1 className="text-2xl font-bold mb-4">Almost done — connect your phone</h1>
        <ol className="space-y-6 list-decimal pl-5">
          <li>
            <p className="font-semibold">Install the free ntfy app</p>
            <p className="text-sm text-neutral-400 mb-2">No account, no email, no ads. It just receives notifications.</p>
            <div className="flex gap-3 text-sm">
              <a className="underline" href={APP_STORE} target="_blank" rel="noreferrer">iPhone (App Store)</a>
              <a className="underline" href={PLAY_STORE} target="_blank" rel="noreferrer">Android (Google Play)</a>
            </div>
          </li>
          <li>
            <p className="font-semibold">In ntfy, tap “+” and subscribe to this topic</p>
            <CopyBox value={done.topic} label="topic" />
            <p className="text-sm text-neutral-400">
              Leave the server set to ntfy.sh. Keep this name to yourself — it's your private channel. On Android you can
              also <a className="underline" href={`ntfy://ntfy.sh/${done.topic}`}>tap here to subscribe</a>.
            </p>
          </li>
          <li>
            <p className="font-semibold">Save your “change or stop” link</p>
            <CopyBox value={done.manage_url} label="manage link" />
            <p className="text-sm text-neutral-400">
              Bookmark it. Every roundup also has a “Change or stop alerts” button, so you can always get back to it.
            </p>
          </li>
        </ol>
        <p className="mt-8 text-neutral-300">
          A welcome message is already waiting in the app. Your first weekly roundup arrives within a day.
        </p>
        <Link href={done.manage_url.replace(/^https?:\/\/[^/]+/, "")} className="inline-block mt-4 underline">
          Open your settings / send a test
        </Link>
      </div>
    );
  }

  return (
    <div>
      <Link href="/" className="text-sm text-neutral-400 underline">← Back to events</Link>
      <h1 className="text-2xl font-bold mt-3 mb-2">Baltimore picks on your phone, once a week</h1>
      <p className="text-neutral-400 mb-6">
        No social media, no account, no email. Pick what you like and get one notification a week with what's
        happening around Baltimore. Change or stop anytime.
      </p>

      <AlertPrefsForm prefs={prefs} onChange={setPrefs} />

      {/* invisible to people; bots that fill every field get rejected */}
      <input
        type="text" tabIndex={-1} autoComplete="off" value={honeypot}
        onChange={(e) => setHoneypot(e.target.value)} className="hidden" aria-hidden name="website"
      />

      {error && <p className="text-red-400 mb-3" role="alert">{error}</p>}
      <button
        onClick={submit}
        disabled={busy || prefs.categories.length === 0}
        className="px-5 py-2 rounded bg-white text-black font-medium disabled:opacity-40"
      >
        {busy ? "Setting up…" : "Get my weekly picks"}
      </button>
      {prefs.categories.length === 0 && <p className="text-sm text-neutral-500 mt-2">Pick at least one interest.</p>}

      <p className="text-xs text-neutral-500 mt-8">
        What we store: your interests, distance, a random channel name, and a scrambled code from your connection used only to block spam sign-ups. No name, email or phone number.
        Notifications are delivered by the open-source ntfy service (ntfy.sh). Unsubscribing deletes everything.
      </p>
    </div>
  );
}
