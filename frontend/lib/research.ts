// shape of public/data/research.json, written by backend/analysis/export_research.py

export interface Band {
  n: number;
  mean: number[]; // one value per day in `days`
  lo: number[]; // 95% confidence band
  hi: number[];
}

export interface WindowStat {
  n: number;
  mean: number | null;
  t: number | null;
  p: number | null;
}

export interface WindowGroup {
  key: string;
  label: string;
  n: number;
  tickers: string[];
  stats: Record<string, WindowStat>; // keyed by window name, e.g. "CAR[0,+1]"
}

export interface Strategy {
  key: string;
  name: string;
  buy: string;
  sell: string;
  days_held: number;
  n: number;
  abnormal: { mean: number; lo: number; hi: number; hit_rate: number; t: number | null; p: number | null };
  raw: number;
  xbi: number;
}

export interface ScatterPoint {
  ticker: string;
  kind: "ORIG" | "EFFICACY";
  date: string;
  runup: number; // CAR[-10,-1]
  after: number; // CAR[+2,+10]
}

export interface Research {
  generated: string;
  events: number;
  companies: number;
  first_event: string;
  last_event: string;
  coverage: {
    note: string;
    not_in_drugsfda: Record<string, string>;
    no_approved_products: string[];
  };
  settings: {
    market: string;
    estimation_window: [number, number];
    event_window: [number, number];
    cluster_days: number;
    years: number;
    round_trip_cost: number;
  };
  days: number[];
  daily_ar: Band;
  car: { all: Band; ORIG: Band; EFFICACY: Band; all_market_adjusted: number[] };
  windows: WindowGroup[];
  strategies: Strategy[];
  scatter: {
    points: ScatterPoint[];
    regression: { n: number; slope: number; intercept: number; p: number; r2: number; clustered_p: number | null };
  };
}

export async function loadResearch(): Promise<Research> {
  const res = await fetch("/data/research.json");
  if (!res.ok) throw new Error(`Could not load research data (${res.status})`);
  return res.json() as Promise<Research>;
}
