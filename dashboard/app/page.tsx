import fs from "fs";
import path from "path";
import Link from "next/link";
import type { Signal } from "@/lib/types";
import { TopBar } from "@/components/chrome/top-bar";

function loadSignals(): Signal[] {
  const raw = fs.readFileSync(
    path.join(process.cwd(), "public/data/signals.json"),
    "utf-8"
  );
  return JSON.parse(raw);
}

const STEPS = [
  {
    number: "01",
    title: "Collect",
    description:
      "Every week, adverse event reports are pulled from the FDA's public database (FAERS) — the same source regulators use to monitor drug safety.",
  },
  {
    number: "02",
    title: "Detect",
    description:
      "Statistical methods compare how often a side effect is reported for a given drug versus all other drugs. Unusual spikes get flagged for attention.",
  },
  {
    number: "03",
    title: "Explore",
    description:
      "Browse the results by drug. See which side effects stand out, how strong the signal is, and what the numbers mean — explained in plain language.",
  },
] as const;

export default function Landing() {
  const signals = loadSignals();
  const nDrugs = new Set(signals.map((s) => s.drug_name)).size;
  const nReports = signals.reduce((sum, s) => sum + s.n_reports, 0);
  const nFlagged = signals.filter((s) => s.flagged).length;
  const refreshDate = signals[0]?.computed_date ?? "—";

  return (
    <div className="min-h-screen bg-bg-page">
      <TopBar refreshDate={refreshDate} />

      <main className="px-6 py-16 max-w-4xl mx-auto">
        {/* Hero */}
        <section className="mb-20 text-center">
          <h1 className="text-4xl sm:text-5xl font-display font-bold tracking-tight text-ink-100 mb-6">
            Drug safety signals,{" "}
            <span className="text-accent">made visible</span>
          </h1>
          <p className="text-lg text-ink-300 max-w-2xl mx-auto mb-10 leading-relaxed">
            Pharos watches for unusual patterns in drug side-effect reports.
            When a medication is linked to a reaction more often than expected,
            the system flags it — giving researchers and the public a clearer
            picture of what the data shows.
          </p>
          <Link
            href="/explore"
            className="inline-flex items-center gap-2 px-6 py-3 rounded-sm bg-accent text-bg-page font-semibold text-base hover:opacity-90 transition-opacity"
          >
            Explore drugs
            <span aria-hidden="true">&rarr;</span>
          </Link>
        </section>

        {/* Stats */}
        <section className="mb-20">
          <div className="grid grid-cols-3 gap-px bg-rule rounded-sm overflow-hidden">
            <div className="bg-bg-surf p-6 text-center">
              <div className="text-3xl font-mono font-semibold text-accent mb-1">
                {nDrugs}
              </div>
              <div className="text-data-xs text-ink-400 uppercase tracking-wide">
                Drugs tracked
              </div>
            </div>
            <div className="bg-bg-surf p-6 text-center">
              <div className="text-3xl font-mono font-semibold text-accent mb-1">
                {nReports.toLocaleString()}
              </div>
              <div className="text-data-xs text-ink-400 uppercase tracking-wide">
                Reports analysed
              </div>
            </div>
            <div className="bg-bg-surf p-6 text-center">
              <div className="text-3xl font-mono font-semibold text-accent mb-1">
                {nFlagged}
              </div>
              <div className="text-data-xs text-ink-400 uppercase tracking-wide">
                Signals flagged
              </div>
            </div>
          </div>
        </section>

        {/* How it works */}
        <section className="mb-20">
          <h2 className="text-data-xs font-mono uppercase tracking-wide text-ink-500 mb-8 text-center">
            How it works
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
            {STEPS.map((step) => (
              <div key={step.number} className="flex flex-col">
                <div className="text-data-xs font-mono text-accent mb-2">
                  {step.number}
                </div>
                <h3 className="text-lg font-display font-semibold text-ink-100 mb-2">
                  {step.title}
                </h3>
                <p className="text-data-sm text-ink-400 leading-relaxed">
                  {step.description}
                </p>
              </div>
            ))}
          </div>
        </section>

        {/* Footer CTA */}
        <section className="text-center border-t border-rule pt-12">
          <p className="text-ink-400 mb-4">
            Updated weekly from FDA FAERS data. Last refresh: {refreshDate}.
          </p>
          <Link
            href="/explore"
            className="text-accent font-medium hover:underline"
          >
            Start exploring &rarr;
          </Link>
        </section>
      </main>
    </div>
  );
}
