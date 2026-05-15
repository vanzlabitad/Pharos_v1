"use client";

import Link from "next/link";
import { BrandMark } from "@/components/brand-mark";

const NAV_ITEMS = [
  { label: "Index", href: "/" },
  { label: "Drugs", href: "/" },
  { label: "Signals", href: "/" },
  { label: "Methodology", href: "/" },
] as const;

export function TopBar({
  active,
  refreshDate,
}: {
  active?: string;
  refreshDate?: string;
}) {
  return (
    <header className="flex items-center justify-between border-b border-rule px-6 py-3 bg-bg-surf">
      <div className="flex items-center gap-8">
        <Link href="/">
          <BrandMark />
        </Link>
        <nav className="flex gap-6">
          {NAV_ITEMS.map((item) => {
            const isActive = active === item.label;
            return (
              <Link
                key={item.label}
                href={item.href}
                className={`text-data-sm font-medium transition-colors ${
                  isActive
                    ? "text-ink-100 border-b-2 border-accent pb-0.5"
                    : "text-ink-400 hover:text-ink-200"
                }`}
              >
                {item.label}
              </Link>
            );
          })}
        </nav>
      </div>
      <div className="flex items-center gap-3 text-data-xs text-ink-400">
        {refreshDate && (
          <>
            <span className="inline-block w-1.5 h-1.5 rounded-full bg-accent" />
            <span className="font-mono">{refreshDate}</span>
          </>
        )}
        <span className="text-ink-500">FAERS</span>
      </div>
    </header>
  );
}
