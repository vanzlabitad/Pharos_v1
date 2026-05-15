import fs from "fs";
import path from "path";
import Link from "next/link";
import type { Signal } from "@/lib/types";
import { TopBar } from "@/components/chrome/top-bar";
import { Stat } from "@/components/data/stat";
import { ColLabel } from "@/components/data/col-label";
import { MiniSparkForest } from "@/components/charts/mini-spark-forest";
import { MethodFootnote } from "@/components/data/method-footnote";

function loadSignals(): Signal[] {
  const raw = fs.readFileSync(
    path.join(process.cwd(), "public/data/signals.json"),
    "utf-8"
  );
  return JSON.parse(raw);
}

function loadSummary(drug: string): string | null {
  const summaryPath = path.join(
    process.cwd(),
    "public/data/summaries.json"
  );
  if (!fs.existsSync(summaryPath)) return null;
  const raw = fs.readFileSync(summaryPath, "utf-8");
  const summaries: Record<string, string> = JSON.parse(raw);
  return summaries[drug] ?? null;
}

export function generateStaticParams() {
  const signals = loadSignals();
  const drugs = [...new Set(signals.map((s) => s.drug_name))];
  return drugs.map((name) => ({ name }));
}

export default async function DrugProfile({
  params,
}: {
  params: Promise<{ name: string }>;
}) {
  const { name } = await params;
  const drugName = decodeURIComponent(name);
  const allSignals = loadSignals();
  const drugSignals = allSignals.filter((s) => s.drug_name === drugName);
  const flaggedSignals = drugSignals.filter((s) => s.flagged);
  const refreshDate = drugSignals[0]?.computed_date ?? "—";

  const totalReports = drugSignals.reduce((sum, s) => sum + s.n_reports, 0);
  const topRor = drugSignals.length
    ? Math.max(...drugSignals.map((s) => s.ror))
    : 0;

  const summary = loadSummary(drugName);

  const sortedFlagged = [...flaggedSignals].sort((a, b) => b.ror - a.ror);
  const displaySignals = sortedFlagged.slice(0, 15);

  return (
    <div className="min-h-screen bg-bg-page">
      <TopBar active="Drugs" refreshDate={refreshDate} />

      <main className="px-6 py-8 max-w-7xl mx-auto">
        {/* Drug name masthead */}
        <div className="flex flex-col lg:flex-row lg:items-end lg:justify-between gap-6 mb-8">
          <h1
            className="font-display font-semibold text-ink-100"
            style={{ fontSize: "96px", lineHeight: "1", letterSpacing: "-0.04em" }}
          >
            {drugName}
          </h1>

          <div className="flex gap-6 border-l border-rule pl-6">
            <Stat label="Reports" value={totalReports.toLocaleString()} size="md" />
            <Stat
              label="Flagged"
              value={flaggedSignals.length}
              accent
              size="md"
            />
            <Stat
              label="Top ROR"
              value={topRor.toFixed(1)}
              glossary="ROR"
              size="md"
            />
          </div>
        </div>

        {/* AI summary pull-quote */}
        <section className="mb-10 grid grid-cols-1 lg:grid-cols-[auto_1fr_200px] gap-6 items-start">
          <span className="text-data-xs font-mono uppercase tracking-wide text-ink-500 pt-1">
            Plain language
          </span>
          <blockquote className="border-l-2 border-accent pl-4 text-data-md text-ink-200 font-display leading-relaxed">
            {summary ?? (
              <span className="text-ink-500 italic">
                AI summary not yet generated for this drug. Summaries are
                created at weekly refresh time for drugs with flagged signals.
              </span>
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
            <h2 className="text-data-xs font-mono uppercase tracking-wide text-ink-500 mb-3">
              Flagged signals ({flaggedSignals.length})
            </h2>
            <div className="overflow-x-auto">
              <table className="w-full text-data-sm">
                <thead>
                  <tr className="border-b border-rule">
                    <th className="text-left py-2 pr-4">
                      <ColLabel glossary="FAERS">Reaction</ColLabel>
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
                    <th className="text-right py-2 pl-3 w-24">
                      <span className="text-data-xs font-mono text-ink-400">
                        Effect
                      </span>
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {displaySignals.map((s) => (
                    <tr
                      key={s.id}
                      className="border-b border-hair hover:bg-bg-surf transition-colors"
                    >
                      <td className="py-2 pr-4 text-ink-200">{s.reaction}</td>
                      <td className="py-2 px-3 text-right font-mono text-accent font-medium">
                        {s.ror.toFixed(2)}
                      </td>
                      <td className="py-2 px-3 text-right font-mono text-ink-300">
                        {s.ror_lower.toFixed(2)}–{s.ror_upper.toFixed(2)}
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
                      <td className="py-2 pl-3 w-24">
                        <MiniSparkForest
                          lo={s.ror_lower}
                          point={s.ror}
                          hi={s.ror_upper}
                          flagged={s.flagged}
                        />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {flaggedSignals.length > 15 && (
              <p className="mt-2 text-data-xs text-ink-500">
                Showing top 15 of {flaggedSignals.length} flagged signals.{" "}
                <Link
                  href={`/drug/${encodeURIComponent(drugName)}/signals`}
                  className="text-accent hover:underline"
                >
                  View all signal scores →
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
              View all signal scores →
            </Link>
          </p>
        )}

        <MethodFootnote />
      </main>
    </div>
  );
}
