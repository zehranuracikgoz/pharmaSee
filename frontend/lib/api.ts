const BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

async function apiFetch<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(errorDetail(text) ?? `API ${res.status}: ${text}`);
  }
  return res.json() as Promise<T>;
}

// fastapi errors: {"detail": "message"} or, for validation (422), {"detail": [{"msg": ...}, ...]}
function errorDetail(body: string): string | null {
  try {
    const { detail } = JSON.parse(body);
    if (typeof detail === "string" && detail) return detail;
    if (Array.isArray(detail)) {
      const msgs = detail.map((d) => d?.msg).filter((m): m is string => typeof m === "string");
      if (msgs.length > 0) return msgs.join("; ");
    }
  } catch {
    // not JSON — fall back to the raw body
  }
  return null;
}

// type
export interface Company {
  ticker : string;
  name: string;
  sector?: string;
  market_cap?: number;
  description?: string;
}

export interface StockPricePoint {
  price_date: string;
  open?: number;
  close? : number;
  high?: number;
  low?: number;
  volume?: number;
}
export interface StockHistoryOut {
  ticker: string;
  period_days: number;
  prices: StockPricePoint[];
}

export interface DrugApproval {
  id: number;
  drug_name: string;
  brand_name? : string;
  approval_date?: string;
  application_type?: string;
  status?: string;
  indication?: string;
}

export interface MomentumScore {
  ticker : string;
  event_date: string;
  t_minus_30_price?: number;
  t_minus_1_price?: number;
  momentum_pct?: number;
  interpretation?: string;
}

export interface TrackedCompany {
  ticker: string;
  name: string;
}

export interface ClinicalTrial {
  nct_id: string;
  title: string;
  phase: string; // first phase only, e.g. "PHASE2"
  phases?: string[]; // all phases, e.g. ["PHASE1", "PHASE2"]
  status: string;
  conditions: string[];
}

export type CatalystEventType =
  | "pdufa"
  | "adcom"
  |  "approval"
  | "crl"
  | "regulatory_submission"
  | "topline_readout"
  | "trial_start"
  | "other";

export type DatePrecision = "day" | "month" | "quarter" | "half" | "year" | "none";

export interface Catalyst {
  id: number;
  ticker: string;
  event_type: CatalystEventType;
  drug: string | null;
  indication: string | null;
  date_text:string | null;
  event_date: string | null; //first day of the period, YYYY-MM-DD
  date_precision: DatePrecision;
  summary: string;
  source_quote: string;
  filing_url: string;
  accession_number: string;
}

export interface CatalystQuery {
  upcoming?: boolean;
  pastDays?: number;
  ticker?: string;
  eventType?: string;
}

export interface Quote {
  price: number | null;
  changePct: number |  null; //vs the previous close
}

export interface CompanyProfileOut {
  company: Company;
  latest_price?: number | null;
  price_change_pct_1d?: number | null;
  approvals: DrugApproval[];
  momentum_scores: MomentumScore[];
}
export interface CompareOut {
  ticker_a: string;
  ticker_b: string;
  company_a?: Company;
  company_b?: Company;
  history_a: StockPricePoint[];
  history_b: StockPricePoint[];
  approvals_a: DrugApproval[];
  approvals_b: DrugApproval[];
}

export interface SearchOut {
  query: string;
  results: Company[];
}

// endpoints

export const api = {
  health: () => apiFetch<{ status: string }>("/health"),

  companies: () => apiFetch<TrackedCompany[]>("/companies"),

  fdaApprovals: (ticker: string) =>
    apiFetch<{ ticker: string; approvals: DrugApproval[] }>(
      `/fda/${ticker}/approvals`
    ),

  stockInfo : (ticker: string) =>
    apiFetch<Company>(`/stocks/${ticker}/info`),

  stockHistory: (ticker: string, periodDays = 365) =>
    apiFetch<StockHistoryOut>(
      `/stocks/${ticker}/history?period_days=${periodDays}`
    ),

  // stockInfo has no price; last close and 1-day change come from a week of history
  quote: async (ticker: string): Promise<Quote> => {
    const h = await apiFetch<StockHistoryOut>(`/stocks/${ticker}/history?period_days=7`);
    const closes = h.prices.map((p) => p.close).filter((c): c is number => c != null);
    const last = closes.at(-1) ?? null;
    const prev = closes.at(-2) ?? null;
    return {
      price: last,
      changePct: last != null && prev ? ((last - prev) / prev) * 100 : null,
    };
  },

  catalysts: ({ upcoming, pastDays, ticker, eventType }: CatalystQuery = {}) => {
    const params = new URLSearchParams();
    if (upcoming) params.set("upcoming", "true");
    if (pastDays) params.set("past_days", String(pastDays));
    if (ticker) params.set("ticker", ticker);
    if (eventType) params.set("event_type", eventType);
    const qs = params.toString();
    return apiFetch<Catalyst[]>(`/catalysts${qs ? `?${qs}` : ""}`);
  },

  clinicalTrials: (ticker: string) =>
    apiFetch<ClinicalTrial[]>(`/fda/${ticker}/trials`),

  searchCompanies: (q: string) =>
    apiFetch<SearchOut>(`/stocks/search?q=${encodeURIComponent(q)}`),

  companyProfile : (ticker: string) =>
    apiFetch<CompanyProfileOut>(`/analysis/profile/${ticker}`),

  momentumScore: (ticker: string, eventDate: string) =>
    apiFetch<MomentumScore>(
      `/analysis/momentum?ticker=${ticker}&event_date=${eventDate}`
    ),

  compareCompanies: (a: string, b: string, periodDays = 365) =>
    apiFetch<CompareOut>(
      `/analysis/compare?a=${a}&b=${b}&period_days=${periodDays}`
    ),
    
};
