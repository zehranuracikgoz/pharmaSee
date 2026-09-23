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
    <nav className = "bg-brand-900 border-b border-brand-700 px-6 py-3 flex items-center gap-8">
      <Link href="/" className="flex items-center gap-2 font-bold text-white text-lg tracking-tight">
        <span className="text-brand-100">💊</span>
        <span>Pharma<span className="text-indigo-300">See</span></span>
      </Link>

      <div className="flex items-center gap-1 ml-4">
        {links.map((l) => (
          <Link
            key={l.href}
            href={l.href}
            className={clsx(
              "px-3 py-1.5 rounded-md text-sm font-medium transition-colors",
              pathname ===l.href
                ? "bg-brand-600 text-white"
                : "text-indigo-200 hover:bg-brand-700 hover:text-white"
            )}
          >
            {l.label}
          </Link>
        ))}
      </div>
      <div className="ml-auto text-xs text-indigo-400 font-mono">
        FDA × yfinance × ClinicalTrials
      </div>
    </nav>
  );
}