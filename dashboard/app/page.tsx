import fs from "fs";
import path from "path";
import Link from "next/link";
import type { Signal } from "@/lib/types";
import { TopBar } from "@/components/chrome/top-bar";
import { SearchBar } from "@/components/forms/search-bar";
import { Stat } from "@/components/data/stat";
import { MiniSparkForest } from "@/components/charts/mini-spark-forest";

function loadSignals(): Signal[] {
  const raw = fs.readFileSync(
    path.join(process.cwd(), "public/data/signals.json"),
    "utf-8"
  );
  return JSON.parse(raw);
}

type DrugSummary = {
  name: string;
  flaggedCount: number;
  totalSignals: number;
  topReaction: string;
  topRor: number;
  topLo: number;
  topHi: number;
  topFlagged: boolean;
};

function buildDrugSummaries(signals: Signal[]): DrugSummary[] {
  const byDrug = new Map<string, Signal[]>();
  for (const s of signals) {
    const list = byDrug.get(s.drug_name) ?? [];
    list.push(s);
    byDrug.set(s.drug_name, list);
  }

  const summaries: DrugSummary[] = [];
  for (const [name, rows] of byDrug) {
    const flagged = rows.filter((r) => r.flagged);
    const top = rows.reduce((a, b) => (a.ror > b.ror ? a : b));
    summaries.push({
      name,
      flaggedCount: flagged.length,
      totalSignals: rows.length,
      topReaction: top.reaction,
      topRor: top.ror,
      topLo: top.ror_lower,
      topHi: top.ror_upper,
      topFlagged: top.flagged,
    });
  }

  return summaries.sort((a, b) => b.flaggedCount - a.flaggedCount);
}

export default function Home() {
  const signals = loadSignals();
  const drugs = buildDrugSummaries(signals);
  const nFlagged = signals.filter((s) => s.flagged).length;
  const nDrugs = drugs.length;
  const nReactions = new Set(signals.map((s) => s.reaction)).size;
  const nReports = signals.reduce((sum, s) => sum + s.n_reports, 0);
  const refreshDate = signals[0]?.computed_date ?? "—";

  return (
    <div className="min-h-screen bg-bg-page">
      <TopBar active="Index" refreshDate={refreshDate} />

      <main className="px-6 py-8 max-w-7xl mx-auto">
        {/* Masthead */}
        <div className="flex flex-col lg:flex-row lg:items-end lg:justify-between gap-6 mb-8">
          <div>
            <h1 className="text-data-2xl font-display font-semibold text-ink-100">
              <span className="text-accent">{nFlagged}</span> signals across{" "}
              {nDrugs} drugs
            </h1>
            <p className="mt-2 text-data-sm text-ink-400 max-w-xl">
              Disproportionality signals detected via ROR (Rothman 2004) and
              PRR/EVANS criterion (Evans 2001) on FDA FAERS spontaneous
              reports.
            </p>
          </div>

          {/* KPI strip */}
          <div className="flex gap-6 border-l border-rule pl-6">
            <Stat label="Reactions" value={nReactions.toLocaleString()} size="md" />
            <Stat label="Reports" value={nReports.toLocaleString()} size="md" />
            <Stat label="Refresh" value="Weekly" size="md" />
            <Stat label="Method" value="EVANS" glossary="EVANS" size="md" />
          </div>
        </div>

        {/* Search */}
        <div className="mb-10">
          <SearchBar size="xl" />
        </div>

        {/* Watchlist grid */}
        <section>
          <h2 className="text-data-xs font-mono uppercase tracking-wide text-ink-500 mb-3">
            Drug index
          </h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-px bg-rule">
            {drugs.map((drug) => (
              <Link
                key={drug.name}
                href={`/drug/${encodeURIComponent(drug.name)}`}
                className="bg-bg-surf p-4 hover:bg-bg-raised transition-colors group"
              >
                <div className="flex items-start justify-between mb-2">
                  <span className="text-data-md font-display font-semibold text-ink-100 group-hover:text-accent transition-colors">
                    {drug.name}
                  </span>
                  {drug.flaggedCount > 0 && (
                    <span className="text-data-xs font-mono px-1.5 py-0.5 rounded-xs bg-accent-wash text-accent">
                      {drug.flaggedCount} flagged
                    </span>
                  )}
                </div>
                <div className="text-data-xs text-ink-400 mb-2 truncate">
                  Top: {drug.topReaction}
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-data-md font-mono font-medium text-accent">
                    {drug.topRor.toFixed(1)}
                  </span>
                  <MiniSparkForest
                    lo={drug.topLo}
                    point={drug.topRor}
                    hi={drug.topHi}
                    flagged={drug.topFlagged}
                  />
                </div>
              </Link>
            ))}
          </div>
        </section>
      </main>
    </div>
  );
}
