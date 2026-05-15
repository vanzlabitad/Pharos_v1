"use client";

export function EvansGlyph({
  n,
  prr,
  chi2,
}: {
  n: number;
  prr: number;
  chi2: number;
}) {
  const checks = [
    { pass: n >= 3, label: "a≥3" },
    { pass: prr >= 2, label: "PRR≥2" },
    { pass: chi2 >= 4, label: "χ²≥4" },
  ];

  return (
    <span className="inline-flex gap-0.5" title={checks.map((c) => `${c.label}: ${c.pass ? "pass" : "fail"}`).join(", ")}>
      {checks.map((c) => (
        <span
          key={c.label}
          className={`inline-block w-2 h-2 rounded-sharp ${
            c.pass ? "bg-accent" : "bg-ink-600"
          }`}
        />
      ))}
    </span>
  );
}
