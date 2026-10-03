"use client";

import { useState, useEffect, Suspense } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from "recharts";
import { api, CompareOut } from "@/lib/api";
import { chartColors } from "@/lib/theme";
import Link from "next/link";

function CompareInner() {
  const params = useSearchParams();
  const [tickers, setTickers] = useState<string[]>([]);

  useEffect(() => {
    api
      .companies()
      .then((list) => setTickers(list.map((c) => c.ticker)))
      .catch(() => setTickers([]));
  }, []);

  // missing, empty or literal "undefined"/"null" params fall back to the defaults
  const tickerParam = (key: string, fallback: string) => {
    const v = params?.get(key)?.trim().toUpperCase();
    return v && v !== "UNDEFINED" && v !== "NULL" ? v : fallback;
  };
  const initialA = tickerParam("a", "MRNA");
  let initialB = tickerParam("b", "BNTX");
  // e.g. /compare?a=BNTX: don't start with the same ticker on both sides
  if (initialB === initialA) initialB = initialA === "MRNA" ? "BNTX" : "MRNA";

  const [tickerA, setTickerA] = useState(initialA);
  const [tickerB, setTickerB] = useState(initialB);
  const [period, setPeriod] = useState(365);
  const [data, setData] = useState<CompareOut | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const load = async (a: string, b: string, p: number) => {
    if (!a || !b || a === b) return;
    setLoading(true);
    setError("");
    try {
      const r = await api.compareCompanies(a, b, p);
      setData(r);
    } catch (e: any) {
      setError(e.message || "Could not load data");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load(tickerA, tickerB, period);
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // keep the selected ticker in the dropdown even if it isn't in the list (e.g. from the URL)
  const optionsFor = (selected: string, other: string) =>
    Array.from(new Set([selected, ...tickers])).filter((t) => t && t !== other);

  // build merged chart data
  const chartData = (() => {
    if (!data) return [];
    const mapA=new Map(data.history_a.map((p) => [p.price_date.slice(0, 10), p.close]));
    const mapB = new Map(data.history_b.map((p) => [p.price_date.slice(0, 10), p.close]));
    const allDates = Array.from(
      new Set([...mapA.keys(), ...mapB.keys()])
    ).sort();
    return allDates.map((date) => ({
      date,
      [tickerA]: mapA.get(date) ?? null,
      [tickerB]: mapB.get(date) ?? null,
    }));
  })();

  return (
    <div className="space-y-6">
      {/* header */}
      <div>
        <h1 className="text-2xl font-bold text-text">Compare Companies</h1>
        <p className="text-sm text-muted mt-0.5">
          Analyze two biotech companies side by side
        </p>
      </div>

      {/* controls */}
      <div className="card p-5">
        <div className="flex flex-wrap items-end gap-4">
          <div className="flex-1 min-w-36">
            <label className = "stat-label block mb-1.5">Company A</label>
            <select
              value={tickerA}
              onChange={(e) => setTickerA(e.target.value)}
              className="w-full bg-surface2 border border-border rounded-lg px-3 py-2 text-text text-sm focus:outline-none focus:ring-2 focus:ring-accent"
            >
              {optionsFor(tickerA, tickerB).map((t) => (
                <option key={t} value={t}>{t}</option>
              ))}
            </select>
          </div>

          <div className="text-muted text-lg pb-2">vs</div>

          <div className="flex-1 min-w-36">
            <label className="stat-label block mb-1.5">Company B</label>
            <select
              value={tickerB}
              onChange={(e) => setTickerB(e.target.value)}
              className="w-full bg-surface2 border border-border rounded-lg px-3 py-2 text-text text-sm focus:outline-none focus:ring-2 focus:ring-accent"
            >
              {optionsFor(tickerB, tickerA).map((t) => (
                <option key={t} value={t}>{t}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="stat-label block mb-1.5">Period</label>
            <div className="flex gap-1">
              {[90, 180, 365].map((d) => (
                <button
                  key={d}
                  onClick={() => { setPeriod(d); if (tickerA !== tickerB) load(tickerA, tickerB, d); }}
                  className={`text-xs px-3 py-2 rounded-md transition-colors ${
                    period === d
                      ? "bg-accent text-bg"
                      : "bg-surface2 text-muted hover:bg-accent/15 hover:text-text"
                  }`}
                >
                  {d === 90 ? "3M" : d === 180 ? "6M" : "1Y"}
                </button>
              ))}
            </div>
          </div>
          <button
            onClick={() => load(tickerA, tickerB, period)}
            disabled={loading || tickerA === tickerB}
            className="bg-accent hover:bg-accent-hover disabled:opacity-50 text-bg text-sm font-medium px-5 py-2 rounded-lg transition-colors"
          >
            {loading ? "Loading…" : "Compare"}
          </button>
        </div>

        {tickerA === tickerB && (
          <p className="text-warning text-xs mt-2">
            Select two different companies
          </p>
        )}
        {error && (
          <p className="text-danger text-sm mt-2">{error}</p>
        )}
      </div>

      {/* chart*/}
      {data && chartData.length > 0 && (
        <div className="card">
          <div className="card-header">
            <span className="font-semibold text-text">Stock Price Comparison</span>
          </div>
          <div className="card-body">
            <ResponsiveContainer width="100%" height={320}>
              <LineChart data={chartData} margin={{ top: 5, right: 10, left: 0, bottom: 5 }}>
                <CartesianGrid strokeDasharray="3 3" stroke={chartColors.border} />
                <XAxis
                  dataKey="date"
                  tick={{ fill: chartColors.textMuted, fontSize: 11 }}
                  tickLine={false}
                  axisLine={{ stroke: chartColors.border }}
                  interval="preserveStartEnd"
                  tickFormatter = {(v: string)=> v.slice(5)}
                />
                <YAxis
                  tick={{ fill: chartColors.textMuted, fontSize: 11 }}
                  tickLine={false}
                  axisLine={false}
                  tickFormatter={(v: number) => `$${v.toFixed(0)}`}
                  width={50}
                />
                <Tooltip
                  contentStyle={{
                    background: chartColors.surface,
                    border: `1px solid ${chartColors.border}`,
                    borderRadius: "8px",
                    fontSize: 12,
                  }}
                  labelStyle={{ color: chartColors.textMuted, marginBottom: 4 }}
                  cursor={{ stroke: chartColors.border }}
                  formatter={(v: number, name: string) => [`$${v.toFixed(2)}`, name]}
                />
                <Legend wrapperStyle={{ fontSize: 12, color: chartColors.textMuted }} />
                <Line
                  type="monotone"
                  dataKey={tickerA}
                  stroke={chartColors.accent}
                  strokeWidth={2}
                  dot = {false}
                  connectNulls
                />
                <Line
                  type="monotone"
                  dataKey={tickerB}
                  stroke={chartColors.success}
                  strokeWidth={2}
                  dot={false}
                  connectNulls
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}
      {/* side by side company info */}
      {data && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {[
            { ticker: tickerA, company: data.company_a, approvals: data.approvals_a },
            { ticker: tickerB , company: data.company_b, approvals: data.approvals_b },
          ].map(({ ticker, company, approvals }) => (
            <div key={ticker} className="card">
              <div className="card-header">
                <span className="badge-ticker text-base">{ticker}</span>
                <span className="text-text font-medium ml-1">
                  {company?.name || ticker}
                </span>
                <Link
                  href={`/company/${ticker}`}
                  className="ml-auto text-xs text-accent hover:text-accent-hover"
                >
                  Details →
                </Link>
              </div>
              <div className = "card-body space-y-3">
                <div className="grid grid-cols-2 gap-3 text-sm">
                  <div>
                    <div className="stat-label">Sector</div>
                    <div className="text-text mt-0.5">
                      {company?.sector || "—"}
                    </div>
                  </div>
                  <div>
                    <div className="stat-label">FDA Approvals</div>
                    <div className="text-text mt-0.5 font-bold text-lg">
                      {approvals.length}
                    </div>
                  </div>

                </div>

                {approvals.length > 0 && (
                  <div>
                    <div className="stat-label mb-2">Recent Approvals</div>
                    <ul className="space-y-1.5">
                      {approvals.slice(0, 4).map((a) => (
                        <li
                          key={a.id}
                          className="flex items-center justify-between text-xs"
                        >
                          <span className="text-text truncate mr-2">
                            {a.drug_name}
                          </span>
                          <span className="text-muted shrink-0 font-mono">
                            {a.approval_date?.slice(0, 10) ?? "—"}
                          </span>
                        </li>
                      ))}
                    </ul>
                  </div>
                )}

              </div>
            </div>
          ))}
        </div>
      )}

      {loading && !data && (
        <div className="card p-8 text-center text-muted">
          Loading comparison data…
        </div>
      )}
    </div>
  );
}
export default function ComparePage() {
  return (
    <Suspense fallback={<div className="text-muted p-8">Loading…</div>}>
      <CompareInner />
      
    </Suspense>
  );
}
