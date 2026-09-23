"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { api, FDACalendarItem } from "@/lib/api";

export default function CalendarPage() {
  const [items, setItems] = useState<FDACalendarItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [daysAhead, setDaysAhead] = useState(90);

  useEffect(() => {
    setLoading(true);
    api
      .fdaCalendar(daysAhead)
      .then((r)=> {
        setItems(r.items);
        setLoading(false);
      })
      .catch(() => {
        setItems([]);
        setLoading(false);
      });
  }, [daysAhead]);

  return (
    <div className = "space-y-6">
      <div className="flex items-center justify-between gap-4 flex-wrap">
        <div>
          <h1 className="text-2xl font-bold text-white">FDA Takvim</h1>
          <p className="text-sm text-gray-400 mt-0.5">
            Yaklaşan ve son FDA onay kararları
          </p>
        </div>
        <div className="flex items-center gap-1">
          {[30, 60, 90, 180].map((d) => (
            <button
              key={d}
              onClick={() => setDaysAhead(d)}
              className={`text-sm px-3 py-1.5 rounded-lg transition-colors ${
                daysAhead ===d
                  ? "bg-brand-600 text-white"
                  : "bg-gray-800 text-gray-400 hover:bg-gray-700 hover:text-white border border-gray-700"
              }`}
            >
              {d} gün
            </button>
          ))}
        </div>
      </div>

      {loading ? (
        <div className="card divide-y divide-gray-700/40">
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="px-5 py-4 flex items-center gap-4 animate-pulse">
              <div className="h-10 w-10 bg-gray-700 rounded-lg shrink-0" />
              <div className="flex-1 space-y-2">
                <div className="h-4 bg-gray-700 rounded w-48" />
                <div className="h-3 bg-gray-700 rounded w-32" />
              </div>
              <div className="h-6 bg-gray-700 rounded w-20" />
            </div>
          ))}
        </div>
      ) : items.length ===0 ? (
        <div className="card p-12 text-center">
          <div className="text-4xl mb-3">📅</div>
          <p className="text-gray-400">
            Bu dönem için takvim verisi bulunamadı.
          </p>
          <p className="text-gray-500 text-sm mt-1">
            FDA sync ile veritabanını güncelleyin.
          </p>
          <button
            onClick={()=> api.fdaSync().then(() => setDaysAhead((d) => d))}
            className="mt-4 text-sm bg-brand-600 hover:bg-brand-700 text-white px-4 py-2 rounded-lg transition-colors"
          >
            FDA Sync Çalıştır
          </button>
        </div>
      ) : (
        <div className="card overflow-hidden">
          <div className = "overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-700/60">
                  <th className="text-left px-5 py-3 text-gray-400 font-medium">Şirket</th>
                  <th className="text-left px-5 py-3 text-gray-400 font-medium">İlaç</th>
                  <th className="text-left px-5 py-3 text-gray-400 font-medium hidden md:table-cell">Tür</th>
                  <th className="text-left px-5 py-3 text-gray-400 font-medium">Tarih</th>
                  <th className="text-left px-5 py-3 text-gray-400 font-medium">Durum</th>
                  <th className="px-5 py-3" />
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-700/40">
                {items.map((item, i) => (
                  <tr
                    key={i}
                    className="hover:bg-gray-700/20 transition-colors"
                  >
                    <td className= "px-5 py-4">
                      <div className="font-mono font-bold text-indigo-300 text-sm">
                        {item.ticker}
                      </div>
                      <div className="text-xs text-gray-500 mt-0.5 truncate max-w-36">
                        {item.company_name}
                      </div>
                    </td>
                    <td className="px-5 py-4 text-white font-medium">
                      {item.drug_name}
                    </td>
                    <td className="px-5 py-4 text-gray-400 hidden md:table-cell">
                      {item.application_type || "—"}
                    </td>
                    <td className="px-5 py-4 font-mono text-xs text-gray-300">
                      {item.approval_date?.slice(0, 10) ?? "—"}
                    </td>
                    <td className="px-5 py-4">
                      <span
                        className={`text-xs px-2 py-0.5 rounded-full font-medium ${
                          item.status === "Approved"
                            ? "bg-emerald-500/20 text-emerald-400"
                            : item.status === "Pending"
                            ? "bg-amber-500/20 text-amber-400"
                            : "bg-gray-700 text-gray-400"
                        }`}
                      >
                        {item.status || "—"}
                      </span>
                    </td>
                    <td className="px-5 py-4 text-right">
                      <Link
                        href={`/company/${item.ticker}`}
                        className="text-xs text-indigo-400 hover:text-indigo-300"
                      >
                        Profil →
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}


      {!loading && items.length > 0 && (
        <p className="text-xs text-gray-500 text-center">
          {items.length} kayıt · Son {daysAhead} günün FDA verileri
        </p>
      )}
    </div>
    
  );
}
