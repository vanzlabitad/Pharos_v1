export function MethodFootnote() {
  return (
    <footer className="mt-8 pt-4 border-t border-hair text-data-xs text-ink-500 max-w-3xl space-y-1">
      <p>
        Disproportionality computed via ROR + PRR on FDA FAERS spontaneous
        reports. Signal = ROR lower 95% CI &gt; 1 (Rothman 2004) AND PRR
        &ge; 2, n &ge; 3, &chi;&sup2; &ge; 4 (Evans 2001).
      </p>
      <p>
        FAERS data reflects reporting patterns, not causal evidence.
        Notoriety bias, indication confounding, and the Weber effect may
        inflate or suppress signals.
      </p>
    </footer>
  );
}
