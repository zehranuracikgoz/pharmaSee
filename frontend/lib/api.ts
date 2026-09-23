const BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

async function apiFetch<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`API ${res.status}: ${text}`);
  }
  return res.json() as Promise<T>;
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

export interface CompanyProfileOut {
  company: Company;
  latest_price?: StockPricePoint;
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

export interface FDACalendarItem {
  ticker: string;
  company_name: string;
  drug_name: string;
  approval_date?: string;
  application_type?: string;
  status?: string;
}

export interface FDACalendarOut {
  days_ahead: number;
  items: FDACalendarItem[];
}

export interface SearchOut {
  query: string;
  results: Company[];
}

// endpoints

export const api = {
  health: () => apiFetch<{ status: string }>("/health"),
  fdaSync: () =>
    apiFetch<{ status: string; message: string }>("/fda/sync", {
      method: "POST",
    }),

  fdaCalendar: (daysAhead = 90) =>
    apiFetch<FDACalendarOut>(`/fda/calendar?days_ahead=${daysAhead}`),

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
