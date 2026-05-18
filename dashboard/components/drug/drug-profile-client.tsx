"use client";

import { useState } from "react";
import Link from "next/link";
import type { Signal } from "@/lib/types";
import { ColLabel } from "@/components/data/col-label";
import { EvansGlyph } from "@/components/charts/forest/evans-glyph";

type Props = {
  drugName: string;
  displaySignals: Signal[];
  flaggedCount: number;
  summary: string | null;
  reactionSummaries: Record<string, string>;
};

export function DrugProfileClient({
  drugName,
  displaySignals,
  flaggedCount,
  summary,
  reactionSummaries,
}: Props) {
  const [selectedReaction, setSelectedReaction] = useState<string | null>(null);

  const activeText = selectedReaction
    ? reactionSummaries[selectedReaction] ?? null
    : summary;

  const handleReactionClick = (reaction: string) => {
    if (selectedReaction === reaction) {
      setSelectedReaction(null);
    } else if (reactionSummaries[reaction]) {
      setSelectedReaction(reaction);
    }
  };

  return (
    <>
      {/* AI summary pull-quote */}
      <section className="mb-10 grid grid-cols-1 lg:grid-cols-[auto_1fr_200px] gap-6 items-start">
        <span className="text-data-xs font-mono uppercase tracking-wide text-ink-500 pt-1">
          {selectedReaction ? (
            <>Reaction: {selectedReaction}</>
          ) : (
            <>Plain language</>
          )}
        </span>
        <blockquote className="border-l-2 border-accent pl-4 text-data-md text-ink-200 font-display leading-relaxed">
          {activeText ?? (
            <span className="text-ink-500 italic">
              AI summary not yet generated for this drug. Summaries are
              created at weekly refresh time for drugs with flagged signals.
            </span>
          )}
          {selectedReaction && (
            <button
              onClick={() => setSelectedReaction(null)}
              className="mt-2 block text-data-xs text-accent hover:underline font-mono"
            >
              &larr; Back to drug summary
            </button>
          )}
        </blockquote>
        <div className="text-data-xs text-ink-500 space-y-1">
          <p className="font-mono">Gemini 2.5 Flash</p>
          <p>AI-generated &middot; Not medical advice</p>
        </div>
      </section>

      {/* Flagged signals table */}
      {displaySignals.length > 0 ? (
        <section>
          <div className="flex items-baseline justify-between mb-3">
            <h2 className="text-data-xs font-mono uppercase tracking-wide text-ink-500">
              Flagged signals &middot; sorted by ROR
            </h2>
            <span className="text-data-xs font-mono text-ink-500">
              {displaySignals.length < flaggedCount
                ? `${displaySignals.length} of ${flaggedCount} shown`
                : `${flaggedCount} total`}
              {" · "}
              <Link
                href={`/drug/${encodeURIComponent(drugName)}/signals`}
                className="text-accent hover:underline"
              >
                open Signal Scores for full forest
              </Link>
            </span>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-data-sm">
              <thead>
                <tr className="border-b border-rule">
                  <th className="text-left py-2 pr-4">
                    <ColLabel>Reaction</ColLabel>
                  </th>
                  <th className="text-right py-2 px-3">
                    <ColLabel glossary="ROR">ROR</ColLabel>
                  </th>
                  <th className="text-right py-2 px-3">
                    <ColLabel glossary="CI">95% CI</ColLabel>
                  </th>
                  <th className="text-right py-2 px-3">
                    <ColLabel glossary="PRR">PRR</ColLabel>
                  </th>
                  <th className="text-right py-2 px-3">
                    <ColLabel glossary="chi-squared">&chi;&sup2;</ColLabel>
                  </th>
                  <th className="text-right py-2 px-3">
                    <ColLabel glossary="n">n</ColLabel>
                  </th>
                  <th className="text-right py-2 pl-3">
                    <ColLabel glossary="EVANS">Effect size</ColLabel>
                  </th>
                </tr>
              </thead>
              <tbody>
                {displaySignals.map((s) => {
                  const hasExplanation = !!reactionSummaries[s.reaction];
                  const isActive = selectedReaction === s.reaction;

                  return (
                    <tr
                      key={s.id}
                      className="border-b border-hair hover:bg-bg-surf transition-colors"
                    >
                      <td className="py-2 pr-4">
                        {hasExplanation ? (
                          <button
                            onClick={() => handleReactionClick(s.reaction)}
                            className={`text-left transition-colors ${
                              isActive
                                ? "text-accent font-medium"
                                : "text-ink-200 hover:text-accent"
                            }`}
                          >
                            {s.reaction}
                          </button>
                        ) : (
                          <span className="text-ink-200">{s.reaction}</span>
                        )}
                      </td>
                      <td className="py-2 px-3 text-right font-mono text-accent font-medium">
                        {s.ror.toFixed(2)}
                      </td>
                      <td className="py-2 px-3 text-right font-mono text-ink-300">
                        {s.ror_lower.toFixed(2)}&ndash;{s.ror_upper.toFixed(2)}
                      </td>
                      <td className="py-2 px-3 text-right font-mono text-ink-300">
                        {s.prr.toFixed(2)}
                      </td>
                      <td className="py-2 px-3 text-right font-mono text-ink-300">
                        {s.chi_squared.toFixed(1)}
                      </td>
                      <td className="py-2 px-3 text-right font-mono text-ink-300">
                        {s.n_reports}
                      </td>
                      <td className="py-2 pl-3 text-right">
                        <EvansGlyph
                          n={s.n_reports}
                          prr={s.prr}
                          chi2={s.chi_squared}
                        />
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          {flaggedCount > 15 && (
            <p className="mt-2 text-data-xs text-ink-500">
              Showing top 15 of {flaggedCount} flagged signals.{" "}
              <Link
                href={`/drug/${encodeURIComponent(drugName)}/signals`}
                className="text-accent hover:underline"
              >
                View all signal scores &rarr;
              </Link>
            </p>
          )}
        </section>
      ) : (
        <p className="text-data-sm text-ink-400">
          No flagged signals for this drug.{" "}
          <Link
            href={`/drug/${encodeURIComponent(drugName)}/signals`}
            className="text-accent hover:underline"
          >
            View all signal scores &rarr;
          </Link>
        </p>
      )}
    </>
  );
}
