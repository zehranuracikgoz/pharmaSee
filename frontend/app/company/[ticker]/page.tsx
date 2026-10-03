"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { AlertTriangle, Star } from "lucide-react";
import { api, CompanyProfileOut } from "@/lib/api";
import StockChart from "@/components/StockChart";
import MomentumBadge from "@/components/MomentumBadge";
import {
  addToWatchlist,
  removeFromWatchlist,
  isInWatchlist,
} from "@/lib/watchlist";

function formatDate(d?: string | null) {
  if (!d) return "—";
  return d.slice(0, 10);
}

function formatPrice(p?: number | null) {
  if (p == null) return "—";
  return `$${p.toFixed(2)}`;
}

function formatBig(v?: number | null) {
  if (!v) return "—";
  if (v >= 1e12) return `$${(v / 1e12).toFixed(2)}T`;
  if (v >= 1e9) return `$${(v / 1e9).toFixed(2)}B`;
  if (v >= 1e6) return `$${(v / 1e6).toFixed(2)}M`;
  return `$${v.toFixed(0)}`;
}

export default function CompanyPage() {
  const params = useParams();
  const ticker = (params?.ticker as string)?.toUpperCase() ?? "";
  const router = useRouter();

  const [profile, setProfile] = useState<CompanyProfileOut | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [watched, setWatched] = useState(false);
  const [period, setPeriod] = useState(365);

  useEffect(() => {
    if (!ticker) return;
    setWatched(isInWatchlist(ticker));

    setLoading(true);
    api
      .companyProfile(ticker)
      .then((p) => {
        setProfile(p);
        setLoading(false);
      })
      .catch((err) => {
        setError(err.message || "Could not load company data");
        setLoading(false);
      });
  }, [ticker]);

  const toggleWatchlist = () => {
    if (watched) {
      removeFromWatchlist(ticker);
      setWatched(false);
    } else {
      addToWatchlist(ticker);
      setWatched(true);
    }
  };

  if (loading) {
    return (
      <div className="space-y-4 animate-pulse">
        <div className="h-8 bg-border rounded w-64" />
        <div className="h-72 bg-surface rounded-xl" />
      </div>
    );
  }

  if (error) {
    return (
      <div className= "card p-8 text-center">
        <AlertTriangle className="h-10 w-10 text-warning mx-auto mb-3" />
        <p className="text-danger font-medium">{error}</p>
        <button
          onClick={() =>router.back()}
          className= "mt-4 text-sm text-accent hover:text-accent-hover"
        >
          ← Go back
        </button>
      </div>
    );
  }

  if (!profile) return null;

  const { company, latest_price, price_change_pct_1d, approvals, momentum_scores } = profile;
  const approvalDates = approvals
    .map((a) => a.approval_date)
    .filter(Boolean) as string[];

// prices come from stock history endpoint
  const avgMomentum =
    momentum_scores.length > 0
      ? momentum_scores
          .map((m) => m.momentum_pct ?? 0)
          .reduce((s, v) => s + v, 0) / momentum_scores.length
      : null;

  return (
    <div className="space-y-6">
      {/*breadcrumb */}
      <div className ="flex items-center gap-2 text-sm text-muted">
        <Link href="/" className="hover:text-text transition-colors">
          Dashboard
        </Link>
        <span>/</span>
        <span className="text-text font-medium">{ticker}</span>
      </div>

      {/* header */}
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div>

          <div className="flex items-center gap-3 flex-wrap">
            <h1 className="text-2xl font-bold text-text">
              {company.name || ticker}
            </h1>
            <span className="badge-ticker text-base">({ticker})</span>
            {latest_price != null && (
              <span className="inline-flex items-baseline gap-2 rounded-lg bg-surface2 border border-border px-2.5 py-1 font-mono text-sm">
                <span className="font-semibold text-text">{formatPrice(latest_price)}</span>
                {price_change_pct_1d != null && (
                  <span className={price_change_pct_1d >= 0 ? "text-success" : "text-danger"}>
                    {price_change_pct_1d >= 0 ? "+" : ""}
                    {price_change_pct_1d.toFixed(2)}%
                  </span>
                )}
              </span>
            )}
          </div>
          <p className="text-sm text-muted mt-0.5">
            {company.sector && `${company.sector} · `}Market Cap:{" "}
            {formatBig(company.market_cap)}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Link
            href={`/compare?a=${ticker}`}
            className="text-sm bg-surface2 border border-border hover:border-accent/50 text-text px-3 py-1.5 rounded-lg transition-colors"
          >
            Compare
          </Link>
          <button
            onClick={toggleWatchlist}
            className={`inline-flex items-center gap-1.5 text-sm px-3 py-1.5 rounded-lg font-medium border transition-colors ${
              watched
                ? "bg-warning/10 text-warning border-warning/40 hover:bg-warning/20"
                : "bg-surface2 border-border hover:border-accent/50 text-text"
            }`}
          >
            <Star className={`h-4 w-4 ${watched ? "fill-current" : ""}`} />
            {watched ? "In Watchlist" : "Add to Watchlist"}
          </button>
        </div>
      </div>

      {/* stat cards*/}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        <div className="card p-4">
          <div className="stat-label">Last Close</div>
          <div className="stat-value text-xl">
            {formatPrice(latest_price)}
          </div>
          {price_change_pct_1d != null && (
            <div
              className={`text-xs mt-1 font-mono ${
                price_change_pct_1d >= 0 ? "text-success" : "text-danger"
              }`}
            >
              {price_change_pct_1d >= 0 ? "▲" : "▼"} {Math.abs(price_change_pct_1d).toFixed(2)}% (1D)
            </div>
          )}
        </div>
        <div className = "card p-4">
          <div className="stat-label">Avg. Momentum</div>
          <div className="mt-2">
            <MomentumBadge momentum={avgMomentum} size="lg" />
          </div>
        </div>
        <div className="card p-4">
          <div className="stat-label">FDA Approvals</div>
          <div className="stat-value text-xl">{approvals.length}</div>
        </div>
        <div className="card p-4">
          <div className="stat-label">Momentum Events</div>
          <div className="stat-value text-xl">{momentum_scores.length}</div>
        </div>
      </div>

      {/* stock chart */}
      <div className="card">
        <div className="card-header justify-between">
          <span className="font-semibold text-text">Stock Price</span>
          <div className="flex items-center gap-1">
            {[30, 90, 180, 365].map((d) => (
              <button
                key={d}
                onClick={() => setPeriod(d)}
                className={`text-xs px-2.5 py-1 rounded-md transition-colors ${
                  period === d
                    ? "bg-accent text-bg"
                    : "text-muted hover:bg-surface2 hover:text-text"
                }`}
              >
                {d === 30 ? "1M" : d === 90 ? "3M" : d === 180 ? "6M" : "1Y"}
              </button>
            ))}
          </div>
        </div>
        <div className="card-body">
          <StockChartLoader
            ticker={ticker}
            periodDays={period}
            approvalDates={approvalDates}
          />
          {approvalDates.length > 0 && (
            <p className="text-xs text-success/80 mt-2">
              — Green lines mark FDA approval dates
            </p>
          )}
        </div>
      </div>

      {/* momentum scores */}
      {momentum_scores.length > 0 && (
        <div className="card">
          <div className="card-header">
            <span className="font-semibold text-text">Momentum Scores</span>
            <span className="text-xs text-muted ml-auto">
              T-30 → T-1 performance
            </span>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border/60">
                  <th className="text-left px-4 py-3 text-muted font-medium">Event Date</th>
                  <th className="text-right px-4 py-3 text-muted font-medium">T-30 Price</th>
                  <th className="text-right px-4 py-3 text-muted font-medium">T-1 Price</th>
                  <th className="text-right px-4 py-3 text-muted font-medium">Momentum</th>
                  <th className="text-left px-4 py-3 text-muted font-medium hidden md:table-cell">Interpretation</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border/40">
                {momentum_scores.map((m, i) => (
                  <tr key={i} className="hover:bg-surface2">
                    <td className="px-4 py-3 text-text font-mono text-xs">
                      {m.event_date}
                    </td>
                    <td className="px-4 py-3 text-right font-mono text-text">
                      {formatPrice(m.t_minus_30_price)}
                    </td>
                    <td className="px-4 py-3 text-right font-mono text-text">
                      {formatPrice(m.t_minus_1_price)}
                    </td>
                    <td className="px-4 py-3 text-right">
                      <MomentumBadge momentum={m.momentum_pct} size="sm" />
                    </td>
                    <td className="px-4 py-3 text-muted text-xs hidden md:table-cell">
                      {m.interpretation || "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

        </div>
      )}

      {/* fda approvals */}
      <div className = "card">
        <div className="card-header">
          <span className="font-semibold text-text">FDA Approvals</span>
          <span className="text-xs text-muted ml-auto">
            {approvals.length} {approvals.length === 1 ? "record" : "records"}
          </span>
        </div>
        {approvals.length === 0 ? (
          <div className="card-body text-muted text-sm">
            No FDA approval data yet
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border/60">
                  <th className="text-left px-4 py-3 text-muted font-medium">Drug</th>
                  <th className="text-left px-4 py-3 text-muted font-medium hidden sm:table-cell">Brand</th>
                  <th className="text-left px-4 py-3 text-muted font-medium">Date</th>
                  <th className="text-left px-4 py-3 text-muted font-medium hidden md:table-cell">Type</th>
                  <th className="text-left px-4 py-3 text-muted font-medium">Status</th>
                </tr>

              </thead>
              <tbody className="divide-y divide-border/40">
                {approvals.map((a) => (
                  <tr key={a.id} className="hover:bg-surface2">
                    <td className="px-4 py-3 text-text font-medium">
                      {a.drug_name}
                    </td>
                    <td className="px-4 py-3 text-muted hidden sm:table-cell">
                      {a.brand_name || "—"}
                    </td>
                    <td className="px-4 py-3 font-mono text-xs text-text">
                      {formatDate(a.approval_date)}
                    </td>
                    <td className="px-4 py-3 text-muted hidden md:table-cell">
                      {a.application_type || "—"}
                    </td>
                    <td className="px-4 py-3">
                      <span
                        className={`text-xs px-2 py-0.5 rounded-full font-medium ${
                          a.status === "Approved"
                            ? "bg-success/20 text-success"
                            : "bg-surface2 text-muted"
                        }`}
                      >
                        {a.status || "—"}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* description */}
      {company.description && (
        <div className="card p-5">
          <h3 className="text-sm font-semibold text-muted uppercase tracking-wide mb-2">
            About the Company
          </h3>
          <p className="text-text text-sm leading-relaxed">
            {company.description}
          </p>
        </div>
      )}
    </div>
  );
}

// separate component to fetch, show chart
function StockChartLoader({
  ticker,
  periodDays,
  approvalDates,
}: {
  ticker : string;
  periodDays: number;
  approvalDates: string[];
}) {
  const [prices, setPrices] = useState<
    { price_date: string; close?: number }[]
  >([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    api
      .stockHistory(ticker, periodDays)
      .then((h) => {
        setPrices(h.prices);
        setLoading(false);
      })
      .catch(() =>{
        setPrices([]);
        setLoading(false);
      });
  }, [ticker, periodDays]);

  if (loading) {
    return (
      <div className="h-72 bg-surface2 rounded-xl animate-pulse flex items-center justify-center text-muted text-sm">
        Loading chart…
      </div>
    );
  }

  return (
    <StockChart
      data={prices}
      approvalDates={approvalDates}
      height={280}
    />
    
  );
}