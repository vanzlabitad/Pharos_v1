"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

export function SearchBar({ size = "md" }: { size?: "md" | "xl" }) {
  const [query, setQuery] = useState("");
  const router = useRouter();

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const trimmed = query.trim().toLowerCase();
    if (trimmed) {
      router.push(`/drug/${encodeURIComponent(trimmed)}`);
    }
  }

  const sizeClasses =
    size === "xl"
      ? "text-data-md px-5 py-3"
      : "text-data-sm px-4 py-2";

  return (
    <form onSubmit={handleSubmit} className="w-full max-w-xl">
      <input
        type="text"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        placeholder="Find a drug · brand or generic"
        className={`w-full ${sizeClasses} bg-bg-surf border border-rule rounded-xs text-ink-100 placeholder:text-ink-500 font-sans focus:outline-none focus:border-accent transition-colors`}
      />
      <p className="mt-1.5 text-data-xs text-ink-500">
        Try metformin, ibuprofen, atorvastatin. Aliases resolved to canonical generic.
      </p>
    </form>
  );
}
