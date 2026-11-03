// Anonymous visitors get a random id stored in a cookie so their quiz answers
// and saved events persist without requiring an account. Idempotent.
export function getOrCreateAnonId(): string {
  if (typeof document === "undefined") return "";
  const match = document.cookie.match(/(?:^|; )anon_id=([^;]+)/);
  if (match) return match[1];
  const id = crypto.randomUUID();
  document.cookie = `anon_id=${id}; path=/; max-age=${60 * 60 * 24 * 365 * 2}; samesite=lax`;
  return id;
}
