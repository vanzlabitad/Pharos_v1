# Pharos — Project CLAUDE.md (v3)

## 1. Project Identity

**Name:** Pharos
**Type:** Pharma intelligence platform — open-source portfolio project
**Status:** Pre-build (start: ~May/June 2026)
**Portfolio-ready deadline:** August 2026
**Owner:** Vanz

### One-line pitch
A pharmacovigilance signal-detection platform that ingests adverse event
data from OpenFDA, computes disproportionality statistics (ROR/PRR), and
visualises drug safety signals — built to demonstrate computational and
analytical fluency to biotech employers.

---

## 2. Goals

### Primary
- Portfolio anchor for autumn 2026 graduate applications
- Targets computational biotech roles (Recursion, Exscientia, LabGenius, etc.)
- Demonstrates: data engineering + reproducible analysis + clean deployment

### Secondary
- Genuinely useful safety-signal tool
- Accessible to non-scientific audiences via plain-language AI summaries
- Reusable architecture for future projects (REVE data layer, Synk signal
  monitoring)

---

## 3. Target Audience

**Computational biotech** (Recursion, Exscientia, LabGenius, etc.)

What they need to see:
- Pipeline architecture and reproducibility
- Documented analytical methodology (not just a dashboard)
- Clean, readable Python code
- Evidence you understand the domain (pharmacovigilance, signal detection)
- GitHub depth: tests, CI, clear commit history, good docs

**General public / non-scientific users**
- Plain-language summaries on every drug profile page
- No assumed background — signals are explained, not just displayed

---

## 4. Architecture

### Single path — Python end-to-end

```
OpenFDA API
    ↓
Python ingestion pipeline (requests, pandas)
    ↓
SQLite database
    ↓
Weekly GitHub Actions cron → static JSON export
    ↓
Vercel (Next.js dashboard + Recharts)
         ↓
Claude API (plain-language summaries, per drug profile)
```

**No R. No dual-language split. One stack, one language.**

---

## 5. Stack (Locked)

| Layer | Tool |
|---|---|
| Language | Python (only) |
| Ingestion | requests, pandas |
| Database | SQLite (→ Postgres in V2 if scale demands) |
| Analysis | Python (scipy, statsmodels) + Quarto (Python engine) |
| Refresh | GitHub Actions cron (weekly) → static JSON |
| Frontend | Next.js + Recharts |
| Deployment | Vercel (free tier) |
| AI summaries | Claude API (claude-sonnet-4-20250514) |

---

## 6. Data Sources

### MVP
| Source | API | Data Type | Auth |
|---|---|---|---|
| OpenFDA | api.fda.gov | Adverse events, drug labels, recalls | Free key (120k req/day) |

### V2 (post-August)
| Source | API | Data Type | Auth |
|---|---|---|---|
| ClinicalTrials.gov | clinicaltrials.gov/api/v2 | Trial metadata, phases, sponsors | None required |
| PubMed / NCBI | eutils.ncbi.nlm.nih.gov | Literature, abstracts, MeSH terms | Free key (10 req/s) |

**Register all API keys before build start — OpenFDA and NCBI are free, 5
minutes each. ClinicalTrials requires no key.**

---

## 7. Database Schema

```sql
-- Adverse events (from OpenFDA)
CREATE TABLE adverse_events (
  id INTEGER PRIMARY KEY,
  drug_name TEXT,
  reaction TEXT,
  outcome TEXT,
  report_date DATE,
  serious INTEGER,   -- 1/0
  source TEXT
);

-- Drug index
CREATE TABLE drugs (
  drug_id INTEGER PRIMARY KEY,
  name TEXT,
  synonym TEXT,
  drug_class TEXT,
  atc_code TEXT
);

-- Signal scores (computed, refreshed weekly)
CREATE TABLE signal_scores (
  id INTEGER PRIMARY KEY,
  drug_name TEXT,
  reaction TEXT,
  ror REAL,          -- Reporting Odds Ratio
  ror_lower REAL,    -- 95% CI lower
  ror_upper REAL,    -- 95% CI upper
  prr REAL,          -- Proportional Reporting Ratio
  n_reports INTEGER,
  computed_date DATE
);
```

V2 adds `trials` and `publications` tables.

---

## 8. Analytical Core — ROR/PRR Disproportionality

This is the defensible piece. Build it properly.

### Method
Disproportionality analysis detects whether a drug-reaction pair is reported
more than expected given the background reporting rate.

**Reporting Odds Ratio (ROR):**
```
ROR = (a/b) / (c/d)

Where:
  a = reports of drug X WITH reaction Y
  b = reports of drug X WITHOUT reaction Y
  c = reports of all other drugs WITH reaction Y
  d = reports of all other drugs WITHOUT reaction Y
```

Signal threshold: ROR lower 95% CI > 1

**Proportional Reporting Ratio (PRR):**
```
PRR = (a / (a+b)) / (c / (c+d))
```

Signal threshold: PRR ≥ 2, n ≥ 3, χ² ≥ 4

### Output
- Signal score table (drug × reaction matrix)
- Flagged signals with confidence intervals
- Quarto report: methodology, assumptions, limitations documented

### Key reference
Rothman et al. (2004) — read before writing any analysis code.

---

## 9. Feature Scope

### MVP (ship by August 2026)
- [ ] OpenFDA adverse event ingestion pipeline
- [ ] SQLite schema (adverse_events, drugs, signal_scores)
- [ ] ROR + PRR computation (documented, tested)
- [ ] Weekly GitHub Actions cron → static JSON export
- [ ] Quarto report: methodology + signal outputs
- [ ] Next.js dashboard:
  - Drug search
  - Adverse event profile view
  - Signal score view (ROR/PRR with CI visualisation)
  - **AI-generated plain-language summaries per drug profile (Claude API)**
- [ ] Clean GitHub README with architecture diagram
- [ ] Unit tests for analysis functions (pytest)

### V2 (post-August)
- [ ] ClinicalTrials.gov ingestion + trial landscape view
- [ ] PubMed ingestion + literature trend view
- [ ] NLP layer: keyword extraction / topic modelling on abstracts
- [ ] Competitor pipeline analysis (trial overlap by sponsor)
- [ ] PostgreSQL migration
- [ ] Email/alert digest for new safety signals

---

## 10. AI Plain-Language Summaries

### Purpose
Make drug safety signals accessible to users without a scientific background.
Every drug profile page leads with a plain-English summary card; technical
data sits below it.

### Implementation
On drug profile page load, the frontend calls the Claude API with the drug's
ROR/PRR data and returns a 2–3 sentence plain-language summary.

**Example prompt (sent to Claude API):**
```
You are a plain-language medical writer. Given the following drug safety
signal data, write a 2-3 sentence summary a non-scientist can understand.
Do not use jargon. Be accurate but accessible.

Drug: Ibuprofen
Top reaction: GI bleeding
ROR: 4.2 (95% CI: 3.8–4.6)
n_reports: 1,204
Signal flagged: Yes

Output only the summary. No preamble.
```

**Example output:**
> "Ibuprofen shows a stronger-than-expected link to stomach bleeding in
> this database. It appeared alongside bleeding reports about 4× more often
> than other drugs. This is a known risk — ibuprofen is generally safe when
> taken as directed, but always take it with food and follow dosage
> instructions."

### Placement in dashboard
- **Drug profile page:** summary card at top, full technical data below
- **Signal score view:** plain-language flag explanation alongside ROR CI chart

### Technical notes
- Model: `claude-sonnet-4-20250514`
- Called client-side on page load (or cached at build time for known drugs)
- Caching recommended: store generated summaries in static JSON at refresh
  time to avoid per-request API cost
- Add UI label: *"AI-generated summary — for reference only, not medical
  advice"*

---

## 11. Refresh Strategy

**Weekly snapshot via GitHub Actions.**

```yaml
# .github/workflows/refresh.yml
- cron: '0 6 * * 1'   # Every Monday 06:00 UTC
```

Pipeline:
1. Fetch latest OpenFDA data
2. Update SQLite
3. Recompute ROR/PRR scores
4. Export static JSON to `/dashboard/public/data/`
5. (Optional) Pre-generate AI summaries for top N drugs → cache in JSON
6. Commit + push → Vercel auto-deploys

This is honest. The dashboard shows a weekly snapshot, not live data.
Say so clearly in the README and UI footer.

---

## 12. File Structure

```
pharos/
├── pipeline/           # Python ETL scripts
│   ├── ingest.py       # OpenFDA fetcher
│   ├── clean.py        # Normalisation + deduplication
│   └── db.py           # SQLite interface (SQLAlchemy)
├── analysis/           # Signal detection
│   ├── disproportionality.py   # ROR/PRR computation
│   ├── report.qmd               # Quarto report
│   └── tests/                   # pytest unit tests
├── db/
│   ├── schema.sql
│   └── pharos.db       # gitignored
├── dashboard/          # Next.js frontend
│   ├── public/data/    # Static JSON (committed weekly)
│   ├── components/
│   │   ├── DrugProfile.jsx      # Includes AI summary card
│   │   └── SignalChart.jsx
│   └── pages/
├── .github/workflows/
│   └── refresh.yml
├── data/               # Cached/sample data (gitignored if large)
├── docs/               # Architecture diagram, API notes, methods
└── README.md
```

---

## 13. Timeline

| Milestone | Target |
|---|---|
| Repo initialised + schema live | End of May 2026 |
| OpenFDA pipeline working | Mid-June 2026 |
| ROR/PRR analysis + Quarto report | End of June 2026 |
| GitHub Actions cron + JSON export | Early July 2026 |
| Frontend MVP deployed (Vercel) | Mid-July 2026 |
| AI summaries integrated (Claude API) | Mid-July 2026 |
| Tests + README + architecture diagram | End of July 2026 |
| Portfolio-ready (CV + LinkedIn) | August 2026 |

---

## 14. Career Positioning

### What Pharos signals to computational biotech recruiters

| Signal | How demonstrated |
|---|---|
| Domain knowledge | Pharmacovigilance, signal detection, FAERS data |
| Data engineering | ETL pipeline, API integration, SQL schema |
| Analytical rigour | ROR/PRR with CI, documented assumptions, reproducible |
| Software quality | Tests (pytest), CI (GitHub Actions), clean commits |
| Deployment | Live demo, Vercel, automated refresh |
| Product thinking | AI summaries for non-scientific users — built for an audience |
| Open science | Public repo, documented methodology, reproducible report |

### CV framing
> "Built Pharos — an open-source pharmacovigilance platform detecting
> adverse drug reaction signals from OpenFDA data using disproportionality
> analysis (ROR/PRR). Includes an ETL pipeline (Python/SQLite), reproducible
> analysis layer (Quarto), interactive dashboard (Next.js), and AI-generated
> plain-language summaries via Claude API. Deployed live with weekly
> automated refresh via GitHub Actions."

### LinkedIn project entry
- Title: Pharos — Pharmacovigilance Signal Detection Platform
- Link: GitHub repo + live demo
- Key skills: Python, SQL, REST APIs, Statistical Analysis, React/Next.js,
  GitHub Actions, Claude API

---

## 15. Working Conventions

- **Language:** Python only. No R.
- **Analysis output format:** Quarto (.qmd) with Python engine
- **Commit style:** conventional commits (`feat:`, `fix:`, `analysis:`, `docs:`)
- **One feature per commit**
- **No premature optimisation:** SQLite until scale actually demands Postgres
- **Analysis before visuals:** working ROR/PRR output before touching the dashboard
- **Tests for analysis functions:** at minimum, test ROR/PRR computation against
  known values before shipping
- **Error handling:** pipeline must handle OpenFDA 404s, timeouts, and partial
  results gracefully — log failures, don't crash silently
- **AI summaries:** cache at refresh time, never call Claude API on every page
  load in production

---

## 16. Related Projects

| Project | Relationship |
|---|---|
| Synk (fmr. Conflictly) | Shares signal-monitoring architecture pattern |
| REVE | Potential future data consumer |
| FAERS pipeline | Predecessor — Pharos extends and formalises this work |
| Dissertation | Domain credibility context |

---

## 17. Open Questions (resolved)

| Question | Decision |
|---|---|
| Name | Pharos |
| Target audience | Computational biotech + general public |
| Language | Python only |
| R vs Python analysis | Python + Quarto (Python engine) |
| Frontend | Next.js + Recharts |
| Hosting | Vercel |
| Refresh strategy | Weekly GitHub Actions → static JSON |
| DrugBank | No — registration friction, licensing risk |
| NLP in MVP | No — V2 only |
| ClinicalTrials / PubMed in MVP | No — V2 only (register keys now) |
| Plain-language summaries | Yes — Claude API, cached at refresh time |
