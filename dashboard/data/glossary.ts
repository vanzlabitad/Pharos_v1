export const GLOSSARY: Record<string, string> = {
  ROR: "Reporting Odds Ratio — how much more often a drug-reaction pair is reported compared to all other drugs. ROR > 1 means over-reported.",
  PRR: "Proportional Reporting Ratio — the proportion of a drug's reports mentioning a reaction, divided by the same proportion for all other drugs.",
  CI: "95% Confidence Interval — the range within which the true value is expected to fall 95% of the time. Narrower = more certain.",
  EVANS: "Evans criterion (Evans 2001): a signal is flagged when PRR ≥ 2, n ≥ 3, and χ² ≥ 4. All three must pass.",
  "chi-squared": "χ² (chi-squared) — a measure of how unlikely the observed drug-reaction association is under the null hypothesis of no association.",
  n: "Number of reports where the drug and reaction co-occur in the database.",
  flagged: "A signal is flagged when BOTH the ROR lower 95% CI > 1 (Rothman) AND the Evans criterion passes (PRR ≥ 2, n ≥ 3, χ² ≥ 4).",
  FAERS: "FDA Adverse Event Reporting System — a spontaneous-reporting database. Signals indicate reporting patterns, not causal evidence.",
  "ror-lower": "Lower bound of the 95% CI for the ROR. When this exceeds 1, the signal passes the Rothman criterion.",
};
