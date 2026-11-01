"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import AlertPrefsForm from "@/components/AlertPrefsForm";
import { AlertPrefs } from "@/lib/alerts";

type Loaded = AlertPrefs & { topic: string; paused: boolean };

export default function ManageAlerts() {
  const [token, setToken] = useState("");
  const [sub, setSub] = useState<Loaded | null>(null);
  const [status, setStatus] = useState<"loading" | "ready" | "missing" | "gone">("loading");
  const [msg, setMsg] = useState("");
  const [busy, setBusy] = useState(false);
  const [confirmStop, setConfirmStop] = useState(false);

  useEffect(() => {
    const t = new URLSearchParams(window.location.search).get("token") || "";
    setToken(t);
    if (!t) return setStatus("missing");
    fetch(`/api/alerts/manage?token=${encodeURIComponent(t)}`)
      .then(async (r) => {
        if (!r.ok) return setStatus("missing");
        setSub(await r.json());
        setStatus("ready");
      })
      .catch(() => setStatus("missing"));
  }, []);

  async function call(method: string, extra: object = {}) {
    setBusy(true);
    setMsg("");
    const res = await fetch("/api/alerts/manage", {
      method,
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ token, ...extra }),
    });
    const json = await res.json().catch(() => ({}));
    setBusy(false);
    return { ok: res.ok, json };
  }

  if (status === "loading") return <p>Loading…</p>;
  if (status === "gone")
    return (
      <div>
        <h1 className="text-2xl font-bold mb-2">You're unsubscribed</h1>
        <p className="text-neutral-400 mb-4">
          Everything about your alerts has been deleted. You can also remove the topic from the ntfy app.
        </p>
        <Link href="/alerts" className="underline">Changed your mind? Sign up again</Link>
      </div>
    );
  if (status === "missing" || !sub)
    return (
      <div>
        <h1 className="text-2xl font-bold mb-2">Link not found</h1>
        <p className="text-neutral-400 mb-4">
          This link isn't valid anymore — you may have already unsubscribed. Use the “Change or stop alerts” button on
          any notification to get a working link.
        </p>
        <Link href="/alerts" className="underline">Sign up for alerts</Link>
      </div>
    );

  return (
    <div>
      <Link href="/" className="text-sm text-neutral-400 underline">← Back to events</Link>
      <h1 className="text-2xl font-bold mt-3 mb-1">Your phone alerts</h1>
      <p className="text-sm text-neutral-400 mb-6">
        ntfy topic: <code>{sub.topic}</code>
        {sub.paused && <span className="ml-2 px-2 py-0.5 rounded bg-yellow-900 text-yellow-200">Paused</span>}
      </p>

      <AlertPrefsForm prefs={sub} onChange={(p) => setSub({ ...sub, ...p })} />

      {msg && <p className="mb-3" role="status">{msg}</p>}

      <div className="flex flex-wrap gap-3">
        <button
          disabled={busy || sub.categories.length === 0}
          onClick={async () => {
            const r = await call("PUT", { ...sub });
            setMsg(r.ok ? "Saved ✓" : r.json.error || "Couldn't save.");
          }}
          className="px-4 py-2 rounded bg-white text-black font-medium disabled:opacity-40"
        >
          Save changes
        </button>
        <button
          disabled={busy}
          onClick={async () => {
            const next = { ...sub, paused: !sub.paused };
            const r = await call("PUT", next);
            if (r.ok) setSub(next);
            setMsg(r.ok ? (next.paused ? "Paused — no notifications until you resume." : "Resumed ✓") : r.json.error);
          }}
          className="px-4 py-2 rounded border border-neutral-600"
        >
          {sub.paused ? "Resume alerts" : "Pause alerts"}
        </button>
        <button
          disabled={busy}
          onClick={async () => {
            const r = await call("POST", { action: "test" });
            setMsg(r.ok ? "Test sent — check your phone." : r.json.error || "Couldn't send a test.");
          }}
          className="px-4 py-2 rounded border border-neutral-600"
        >
          Send a test
        </button>
      </div>

      <div className="mt-10 border-t border-neutral-800 pt-6">
        {!confirmStop ? (
          <button onClick={() => setConfirmStop(true)} className="text-red-400 underline">
            Unsubscribe and delete my alerts
          </button>
        ) : (
          <div>
            <p className="mb-3">This stops all notifications and deletes your settings. Continue?</p>
            <div className="flex gap-3">
              <button
                disabled={busy}
                onClick={async () => {
                  const r = await call("DELETE");
                  if (r.ok) setStatus("gone");
                  else setMsg(r.json.error || "Couldn't unsubscribe.");
                }}
                className="px-4 py-2 rounded bg-red-600 text-white font-medium"
              >
                Yes, unsubscribe
              </button>
              <button onClick={() => setConfirmStop(false)} className="px-4 py-2 rounded border border-neutral-600">
                Keep my alerts
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
