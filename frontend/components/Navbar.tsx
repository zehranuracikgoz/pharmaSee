"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import clsx from "clsx";

const links = [
  { href: "/", label: "Dashboard" },
  { href: "/calendar", label: "FDA Takvim" },
  { href: "/compare", label: "Karşılaştır" },
  { href: "/watchlist", label: "Watchlist" },
];

export default function Navbar() {
  const pathname = usePathname();

  return (
    <nav className="bg-white border-b border-slate-200 px-6 py-3 flex items-center gap-8 shadow-sm">
      <Link href="/" className="flex items-center gap-2 font-bold text-slate-900 text-lg tracking-tight">
        <span className="text-brand-700">💊</span>
        <span>Pharma<span className="text-accent-600">See</span></span>
      </Link>

      <div className="flex items-center gap-1 ml-4">
        {links.map((l) => (
          <Link
            key={l.href}
            href={l.href}
            className={clsx(
              "px-3 py-1.5 rounded-md text-sm font-medium transition-colors",
              pathname === l.href
                ? "bg-brand-700 text-white"
                : "text-slate-500 hover:bg-slate-100 hover:text-slate-900"
            )}
          >
            {l.label}
          </Link>
        ))}
      </div>
      <div className="ml-auto text-xs text-slate-400 font-mono">
        FDA × yfinance × ClinicalTrials
      </div>
    </nav>
  );
}