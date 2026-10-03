"use client";

import { useEffect, useState } from "react";
import { ExternalLink, FlaskConical } from "lucide-react";
import { api, ClinicalTrial, TrackedCompany } from "@/lib/api";

// backend returns at most this many trials per company (TRIALS_PAGE_SIZE in fda_service.py)
const TRIALS_CAP = 100;

const PHASES = [
  { key: 1, label: "Phase 1", bar: "bg-accent/35" },
  { key: 2, label: "Phase 2", bar: "bg-accent/65" },
  { key: 3, label: "Phase 3", bar: "bg-accent" },
] as const;

// use company name not ticker — "MRNA" as a keyword would match
// every mRNA study instead of just Moderna's
function trialsUrl(name: string) {
  return `https://clinicaltrials.gov/search?spons=${encodeURIComponent(name)}`;
}

// combined trials (e.g. phase 1/2) count toward their highest phase; phase 4 / n/a are skipped
function highestPhase(t: ClinicalTrial): 1 | 2 | 3 | null {
  const phases = t.phases?.length ? t.phases : [t.phase];
  let best: 1 | 2 | 3 | null = null;
  for (const p of phases) {
    const n = p === "PHASE3" ? 3 : p === "PHASE2" ? 2 : p === "PHASE1" || p === "EARLY_PHASE1" ? 1 : null;
    if (n && (!best || n > best)) best = n;
  }
  return best;
}

interface TrialState {
  loading: boolean;
  error?: boolean;
  total?: number;
  counts?: Record<1 | 2 | 3, number>;
}

function PhaseBar({ state }: { state: TrialState | undefined }) {
  if (!state || state.loading) {
    return (
      <div className="space-y-2 animate-pulse">
        <div className="h-2 bg-border rounded-full" />
        <div className="h-3 bg-border rounded w-3/4" />
      </div>
    );
  }
  if (state.error || !state.counts) {
    return <p className="text-xs text-muted">Trial data unavailable</p>;
  }

  const counts = state.counts;
  const phased = counts[1] + counts[2] + counts[3];
  if (phased === 0) {
    return <p className="text-xs text-muted">No active Phase 1–3 trials found</p>;
  }

  return (
    <div className="space-y-2">
      <div className="flex h-2 overflow-hidden rounded-full bg-surface2">
        {PHASES.map(({ key, bar }) =>
          counts[key] > 0 ? (
            <div key={key} className={bar} style={{ width: `${(counts[key] / phased) * 100}%` }} />
          ) : null
        )}
      </div>
      <div className="flex flex-wrap gap-x-3 gap-y-1 text-xs text-muted">
        {PHASES.map(({ key, label, bar }) => (
          <span key={key} className="inline-flex items-center gap-1.5">
            <span className={`h-2 w-2 rounded-full ${bar}`} />
            {label} <span className="font-mono text-text">{counts[key]}</span>
          </span>
        ))}
      </div>
    </div>
  );
}

export default function ClinicalTrialsPage() {
  const [companies, setCompanies] = useState<TrackedCompany[]>([]);
  const [trials, setTrials] = useState<Record<string, TrialState>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    api
      .companies()
      .then((list) => {
        setCompanies(list);
        setTrials(Object.fromEntries(list.map((c) => [c.ticker, { loading: true }])));

        list.forEach(({ ticker }) => {
          api
            .clinicalTrials(ticker)
            .then((items) => {
              const counts = { 1: 0, 2: 0, 3: 0 };
              for (const t of items) {
                const p = highestPhase(t);
                if (p) counts[p] += 1;
              }
              setTrials((prev) => ({
                ...prev,
                [ticker]: { loading: false, total: items.length, counts },
              }));
            })
            .catch(() =>
              setTrials((prev) => ({ ...prev, [ticker]: { loading: false, error: true } }))
            );
        });
      })
      .catch((e) => setError(e.message || "Could not load the company list"))
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-text">Clinical Trials Pipeline</h1>
        <p className="text-sm text-muted mt-0.5">
          Phase I / II / III trials for tracked companies
        </p>
      </div>

      {loading ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="card p-5 space-y-3 animate-pulse">
              <div className="h-4 bg-border rounded w-16" />
              <div className="h-4 bg-border rounded w-2/3" />
              <div className="h-2 bg-border rounded-full" />
              <div className="h-8 bg-border rounded w-28" />
            </div>
          ))}
        </div>
      ) : error ? (
        <div className="card p-8 text-center text-danger">{error}</div>
      ) : (
        <>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {companies.map((c) => {
              const state = trials[c.ticker];
              return (
                <div key={c.ticker} className="card p-5 flex flex-col gap-4">
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <div className="badge-ticker">{c.ticker}</div>
                      <div className="text-text font-medium mt-1 truncate">{c.name}</div>
                    </div>
                    <div className="flex items-center gap-1.5 text-xs text-muted shrink-0">
                      <FlaskConical className="h-4 w-4" />
                      {state && !state.loading && state.total != null && (
                        <span className="font-mono text-text">
                          {state.total >= TRIALS_CAP ? `${TRIALS_CAP}+` : state.total}
                        </span>
                      )}
                    </div>
                  </div>

                  <PhaseBar state={state} />

                  <a
                    href={trialsUrl(c.name)}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="mt-auto inline-flex w-fit items-center gap-1.5 rounded-lg border border-border bg-surface2 px-3 py-1.5 text-sm text-text hover:border-accent/50 transition-colors"
                  >
                    View Trials
                    <ExternalLink className="h-3.5 w-3.5 text-muted" />
                  </a>
                </div>
              );
            })}
          </div>

          <p className="text-xs text-muted">
            Counts cover recruiting and active trials where the company is sponsor or
            collaborator, up to {TRIALS_CAP} per company. Combined trials (e.g. Phase 1/2)
            count toward their highest phase.
          </p>
        </>
      )}
    </div>
  );
}
