"use client";

import { Suspense, useEffect, useMemo, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";
import { AlertTriangle, TrendingUp } from "lucide-react";
import { api, CompanyProfileOut, MomentumScore } from "@/lib/api";
import MomentumBadge from "@/components/MomentumBadge";

// REGN has FDA history; MRNA/BNTX don't show up in OpenFDA's drugsfda
const DEFAULT_TICKER = "REGN" ;

function formatPrice(p?: number | null) {
  return p==null ? "—" : `$${p.toFixed(2)}`;
}

interface EventCard extends MomentumScore {
  drugs: string[];
}

function ImpactInner() {
  const router = useRouter();
  const params = useSearchParams();
  const [tickers, setTickers] = useState<{ ticker: string; name: string }[]>([]);
  const [ticker, setTicker] = useState(
    params?.get("ticker")?.trim().toUpperCase() || DEFAULT_TICKER
  );
  const [profile, setProfile] = useState<CompanyProfileOut | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() =>{
    api.companies().then(setTickers).catch(() => setTickers([]));
  }, []);

  useEffect(() => {
    let cancelled = false; //ignore late responses after switching tickers
    setLoading(true);
    setError("");
    api
      .companyProfile(ticker)
      .then((p) => !cancelled && setProfile(p))
      .catch((e) => {
        if (cancelled) return;
        setProfile(null);
        setError(e.message || "Could not load impact data");
      })
      .finally(() => !cancelled && setLoading(false));
    return () => {
      cancelled = true;
    };
  }, [ticker]);

  const selectTicker = (t: string) => {
    setTicker(t);
    router.replace(`/impact?ticker=${t}`, { scroll: false });
  };

  const { events, withoutData } = useMemo(() => {
    if (!profile) return { events: [] as EventCard[], withoutData: 0 };

    // merge drug names by date
    const drugsByDate = new Map<string, string[]>();
    for (const a of profile.approvals) {
      if (!a.approval_date) continue;
      const day = a.approval_date.slice(0, 10);
      const names = drugsByDate.get(day) ?? [];
      if (!names.includes(a.drug_name)) names.push(a.drug_name);
      drugsByDate.set(day, names);
    }

    // one card per date — backend returns one score per approval so same-day events repeat
    const byDate =  new Map<string, EventCard>();
    for (const m of profile.momentum_scores) {
      const day = m.event_date.slice(0, 10);
      if (!byDate.has(day)) byDate.set(day, { ...m, drugs: drugsByDate.get(day) ?? [] });
    }

    const all = Array.from(byDate.values()).sort((x, y) =>
      y.event_date.localeCompare(x.event_date)
    );
    const scored = all.filter((m) => m.momentum_pct != null);
    return { events: scored, withoutData: all.length - scored.length };
  }, [profile]);

  const avg =
    events.length > 0
      ? events.reduce((s, m ) => s + (m.momentum_pct ?? 0), 0) / events.length
      : null;
  const positiveShare =
    events.length > 0
      ? (events.filter((m) => (m.momentum_pct ?? 0) >= 0).length / events.length) * 100
      : null;

  const options = tickers.some((t) => t.ticker === ticker)
    ? tickers
    : [{ ticker, name: ticker }, ...tickers];

  return (
    <div className="space-y-6">
      <div className="flex items-end justify-between gap-4 flex-wrap">
        <div>
          <h1 className ="text-2xl font-bold text-text">Impact Analysis</h1>
          <p className="text-sm text-muted mt-0.5">
            Stock momentum around FDA approval events
          </p>
        </div>
        <div className="w-full sm:w-64">
          <label htmlFor="impact-ticker" className="stat-label block mb-1.5">
            Company
          </label>
          <select
            id="impact-ticker"
            value={ticker}
            onChange={(e) => selectTicker(e.target.value)}
            className="w-full bg-surface2 border border-border rounded-lg px-3 py-2 text-text text-sm focus:outline-none focus:ring-2 focus:ring-accent"
          
          >
            {options.map((t) => (
              <option key={t.ticker} value={t.ticker}>
                {t.ticker} — {t.name}
              </option>
            ))}
          </select>
        </div>
      </div>

      <p className="text-xs text-muted">
        Momentum = price change from 30 days before the approval (T-30) to the day before (T-1).
        A strong run-up suggests the market expected the approval.
      </p>

      {loading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="card p-5 space-y-3 animate-pulse">
              <div className="h-4 bg-border rounded w-2/3" />
              <div className="h-3 bg-border rounded w-1/3" />
              <div className="h-10 bg-border rounded" />
              <div className="h-3 bg-border rounded w-3/4" />
            
            </div>
          ))}
        </div>
      ) : error ? (
        <div className="card p-8 text-center">
          <AlertTriangle className="h-10 w-10 text-warning mx-auto mb-3" />
          <p className="text-danger font-medium">{error}</p>
        </div>
      ) : events.length === 0 ? (
        <div className="card p-12 text-center">
          <TrendingUp className="h-10 w-10 text-muted mx-auto mb-3" />
          <p className="text-text font-medium">No momentum data for {ticker}</p>
          <p className="text-muted text-sm mt-1">
            {withoutData > 0
              ? `${withoutData} FDA approval${withoutData === 1 ? " is" : "s are"} older than the available price history.`
              : "No FDA approvals were found for this company in OpenFDA."}
          </p>
        </div>
      ) : (
        <>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <div className="card p-4">
              <div className="stat-label">Approval Events</div>
              <div className="stat-value">{events.length}</div>
            </div>
            <div className="card p-4">
              <div className="stat-label">Avg. Momentum</div>
              <div className="mt-2">
                <MomentumBadge momentum={avg} size="lg" />
              </div>
            </div>
            <div className = "card p-4">
              <div className="stat-label">Positive Run-ups</div>
              <div className="stat-value">{positiveShare!.toFixed(0)}%</div>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
            {events.map((m) => (
              <div key={m.event_date} className="card p-5 flex flex-col gap-4">
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <div
                      className="font-semibold text-text truncate"
                      title={m.drugs.join(", ") || undefined}
                    >
                      {m.drugs.length > 0 ? m.drugs.join(", ") : "FDA approval"}
                    </div>
                    <div className="text-xs text-muted font-mono mt-0.5">{m.event_date}</div>
                  </div>
                  <MomentumBadge momentum={m.momentum_pct} size="sm" />
                </div>

                <div className="grid grid-cols-2 gap-3 rounded-lg bg-surface2 px-4 py-3">
                  <div>
                    <div className="stat-label">T-30 Price</div>
                    <div className="font-mono text-text mt-0.5">{formatPrice(m.t_minus_30_price)}</div>
                  </div>
                  <div>
                    <div className="stat-label">T-1 Price</div>
                    <div className="font-mono text-text mt-0.5">{formatPrice(m.t_minus_1_price)}</div>
                  </div>
                </div>

                {m.interpretation && (
                  <p className="text-sm text-muted leading-snug">{m.interpretation}</p>
                )}
              </div>
            ))}
          </div>

          <div className="flex items-center justify-between gap-4 flex-wrap text-xs text-muted">
            <span>
              {withoutData > 0 &&
                `${withoutData} older approval${withoutData === 1 ? "" : "s"} without enough price history ${withoutData === 1 ? "is" : "are"} not shown.`}
            </span>
            <Link href={`/company/${ticker}`} className="text-accent hover:text-accent-hover">
              {ticker} company profile →
            </Link>
          </div>
        </>
      )}
      
    </div>
  );
}

export default function ImpactPage() {
  return (
    <Suspense fallback={<div className="text-muted p-8">Loading…</div>}>
      <ImpactInner />
    </Suspense>
  );
}