"use client";

import { INTERESTS, RADII, AlertPrefs } from "@/lib/alerts";

export default function AlertPrefsForm({ prefs, onChange }: { prefs: AlertPrefs; onChange: (p: AlertPrefs) => void }) {
  function toggle(key: string) {
    const has = prefs.categories.includes(key);
    onChange({ ...prefs, categories: has ? prefs.categories.filter((c) => c !== key) : [...prefs.categories, key] });
  }

  return (
    <div>
      <fieldset className="mb-6">
        <legend className="font-semibold mb-2">What are you into?</legend>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
          {INTERESTS.map((i) => {
            const on = prefs.categories.includes(i.key);
            return (
              <label
                key={i.key}
                className={`flex items-center gap-2 border rounded-lg px-3 py-2 cursor-pointer ${
                  on ? "border-white bg-neutral-800" : "border-neutral-700"
                }`}
              >
                <input type="checkbox" checked={on} onChange={() => toggle(i.key)} className="sr-only" />
                <span aria-hidden>{i.emoji}</span>
                <span>{i.label}</span>
                {on && <span className="ml-auto" aria-hidden>✓</span>}
              </label>
            );
          })}
        </div>
      </fieldset>

      <div className="mb-6">
        <label className="font-semibold block mb-2" htmlFor="radius">How far will you go?</label>
        <select
          id="radius"
          value={prefs.radius_mi}
          onChange={(e) => onChange({ ...prefs, radius_mi: parseInt(e.target.value) })}
          className="bg-neutral-900 border border-neutral-700 rounded px-3 py-2"
        >
          {RADII.map((r) => (
            <option key={r} value={r}>
              {r === 5 ? "5 miles — city neighborhoods" : r === 10 ? "10 miles — city + close county" : r === 20 ? "20 miles — Columbia, Towson & beyond" : "35 miles — the whole region"}
            </option>
          ))}
        </select>
      </div>

      <label className="flex items-start gap-3 mb-3">
        <input
          type="checkbox"
          className="mt-1"
          checked={prefs.free_only}
          onChange={(e) => onChange({ ...prefs, free_only: e.target.checked })}
        />
        <span>
          <span className="font-semibold">Free events only</span>
          <span className="block text-sm text-neutral-400">Free events are always listed first either way.</span>
        </span>
      </label>

      <label className="flex items-start gap-3 mb-6">
        <input
          type="checkbox"
          className="mt-1"
          checked={prefs.instant}
          onChange={(e) => onChange({ ...prefs, instant: e.target.checked })}
        />
        <span>
          <span className="font-semibold">Also ping me right away</span>
          <span className="block text-sm text-neutral-400">
            A quick heads-up when a new jazz/blues show, free or pop-up music, or market event is posted. Never
            between 10 PM and 8 AM. Otherwise you just get the weekly roundup.
          </span>
        </span>
      </label>
    </div>
  );
}
