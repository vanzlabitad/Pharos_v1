-- Pharos database schema
-- Adverse events ingested from OpenFDA FAERS
CREATE TABLE IF NOT EXISTS adverse_events (
  id          INTEGER PRIMARY KEY,
  drug_name   TEXT    NOT NULL,
  reaction    TEXT    NOT NULL,
  outcome     TEXT,
  report_date DATE,
  serious     INTEGER,   -- 1 = serious, 0 = not serious
  source      TEXT
);

-- drug_name is the primary query key in every lookup
CREATE INDEX IF NOT EXISTS idx_ae_drug ON adverse_events(drug_name);

-- Drug index (populated separately; not used by ingestion pipeline)
CREATE TABLE IF NOT EXISTS drugs (
  drug_id    INTEGER PRIMARY KEY,
  name       TEXT,
  synonym    TEXT,
  drug_class TEXT,
  atc_code   TEXT
);

-- ROR/PRR signal scores — recomputed weekly by analysis layer
CREATE TABLE IF NOT EXISTS signal_scores (
  id            INTEGER PRIMARY KEY,
  drug_name     TEXT,
  reaction      TEXT,
  ror           REAL,
  ror_lower     REAL,   -- 95% CI lower bound
  ror_upper     REAL,   -- 95% CI upper bound
  prr           REAL,
  n_reports     INTEGER,
  computed_date DATE
);

CREATE INDEX IF NOT EXISTS idx_ss_drug ON signal_scores(drug_name);
