// SERVER ONLY. Uses the Supabase service key, which bypasses row-level security.
// Never import this from a "use client" file.
import { createClient } from "@supabase/supabase-js";

export function adminClient() {
  const url = process.env.SUPABASE_URL || process.env.NEXT_PUBLIC_SUPABASE_URL;
  const key = process.env.SUPABASE_SERVICE_KEY;
  if (!url || !key) throw new Error("SUPABASE_SERVICE_KEY is not set in Vercel's environment variables");
  return createClient(url, key, { auth: { persistSession: false } });
}
