"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { CalendarDays } from "lucide-react";
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
          <h1 className="text-2xl font-bold text-text">FDA Calendar</h1>
          <p className="text-sm text-muted mt-0.5">
            Upcoming and recent FDA approval decisions
          </p>
        </div>
        <div className="flex items-center gap-1">
          {[30, 60, 90, 180].map((d) => (
            <button
              key={d}
              onClick={() => setDaysAhead(d)}
              className={`text-sm px-3 py-1.5 rounded-lg transition-colors ${
                daysAhead ===d
                  ? "bg-accent text-bg"
                  : "bg-surface text-muted hover:bg-surface2 hover:text-text border border-border"
              }`}
            >
              {d} days
            </button>
          ))}
        </div>
      </div>

      {loading ? (
        <div className="card divide-y divide-border/40">
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="px-5 py-4 flex items-center gap-4 animate-pulse">
              <div className="h-10 w-10 bg-border rounded-lg shrink-0" />
              <div className="flex-1 space-y-2">
                <div className="h-4 bg-border rounded w-48" />
                <div className="h-3 bg-border rounded w-32" />
              </div>
              <div className="h-6 bg-border rounded w-20" />
            </div>
          ))}
        </div>
      ) : items.length ===0 ? (
        <div className="card p-12 text-center">
          <CalendarDays className="h-10 w-10 text-muted mx-auto mb-3" />
          <p className="text-muted">
            No calendar data for this period.
          </p>
          <p className="text-muted text-sm mt-1">
            Run an FDA sync to update the database.
          </p>
          <button
            onClick={()=> api.fdaSync().then(() => setDaysAhead((d) => d))}
            className="mt-4 text-sm bg-accent hover:bg-accent-hover text-bg px-4 py-2 rounded-lg transition-colors"
          >
            Run FDA Sync
          </button>
        </div>
      ) : (
        <div className="card overflow-hidden">
          <div className = "overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border/60">
                  <th className="text-left px-5 py-3 text-muted font-medium">Company</th>
                  <th className="text-left px-5 py-3 text-muted font-medium">Drug</th>
                  <th className="text-left px-5 py-3 text-muted font-medium hidden md:table-cell">Type</th>
                  <th className="text-left px-5 py-3 text-muted font-medium">Date</th>
                  <th className="text-left px-5 py-3 text-muted font-medium">Status</th>
                  <th className="px-5 py-3" />
                </tr>
              </thead>
              <tbody className="divide-y divide-border/40">
                {items.map((item, i) => (
                  <tr
                    key={i}
                    className="hover:bg-surface2 transition-colors"
                  >
                    <td className= "px-5 py-4">
                      <div className="font-mono font-bold text-accent text-sm">
                        {item.ticker}
                      </div>
                      <div className="text-xs text-muted mt-0.5 truncate max-w-36">
                        {item.company_name}
                      </div>
                    </td>
                    <td className="px-5 py-4 text-text font-medium">
                      {item.drug_name}
                    </td>
                    <td className="px-5 py-4 text-muted hidden md:table-cell">
                      {item.application_type || "—"}
                    </td>
                    <td className="px-5 py-4 font-mono text-xs text-text">
                      {item.approval_date?.slice(0, 10) ?? "—"}
                    </td>
                    <td className="px-5 py-4">
                      <span
                        className={`text-xs px-2 py-0.5 rounded-full font-medium ${
                          item.status === "Approved"
                            ? "bg-success/20 text-success"
                            : item.status === "Pending"
                            ? "bg-warning/20 text-warning"
                            : "bg-surface2 text-muted"
                        }`}
                      >
                        {item.status || "—"}
                      </span>
                    </td>
                    <td className="px-5 py-4 text-right">
                      <Link
                        href={`/company/${item.ticker}`}
                        className="text-xs text-accent hover:text-accent-hover"
                      >
                        Profile →
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
        <p className="text-xs text-muted text-center">
          {items.length} {items.length === 1 ? "record" : "records"} · FDA decisions in the next {daysAhead} days
        </p>
      )}
    </div>
    
  );
}
