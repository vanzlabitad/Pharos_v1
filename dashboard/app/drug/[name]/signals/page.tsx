import fs from "fs";
import path from "path";
import type { Signal } from "@/lib/types";
import { SignalScoresClient } from "@/components/pages/signal-scores-client";

function loadSignals(): Signal[] {
  const raw = fs.readFileSync(
    path.join(process.cwd(), "public/data/signals.json"),
    "utf-8"
  );
  return JSON.parse(raw);
}

export function generateStaticParams() {
  const signals = loadSignals();
  const drugs = [...new Set(signals.map((s) => s.drug_name))];
  return drugs.map((name) => ({ name }));
}

export default async function SignalScoresPage({
  params,
}: {
  params: Promise<{ name: string }>;
}) {
  const { name } = await params;
  const drugName = decodeURIComponent(name);
  const allSignals = loadSignals();
  const drugSignals = allSignals.filter((s) => s.drug_name === drugName);

  return <SignalScoresClient drugName={drugName} drugSignals={drugSignals} />;
}
