"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { api, Company, StockPricePoint } from "@/lib/api";
import {
  getWatchlist,
  removeFromWatchlist,
} from "@/lib/watchlist";
import MomentumBadge from "@/components/MomentumBadge";

interface WatchItem {
  ticker: string;
  company?: Company;
  latestPrice?: StockPricePoint;
  loading: boolean;
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
    setItems(tickers.map((t) => ({ ticker: t, loading: true })));

    tickers.forEach((ticker)=> {
      api
        .stockInfo(ticker)
        .then((info) => {
          setItems((prev) =>
            prev.map((item) =>
              item.ticker === ticker
                ? { ...item, company: info, loading: false }
                : item
            )
          );
        })

        .catch(() => {
          setItems((prev) =>
            prev.map((item) =>
              item.ticker === ticker ? { ...item, loading: false } : item
            )
          );
        });
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
        <h1 className="text-2xl font-bold text-white">Watchlist</h1>
        <p className="text-sm text-gray-400 mt-0.5">
          Takip ettiğin şirketler — tarayıcında saklanır
        </p>
      </div>

      {items.length=== 0 ? (
        <div className="card p-12 text-center">
          <div className="text-5xl mb-4">⭐</div>
          <h2 className="text-lg font-semibold text-white mb-2">
            Watchlist boş
          </h2>
          <p className="text-gray-400 text-sm mb-6">
            Şirket profilinden "Watchlist'e Ekle" butonuna tıklayarak
            şirket ekleyebilirsin.
          </p>
          <Link
            href= "/"
            className="inline-block bg-brand-600 hover:bg-brand-700 text-white text-sm font-medium px-5 py-2 rounded-lg transition-colors"
          >
            Şirketlere Göz At →
          </Link>
        </div>
      ) : (
        <div className="card overflow-hidden">
          <div className="card-header justify-between">
            <span className="font-semibold text-white">
              {items.length} şirket takip ediliyor
            </span>
            <Link
              href="/compare"
              className="text-xs text-indigo-400 hover:text-indigo-300"
            >
              Karşılaştır
            </Link>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-700/60">
                  <th className="text-left px-5 py-3 text-gray-400 font-medium">Ticker</th>
                  <th className="text-left px-5 py-3 text-gray-400 font-medium">Şirket</th>
                  <th className="text-left px-5 py-3 text-gray-400 font-medium hidden md:table-cell">Sektör</th>
                  <th className="px-5 py-3" />
                </tr>
              </thead>
              <tbody className ="divide-y divide-gray-700/40">
                {items.map((item) => (
                  <tr
                    key={item.ticker}
                    className="hover:bg-gray-700/20 transition-colors"
                  >
                    <td className = "px-5 py-4">
                      <Link
                        href={`/company/${item.ticker}`}
                        className="badge-ticker hover:text-indigo-200 transition-colors"
                      >
                        {item.ticker}
                      </Link>
                    </td>
                    <td className="px-5 py-4 text-white">
                      {item.loading ? (
                        <div className="h-4 bg-gray-700 rounded w-36 animate-pulse" />
                      ) : (
                        item.company?.name || item.ticker
                      )}
                    </td>
                    <td className="px-5 py-4 text-gray-400 hidden md:table-cell">
                      {item.loading ? (
                        <div className ="h-4 bg-gray-700 rounded w-24 animate-pulse" />
                      ) : (
                        item.company?.sector || "Biotechnology"
                      )}
                    </td>
                    <td className="px-5 py-4 text-right">
                      <div className="flex items-center justify-end gap-3">
                        <Link
                          href={`/company/${item.ticker}`}
                          className="text-xs text-indigo-400 hover:text-indigo-300"
                        >
                          Profil →
                        </Link>
                        <button
                          onClick={()=> remove(item.ticker)}
                          className="text-xs text-gray-500 hover:text-red-400 transition-colors"
                          title="Kaldır"
                        >
                          X
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
      {items.length > 0 && (
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          {items.slice(0, 2).map((item) => (
            <Link
              key={item.ticker}
              href={`/compare?a=${items[0]?.ticker}&b=${items[1]?.ticker}`}
              className="card p-4 hover:border-brand-500/40 transition-colors flex items-center gap-3"
            >
              <span className="text-xl">⚖️</span>
              <div>
                <div className="text-white text-sm font-medium">
                  {items[0]?.ticker} vs {items[1]?.ticker} Karşılaştır
                </div>
                <div className="text-xs text-gray-500">Grafik analizi →</div>
              </div>
            </Link>

          )).slice(0, 1)}
        </div>
      )}
      
    </div>
  );
}