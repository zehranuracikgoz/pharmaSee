"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { api, Company } from "@/lib/api";
import SearchBar from "@/components/SearchBar";
import { getWatchlist } from "@/lib/watchlist";

const TICKERS = [
  "MRNA", "BNTX", "PFE", "REGN", "BIIB",
  "GILD", "AMGN", "VRTX", "SGEN", "BLUE",
  "BEAM", "CRSP", "NTLA",
];

interface CompanyRow extends Company {
  loading: boolean;
}

function formatMarketCap(v?: number) {
  if (!v) return "—";
  if (v >= 1e12) return `$${(v / 1e12).toFixed(2)}T`;
  if (v >= 1e9) return `$${(v / 1e9).toFixed(2)}B`;
  if (v >= 1e6) return `$${(v / 1e6).toFixed(2)}M`;
  return `$${v.toFixed(0)}`;
}

export default function DashboardPage() {
  const [companies, setCompanies] = useState<CompanyRow[]>([]);
  const [syncing, setSyncing] = useState(false);
  const [syncMsg, setSyncMsg] = useState("");
  const [watchlist, setWatchlist] = useState<string[]>([]);
  useEffect(() => {
    setWatchlist(getWatchlist());
  }, []);

  useEffect(() => {
    TICKERS.forEach((ticker) => {
      setCompanies((prev) => {
        if (prev.find((c) => c.ticker === ticker)) return prev;
        return [
          ...prev,
          { ticker, name: "", loading: true },
        ] as CompanyRow[];
      });

      api
        .stockInfo(ticker)
        .then((info) => {
          setCompanies((prev) =>
            prev.map((c) =>
              c.ticker === ticker ? { ...info, loading: false } : c
            )
          );
        })
        .catch(() => {
          setCompanies((prev) =>
            prev.map((c) =>
              c.ticker === ticker
                ? { ticker, name: ticker, loading: false }
                : c
            )
          );
        });
    });
  }, []);

  const handleSync = async () => {
    setSyncing(true);
    setSyncMsg("");
    try {
      const r = await api.fdaSync();
      setSyncMsg(r.message);
    } catch {
      setSyncMsg("Sync başarısız oldu");
    } finally {
      setSyncing(false);
    }
  };

  const watchlistCompanies = companies.filter((c) =>
    watchlist.includes(c.ticker)
  );

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between gap-4 flex-wrap">
        <div>
          <h1 className="text-2xl font-bold text-white">Dashboard</h1>
          <p className="text-sm text-gray-400 mt-0.5">
            Biotech hisseleri ve FDA onay verilerine genel bakış
          </p>
        </div>
        <div className="flex items-center gap-3">
          <SearchBar />
          <button
            onClick={handleSync}
            disabled={syncing}
            className="inline-flex items-center gap-2 bg-brand-600 hover:bg-brand-700 disabled:opacity-50 text-white text-sm font-medium px-4 py-2 rounded-lg transition-colors"
          >
            {syncing ? "Senkronize ediliyor…" : "🔄 FDA Sync"}
          </button>
        </div>
      </div>

      {syncMsg && (
        <div className="text-sm text-emerald-400 bg-emerald-500/10 border border-emerald-500/20 rounded-lg px-4 py-2">
          ✓ {syncMsg}
        </div>
      )}

      {watchlistCompanies.length > 0 && (
        <section>
          <h2 className="text-sm font-semibold text-gray-400 uppercase tracking-wide mb-3">
            ⭐ Watchlist
          </h2>
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-3">
            {watchlistCompanies.map((c) => (
              <Link
                key={c.ticker}
                href={`/company/${c.ticker}`}
                className="card p-4 hover:border-brand-500/50 transition-colors group"
              >
                <div className="badge-ticker group-hover:text-indigo-200 transition-colors">
                  {c.ticker}
                </div>
                <div className="text-white font-medium text-sm mt-1 truncate">
                  {c.name || c.ticker}
                </div>
                <div className="text-xs text-gray-500 mt-0.5">
                  {formatMarketCap(c.market_cap)}
                </div>
              </Link>
            ))}
          </div>
        </section>
      )}

      {/* for stats bar */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        <div className="card p-4">
          <div className="stat-label">Toplam Şirket</div>
          <div className="stat-value">{companies.length}</div>
        </div>
        <div className="card p-4">
          <div className="stat-label">Watchlist</div>
          <div className="stat-value">{watchlist.length}</div>
        </div>
        <div className = "card p-4">
          <div className="stat-label">Veri Kaynağı</div>
          <div className="text-lg font-bold text-indigo-300">OpenFDA</div>
        </div>
        <div className="card p-4">
          <div className="stat-label">Hisse Verisi</div>
          <div className="text-lg font-bold text-indigo-300">yfinance</div>
        </div>
      </div>

      {/* for company table */}
      <section>
        <h2 className = "text-sm font-semibold text-gray-400 uppercase tracking-wide mb-3">
          Tüm Şirketler
        </h2>
        <div className="card overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-700/60">
                  <th className="text-left px-4 py-3 text-gray-400 font-medium">
                    Ticker
                  </th>
                  <th className="text-left px-4 py-3 text-gray-400 font-medium">
                    Şirket
                  </th>
                  <th className ="text-left px-4 py-3 text-gray-400 font-medium hidden md:table-cell">
                    Sektör
                  </th>
                  <th className="text-right px-4 py-3 text-gray-400 font-medium">
                    Piyasa Değeri
                  </th>
                  <th className="px-4 py-3" />
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-700/40">
                {companies.length === 0
                  ? Array.from({ length: 8 }).map((_, i) => (
                      <tr key = {i} className="animate-pulse">
                        <td className="px-4 py-3">
                          <div className="h-4 bg-gray-700 rounded w-12" />
                        </td>
                        <td className="px-4 py-3">
                          <div className="h-4 bg-gray-700 rounded w-40" />
                        </td>
                        <td className="px-4 py-3 hidden md:table-cell">
                          <div className="h-4 bg-gray-700 rounded w-24" />
                        </td>
                        <td className="px-4 py-3 text-right">
                          <div className="h-4 bg-gray-700 rounded w-20 ml-auto" />
                        </td>
                        <td className="px-4 py-3" />
                      </tr>
                    ))
                  : companies.map((c) => (
                      <tr
                        key={c.ticker}
                        className="hover:bg-gray-700/30 transition-colors"
                      >
                        <td className="px-4 py-3">
                          <span className="badge-ticker">{c.ticker}</span>
                        </td>
                        <td className="px-4 py-3 text-white">
                          {c.loading ? (
                            <div className="h-4 bg-gray-700 rounded w-32 animate-pulse" />
                          ) : (
                            c.name || c.ticker
                          )}
                        </td>
                        <td className="px-4 py-3 text-gray-400 hidden md:table-cell">
                          {c.sector|| "Biotechnology"}
                        </td>
                        <td className="px-4 py-3 text-right font-mono text-gray-300">
                          {c.loading ? (
                            <div className="h-4 bg-gray-700 rounded w-16 ml-auto animate-pulse" />
                          ) : (
                            formatMarketCap(c.market_cap)
                          )}
                        </td>
                        <td className="px-4 py-3 text-right">
                          <Link
                            href={`/company/${c.ticker}`}
                            className="text-xs text-indigo-400 hover:text-indigo-300 font-medium"
                          >
                            Detay
                          </Link>
                        </td>
                      </tr>
                    ))}
              </tbody>
            </table>
          </div>
        </div>
      </section>

      {/* for quick links */}
      <section className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <Link
          href="/calendar"
          className="card p-5 hover:border-amber-500/40 transition-colors group"
        >
          <div className="text-2xl mb-2">📅</div>
          <div className="font-semibold text-white group-hover:text-amber-300 transition-colors">
            FDA Takvim
          </div>
          <div className="text-xs text-gray-400 mt-1">
            Yaklaşan FDA onay kararları
          </div>
        </Link>
        <Link
          href="/compare"
          className="card p-5 hover:border-brand-500/40 transition-colors group"
        >
          <div className = "text-2xl mb-2">⚖️</div>
          <div className="font-semibold text-white group-hover:text-indigo-300 transition-colors">
            Şirket Karşılaştır
          </div>
          <div className="text-xs text-gray-400 mt-1">
            İki ticker yan yana grafik
          </div>
        </Link>
        <Link
          href="/watchlist"
          className="card p-5 hover:border-emerald-500/40 transition-colors group"
        >
          <div className="text-2xl mb-2">⭐</div>
          <div className="font-semibold text-white group-hover:text-emerald-300 transition-colors">
            Watchlist
          </div>
          <div className="text-xs text-gray-400 mt-1">
            Takip ettiğin şirketler
          </div>
        </Link>
      </section>

    </div>
  );
}