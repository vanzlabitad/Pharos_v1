-- Pharos database schema
-- Foreign-key enforcement requires `PRAGMA foreign_keys = ON;` per
-- connection; pipeline.db.get_engine sets this automatically.

-- Drug index. drug_name in adverse_events and signal_scores references
-- drugs(name); pipeline.clean.clean_adverse_events inserts canonical names
-- here on first observation.
CREATE TABLE IF NOT EXISTS drugs (
  drug_id    INTEGER PRIMARY KEY,
  name       TEXT    NOT NULL UNIQUE,
  drug_class TEXT,
  atc_code   TEXT
);

-- Brand → canonical name lookup. Seeded from pipeline/drug_aliases.json by
-- pipeline.db.seed_drug_aliases at refresh time.
CREATE TABLE IF NOT EXISTS drug_aliases (
  alias          TEXT PRIMARY KEY,
  canonical_name TEXT NOT NULL,
  FOREIGN KEY (canonical_name) REFERENCES drugs(name)
);

-- Adverse events ingested from OpenFDA FAERS.
-- drug_name is the canonical generic from pipeline.normalise.canonical.
-- report_date is OpenFDA receivedate, parsed to ISO date by pipeline.clean.
CREATE TABLE IF NOT EXISTS adverse_events (
  id          INTEGER PRIMARY KEY,
  drug_name   TEXT    NOT NULL,
  reaction    TEXT    NOT NULL,
  outcome     TEXT,
  report_date DATE,
  serious     INTEGER,   -- 1 = serious, 0 = not serious
  source      TEXT,
  FOREIGN KEY (drug_name) REFERENCES drugs(name)
);

CREATE INDEX IF NOT EXISTS idx_ae_drug     ON adverse_events(drug_name);
CREATE INDEX IF NOT EXISTS idx_ae_reaction ON adverse_events(reaction);

-- ROR/PRR signal scores — recomputed weekly by analysis layer.
-- UNIQUE prevents duplicate rows on rerun.
CREATE TABLE IF NOT EXISTS signal_scores (
  id            INTEGER PRIMARY KEY,
  drug_name     TEXT    NOT NULL,
  reaction      TEXT    NOT NULL,
  ror           REAL,
  ror_lower     REAL,   -- 95% CI lower bound
  ror_upper     REAL,   -- 95% CI upper bound
  prr           REAL,
  chi_squared   REAL,
  n_reports     INTEGER,
  computed_date DATE,
  UNIQUE (drug_name, reaction, computed_date),
  FOREIGN KEY (drug_name) REFERENCES drugs(name)
);

CREATE INDEX IF NOT EXISTS idx_ss_drug ON signal_scores(drug_name);
