"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { ArrowLeftRight, CalendarDays, Download, Star } from "lucide-react";
import { api, Company } from "@/lib/api";
import SearchBar from "@/components/SearchBar";
import { getWatchlist } from "@/lib/watchlist";

interface CompanyRow extends Company {
  loading: boolean;
  changePct?: number | null; // 1-day % change
  quoteLoading: boolean;
}

function formatChange(c: number) {
  return `${c >= 0 ? "+" : ""}${c.toFixed(2)}%`;
}

function formatMarketCap(v?: number) {
  if (!v) return "—";
  if (v >= 1e12) return `$${(v / 1e12).toFixed(2)}T`;
  if (v >= 1e9) return `$${(v / 1e9).toFixed(2)}B`;
  if (v >= 1e6) return `$${(v / 1e6).toFixed(2)}M`;
  return `$${v.toFixed(0)}`;
}

function csvCell(value: string | number | undefined | null): string {
  if (value ==null) return "";
  let s = String(value);
  // keep spreadsheet apps from evaluating text as a formula
  // real numbers (e.g. "-1.14") are written as-is
  if (/^[=+\-@]/.test(s) && !/^[+-]?\d+(\.\d+)?([eE][+-]?\d+)?$/.test(s)) s = `'${s}`;
  return /[",\r\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
}

function downloadCompaniesCsv(rows: CompanyRow[]) {
  const lines = [
    "ticker,name,sector,market_cap,change_1d_pct",
    ...rows.map((c) =>
      [c.ticker, c.name, c.sector, c.market_cap, c.changePct?.toFixed(2)].map(csvCell).join(",")
    ),
  ];
  // bom so excel opens the file as UTF-8
  const blob = new Blob(["\uFEFF" + lines.join("\r\n")], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const a=document.createElement("a");
  a.href = url;
  a.download = "pharmasee_companies.csv";
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

export default function DashboardPage() {
  const searchRef = useRef<HTMLInputElement>(null);
  const [companies, setCompanies] = useState<CompanyRow[]>([]);
  const [initialLoad, setInitialLoad] = useState(true);
  const [listError, setListError] = useState("");
  const [watchlist, setWatchlist] = useState<string[]>([]);

  // Load watchlist
  useEffect(() => {
    setWatchlist(getWatchlist());
  }, []);

  // "/" focuses the search box, unless the user is already typing somewhere
  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key !== "/" || e.ctrlKey || e.metaKey || e.altKey) return;
      const el = document.activeElement as HTMLElement | null;
      if (el && (["INPUT", "TEXTAREA", "SELECT"].includes(el.tagName) || el.isContentEditable)) {
        return;
      }
      e.preventDefault(); // don't type the "/" into the box
      searchRef.current?.focus();
    };
    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, []);

  // /companies only returns ticker + name; market cap and sector are filled in per row
  const enrich = (tickers: string[]) => {
    tickers.forEach((ticker) => {
      api
        .stockInfo(ticker)
        .then((info) =>
          setCompanies((prev) =>
            prev.map((c) => (c.ticker === ticker ? { ...c, ...info, loading: false } : c))
          )
        )
        .catch(() =>
          setCompanies((prev) =>
            prev.map((c) => (c.ticker === ticker ? { ...c, loading: false } : c))
          )
        );

      api
        .quote(ticker)
        .then(({ changePct }) =>
          setCompanies((prev) =>
            prev.map((c) => (c.ticker === ticker ? { ...c, changePct, quoteLoading: false } : c))
          )
        )
        .catch(() =>
          setCompanies((prev) =>
            prev.map((c) => (c.ticker === ticker ? { ...c, quoteLoading: false } : c))
          )
        );
    });
  };

  const loadCompanies = () =>
    api.companies().then((list) => {
      setListError("");
      setCompanies(list.map((c) => ({ ...c, loading: true, quoteLoading: true })));
      enrich(list.map((c) => c.ticker));
    });

  // Load company list — one fast call, details fill in afterwards
  useEffect(() => {
    loadCompanies()
      .then(() => setInitialLoad(false))
      .catch((err) => {
        setListError(err.message || "Could not load the company list");
        setInitialLoad(false);
      });
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const watchlistCompanies = companies.filter((c) =>
    watchlist.includes(c.ticker)
  );

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between gap-4 flex-wrap">
        <div>
          <h1 className="text-2xl font-bold text-text">Dashboard</h1>
          <p className="text-sm text-muted mt-0.5">
            Overview of biotech stocks and FDA approval data
          </p>
        </div>
        <SearchBar inputRef={searchRef} />
      </div>

      {watchlistCompanies.length > 0 && (
        <section>
          <h2 className="flex items-center gap-2 text-sm font-semibold text-muted uppercase tracking-wide mb-3">
            <Star className="h-4 w-4 text-warning" />
            Watchlist
          </h2>
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-3">
            {watchlistCompanies.map((c) => (
              <Link
                key={c.ticker}
                href={`/company/${c.ticker}`}
                className="card p-4 hover:border-accent/50 transition-colors group"
              >
                <div className="badge-ticker group-hover:text-accent-hover transition-colors">
                  {c.ticker}
                </div>
                <div className="text-text font-medium text-sm mt-1 truncate">
                  {c.name || c.ticker}
                </div>
                <div className="text-xs text-muted mt-0.5">
                  {formatMarketCap(c.market_cap)}
                </div>
              </Link>
            ))}
          </div>
        </section>
      )}

      {/* stats bar */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        <div className="card p-4">
          <div className="stat-label">Companies</div>
          <div className="stat-value">{companies.length}</div>
        </div>
        <div className="card p-4">
          <div className="stat-label">Watchlist</div>
          <div className="stat-value">{watchlist.length}</div>
        </div>
        <div className="card p-4">
          <div className="stat-label">Data Source</div>
          <div className="text-lg font-bold text-accent">OpenFDA</div>
        </div>
        <div className="card p-4">
          <div className="stat-label">Stock Data</div>
          <div className="text-lg font-bold text-accent">yfinance</div>
        </div>
      </div>

      <section>
        <div className="flex items-center justify-between gap-3 mb-3">
          <h2 className="text-sm font-semibold text-muted uppercase tracking-wide">
            All Companies
          </h2>
          <button
            onClick={() => downloadCompaniesCsv(companies)}
            disabled={initialLoad || companies.length === 0}
            className="inline-flex items-center gap-1.5 text-xs text-muted hover:text-text bg-surface2 border border-border hover:border-accent/50 disabled:opacity-50 disabled:pointer-events-none px-2.5 py-1.5 rounded-md transition-colors"
          >
            <Download className="h-3.5 w-3.5" />
            Export CSV
          </button>
        </div>
        <div className="card overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border/60">
                  <th className="text-left px-4 py-3 text-muted font-medium">
                    Ticker
                  </th>
                  <th className="text-left px-4 py-3 text-muted font-medium">
                    Company
                  </th>
                  <th className="text-left px-4 py-3 text-muted font-medium hidden md:table-cell">
                    Sector
                  </th>
                  <th className="text-right px-4 py-3 text-muted font-medium">
                    Market Cap
                  </th>
                  <th className="text-right px-4 py-3 text-muted font-medium">
                    1D
                  </th>
                  <th className="px-4 py-3" />
                </tr>
              </thead>
              <tbody className="divide-y divide-border/40">
                {initialLoad ? (
                  Array.from({ length: 8 }).map((_, i) => (
                    <tr key={i} className="animate-pulse">
                      <td className="px-4 py-3">
                        <div className="h-4 bg-border rounded w-12" />
                      </td>
                      <td className="px-4 py-3">
                        <div className="h-4 bg-border rounded w-40" />
                      </td>
                      <td className="px-4 py-3 hidden md:table-cell">
                        <div className="h-4 bg-border rounded w-24" />
                      </td>
                      <td className="px-4 py-3 text-right">
                        <div className="h-4 bg-border rounded w-20 ml-auto" />
                      </td>
                      <td className="px-4 py-3 text-right">
                        <div className="h-4 bg-border rounded w-12 ml-auto" />
                      </td>
                      <td className="px-4 py-3" />
                    </tr>
                  ))
                ) : companies.length === 0 ? (
                  <tr>
                    <td
                      colSpan={6}
                      className={`px-4 py-8 text-center ${listError ? "text-danger" : "text-muted"}`}
                    >
                      {listError || "No companies found."}
                    </td>
                  </tr>
                ) : (
                  companies.map((c) => (
                    <tr
                      key={c.ticker}
                      className="hover:bg-surface2 transition-colors"
                    >
                      <td className="px-4 py-3">
                        <span className="badge-ticker">{c.ticker}</span>
                      </td>
                      <td className="px-4 py-3 text-text">
                        {c.name || c.ticker}
                      </td>
                      <td className="px-4 py-3 text-muted hidden md:table-cell">
                        {c.loading ? (
                          <div className="h-4 bg-border rounded w-24 animate-pulse" />
                        ) : (
                          c.sector || "—"
                        )}
                      </td>
                      <td className="px-4 py-3 text-right font-mono text-text">
                        {c.loading ? (
                          <div className="h-4 bg-border rounded w-16 ml-auto animate-pulse" />
                        ) : (
                          formatMarketCap(c.market_cap)
                        )}
                      </td>
                      <td className="px-4 py-3 text-right font-mono text-xs">
                        {c.quoteLoading ? (
                          <div className="h-4 bg-border rounded w-12 ml-auto animate-pulse" />
                        ) : c.changePct == null ? (
                          <span className="text-muted">—</span>
                        ) : (
                          <span className={c.changePct >= 0 ? "text-success" : "text-danger"}>
                            {formatChange(c.changePct)}
                          </span>
                        )}
                      </td>
                      <td className="px-4 py-3 text-right">
                        <Link
                          href={`/company/${c.ticker}`}
                          className="text-xs text-accent hover:text-accent-hover font-medium"
                        >
                          Details →
                        </Link>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      </section>

      {/* Quick links */}
      <section className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <Link
          href="/calendar"
          className="card p-5 hover:border-accent/40 transition-colors group"
        >
          <CalendarDays className="h-6 w-6 text-accent mb-3" />
          <div className="font-semibold text-text group-hover:text-accent-hover transition-colors">
            Catalyst Calendar
          </div>
          <div className="text-xs text-muted mt-1">
            Upcoming FDA decisions and trial readouts
          </div>
        </Link>
        <Link
          href="/compare"
          className="card p-5 hover:border-accent/40 transition-colors group"
        >
          <ArrowLeftRight className="h-6 w-6 text-accent mb-3" />
          <div className="font-semibold text-text group-hover:text-accent-hover transition-colors">
            Compare Companies
          </div>
          <div className="text-xs text-muted mt-1">
            Two tickers side by side
          </div>
        </Link>
        <Link
          href="/watchlist"
          className="card p-5 hover:border-accent/40 transition-colors group"
        >
          <Star className="h-6 w-6 text-warning mb-3" />
          <div className="font-semibold text-text group-hover:text-accent-hover transition-colors">
            Watchlist
          </div>
          <div className="text-xs text-muted mt-1">
            Companies you follow
          </div>
        </Link>
      </section>
    </div>
  );
}