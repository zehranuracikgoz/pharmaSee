"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import clsx from "clsx";
import {
  ArrowLeftRight,
  CalendarDays,
  ChartLine,
  FlaskConical,
  LayoutDashboard,
  Menu,
  Star,
  TrendingUp,
  X,
} from "lucide-react";
import DataFreshness from "@/components/DataFreshness";
import PulseLogo from "@/components/PulseLogo";

const links = [
  { href: "/", label: "Dashboard", icon: LayoutDashboard },
  { href: "/calendar", label: "Catalysts", icon: CalendarDays },
  { href: "/impact", label: "Impact", icon: TrendingUp },
  { href: "/research", label: "Research", icon: ChartLine },
  { href: "/clinicaltrials", label: "Clinical Trials", icon: FlaskConical },
  { href: "/compare", label: "Compare", icon: ArrowLeftRight },
  { href: "/watchlist", label: "Watchlist", icon: Star },
];

export default function Navbar() {
  const pathname = usePathname();
  const [open, setOpen] = useState(false);

  // close the mobile menu after navigating
  useEffect(() => setOpen(false), [pathname]);

  return (
    <nav className="relative bg-surface border-b border-border px-4 sm:px-6 py-3 flex items-center gap-4 lg:gap-8 shadow-sm">
      <Link href="/" className="flex items-center gap-2 font-bold text-text text-lg tracking-tight shrink-0">
        <PulseLogo className="text-accent" size={22} />
        <span>Pharma<span className="text-accent">See</span></span>
      </Link>

      {/* seven links only fit from sm up: icons first, labels from lg */}
      <div className="hidden sm:flex items-center gap-1">
        {links.map(({ href, label, icon: Icon }) => (
          <Link
            key={href}
            href={href}
            title={label}
            aria-label={label}
            className={clsx(
              "inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md text-sm font-medium whitespace-nowrap transition-colors",
              pathname===href
                ? "bg-accent/15 text-accent"
                : "text-muted hover:bg-surface2 hover:text-text"
            )}
          >
            <Icon className="h-4 w-4 shrink-0" />
            <span className="hidden lg:inline">{label}</span>
          </Link>
        ))}
      </div>

      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        aria-label={open ? "Close menu" : "Open menu"}
        aria-expanded={open}
        aria-controls="mobile-menu"
        className="sm:hidden ml-auto p-2 -mr-2 rounded-md text-muted hover:bg-surface2 hover:text-text transition-colors"
      >
        {open ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
      </button>

      {open && (
        <div
          id="mobile-menu"
          className="sm:hidden absolute left-0 right-0 top-full z-40 bg-surface border-b border-border shadow-lg p-2 flex flex-col"
        >
          {links.map(({ href, label, icon: Icon }) => (
            <Link
              key={href}
              href={href}
              className={clsx(
                "flex items-center gap-3 px-3 py-2.5 rounded-md text-sm font-medium transition-colors",
                pathname===href
                  ? "bg-accent/15 text-accent"
                  : "text-muted hover:bg-surface2 hover:text-text"
              )}
            >
              <Icon className="h-4 w-4 shrink-0" />
              {label}
            </Link>
          ))}
        </div>
      )}

      <div className="ml-auto hidden xl:flex items-center gap-4">
        <DataFreshness />
        <span className="hidden 2xl:inline text-xs text-muted font-mono">
          FDA × yfinance × ClinicalTrials
        </span>
      </div>
    </nav>
  );
}
