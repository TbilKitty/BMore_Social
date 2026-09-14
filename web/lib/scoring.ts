export type EventRow = {
  id: string;
  title: string;
  categories: string[];
  start_time: string;
  [key: string]: any;
};

// See scraper/scoring.py for the documented formula this mirrors.
export function matchScore(event: EventRow, weights: Record<string, number>): number {
  if (!event.categories?.length) return 0.3;
  const scores = event.categories.map((c) => weights[c] ?? 0);
  return scores.reduce((a, b) => a + b, 0) / scores.length;
}

export function noveltyScore(event: EventRow, recentCategories: string[][]): number {
  if (!recentCategories.length) return 1.0;
  const eventCats = new Set(event.categories ?? []);
  const overlapping = recentCategories.filter((cats) => cats.some((c) => eventCats.has(c)));
  return 1 - overlapping.length / recentCategories.length;
}
