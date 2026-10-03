"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { ArrowLeftRight, Star, X } from "lucide-react";
import { api, Company } from "@/lib/api";
import {
  getWatchlist,
  removeFromWatchlist,
} from "@/lib/watchlist";

interface WatchItem {
  ticker: string;
  company?: Company;
  loading: boolean;
  price?: number | null;
  changePct?: number | null;
  priceLoading: boolean;
}

function formatPrice(p?: number | null) {
  return p == null ? "—" : `$${p.toFixed(2)}`;
}

function formatChange(c: number) {
  return `${c >= 0 ? "+" : ""}${c.toFixed(2)}%`;
}

export default function WatchlistPage() {
  const [items, setItems] = useState<WatchItem[]>([]);
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
    const tickers =getWatchlist();
    if (tickers.length === 0) {
      setItems([]);
      return;
    }
    setItems(tickers.map((t) => ({ ticker: t, loading: true, priceLoading: true })));

    const update = (ticker: string, patch: Partial<WatchItem>) =>
      setItems((prev) =>
        prev.map((item) => (item.ticker === ticker ? { ...item, ...patch } : item))
      );

    tickers.forEach((ticker)=> {
      api
        .stockInfo(ticker)
        .then((info) => update(ticker, { company: info, loading: false }))
        .catch(() => update(ticker, { loading: false }));

      api
        .quote(ticker)
        .then((q) => update(ticker, { ...q, priceLoading: false }))
        .catch(() => update(ticker, { priceLoading: false }));
    });
  }, []);

  const remove = (ticker: string) => {
    removeFromWatchlist(ticker);
    setItems((prev )=> prev.filter((i) => i.ticker !== ticker));
  };

  if (!mounted) return null;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-text">Watchlist</h1>
        <p className="text-sm text-muted mt-0.5">
          Companies you follow — stored in your browser
        </p>
      </div>

      {items.length=== 0 ? (
        <div className="card p-12 text-center">
          <Star className="h-12 w-12 text-warning mx-auto mb-4" />
          <h2 className="text-lg font-semibold text-text mb-2">
            Your watchlist is empty
          </h2>
          <p className="text-muted text-sm mb-6">
            Add companies with the "Add to Watchlist" button on a
            company profile.
          </p>
          <Link
            href= "/"
            className="inline-block bg-accent hover:bg-accent-hover text-bg text-sm font-medium px-5 py-2 rounded-lg transition-colors"
          >
            Browse Companies →
          </Link>
        </div>
      ) : (
        <div className="card overflow-hidden">
          <div className="card-header justify-between">
            <span className="font-semibold text-text">
              {items.length} {items.length === 1 ? "company" : "companies"} tracked
            </span>
            <Link
              href="/compare"
              className="text-xs text-accent hover:text-accent-hover"
            >
              Compare
            </Link>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border/60">
                  <th className="text-left px-5 py-3 text-muted font-medium">Ticker</th>
                  <th className="text-left px-5 py-3 text-muted font-medium">Company</th>
                  <th className="text-left px-5 py-3 text-muted font-medium hidden md:table-cell">Sector</th>
                  <th className="text-right px-5 py-3 text-muted font-medium">Price</th>
                  <th className="text-right px-5 py-3 text-muted font-medium">1D</th>
                  <th className="px-5 py-3" />
                </tr>
              </thead>
              <tbody className ="divide-y divide-border/40">
                {items.map((item) => (
                  <tr
                    key={item.ticker}
                    className="hover:bg-surface2 transition-colors"
                  >
                    <td className = "px-5 py-4">
                      <Link
                        href={`/company/${item.ticker}`}
                        className="badge-ticker hover:text-accent-hover transition-colors"
                      >
                        {item.ticker}
                      </Link>
                    </td>
                    <td className="px-5 py-4 text-text">
                      {item.loading ? (
                        <div className="h-4 bg-border rounded w-36 animate-pulse" />
                      ) : (
                        item.company?.name || item.ticker
                      )}
                    </td>
                    <td className="px-5 py-4 text-muted hidden md:table-cell">
                      {item.loading ? (
                        <div className ="h-4 bg-border rounded w-24 animate-pulse" />
                      ) : (
                        item.company?.sector || "—"
                      )}
                    </td>
                    <td className="px-5 py-4 text-right font-mono text-text">
                      {item.priceLoading ? (
                        <div className="h-4 bg-border rounded w-16 ml-auto animate-pulse" />
                      ) : (
                        formatPrice(item.price)
                      )}
                    </td>
                    <td className="px-5 py-4 text-right font-mono text-xs">
                      {item.priceLoading ? (
                        <div className="h-4 bg-border rounded w-12 ml-auto animate-pulse" />
                      ) : item.changePct == null ? (
                        <span className="text-muted">—</span>
                      ) : (
                        <span className={item.changePct >= 0 ? "text-success" : "text-danger"}>
                          {formatChange(item.changePct)}
                        </span>
                      )}
                    </td>
                    <td className="px-5 py-4 text-right">
                      <div className="flex items-center justify-end gap-3">
                        <Link
                          href={`/company/${item.ticker}`}
                          className="text-xs text-accent hover:text-accent-hover"
                        >
                          Profile →
                        </Link>
                        <button
                          onClick={()=> remove(item.ticker)}
                          className="text-xs text-muted hover:text-danger transition-colors"
                          title="Remove"
                          aria-label={`Remove ${item.ticker}`}
                        >
                          <X className="h-4 w-4" />
                        </button>
                      </div>
                    </td>
                  </tr>

                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
      {items.length >= 2 && (
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <Link
            href={`/compare?a=${items[0].ticker}&b=${items[1].ticker}`}
            className="card p-4 hover:border-accent/40 transition-colors flex items-center gap-3"
          >
            <ArrowLeftRight className="h-5 w-5 text-accent shrink-0" />
            <div>
              <div className="text-text text-sm font-medium">
                Compare {items[0].ticker} vs {items[1].ticker}
              </div>
              <div className="text-xs text-muted">Chart analysis →</div>
            </div>
          </Link>
        </div>
      )}
      
    </div>
  );
}