"use client";

import { useEffect, useState } from "react";
import { ExternalLink, FlaskConical, Info } from "lucide-react";
import{ api, TrackedCompany } from "@/lib/api";

// use company name not ticker — "MRNA" as a keyword would match
// every mRNA study instead of just Moderna's
function trialsUrl(name: string) {
  return `https://clinicaltrials.gov/search?spons=${encodeURIComponent(name)}`;
}

export default function ClinicalTrialsPage() {
  const [companies, setCompanies] = useState<TrackedCompany[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    api
      .companies()
      .then(setCompanies)
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

      <div className = "flex items-start gap-2 rounded-lg border border-accent/30 bg-accent/10 px-4 py-3 text-sm text-accent">
        <Info className="h-4 w-4 mt-0.5 shrink-0" />
        <p>Live trial data coming soon — click View Trials to search ClinicalTrials.gov directly</p>
      </div>

      {loading ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="card p-5 space-y-3 animate-pulse">
              <div className="h-4 bg-border rounded w-16" />
              <div className="h-4 bg-border rounded w-2/3" />
              <div className="h-8 bg-border rounded w-28" />
            </div>
          ))}
        </div>
      ) : error ? (
        <div className = "card p-8 text-center text-danger">{error}</div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {companies.map((c) => (
            <div key={c.ticker} className="card p-5 flex flex-col gap-4">
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <div className="badge-ticker">{c.ticker}</div>
                  <div className="text-text font-medium mt-1 truncate">{c.name}</div>
                </div>
                <FlaskConical className="h-5 w-5 text-muted shrink-0" />
              </div>
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
          ))}
        </div>
      )}
    </div>
  );
}