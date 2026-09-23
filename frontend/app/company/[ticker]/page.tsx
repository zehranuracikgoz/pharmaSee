"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
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
        setError(err.message || "Şirket verisi alınamadı");
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
        <div className="h-8 bg-gray-700 rounded w-64" />
        <div className="h-72 bg-gray-800 rounded-xl" />
      </div>
    );
  }

  if (error) {
    return (
      <div className= "card p-8 text-center">
        <div className="text-4xl mb-3">⚠️</div>
        <p className="text-red-400 font-medium">{error}</p>
        <button
          onClick={() =>router.back()}
          className= "mt-4 text-sm text-indigo-400 hover:text-indigo-300"
        >
          ← Geri dön
        </button>
      </div>
    );
  }

  if (!profile) return null;

  const { company, latest_price, approvals, momentum_scores } = profile;
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
      <div className ="flex items-center gap-2 text-sm text-gray-400">
        <Link href="/" className="hover:text-white transition-colors">
          Dashboard
        </Link>
        <span>/</span>
        <span className="text-white font-medium">{ticker}</span>
      </div>

      {/* header */}
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div>

          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-bold text-white">
              {company.name || ticker}
            </h1>
            <span className="badge-ticker text-base">({ticker})</span>
          </div>
          <p className="text-sm text-gray-400 mt-0.5">
            {company.sector || "Biotechnology"} · Piyasa Değeri:{" "}
            {formatBig(company.market_cap)}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Link
            href={`/compare?a=${ticker}`}
            className="text-sm bg-gray-700 hover:bg-gray-600 text-white px-3 py-1.5 rounded-lg transition-colors"
          >
            Karşılaştır
          </Link>
          <button
            onClick={toggleWatchlist}
            className={`text-sm px-3 py-1.5 rounded-lg font-medium transition-colors ${
              watched
                ? "bg-amber-500/20 text-amber-400 hover:bg-amber-500/30 ring-1 ring-amber-500/40"
                : "bg-gray-700 hover:bg-gray-600 text-gray-300"
            }`}
          >
            {watched ? "⭐ Watchlist'te" : "☆ Watchlist'e Ekle"}
          </button>
        </div>
      </div>

      {/* stat cards*/}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        <div className="card p-4">
          <div className="stat-label">Son Kapanış</div>
          <div className="stat-value text-xl">
            {formatPrice(latest_price?.close)}
          </div>
          <div className="text-xs text-gray-500 mt-1">
            {formatDate(latest_price?.price_date)}
          </div>
        </div>
        <div className = "card p-4">
          <div className="stat-label">Ortalama Momentum</div>
          <div className="mt-2">
            <MomentumBadge momentum={avgMomentum} size="lg" />
          </div>
        </div>
        <div className="card p-4">
          <div className="stat-label">FDA Onayları</div>
          <div className="stat-value text-xl">{approvals.length}</div>
        </div>
        <div className="card p-4">
          <div className="stat-label">Momentum Olayları</div>
          <div className="stat-value text-xl">{momentum_scores.length}</div>
        </div>
      </div>

      {/* stock chart */}
      <div className="card">
        <div className="card-header justify-between">
          <span className="font-semibold text-white">📈 Hisse Fiyatı</span>
          <div className="flex items-center gap-1">
            {[30, 90, 180, 365].map((d) => (
              <button
                key={d}
                onClick={() => setPeriod(d)}
                className={`text-xs px-2.5 py-1 rounded-md transition-colors ${
                  period === d
                    ? "bg-brand-600 text-white"
                    : "text-gray-400 hover:bg-gray-700 hover:text-white"
                }`}
              >
                {d === 30 ? "1A" : d === 90 ? "3A" : d === 180 ? "6A" : "1Y"}
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
            <p className="text-xs text-amber-400/80 mt-2">
              — Sarı çizgiler FDA onay tarihlerini gösterir
            </p>
          )}
        </div>
      </div>

      {/* momentum scores */}
      {momentum_scores.length > 0 && (
        <div className="card">
          <div className="card-header">
            <span className="font-semibold text-white">🚀 Momentum Skorları</span>
            <span className="text-xs text-gray-500 ml-auto">
              T-30 → T-1 performansı
            </span>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-700/60">
                  <th className="text-left px-4 py-3 text-gray-400 font-medium">Olay Tarihi</th>
                  <th className="text-right px-4 py-3 text-gray-400 font-medium">T-30 Fiyat</th>
                  <th className="text-right px-4 py-3 text-gray-400 font-medium">T-1 Fiyat</th>
                  <th className="text-right px-4 py-3 text-gray-400 font-medium">Momentum</th>
                  <th className="text-left px-4 py-3 text-gray-400 font-medium hidden md:table-cell">Yorum</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-700/40">
                {momentum_scores.map((m, i) => (
                  <tr key={i} className="hover:bg-gray-700/20">
                    <td className="px-4 py-3 text-gray-300 font-mono text-xs">
                      {m.event_date}
                    </td>
                    <td className="px-4 py-3 text-right font-mono text-gray-300">
                      {formatPrice(m.t_minus_30_price)}
                    </td>
                    <td className="px-4 py-3 text-right font-mono text-gray-300">
                      {formatPrice(m.t_minus_1_price)}
                    </td>
                    <td className="px-4 py-3 text-right">
                      <MomentumBadge momentum={m.momentum_pct} size="sm" />
                    </td>
                    <td className="px-4 py-3 text-gray-400 text-xs hidden md:table-cell">
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
          <span className="font-semibold text-white">💊 FDA Onayları</span>
          <span className="text-xs text-gray-500 ml-auto">
            {approvals.length} kayıt
          </span>
        </div>
        {approvals.length === 0 ? (
          <div className="card-body text-gray-500 text-sm">
            Henüz FDA onay verisi yok
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-700/60">
                  <th className="text-left px-4 py-3 text-gray-400 font-medium">İlaç</th>
                  <th className="text-left px-4 py-3 text-gray-400 font-medium hidden sm:table-cell">Marka</th>
                  <th className="text-left px-4 py-3 text-gray-400 font-medium">Tarih</th>
                  <th className="text-left px-4 py-3 text-gray-400 font-medium hidden md:table-cell">Tür</th>
                  <th className="text-left px-4 py-3 text-gray-400 font-medium">Durum</th>
                </tr>

              </thead>
              <tbody className="divide-y divide-gray-700/40">
                {approvals.map((a) => (
                  <tr key={a.id} className="hover:bg-gray-700/20">
                    <td className="px-4 py-3 text-white font-medium">
                      {a.drug_name}
                    </td>
                    <td className="px-4 py-3 text-gray-400 hidden sm:table-cell">
                      {a.brand_name || "—"}
                    </td>
                    <td className="px-4 py-3 font-mono text-xs text-gray-300">
                      {formatDate(a.approval_date)}
                    </td>
                    <td className="px-4 py-3 text-gray-400 hidden md:table-cell">
                      {a.application_type || "—"}
                    </td>
                    <td className="px-4 py-3">
                      <span
                        className={`text-xs px-2 py-0.5 rounded-full font-medium ${
                          a.status === "Approved"
                            ? "bg-emerald-500/20 text-emerald-400"
                            : "bg-gray-700 text-gray-400"
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
          <h3 className="text-sm font-semibold text-gray-400 uppercase tracking-wide mb-2">
            Şirket Hakkında
          </h3>
          <p className="text-gray-300 text-sm leading-relaxed">
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
      <div className="h-72 bg-gray-800/60 rounded-xl animate-pulse flex items-center justify-center text-gray-500 text-sm">
        Grafik yükleniyor…
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