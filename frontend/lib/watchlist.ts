"use client";

const KEY = "pharmasee_watchlist";

export function getWatchlist(): string[] {
  if (typeof window === "undefined") return [];
  try {
    const raw= localStorage.getItem(KEY);
    return raw ? (JSON.parse(raw) as string[]) : [];
  } catch {
    return [];
  }
}
export function addToWatchlist(ticker: string): string[] {
  const list = getWatchlist();
  if (!list.includes(ticker)) {
    const next = [...list, ticker];
    localStorage.setItem(KEY, JSON.stringify(next));
    return next;
  }
  return list ;
}

export function removeFromWatchlist(ticker: string): string[] {
  const next = getWatchlist().filter((t) => t !== ticker);
  localStorage.setItem(KEY, JSON.stringify(next));
  return next;
}

export function isInWatchlist(ticker: string): boolean {
  return getWatchlist().includes(ticker);

}