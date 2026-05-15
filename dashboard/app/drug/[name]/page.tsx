import fs from "fs";
import path from "path";

type Signal = { drug_name: string };

export function generateStaticParams() {
  const raw = fs.readFileSync(
    path.join(process.cwd(), "public/data/signals.json"),
    "utf-8"
  );
  const signals: Signal[] = JSON.parse(raw);
  const drugs = [...new Set(signals.map((s) => s.drug_name))];
  return drugs.map((name) => ({ name }));
}

export default async function DrugProfile({
  params,
}: {
  params: Promise<{ name: string }>;
}) {
  const { name } = await params;
  return (
    <main className="min-h-screen bg-bg-page p-8">
      <h1 className="text-data-2xl font-display font-semibold text-ink-100">
        {decodeURIComponent(name)}
      </h1>
      <p className="mt-2 text-ink-400">Drug profile — redesign pending.</p>
    </main>
  );
}
