# Pharos — Project CLAUDE.md (v4)

*Last updated: 2026-05-04*

## 1. Project Identity

**Name:** Pharos
**Type:** Pharma intelligence platform — open-source portfolio project
**Status:** Build in progress — pipeline + analysis layer complete; dashboard pending
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
Gemini API (plain-language summaries, per drug profile)
```

**No R. No dual-language split. One stack, one language.**

---

## 5. Stack (Locked)

| Layer | Tool |
|---|---|
| Language | Python (only) |
| Ingestion | requests, pandas |
| Database | SQLite (Postgres migration triggered when row count > 10M or query p95 > 500 ms) |
| Analysis | Python (scipy, statsmodels) + Quarto (Python engine) |
| Refresh | GitHub Actions cron (weekly) → static JSON |
| Frontend | Next.js + Recharts |
| Deployment | Vercel (free tier) |
| AI summaries | Gemini API (`gemini-2.5-flash` — pinned; can be re-pinned per refresh run) |

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

OpenFDA key is registered and live. NCBI key registration deferred to V2.

---

## 7. Database Schema

Source of truth: [`db/schema.sql`](db/schema.sql). Do not duplicate it here — keep that file canonical.

ER summary:

- `drugs(name UNIQUE)` — canonical drug index.
- `drug_aliases(alias PK) → drugs(name)` — brand → generic lookup, seeded from [`pipeline/drug_aliases.json`](pipeline/drug_aliases.json) at refresh time.
- `adverse_events.drug_name → drugs(name)` — one row per (report, reaction) pair; `report_date` is OpenFDA `receivedate`.
- `signal_scores.drug_name → drugs(name)` with `UNIQUE(drug_name, reaction, computed_date)` — recomputed weekly; `chi_squared` persisted for the Quarto report.
- FK enforcement requires `PRAGMA foreign_keys = ON`, set automatically by `pipeline.db.get_engine`.

V2 adds `trials` and `publications` tables.

---

## 8. Analytical Core — ROR/PRR Disproportionality

The defensible piece. Implementation lives in [`analysis/disproportionality.py`](analysis/disproportionality.py); every claim below maps to a function or test there.

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
95 % CI: SE = √(1/a + 1/b + 1/c + 1/d), bounds = exp(ln(ROR) ± 1.96·SE).

**Proportional Reporting Ratio (PRR):**
```
PRR = (a / (a+b)) / (c / (c+d))
χ²  = N · (ad − bc)² / [(a+b)(c+d)(a+c)(b+d)]    (exact Pearson)
```

### Signal flag

A drug-reaction pair is flagged as a signal when **both** the ROR and PRR
criteria pass:

- **ROR:** lower 95 % CI > 1 (strict inequality) — Rothman 2004.
- **PRR:** PRR ≥ 2 **AND** a ≥ 3 **AND** χ² ≥ 4 (all inclusive, all required) — Evans 2001 (the EVANS criterion).

See `flag_signal` in `analysis/disproportionality.py`.

### Methodology decisions

**Drug-name canonicalisation.** Reports are aggregated under a canonical
generic name resolved by `pipeline.normalise.canonical`, which consults a
curated alias table at [`pipeline/drug_aliases.json`](pipeline/drug_aliases.json)
and falls through to `lower().strip()` for unmapped names. Coverage is
deliberately narrow (≈ 30 common brands → generics). Unmapped brand names
remain a known weakness — RxNorm integration is V2.

**Background denominator.** "All other drugs" is taken globally — every drug
in `adverse_events` other than the target drug, across the full ingested
date range. No stratification by ATC class, indication, or time window is
applied. This is the simplest defensible choice and is documented as a
limitation below; stratified analysis (Bate-style sub-group ROR) is V2.

**Zero-cell handling (Yates).** When any contingency cell is zero, the
default behaviour is to apply Yates' 0.5 continuity correction (Rothman
2004 §15) — 0.5 is added to every cell before computing — and return a
finite estimate. Strict-mode callers pass `continuity_correction=False`
to get `None` instead. `n_reports` always reflects the *observed* `a`, not
the corrected value, so Yates does not promote noise into flagged signals
(the EVANS `a ≥ 3` floor still gates `flag_signal`).

Two cases bypass Yates and always return `None`:
- `a + b == 0` (drug entirely absent from the dataset).
- `c + d == 0` (no comparator drugs).

**Cell-inclusion floor.** `compute_all_signals` skips pairs with observed
`a < min_reports` (default 3) before computing anything — the EVANS-criterion
floor for stable PRR estimation. This is what keeps the signal table finite
on FAERS-scale data: a naïve `n_drugs × n_reactions` matrix is ~10⁸ cells.

### Known limitations (FAERS-specific)

FAERS is a spontaneous-reporting database. Disproportionality on FAERS is
useful for hypothesis generation and is not causal evidence. Signals must
be read with these constraints in mind:

- **Notoriety bias.** Recent media coverage inflates reporting rates; the resulting signal reflects attention, not pharmacology.
- **Indication confounding.** A drug's indication can co-occur with the reaction independent of the drug (e.g. anti-emetic flagged for the cancer it treats).
- **Weber effect.** Reporting peaks 1–2 years after launch and decays — early signals are not directly comparable to late-cycle ones.
- **Masking.** A common drug-event pair can suppress signal detection for related, less-reported pairs in the same comparator pool.
- **Stimulated reporting.** Litigation, regulatory letters, or social-media campaigns spike reports without underlying epidemiological change.
- **No exposure denominator.** FAERS records report counts, not patient-exposure denominators — ROR is *reporting* odds, not incidence.
- **Brand-vs-generic ambiguity.** Mitigated by the alias table but not eliminated; unmapped brands still split signals.

These are reproduced in the Quarto report alongside the signal outputs.

### Key references
- Rothman KJ, Lanes S, Sacks ST. *The reporting odds ratio and its advantages over the proportional reporting ratio.* Pharmacoepidemiol Drug Saf. 2004; 13: 519–523.
- Evans SJW, Waller PC, Davis S. *Use of proportional reporting ratios (PRRs) for signal generation from spontaneous adverse drug reaction reports.* Pharmacoepidemiol Drug Saf. 2001; 10: 483–486.

---

## 9. Feature Scope

### MVP (ship by August 2026)
- [x] OpenFDA adverse event ingestion pipeline — `pipeline/ingest.py`
- [x] SQLite schema (adverse_events, drugs, signal_scores) — `db/schema.sql`
- [x] ROR + PRR computation (documented, tested) — `analysis/disproportionality.py`
- [x] Weekly GitHub Actions cron → static JSON export — `.github/workflows/refresh.yml`, `pipeline/export.py`
- [x] Unit tests for analysis functions (pytest) — 40 tests in `analysis/tests/`
- [ ] Quarto report: methodology + signal outputs (file exists at `analysis/report.qmd`; methodology section to be expanded — see §8)
- [ ] Next.js dashboard (only `dashboard/public/data/*.json` exists; no app scaffold yet):
  - Drug search
  - Adverse event profile view
  - Signal score view (ROR/PRR with CI visualisation)
  - **AI-generated plain-language summaries per drug profile (Gemini API) — see §10**
- [ ] Clean GitHub README with architecture diagram

### V2 (post-August)
- [ ] ClinicalTrials.gov ingestion + trial landscape view
- [ ] PubMed ingestion + literature trend view
- [ ] NLP layer: keyword extraction / topic modelling on abstracts
- [ ] Competitor pipeline analysis (trial overlap by sponsor)
- [ ] Email/alert digest for new safety signals

---

## 10. AI Plain-Language Summaries

### Purpose
Make drug safety signals accessible to users without a scientific background.
Every drug profile page leads with a plain-English summary card; technical
data sits below it.

### Architecture (single path)
Summaries are **generated during the GitHub Actions weekly refresh** and
committed as static JSON alongside the signal data. The frontend reads JSON.
**There is no runtime call to the Gemini API from the browser** — the API
key never leaves the CI environment.

Coverage heuristic: generate a summary for every drug with at least one
flagged signal in the current refresh, capped at 200 drugs per refresh.

### Forbidden patterns (key safety)
The Gemini key is a server-only secret. The following are blocked by the
pre-commit hook (`.githooks/pre-commit`) and the CI secret-scan workflow
(`.github/workflows/secret-scan.yml`):

- `NEXT_PUBLIC_GEMINI*` and `NEXT_PUBLIC_GOOGLE*` — Next.js publishes any
  `NEXT_PUBLIC_*` env var into the browser bundle. Using either prefix on
  the Gemini key would ship it to every user that loads the dashboard.
  Never use them.
- `AIza...` literals anywhere in committed code — Google API keys (Gemini
  included) all start with this prefix. The only places this string may
  appear are docs explaining the rule and the scanner itself.

The scanner also blocks legacy Anthropic patterns (`sk-ant-*`,
`NEXT_PUBLIC_ANTHROPIC*`) as a defensive layer, in case the project ever
experiments with Claude alongside Gemini.

The Gemini SDK (`google-generativeai`) is only ever imported from a Python
module run inside GitHub Actions. The frontend has no Gemini dependency,
no Gemini env var, and no API route that proxies the key. If a future
feature needs more than pre-generated summaries, build a *server-side*
Next.js API route that reads `GEMINI_API_KEY` from the server runtime —
never from the client.

Install the pre-commit hook locally with: `git config core.hooksPath .githooks`.

**Example prompt (sent to Gemini API at refresh time):**
```
You are a plain-language medical writer. Given the following drug safety
signal data, write a 2-3 sentence summary a non-scientist can understand.

Constraints:
- Do not give medical advice, dosage recommendations, or guidance on
  whether to take or avoid the drug.
- Describe the statistical signal only — what it measures and what it
  does and does not tell us.
- Do not use jargon (or define it briefly when unavoidable).

Drug: Ibuprofen
Top reaction: GI bleeding
ROR: 4.2 (95% CI: 3.8–4.6)
n_reports: 1,204
Signal flagged: Yes

Output only the summary. No preamble.
```

**Example output:**
> "In this database, reports involving ibuprofen mention stomach bleeding
> about four times more often than reports involving other drugs. A signal
> like this flags a pattern worth investigating; it does not by itself
> prove the drug is the cause."

### Placement in dashboard
- **Drug profile page:** summary card at top, full technical data below.
- **Signal score view:** plain-language flag explanation alongside ROR CI chart.

### Technical notes
- Model: `gemini-2.5-flash` (pinned; re-pin at refresh time when upgrading).
- Generated at refresh time only; cached in `dashboard/public/data/summaries.json`.
- UI label on every summary card: *"AI-generated summary — for reference only, not medical advice."*

---

## 11. Refresh Strategy

**Weekly snapshot via GitHub Actions.**

```yaml
# .github/workflows/refresh.yml
- cron: '0 6 * * 1'   # Every Monday 06:00 UTC
```

Pipeline:
1. Fetch latest OpenFDA data (with retry on 429; raises after 3 attempts)
2. Update SQLite
3. Recompute ROR/PRR scores
4. Export static JSON to `/dashboard/public/data/`
5. Pre-generate AI summaries for every drug with ≥1 flagged signal (cap 200/refresh) → cache in `dashboard/public/data/summaries.json`
6. Commit + push → Vercel auto-deploys

Failure mode: any uncaught exception exits the GitHub Actions workflow non-zero and emails the repo owner. Do not catch errors silently in the refresh path — better a loud failure than a quiet stale dashboard.

The dashboard shows a weekly snapshot, not live data. Say so clearly in the README and UI footer.

---

## 12. File Structure

```
pharos/
├── pipeline/                       # Python ETL
│   ├── ingest.py                   # OpenFDA fetcher (with 429 retry)
│   ├── clean.py                    # Normalisation + deduplication
│   ├── normalise.py                # canonical(drug_name) — alias lookup
│   ├── drug_aliases.json           # Brand → generic seed data
│   ├── db.py                       # SQLite interface (SQLAlchemy)
│   ├── export.py                   # Static JSON exports
│   ├── run_refresh.py              # Weekly orchestration entrypoint
│   └── tests/                      # pytest unit tests
├── analysis/
│   ├── disproportionality.py       # ROR/PRR computation
│   ├── report.qmd                  # Quarto report (source)
│   └── tests/                      # pytest unit + live tests
├── db/
│   ├── schema.sql                  # Source of truth (see §7)
│   └── pharos.db                   # gitignored
├── dashboard/                      # Next.js frontend (scaffold pending)
│   └── public/data/                # Static JSON, committed weekly
├── .github/workflows/
│   └── refresh.yml
├── docs/                           # Long-form docs (career, methodology)
└── README.md                       # pending — see §9
```

---

## 13. Timeline

| Milestone | Status |
|---|---|
| Repo, schema, OpenFDA pipeline, ROR/PRR + Quarto, weekly cron + JSON export, unit tests | ✅ Completed May 2026 |
| Methodology hardening (drug normalisation, Yates, min_reports, FAERS limitations) | June 2026 |
| Frontend MVP deployed (Vercel) | June 2026 |
| AI summaries integrated (Gemini API, pre-generated at refresh) | July 2026 |
| README + architecture diagram | July 2026 |
| Portfolio-ready (CV + LinkedIn) | August 2026 |

---

## 14. Career Positioning

Recruiter-facing copy (CV framing, LinkedIn entry, signal table) lives in [`docs/career.md`](docs/career.md). Kept out of CLAUDE.md so this file stays focused on agent behaviour rules.

---

## 15. Working Conventions

- **Language:** Python only. No R.
- **Analysis output format:** Quarto (.qmd) with Python engine
- **Commit style:** conventional commits (`feat:`, `fix:`, `analysis:`, `docs:`)
- **One feature per commit**
- **No premature optimisation:** trust the §5 migration trigger — don't move to Postgres before it fires.
- **Analysis before visuals:** working ROR/PRR output before touching the dashboard.
- **Error handling:** pipeline must handle OpenFDA 404s, timeouts, and 429s gracefully (retry with backoff, then raise — see §16).
- **AI summaries:** generated at refresh time only; never called from the browser (see §10).

---

## 16. Risk Register

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| OpenFDA schema drift | Med | Med | Live integration tests in `analysis/tests/test_live.py`; weekly cron failure surfaces drift loudly. |
| OpenFDA 429 rate-limit | Low | Med | Exponential-backoff retry in `pipeline.ingest._fetch_page` (1s → 2s → 4s, then raise). |
| `signals.json` size growth | Med | Med | EVANS floor (`min_reports = 3`) bounds row count; rotate to blob storage if file > 5 MB. |
| Vercel deploy size cap | Low | High | Same trigger as JSON growth. Hard cap on free tier ~100 MB. |
| Gemini API monthly cost | Low | Low | Capped at ~200 summaries / refresh (§10). Free tier currently covers full weekly load; one-time cost per refresh if it ever exceeds. |
| FAERS quarterly data lag | Cert. | Low | Dashboard footer states "data current to [latest receivedate]". |
| Drug normalisation gaps | High | Med | Curated alias table in `pipeline/drug_aliases.json`; coverage tracked. RxNorm in V2. |
| Background-denominator bias | Cert. | Med | Documented in §8 limitations; stratified analysis is V2. |

---

## 17. Quarto Report Distribution

The Quarto report at [`analysis/report.qmd`](analysis/report.qmd) is the human-readable methodology + signal-output document. It must reach a recruiter without them cloning the repo.

- Rendered to `analysis/report.html` on each refresh by the GitHub Actions workflow.
- Copied to `dashboard/public/report.html` so Vercel serves it at `/report.html`.
- Linked from the dashboard footer ("Methodology and limitations").
- Source `.qmd` is committed; rendered `.html` is gitignored at the source path but committed at the dashboard path (regenerated weekly).

---

## 18. Related Projects

| Project | Relationship |
|---|---|
| Synk (fmr. Conflictly) | Shares signal-monitoring architecture pattern |
| REVE | Potential future data consumer |
| FAERS pipeline | Predecessor — Pharos extends and formalises this work |
| Dissertation | Domain credibility context |

---

## 19. Open Questions (resolved)

| Question | Decision |
|---|---|
| Target audience | Computational biotech + general public |
| Frontend | Next.js + Recharts |
| Hosting | Vercel (free tier; trigger in §5 for migration) |
| Refresh strategy | Weekly GitHub Actions → static JSON |
| NLP in MVP | No — V2 only |
| ClinicalTrials / PubMed in MVP | No — V2 only |
| Plain-language summaries | Yes — Gemini API, generated at refresh time (see §10) |
