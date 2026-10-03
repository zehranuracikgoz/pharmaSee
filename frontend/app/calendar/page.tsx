"use client";

import { Suspense, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";
import { AlertTriangle, CalendarDays, ChevronDown, ExternalLink, History } from "lucide-react";
import {
  api,
  Catalyst,
  CatalystEventType,
  DatePrecision,
  TrackedCompany,
} from "@/lib/api";

const RECENT_DAYS = 90;

const EVENT_META: Record<CatalystEventType, { label: string; chip: string }> = {
  pdufa: { label: "PDUFA", chip: "bg-accent/15 text-accent ring-accent/30" },
  adcom: { label: "AdCom", chip: "bg-violet-500/15 text-violet-300 ring-violet-500/30" },
  approval: { label: "Approval", chip: "bg-success/15 text-success ring-success/30" },
  crl: { label: "CRL", chip: "bg-danger/15 text-danger ring-danger/30" },
  regulatory_submission: { label: "Regulatory filing", chip: "bg-warning/15 text-warning ring-warning/30" },
  topline_readout: { label: "Topline readout", chip: "bg-indigo-500/15 text-indigo-300 ring-indigo-500/30" },
  trial_start: { label: "Trial start", chip: "bg-teal-500/15 text-teal-300 ring-teal-500/30" },
  other: { label: "Other", chip: "bg-surface2 text-muted ring-border" },
};
const EVENT_TYPES = Object.keys(EVENT_META) as CatalystEventType[];

const MONTHS = ["January", "February", "March", "April", "May", "June", "July",
  "August", "September", "October", "November", "December"];

// event_date is the first day of the period; split the string to avoid timezone shifts
function parseDay(iso: string) {
  const [y, m] = iso.split("-").map(Number);
  return { year: y, month: m - 1 };
}

interface Period {
  key: string;
  label: string;
  end: number; // last day of the period (utc ms)
  span: number; // months covered: breaks ties so "Q4 2026" comes before "2026"
}

function periodOf(c: Catalyst): Period {
  if (!c.event_date) return { key: "tbd", label: "Date TBD", end: Number.MAX_SAFE_INTEGER, span: 0 };
  const { year, month } = parseDay(c.event_date);
  const endOf = (lastMonth: number) => Date.UTC(year, lastMonth + 1, 0); // last day of lastMonth
  switch (c.date_precision as DatePrecision) {
    case "quarter": {
      const q = Math.floor(month / 3) + 1;
      return { key: `${year}-q${q}`, label: `Q${q} ${year}`, end: endOf(q * 3 - 1), span: 3 };
    }
    case "half": {
      const h = month < 6 ? 1 : 2;
      return { key: `${year}-h${h}`, label: `H${h} ${year}`, end: endOf(h * 6 - 1), span: 6 };
    }
    case "year":
      return { key: `${year}`, label: `${year}`, end: endOf(11), span: 12 };
    default: //day / month
      return { key: `${year}-m${month}`, label: `${MONTHS[month]} ${year}`, end: endOf(month), span: 1 };
  }
}

// soonest-ending periods first ("October 2026" before "Q4 2026" before "2026")
function groupByPeriod(items: Catalyst[]) {
  const groups = new Map<string, Period & { items: Catalyst[] }>();
  for (const c of items) {
    const p = periodOf(c);
    const group = groups.get(p.key) ?? { ...p, items: [] };
    group.items.push(c);
    groups.set(p.key, group);
  }
  return Array.from(groups.values()).sort((a, b) => a.end - b.end || a.span - b.span);
}

function CatalystCard({ c }: { c: Catalyst }) {
  const meta =EVENT_META[c.event_type] ?? EVENT_META.other;
  return (
    <div className="card p-4 flex flex-col gap-3">
      <div className="flex items-center gap-2 flex-wrap">
        <Link href={`/company/${c.ticker}`} className="badge-ticker hover:text-accent-hover transition-colors">
          {c.ticker}
        </Link>
        <span className= {`text-xs font-medium px-2 py-0.5 rounded-full ring-1 ${meta.chip}`}>
          {meta.label}
        </span>
        {c.date_text && <span className="ml-auto text-xs font-mono text-muted">{c.date_text}</span>}
      </div>

      <div>
        <div className="text-text font-medium">{c.drug ?? "Unnamed program"}</div>
        {c.indication && <div className="text-xs text-muted mt-0.5">{c.indication}</div>}
      </div>

      <p className="text-sm text-text/90 leading-snug">{c.summary}</p>

      <details className="group">
        <summary className="inline-flex items-center gap-1 text-xs text-accent hover:text-accent-hover cursor-pointer list-none select-none">
          <ChevronDown className="h-3.5 w-3.5 transition-transform group-open:rotate-180" />
          Source

        </summary>
        <blockquote className="mt-2 border-l-2 border-accent/40 bg-surface2 rounded-r-md px-3 py-2 text-xs text-muted italic leading-relaxed">
          {c.source_quote}
        </blockquote>
        <a
          href={c.filing_url}
          target= "_blank"
          rel="noopener noreferrer"
          className="mt-2 inline-flex items-center gap-1 text-xs text-accent hover:text-accent-hover"
        >
          View SEC filing
          <ExternalLink className="h-3 w-3" />
        </a>
      </details>
    </div>
  );
}

function CardsSkeleton({ count }: { count: number }) {
  return (
    <div className ="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
      {Array.from({ length: count }).map((_, i) => (
        <div key={i} className="card p-4 space-y-3 animate-pulse">
          <div className="flex gap-2">
            <div className="h-4 bg-border rounded w-12" />
            <div className="h-4 bg-border rounded-full w-24" />
          </div>
          <div className="h-4 bg-border rounded w-2/3" />
          <div className="h-3 bg-border rounded w-full" />
          <div className="h-3 bg-border rounded w-4/5" />
        </div>
      ))}
    </div>
  );
}

function EmptySection({ text }: { text: string }) {
  return <div className="card p-8 text-center text-sm text-muted">{text}</div>;
}

function CatalystsInner() {
  const router = useRouter();
  const params = useSearchParams();
  const ticker = params?.get("ticker")?.toUpperCase() || "";
  const eventType = params?.get("type") || "";

  const [companies, setCompanies] = useState<TrackedCompany[]>([]);
  const [upcoming, setUpcoming] = useState<Catalyst[]>([]);
  const [recent, setRecent] = useState<Catalyst[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    api.companies().then(setCompanies).catch(() => setCompanies([]));
  }, []);

  useEffect(() => {
    let cancelled = false; //ignore late responses after a filter change
    setLoading(true);
    setError("");
    const filters = { ticker: ticker || undefined, eventType: eventType || undefined };
    Promise.all([
      api.catalysts({ ...filters, upcoming: true }),
      api.catalysts({ ...filters, pastDays: RECENT_DAYS }),
    ])
      .then(([up, past]) => {
        if (cancelled) return;
        setUpcoming(up);
        setRecent(past);
      })
      .catch((e) =>!cancelled && setError(e.message || "Could not load catalysts"))
      .finally(() => !cancelled && setLoading(false));
    return () => {
      cancelled = true;
    };
  }, [ticker, eventType]);

  const setFilter = (key: "ticker" | "type", value: string) => {
    const next = new URLSearchParams(params?.toString());
    if (value) next.set(key, value);
    else next.delete(key);
    const qs = next.toString();
    router.replace(`/calendar${qs ? `?${qs}` : ""}`, { scroll: false });
  };

  const filtered = Boolean(ticker || eventType);
  const groups = groupByPeriod(upcoming);

  return (
    <div className="space-y-8">
      <div className="flex items-end justify-between gap-4 flex-wrap">
        <div>
          <h1 className="text-2xl font-bold text-text">Catalyst Calendar</h1>
          <p className="text-sm text-muted mt-0.5">
            Upcoming FDA decisions and trial readouts, extracted by AI from SEC filings
          </p>
        </div>
        <div className="flex items-end gap-3 flex-wrap">
          <div>
            <label htmlFor="cat-ticker" className="stat-label block mb-1.5">Company</label>
            <select
              id="cat-ticker"
              value={ticker}
              onChange={(e) => setFilter("ticker", e.target.value)}
              className="bg-surface2 border border-border rounded-lg px-3 py-2 text-text text-sm focus:outline-none focus:ring-2 focus:ring-accent"
            >
              <option value="">All companies</option>
              {companies.map((c) => (
                <option key={c.ticker} value={c.ticker}>{c.ticker} — {c.name}</option>
              ))}

            </select>
          </div>
          <div>
            <label htmlFor="cat-type" className="stat-label block mb-1.5">Event type</label>
            <select
              id="cat-type"
              value={eventType}
              onChange={(e) => setFilter("type", e.target.value)}
              className="bg-surface2 border border-border rounded-lg px-3 py-2 text-text text-sm focus:outline-none focus:ring-2 focus:ring-accent"
            >
              <option value="">All types</option>
              {EVENT_TYPES.map((t) => (
                <option key={t} value={t}>{EVENT_META[t].label}</option>
              ))}
            </select>
          </div>
        </div>
      </div>

      {error ? (
        <div className="card p-8 text-center">
          <AlertTriangle className="h-10 w-10 text-warning mx-auto mb-3" />
          <p className="text-danger font-medium">{error}</p>
        </div>
      ) : (
        <>
          <section className="space-y-4">
            <h2 className="flex items-center gap-2 text-sm font-semibold text-muted uppercase tracking-wide">
              <CalendarDays className="h-4 w-4 text-accent" />
              Upcoming
              {!loading && <span className="font-mono normal-case text-text">{upcoming.length}</span>}
            </h2>
            {loading ? (
              <CardsSkeleton count={6} />
            ) : groups.length ===0 ? (
              <EmptySection
                text={filtered ? "No upcoming catalysts match these filters." : "No upcoming catalysts yet."}
              />
            ) : (
              groups.map((g) => (
                <div key={g.label} className="space-y-3">
                  <h3 className="text-sm font-semibold text-text border-b border-border pb-2">{g.label}</h3>
                  <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
                    {g.items.map((c) => <CatalystCard key={c.id} c={c} />)}
                  </div>
                </div>
              ))
            )}
          </section>

          <section className="space-y-4">
            < h2 className="flex items-center gap-2 text-sm font-semibold text-muted uppercase tracking-wide">
              <History className="h-4 w-4 text-accent" />
              Recent
              <span className="normal-case font-normal">· last {RECENT_DAYS} days</span>
              {!loading && <span className="font-mono normal-case text-text">{recent.length}</span>}
            </>
            {loading ? (
              <CardsSkeleton count={3} />
            ) : recent.length === 0 ? (
              <EmptySection
                text={filtered
                  ? `No catalysts in the last ${RECENT_DAYS} days match these filters.`
                  : `No catalysts in the last ${RECENT_DAYS} days.`}
              />
            ) : (
              <div className= "grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
                {recent.map((c) => <CatalystCard key={c.id} c={c} />)}
              </div>
            )}
          </section>
        </>
      )}

      <p className="text-xs text-muted border-t border-border pt-4">
        Extracted automatically from SEC 8-K/6-K filings with Gemini. Every item links to its
        source; verify before relying on it.
      </p>
    </div>
  );
}

export default function CatalystCalendarPage() {
  return(
    <Suspense fallback={<div className="text-muted p-8">Loading…</div>}>
      <CatalystsInner />
    </Suspense>
  );
}
