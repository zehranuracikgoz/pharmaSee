"use client";

import { useState, useCallback, useRef } from "react";
import { useRouter } from "next/navigation";
import { api, Company } from "@/lib/api";

export default function SearchBar() {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<Company[]>([]);
  const [loading, setLoading] = useState(false);
  const [open, setOpen] = useState(false);
  const router = useRouter();
  const timer = useRef<ReturnType<typeof setTimeout>>();

  const search = useCallback((q: string) => {
    if (timer.current) clearTimeout(timer.current);
    if (!q.trim()) {
      setResults([]);
      setOpen(false);
      return;
    }
    timer.current = setTimeout(async () => {
      setLoading(true);
      try {
        const data = await api.searchCompanies(q);
        setResults(data.results);
        setOpen(true);
      } catch {
        setResults([]);
      } finally {
        setLoading(false);
      }
    }, 300);
  }, []);

  return (
    <div className="relative w-full max-w-sm">
      <div className="relative">
        <input
          type="text"
          value={query}
          onChange={(e) => {
            setQuery(e.target.value);
            search(e.target.value);
          }}
          onBlur={() => setTimeout(() => setOpen(false), 150)}
          placeholder="Şirket veya ticker ara…"
          className="w-full bg-gray-800 border border-gray-700 rounded-lg pl-9 pr-4 py-2 text-sm text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-brand-500 focus:border-transparent"
        />
        <span className="absolute left-3 top-2.5 text-gray-500 text-sm">🔍</span>
        {loading && (
          <span className="absolute right-3 top-2.5 text-gray-500 text-xs animate-pulse">
            …
          </span>
        )}
      </div>

      {open && results.length > 0 && (
        <div className =" absolute top-full mt-1 w-full bg-gray-800 border border-gray-700 rounded-lg shadow-xl z-50 overflow-hidden">
          {results.map((c) => (
            <button
              key={c.ticker}
              onMouseDown={() => {
                router.push(`/company/${c.ticker}`);
                setOpen(false);
                setQuery("");
              }}
              className = "w-full flex items-center gap-3 px-4 py-2.5 hover:bg-gray-700 text-left transition-colors"
            >
              <span className="font-mono font-bold text-indigo-300 text-sm w-16">
                {c.ticker}
              </span>
              <span className="text-white text-sm truncate">{c.name}</span>
              {c.sector && (
                <span className="ml-auto text-xs text-gray-500 shrink-0">
                  {c.sector}
                </span>
              )}
            </button>
          ))}
        </div>
      )}

      {open && results.length ===0 && !loading && query && (
        <div className="absolute top-full mt-1 w-full bg-gray-800 border border-gray-700 rounded-lg shadow-xl z-50 px-4 py-3 text-sm text-gray-500">
          Sonuç bulunamadı
        </div>
      )}
    </div>

  );
}