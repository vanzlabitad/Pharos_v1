import fs from "fs";
import path from "path";
import type { Signal, DrugMeta, DrugSummary } from "@/lib/types";
import { TopBar } from "@/components/chrome/top-bar";
import { Stat } from "@/components/data/stat";
import { MethodFootnote } from "@/components/data/method-footnote";
import { DrugProfileClient } from "@/components/drug/drug-profile-client";

function loadSignals(): Signal[] {
  const raw = fs.readFileSync(
    path.join(process.cwd(), "public/data/signals.json"),
    "utf-8"
  );
  return JSON.parse(raw);
}

function loadDrugMeta(): Record<string, DrugMeta> {
  const metaPath = path.join(process.cwd(), "public/data/drug-metadata.json");
  if (!fs.existsSync(metaPath)) return {};
  return JSON.parse(fs.readFileSync(metaPath, "utf-8"));
}

function loadSummary(drug: string): DrugSummary | null {
  const summaryPath = path.join(process.cwd(), "public/data/summaries.json");
  if (!fs.existsSync(summaryPath)) return null;
  const raw = fs.readFileSync(summaryPath, "utf-8");
  const summaries = JSON.parse(raw);
  const entry = summaries[drug];
  if (!entry) return null;
  if (typeof entry === "string") {
    return { overall: entry, reactions: {} };
  }
  return entry as DrugSummary;
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

  const meta = loadDrugMeta();
  const drugMeta = meta[drugName];

  const totalReports = drugSignals.reduce((sum, s) => sum + s.n_reports, 0);
  const topRor = drugSignals.length
    ? Math.max(...drugSignals.map((s) => s.ror))
    : 0;

  const summaryData = loadSummary(drugName);

  const sortedFlagged = [...flaggedSignals].sort((a, b) => b.ror - a.ror);
  const displaySignals = sortedFlagged.slice(0, 15);

  return (
    <div className="min-h-screen bg-bg-page">
      <TopBar refreshDate={refreshDate} />

      <main className="px-6 py-8 max-w-7xl mx-auto">
        {/* Breadcrumb */}
        <p className="text-data-xs font-mono uppercase tracking-wide text-ink-500 mb-4">
          Drug brief &middot; {refreshDate}
          {drugMeta?.atc_code && <> &middot; ATC {drugMeta.atc_code}</>}
        </p>

        {/* Drug name masthead */}
        <div className="flex flex-col lg:flex-row lg:items-end lg:justify-between gap-6 mb-2">
          <h1
            className="font-display font-semibold text-ink-100"
            style={{
              fontSize: "96px",
              lineHeight: "1",
              letterSpacing: "-0.04em",
            }}
          >
            {drugName}
          </h1>

          <div className="flex gap-6 border-l border-rule pl-6">
            <Stat label="Reports" value={totalReports.toLocaleString()} size="md" />
            <Stat label="Flagged" value={flaggedSignals.length} accent size="md" />
            <Stat
              label="Top ROR"
              value={topRor.toFixed(2)}
              glossary="ROR"
              size="md"
            />
          </div>
        </div>

        {/* Drug class + aliases */}
        <p className="text-data-sm text-ink-400 mb-8">
          {drugMeta?.drug_class && (
            <span className="text-ink-300">{drugMeta.drug_class}</span>
          )}
          {drugMeta?.aliases && drugMeta.aliases.length > 0 && (
            <>
              {drugMeta?.drug_class && <> &middot; </>}
              <span className="text-ink-500">
                aliases: {drugMeta.aliases.join(", ")}
              </span>
            </>
          )}
        </p>

        <DrugProfileClient
          drugName={drugName}
          displaySignals={displaySignals}
          flaggedCount={flaggedSignals.length}
          summary={summaryData?.overall ?? null}
          reactionSummaries={summaryData?.reactions ?? {}}
        />

        <MethodFootnote />
      </main>
    </div>
  );
}
