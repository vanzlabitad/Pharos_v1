export type Signal = {
  id: number;
  drug_name: string;
  reaction: string;
  ror: number;
  ror_lower: number;
  ror_upper: number;
  prr: number;
  chi_squared: number;
  n_reports: number;
  computed_date: string;
  flagged: boolean;
};

export type DrugMeta = {
  drug_class: string;
  atc_code: string;
  aliases: string[];
};

export type AdverseEvent = {
  id: number;
  drug_name: string;
  reaction: string;
  outcome: string;
  report_date: string;
  serious: number;
  source: string;
};

export type DrugSummary = {
  overall: string;
  reactions: Record<string, string>;
};
