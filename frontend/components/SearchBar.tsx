"use client";

import { useState, useCallback, useRef } from "react";
import { useRouter } from "next/navigation";
import { Search } from "lucide-react";
import { api, Company } from "@/lib/api";

interface Props {
  // lets the page focus the input (e.g. the "/" shortcut); also shows the shortcut hint
  inputRef?: React.Ref<HTMLInputElement>;
}

export default function SearchBar({ inputRef }: Props) {
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
          ref={inputRef}
          type="text"
          aria-label="Search company or ticker"
          value={query}
          onChange={(e) => {
            setQuery(e.target.value);
            search(e.target.value);
          }}
          onBlur={() => setTimeout(() => setOpen(false), 150)}
          placeholder="Search company or ticker…"
          className="w-full bg-surface border border-border rounded-lg pl-9 pr-4 py-2 text-sm text-text placeholder-muted focus:outline-none focus:ring-2 focus:ring-accent focus:border-transparent"
        />
        <Search className="absolute left-3 top-2.5 h-4 w-4 text-muted pointer-events-none" />
        {loading ? (
          <span className="absolute right-3 top-2.5 text-muted text-xs animate-pulse">
            …
          </span>
        ) : (
          inputRef && !query && (
            <kbd className="absolute right-2.5 top-2 rounded border border-border bg-surface2 px-1.5 text-[11px] font-mono text-muted pointer-events-none">
              /
            </kbd>
          )
        )}
      </div>

      {open && results.length > 0 && (
        <div className =" absolute top-full mt-1 w-full bg-surface border border-border rounded-lg shadow-xl z-50 overflow-hidden">
          {results.map((c) => (
            <button
              key={c.ticker}
              onMouseDown={() => {
                router.push(`/company/${c.ticker}`);
                setOpen(false);
                setQuery("");
              }}
              className = "w-full flex items-center gap-3 px-4 py-2.5 hover:bg-surface2 text-left transition-colors"
            >
              <span className="font-mono font-bold text-accent text-sm w-16">
                {c.ticker}
              </span>
              <span className="text-text text-sm truncate">{c.name}</span>
              {c.sector && (
                <span className="ml-auto text-xs text-muted shrink-0">
                  {c.sector}
                </span>
              )}
            </button>
          ))}
        </div>
      )}

      {open && results.length ===0 && !loading && query && (
        <div className="absolute top-full mt-1 w-full bg-surface border border-border rounded-lg shadow-xl z-50 px-4 py-3 text-sm text-muted">
          No results found
        </div>
      )}
    </div>

  );
}