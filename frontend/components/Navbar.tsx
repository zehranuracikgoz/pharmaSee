"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import clsx from "clsx";
import {
  ArrowLeftRight,
  CalendarDays,
  FlaskConical,
  LayoutDashboard,
  Star,
  TrendingUp,
} from "lucide-react";
import DataFreshness from "@/components/DataFreshness";
import PulseLogo from "@/components/PulseLogo";

const links = [
  { href: "/", label: "Dashboard", icon: LayoutDashboard },
  { href: "/calendar", label: "Catalysts", icon: CalendarDays },
  { href: "/impact", label: "Impact", icon: TrendingUp },
  { href: "/clinicaltrials", label: "Clinical Trials", icon: FlaskConical },
  { href: "/compare", label: "Compare", icon: ArrowLeftRight },
  { href: "/watchlist", label: "Watchlist", icon: Star },
];

export default function Navbar() {
  const pathname = usePathname();

  return (
    <nav className="bg-surface border-b border-border px-4 sm:px-6 py-3 flex items-center gap-4 lg:gap-8 shadow-sm">
      <Link href="/" className="flex items-center gap-2 font-bold text-text text-lg tracking-tight shrink-0">
        <PulseLogo className="text-accent" size={22} />
        <span>Pharma<span className="text-accent">See</span></span>
      </Link>

      <div className="flex items-center gap-1 overflow-x-auto">
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
            {/* icon-only below lg so six links fit */}
            <span className="hidden lg:inline">{label}</span>
          </Link>
        ))}
      </div>
      <div className="ml-auto hidden xl:flex items-center gap-4">
        <DataFreshness />
        <span className="hidden 2xl:inline text-xs text-muted font-mono">
          FDA × yfinance × ClinicalTrials
        </span>
      </div>
    </nav>
  );
}