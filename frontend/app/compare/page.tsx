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
import Link from "next/link";

const BIOTECH_TICKERS = [
  "MRNA", "BNTX", "PFE", "REGN", "BIIB",
  "GILD", "AMGN", "VRTX", "SGEN", "BLUE",
  "BEAM", "CRSP", "NTLA",
];

function CompareInner() {
  const params = useSearchParams();

  const [tickerA, setTickerA] = useState(params?.get("a") ?? "MRNA");
  const [tickerB, setTickerB] = useState(params?.get("b") ?? "BNTX");
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
      setError(e.message || "Veri alınamadı");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load(tickerA, tickerB, period);
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

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
        <h1 className="text-2xl font-bold text-white">Şirket Karşılaştırma</h1>
        <p className="text-sm text-gray-400 mt-0.5">
          İki biyoteknoloji şirketini yan yana analiz edin
        </p>
      </div>

      {/* controls */}
      <div className="card p-5">
        <div className="flex flex-wrap items-end gap-4">
          <div className="flex-1 min-w-36">
            <label className = "stat-label block mb-1.5">Şirket A</label>
            <select
              value={tickerA}
              onChange={(e) => setTickerA(e.target.value)}
              className="w-full bg-gray-700 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
            >
              {BIOTECH_TICKERS.filter((t) => t !==tickerB).map((t) => (
                <option key={t} value={t}>{t}</option>
              ))}
            </select>
          </div>

          <div className="text-gray-400 text-lg pb-2">vs</div>

          <div className="flex-1 min-w-36">
            <label className="stat-label block mb-1.5">Şirket B</label>
            <select
              value={tickerB}
              onChange={(e) => setTickerB(e.target.value)}
              className="w-full bg-gray-700 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
            >
              {BIOTECH_TICKERS.filter((t) => t !== tickerA).map((t) => (
                <option key={t} value={t}>{t}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="stat-label block mb-1.5">Süre</label>
            <div className="flex gap-1">
              {[90, 180, 365].map((d) => (
                <button
                  key={d}
                  onClick={() => setPeriod(d)}
                  className={`text-xs px-3 py-2 rounded-md transition-colors ${
                    period === d
                      ?"bg-brand-600 text-white"
                      : "bg-gray-700 text-gray-400 hover:bg-gray-600 hover:text-white"
                  }`}
                >
                  {d === 90 ? "3A" : d === 180 ? "6A" : "1Y"}
                </button>
              ))}
            </div>
          </div>
          <button
            onClick={() => load(tickerA, tickerB, period)}
            disabled={loading || tickerA === tickerB}
            className="bg-brand-600 hover:bg-brand-700 disabled:opacity-50 text-white text-sm font-medium px-5 py-2 rounded-lg transition-colors"
          >
            {loading ? "Yükleniyor…" : "Karşılaştır"}
          </button>
        </div>

        {tickerA === tickerB && (
          <p className="text-amber-400 text-xs mt-2">
            Farklı iki şirket seçin
          </p>
        )}
        {error && (
          <p className="text-red-400 text-sm mt-2">{error}</p>
        )}
      </div>

      {/* chart*/}
      {data && chartData.length > 0 && (
        <div className="card">
          <div className="card-header">
            <span className="font-semibold text-white">📊 Hisse Fiyatı Karşılaştırması</span>
          </div>
          <div className="card-body">
            <ResponsiveContainer width="100%" height={320}>
              <LineChart data={chartData} margin={{ top: 5, right: 10, left: 0, bottom: 5 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" />
                <XAxis
                  dataKey="date"
                  tick={{ fill: "#6b7280", fontSize: 11 }}
                  tickLine={false}
                  axisLine={{ stroke: "#374151" }}
                  interval="preserveStartEnd"
                  tickFormatter = {(v: string)=> v.slice(5)}
                />
                <YAxis
                  tick={{ fill: "#6b7280", fontSize: 11 }}
                  tickLine={false}
                  axisLine={false}
                  tickFormatter={(v: number) => `$${v.toFixed(0)}`}
                  width={50}
                />
                <Tooltip
                  contentStyle={{
                    background: "#1f2937",
                    border: "1px solid #374151 ",
                    borderRadius: "8px",
                    fontSize: 12,
                  }}
                  labelStyle={{ color: "#9ca3af", marginBottom: 4 }}
                  formatter={(v: number) => [`$${v.toFixed(2)}`]}
                />
                <Legend wrapperStyle={{ fontSize: 12, color: "#9ca3af" }} />
                <Line
                  type="monotone"
                  dataKey={tickerA}
                  stroke="#818cf8"
                  strokeWidth={2}
                  dot = {false}
                  connectNulls
                />
                <Line
                  type="monotone"
                  dataKey={tickerB}
                  stroke="#34d399"
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
                <span className="text-white font-medium ml-1">
                  {company?.name || ticker}
                </span>
                <Link
                  href={`/company/${ticker}`}
                  className="ml-auto text-xs text-indigo-400 hover:text-indigo-300"
                >
                  Detay →
                </Link>
              </div>
              <div className = "card-body space-y-3">
                <div className="grid grid-cols-2 gap-3 text-sm">
                  <div>
                    <div className="stat-label">Sektör</div>
                    <div className="text-white mt-0.5">
                      {company?.sector || "Biotechnology"}
                    </div>
                  </div>
                  <div>
                    <div className="stat-label">FDA Onayları</div>
                    <div className="text-white mt-0.5 font-bold text-lg">
                      {approvals.length}
                    </div>
                  </div>

                </div>

                {approvals.length > 0 && (
                  <div>
                    <div className="stat-label mb-2">Son Onaylar</div>
                    <ul className="space-y-1.5">
                      {approvals.slice(0, 4).map((a) => (
                        <li
                          key={a.id}
                          className="flex items-center justify-between text-xs"
                        >
                          <span className="text-gray-300 truncate mr-2">
                            {a.drug_name}
                          </span>
                          <span className="text-gray-500 shrink-0 font-mono">
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
        <div className="card p-8 text-center text-gray-500">
          Karşılaştırma verileri yükleniyor…
        </div>
      )}
    </div>
  );
}
export default function ComparePage() {
  return (
    <Suspense fallback={<div className="text-gray-400 p-8">Yükleniyor…</div>}>
      <CompareInner />
      
    </Suspense>
  );
}
