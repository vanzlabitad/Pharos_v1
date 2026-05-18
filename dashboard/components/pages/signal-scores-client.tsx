"use client";

import { useState, useMemo } from "react";
import { TopBar } from "@/components/chrome/top-bar";
import { ForestPlot, type ForestRow } from "@/components/charts/forest/forest-plot";
import { MethodFootnote } from "@/components/data/method-footnote";
import type { Signal } from "@/lib/types";

type SortKey = "ror" | "n" | "ci_width";

function toForestRow(s: Signal): ForestRow {
  return {
    reaction: s.reaction,
    ror: s.ror,
    lo: s.ror_lower,
    hi: s.ror_upper,
    n: s.n_reports,
    prr: s.prr,
    chi2: s.chi_squared,
    flagged: s.flagged,
  };
}

function sortRows(rows: ForestRow[], key: SortKey): ForestRow[] {
  const sorted = [...rows];
  switch (key) {
    case "ror":
      sorted.sort((a, b) => b.ror - a.ror);
      break;
    case "n":
      sorted.sort((a, b) => b.n - a.n);
      break;
    case "ci_width":
      sorted.sort((a, b) => (b.hi - b.lo) - (a.hi - a.lo));
      break;
  }
  return sorted;
}

export function SignalScoresClient({
  drugName,
  drugSignals,
}: {
  drugName: string;
  drugSignals: Signal[];
}) {
  const [sortKey, setSortKey] = useState<SortKey>("ror");
  const [flaggedOnly, setFlaggedOnly] = useState(false);
  const [showAll, setShowAll] = useState(false);

  const filtered = useMemo(() => {
    return flaggedOnly
      ? drugSignals.filter((s) => s.flagged)
      : drugSignals;
  }, [drugSignals, flaggedOnly]);

  const forestRows = useMemo(() => {
    const rows = filtered.map(toForestRow);
    const sorted = sortRows(rows, sortKey);
    return showAll ? sorted : sorted.slice(0, 15);
  }, [filtered, sortKey, showAll]);

  const flaggedCount = drugSignals.filter((s) => s.flagged).length;
  const refreshDate = drugSignals[0]?.computed_date ?? "—";

  return (
    <div className="min-h-screen bg-bg-page">
      <TopBar refreshDate={refreshDate} />

      <main className="px-6 py-8 max-w-[1200px] mx-auto">
        {/* Header */}
        <div className="mb-6">
          <h1>
            <span className="text-data-xl font-display font-semibold text-ink-100">
              {drugName}
            </span>
            <span className="text-data-xl font-display text-ink-400 ml-2">
              signal scores
            </span>
          </h1>
          <p className="mt-1 text-data-sm text-ink-400">
            {flaggedCount} flagged signal{flaggedCount !== 1 ? "s" : ""} &middot;
            EVANS indicator on each row
          </p>
        </div>

        {/* Controls strip */}
        <div className="flex flex-wrap items-center gap-2 mb-6">
          <span className="text-data-xs font-mono text-ink-500 mr-2">
            Sort:
          </span>
          {(
            [
              ["ror", "ROR"],
              ["n", "n"],
              ["ci_width", "CI width"],
            ] as [SortKey, string][]
          ).map(([key, label]) => (
            <button
              key={key}
              onClick={() => setSortKey(key)}
              className={`px-3 py-1 text-data-xs font-mono rounded-xs border transition-colors ${
                sortKey === key
                  ? "border-accent text-accent bg-accent-wash"
                  : "border-rule text-ink-400 hover:text-ink-200 hover:border-edge"
              }`}
            >
              {label}
            </button>
          ))}

          <span className="mx-2 text-ink-600">|</span>

          <button
            onClick={() => setFlaggedOnly(!flaggedOnly)}
            className={`px-3 py-1 text-data-xs font-mono rounded-xs border transition-colors ${
              flaggedOnly
                ? "border-accent text-accent bg-accent-wash"
                : "border-rule text-ink-400 hover:text-ink-200 hover:border-edge"
            }`}
          >
            Flagged only
          </button>

          <span className="ml-auto text-data-xs font-mono text-ink-500">
            {forestRows.length}
            {!showAll && filtered.length > 15
              ? ` of ${filtered.length}`
              : ""}{" "}
            rows
          </span>
        </div>

        {/* Two-column layout: forest plot + right rail */}
        <div className="flex gap-6">
          {/* Main forest plot */}
          <div className="flex-1 overflow-x-auto">
            {forestRows.length > 0 ? (
              <ForestPlot rows={forestRows} showEvans />
            ) : (
              <p className="text-data-sm text-ink-400 py-8">
                No signals match the current filter.
              </p>
            )}
            {!showAll && filtered.length > 15 && (
              <button
                onClick={() => setShowAll(true)}
                className="mt-3 px-4 py-1.5 text-data-xs font-mono text-accent border border-accent rounded-xs hover:bg-accent-wash transition-colors"
              >
                Show all {filtered.length} rows
              </button>
            )}
          </div>

          {/* Right rail */}
          <aside className="hidden lg:block w-[280px] flex-shrink-0 bg-bg-surf p-4 rounded-sm border border-hair self-start">
            <h3 className="text-data-xs font-mono uppercase tracking-wide text-ink-400 mb-3">
              How to read this
            </h3>
            <dl className="space-y-3 text-data-xs">
              <div className="flex items-start gap-2">
                <svg width={14} height={14} className="flex-shrink-0 mt-0.5">
                  <circle cx={7} cy={7} r={5.5} fill="var(--accent)" />
                </svg>
                <dd className="text-ink-300">
                  Flagged signal &mdash; both ROR and EVANS criteria pass.
                  The blue halo marks statistical strength.
                </dd>
              </div>
              <div className="flex items-start gap-2">
                <svg width={14} height={14} className="flex-shrink-0 mt-0.5">
                  <circle cx={7} cy={7} r={4} fill="var(--ink-300)" />
                </svg>
                <dd className="text-ink-300">
                  Not flagged &mdash; the signal did not pass both criteria.
                  May still be informative.
                </dd>
              </div>
              <div className="flex items-start gap-2">
                <svg width={14} height={14} className="flex-shrink-0 mt-0.5">
                  <polygon
                    points="13,7 8,4 8,10"
                    fill="var(--ink-400)"
                  />
                </svg>
                <dd className="text-ink-300">
                  Arrow &mdash; the 95% CI extends beyond the chart bounds
                  (0.1&ndash;100). Wide CIs indicate high uncertainty,
                  often from small n.
                </dd>
              </div>
              <div className="flex items-start gap-2">
                <span className="flex gap-0.5 flex-shrink-0 mt-1">
                  <span className="inline-block w-2 h-2 bg-accent" />
                  <span className="inline-block w-2 h-2 bg-accent" />
                  <span className="inline-block w-2 h-2 bg-ink-600" />
                </span>
                <dd className="text-ink-300">
                  EVANS glyphs &mdash; three squares for a&ge;3, PRR&ge;2,
                  &chi;&sup2;&ge;4. Filled = pass. Shows why a row was or
                  wasn&apos;t flagged.
                </dd>
              </div>
            </dl>

            <div className="mt-4 pt-3 border-t border-hair">
              <h4 className="text-data-xs font-mono uppercase tracking-wide text-ink-400 mb-2">
                Flag definition
              </h4>
              <p className="text-data-xs font-mono text-ink-400 leading-relaxed">
                flagged = ROR lower CI &gt; 1
                <br />
                &nbsp;&nbsp;AND PRR &ge; 2
                <br />
                &nbsp;&nbsp;AND n &ge; 3
                <br />
                &nbsp;&nbsp;AND &chi;&sup2; &ge; 4
              </p>
            </div>

            <div className="mt-4 pt-3 border-t border-hair">
              <h4 className="text-data-xs font-mono uppercase tracking-wide text-ink-400 mb-2">
                FAERS caveats
              </h4>
              <ul className="text-data-xs text-ink-500 space-y-1 list-disc list-inside">
                <li>Spontaneous reports &ne; causal evidence</li>
                <li>Notoriety bias inflates media-covered drugs</li>
                <li>Indication confounding (drug&apos;s disease = reaction)</li>
                <li>Weber effect: reports peak 1&ndash;2 yr post-launch</li>
                <li>No exposure denominator (reporting odds, not incidence)</li>
              </ul>
            </div>
          </aside>
        </div>

        <MethodFootnote />
      </main>
    </div>
  );
}
