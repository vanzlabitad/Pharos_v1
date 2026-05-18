"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { BrandMark } from "@/components/brand-mark";

const NAV_ITEMS = [
  { label: "Home", href: "/" },
  { label: "Explore", href: "/explore" },
  { label: "Methodology", href: "/report.html" },
] as const;

export function TopBar({ refreshDate }: { refreshDate?: string }) {
  const pathname = usePathname();

  return (
    <header className="flex items-center justify-between border-b border-rule px-6 py-3 bg-bg-surf">
      <div className="flex items-center gap-8">
        <Link href="/">
          <BrandMark />
        </Link>
        <nav className="flex gap-6">
          {NAV_ITEMS.map((item) => {
            const isActive =
              item.href === "/"
                ? pathname === "/"
                : pathname.startsWith(item.href) ||
                  (item.href === "/explore" && pathname.startsWith("/drug"));
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
