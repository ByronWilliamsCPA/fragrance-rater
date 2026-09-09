# Architecture Review: Toward a Preference-Fingerprint Fragrance System

> **Status**: Proposal — not yet agreed or implemented
> **Purpose**: Compare the current application against the target "preference fingerprint /
> active-learning" product described by the project owner, and propose a normalized data
> model and staged roadmap.
> **Created**: 2026-09-09
> **Supersedes (pending agreement)**: The data model in [concept.md](../../concept.md),
> [tech-spec.md](tech-spec.md) §"Data Model", and [ADR-004](adr/adr-004-recommendation-algorithm.md).
> Infrastructure decisions in [ADR-001](adr/adr-001-initial-architecture.md) and
> [ADR-002](adr/adr-002-data-source-strategy.md) are **not** challenged by this review.

This document does not change any code or schema. It is the discussion artifact requested
before any structural work begins.

---

## 1. Current-State Assessment

### 1.1 What actually exists today (the running application)

This is the most important finding of the review: **there is effectively no fragrance
domain implementation yet**, despite the amount of planning documentation in the repo.

| Layer | State |
|---|---|
| Database | **None.** No SQLAlchemy models, no Alembic migrations, no DB driver in `pyproject.toml`. `docker-compose.yml` already provisions a Postgres service and a `DATABASE_URL`, but nothing in `src/` connects to it. |
| Fragrance catalog | `src/fragrance_rater/api/fragrances.py` returns a **hardcoded, in-memory list of 3 fragrances** (Aventus, Sauvage, Bleu de Chanel). Its own docstring says this exists "to give the OpenAPI document a realistic, tagged resource," not as real inventory. |
| Evaluators / Reviewers | **Not modeled at all.** No `Evaluator`/`Reviewer` entity, no way to attribute anything to Byron, Ariannah, Bayden, or Veronica. |
| Ratings / Evaluations | **Not persisted.** The only rating-shaped feature is `POST /ratings`, which sends a free-text description to an LLM (OpenRouter, `anthropic/claude-3.5-sonnet`) and returns a 1–10 score + reasoning **synchronously, with nothing written to storage**. |
| Blind testing, sessions, notes ontology, calibration/canonical roles, physical items/formulations, historical preferences | **None exist.** |
| Frontend | `frontend/src/App.tsx` is the **unmodified Vite + React template** (counter button, "Backend API Status" health check). No evaluation UI, no fragrance UI of any kind. |

So today's "app" is a cookiecutter-generated FastAPI/React skeleton plus one demo endpoint
that asks an LLM to *guess* whether a fragrance description sounds appealing. It does not yet
do any of the three things stated in the product objective (learn preferences, build
vocabulary, or recommend).

**Practical implication**: there is no real evaluation or rating data sitting in a database
anywhere. The "preserve existing data" concern in the original ask is much smaller than it
would be for a mature app — see §4 (Migration Implications).

### 1.2 What the planning documents propose (never built)

`concept.md` (Dec 2024) and the generated `docs/planning/*` (tech-spec, ADRs, roadmap,
PROJECT-PLAN, and the illustrative `docs/planning/backend/` FastAPI scaffold) describe a
**different, simpler system** than the one now being targeted:

- One `Fragrance` table carrying `primary_family` / `subfamily` / `intensity` as enums
  (Michael Edwards Fragrance Wheel: 4 families, 14 subfamilies).
- `Note` and `Accord` as normalized many-to-many tables — this part **is** compatible with
  the new target and is worth keeping.
- `Reviewer` + `Evaluation` with a single 1–5 star rating, free-text notes, optional
  longevity/sillage — one evaluation conceptually representing "how Reviewer X feels about
  Fragrance Y," with no blind/reveal distinction, no repeated-test model, no sessions.
- A single weighted-affinity scoring formula (`ADR-004`) producing one 0–1 "match score,"
  with an LLM (`ADR-003`, OpenRouter) bolted on afterward purely to generate a prose
  explanation of that already-computed score.
- No concept of fragrance *version* (EDT vs EDP vs reformulation), no physical items, no
  calibration/canonical/exploratory classification, no perceived-notes-vs-published-notes
  separation, no information-value/active-learning axis.

This plan was never implemented (the `docs/planning/backend/` scaffold itself is
incomplete — `database.py` imports `app.models`, which doesn't exist anywhere in the repo).
So it isn't "legacy code to migrate off of" — it's a **design that should be treated as
superseded**, not extended. Below, §5 explains exactly which parts survive and which don't.

### 1.3 What's already good and should be kept as-is

- **Infrastructure decisions** (ADR-001: Docker Compose monolith with Postgres; ADR-002:
  tiered data acquisition — Kaggle → manual → paid API). These are sound regardless of the
  data model that sits on top of them.
- **SQLAlchemy 2.0 + Alembic** as the intended ORM/migration toolchain (declared in
  tech-spec.md, not yet wired up) — appropriate for the normalized schema below.
- The project's existing **exception hierarchy, structured logging, correlation
  middleware, and CLI scaffolding** in `src/fragrance_rater/` — generic infrastructure that
  the fragrance domain code will sit on top of without modification.
- The **general shape** of `Note`/`FragranceNote` and `Accord`/`FragranceAccord` as
  many-to-many junction tables — the target model keeps this pattern, just adds
  provenance/position/confidence fields and points the FK at `FragranceVersion` instead of
  a flat `Fragrance`.
- `TEST_MODE` seam in the LLM client — worth reusing for any future LLM-backed explanation
  feature.

### 1.4 Architectural limitations / technical debt relative to the target

1. **No persistence layer at all** — has to be built from zero; not a migration problem, an
   initial-build problem.
2. **One-giant-Fragrance-table design** in the planning docs — collapses house, product
   identity, formulation/concentration, and physical inventory into one row. Directly
   contradicts target §5's requirement to distinguish House / Fragrance / FragranceVersion /
   PhysicalItem (e.g., Byron's 2006–2016 Armani Code bottle vs. a current bottle).
2. **Family/subfamily enums instead of feature vectors** — a fragrance can only belong to
   one primary family and one subfamily. The target (§3, §14) wants overlapping,
   multi-dimensional coverage (a fragrance can be woody *and* smoky *and* leather at once),
   which enums can't represent but a `Note`/`Accord` many-to-many model can.
3. **Single rating field, no blind/reveal split** — `Evaluation.rating` is one integer with
   no notion of "recorded before the evaluator knew what it was." This is disqualifying for
   the blind-testing workflow in target §7, which is central to the product's credibility.
4. **No repeated-evaluation or physical-item model** — nothing distinguishes "the same
   conceptual fragrance, tested twice from two different sample sources" (the RDZ Leyenda 21
   reliability experiment in target §12 requires this) or accounts for format effects (oil vs.
   spray, target §13).
5. **Single score, no interpretability structure** — `ADR-004`'s formula returns one
   number; the LLM is used only to narrate it after the fact. The target's Predicted-Liking
   vs. Information-Value split (§15) and "explain via feature attribution" requirement (§14)
   need the score computation itself to be structured around named features (specific
   notes/accords with signed weights), not a black box the LLM narrates.
6. **The live `/ratings` endpoint solves a different problem than the target system.** It
   asks an LLM to *estimate* whether a fragrance sounds appealing from a text description —
   there is no evaluator, no persistence, and no relationship to anything a human actually
   smelled. This is not a small variant of the target's "recommendation explanation"
   feature; it's answering "would an AI like this," not "record what a person perceived."
   It should not be extended into the evaluation-capture system — see §6.

---

## 2. Target Architecture at a Glance

Mapping the request's 27 numbered concerns onto data-model concerns, the target needs:

- **Identity layer**: `House → Fragrance → FragranceVersion → PhysicalItem` (§5).
- **Vocabulary layer**: `Note`, `Accord`, each with a join table to `FragranceVersion`
  carrying position/strength + **provenance** (published vs. inferred vs. personally
  perceived) (§6, §10, §20).
- **Classification layer**: non-exclusive roles (`calibration`, `canonical`, `exploratory`)
  attached to a `FragranceVersion`, plus a controlled vocabulary of "coverage dimensions"
  (citrus, vetiver, animalic, …) so the Calibration 30's coverage can be reasoned about
  explicitly (§2, §3, §4, §23).
- **People layer**: a generic `Evaluator`/`Person` entity — no hardcoded family members
  (§1).
- **Evaluation-capture layer**: `EvaluationSession` → `Evaluation` (blind vs. post-reveal,
  screening vs. wear, one-to-many wear checkpoints), plus a parallel `HistoricalPreference`
  table for pre-existing, non-controlled knowledge (§7, §8, §9, §11, §12, §13).
- **Perception layer**: `PerceivedNote` — raw free text plus an optional, non-destructive
  mapping to canonical `Note`s (§10).
- **Modeling layer** (schema placeholders only until Phase 3–5): preference fingerprints,
  two independent recommendation scores, evaluator-similarity, model/version metadata for
  reproducibility (§14–§21).

The rest of this document details each layer, then sequences the work.

---

## 3. Proposed Normalized Data Model

This is a conceptual model (entities, fields, relationships) — not final SQLAlchemy code.
Field lists are illustrative, not exhaustive; exact types get pinned down during
implementation.

### 3.1 Identity & Inventory

```
HOUSE
  id, name, aliases[], country (nullable)

FRAGRANCE                          (conceptual product identity)
  id, house_id → HOUSE, name, aliases[]
  first_release_year (nullable)
  external_ids (e.g., Fragrantica slug) — provenance-tracked, see §3.5

FRAGRANCE_VERSION                  (a specific, dateable formulation)
  id, fragrance_id → FRAGRANCE
  concentration          enum: EDT | EDP | Parfum/Extrait | Cologne | Elixir | Oil | Other
  flanker_name           (nullable — e.g., "Intense", "Absolu")
  release_year           (nullable)
  formulation_era        (free text/nullable, e.g., "pre-2012", "current")
  reformulation_of_id    → FRAGRANCE_VERSION (nullable self-FK; links successive formulations)
  perfumers[]            (m2m to a small PERFUMER lookup table)
  marketed_gender        (nullable — descriptive, not used to gate anything)
  status                 enum: current | discontinued | limited_edition
  notes_free_text        (curator notes)

PHYSICAL_ITEM                      (the literal thing in the collection)
  id, fragrance_version_id → FRAGRANCE_VERSION
  owner_id → PERSON (nullable — household-shared items allowed)
  source_vendor           (nullable)
  container_type          enum: full_bottle | manufacturer_sample | decant | oil_vial | spray_vial
  application_method      enum: spray | dab | oil | other
  size_ml                 (nullable)
  acquisition_date        (nullable, exact)
  acquisition_period_text (nullable, approximate — e.g., "~2006–2016")
  batch_code              (nullable)
  notes_free_text
```

**Why this shape**: `FRAGRANCE` is what a person means when they say "Armani Code."
`FRAGRANCE_VERSION` is what actually determines the scent profile (Byron's legacy EDT vs. a
current EDT vs. an EDP). `PHYSICAL_ITEM` is what actually gets smelled in an evaluation —
this is what lets the RDZ Leyenda 21 duplicate-source scenario (§12) and the
oil-vs-spray-performance caveat (§13) be represented without hacks. All note/accord/role
data attaches at the `FRAGRANCE_VERSION` level, since that's the level at which "does this
smell like X" is actually true or false — not the abstract product name.

### 3.2 Classification (Calibration / Canonical / Exploratory)

```
FRAGRANCE_VERSION_ROLE
  fragrance_version_id → FRAGRANCE_VERSION
  role            enum: calibration | canonical | exploratory
  rationale       (free text — why this fills this role)
  added_at
  # unique on (fragrance_version_id, role); a version can hold multiple rows
  # (e.g., both calibration and canonical), satisfying "may be BOTH"

COVERAGE_DIMENSION                 (controlled, editable vocabulary — NOT an enum)
  id, name (e.g., "vetiver", "aldehydic floral", "animalic/challenging")
  description

CALIBRATION_COVERAGE               (many-to-many: overlapping by design)
  fragrance_version_id → FRAGRANCE_VERSION
  dimension_id → COVERAGE_DIMENSION
  weight (0–1, "how strongly this version represents this dimension")

CALIBRATION_SET                    (optional but cheap — supports set evolution over time)
  id, name (e.g., "Calibration 30 v1"), created_at
CALIBRATION_SET_MEMBERSHIP
  set_id → CALIBRATION_SET, fragrance_version_id → FRAGRANCE_VERSION, added_at, rationale
```

**Why `CALIBRATION_SET` is worth the extra table now**: the request says Calibration 30
membership "is still being finalized." If membership changes later, you want to know which
set an evaluator's historical session drew from, rather than inferring it retroactively from
whichever fragrances happen to carry the `calibration` role *today*. This is cheap insurance
against a rewritten history, in the spirit of §21 (Data Versioning).

`role` is deliberately never exposed to evaluators during blind testing — that's an
application/API-layer rule (the serializer used by the blind-evaluation screen simply never
selects this table), not a schema concern.

### 3.3 Vocabulary (Notes & Accords) — with mandatory provenance separation

```
NOTE
  id, canonical_name, description (nullable)
NOTE_ALIAS
  note_id → NOTE, alias

ACCORD
  id, name, description (nullable)

FRAGRANCE_NOTE                     (published/inferred — never evaluator perception)
  fragrance_version_id → FRAGRANCE_VERSION, note_id → NOTE
  position        enum: top | heart | base | unspecified
  <provenance fields — see §3.5>

FRAGRANCE_ACCORD
  fragrance_version_id → FRAGRANCE_VERSION, accord_id → ACCORD
  strength        float 0–1
  <provenance fields — see §3.5>
```

`FRAGRANCE_NOTE`/`FRAGRANCE_ACCORD` represent **published or third-party/inferred**
metadata only. What an evaluator personally smells is a completely separate table
(`PERCEIVED_NOTE`, §3.6) — the request is explicit (§6, §10) that these must never collapse
into one field, and this model keeps them structurally incapable of colliding.

### 3.4 People

```
PERSON                              (generic — "evaluator" is a role this person plays,
  id, display_name, notes_free_text  not a hardcoded type; the same table can also be
                                      a PHYSICAL_ITEM.owner_id above)
```

No family members are hardcoded anywhere; adding Veronica is a row insert.

### 3.5 Provenance (applied uniformly, not a separate mega-table)

Rather than one polymorphic "Provenance" table (which tends to become an
unqueryable junk drawer), attach the same field group directly to every fact table
that can come from multiple sources (`FRAGRANCE_NOTE`, `FRAGRANCE_ACCORD`, `FRAGRANCE.
external_ids`, and later AI-derived rows):

```
source_type        enum: manufacturer_published | third_party_db | ai_inferred | manual_research
source_name         (nullable — e.g., "Fragrantica", "Byron")
source_url          (nullable)
retrieved_at         (nullable)
confidence          float 0–1
verified_by         → PERSON (nullable)
verified_at          (nullable)
```

This directly implements §20's requirement and keeps "AI-generated metadata" from silently
becoming authoritative: a query can always filter to `verified_by IS NOT NULL` or
`source_type = manufacturer_published` when accuracy matters more than coverage.

**Versioning discipline (§21)**: corrections to these facts are modeled as new rows with
`is_current = true` and the old row flipped to `is_current = false` (with a
`superseded_by_id` self-FK) rather than in-place `UPDATE`s. This preserves "we used to think
this had bergamot" as an auditable fact, which matters once recommendation models start
citing specific notes as reasons.

### 3.6 Historical Preferences (pre-formal-testing knowledge)

```
HISTORICAL_PREFERENCE
  id, evaluator_id → PERSON, fragrance_id → FRAGRANCE (version often unknown for old memories)
  sentiment        enum: favorite | like | neutral | dislike | hate
  free_text
  recorded_at
  source_type      (e.g., "recalled/verbal" — reuses the provenance enum where it fits)
```

Kept structurally separate from `EVALUATION` for exactly the reason given in §11: if Byron
later blind-tests Rasasi Qasamat Ebhar, both records persist so the historical claim and the
controlled result can be compared, never merged or overwritten.

### 3.7 Evaluation Capture (the blind-testing / two-stage core)

```
EVALUATION_SESSION
  id, evaluator_id → PERSON, session_datetime
  session_type      enum: screening | wear
  test_medium       enum: blotter | skin
  context_free_text  (weather/mood/etc., nullable)

EVALUATION
  id, session_id → EVALUATION_SESSION (nullable — a session groups sittings, but ad hoc
                                        single evaluations should also be possible)
  evaluator_id → PERSON
  physical_item_id → PHYSICAL_ITEM      # not fragrance_id — captures which literal sample,
                                         # required for the duplicate-source reliability case
  stage             enum: screening | wear
  blind_label        (e.g., "K17" — shown to the evaluator instead of the real name)
  phase             enum: blind | post_reveal
  reveals_evaluation_id → EVALUATION (nullable self-FK; a post_reveal row points back at
                                       the blind row it follows up on — the blind row is
                                       never edited or overwritten)
  locked_at          (once set, the blind response is immutable)
  created_at

SCREENING_OBSERVATION               (1:1 with a screening-stage EVALUATION)
  evaluation_id → EVALUATION
  initial_liking        0–10
  fresh_rich, dry_sweet, light_heavy, clean_earthy, familiar_unusual   — each 0–10,
                                                                          documented endpoints
  free_text
  confidence            1–5

WEAR_OBSERVATION                    (1:many with a wear-stage EVALUATION — one row per
                                      checkpoint: opening / mid-drydown / late-drydown)
  evaluation_id → EVALUATION
  checkpoint             enum: opening | mid_drydown | late_drydown | custom
  elapsed_minutes         (nullable int — actual elapsed time, never forced to a fixed slot)
  overall_liking, opening_liking, drydown_liking   0–10 (nullable as applicable to checkpoint)
  would_wear             bool
  would_buy              bool                      # explicitly independent of would_wear
  perceived_projection, perceived_longevity   — ordinal scale
  dimensional_ratings     (same bipolar set as screening, optional here)
  free_text
  confidence             1–5

PERCEIVED_NOTE                      (attached to an EVALUATION — either stage)
  evaluation_id → EVALUATION
  raw_text                                          # always retained verbatim
  mapped_note_id → NOTE (nullable)                  # optional, non-destructive clustering
  confidence (nullable)
```

**Why `physical_item_id` and not `fragrance_version_id` on `EVALUATION`**: it's the
strictest option and everything else derives from it (`physical_item → fragrance_version →
fragrance`). It's the only granularity that can represent "two decants of the same
fragrance from different vendors, blind-tested without telling the evaluator they're the
same" — exactly the RDZ Leyenda 21 case in §12 — and the oil-vs-spray performance caveat in
§13 (since `container_type`/`application_method` live on `PHYSICAL_ITEM`).

**Why blind/reveal is two rows, not one row with nullable "revealed" columns**: an
`UPDATE` that reveals a fragrance and appends post-reveal comments to the *same* row would
either destroy the blind record or require awkward "was this touched after reveal"
bookkeeping. Two rows linked by `reveals_evaluation_id`, with the first one becoming
immutable at `locked_at`, is simpler to reason about and directly answers "what did they
think blind vs. after knowing" as two clean queries.

**Repeated testing (§12)** falls out for free: nothing here enforces one evaluation per
(evaluator, fragrance) — an evaluator can have arbitrarily many `EVALUATION` rows against the
same or different `PHYSICAL_ITEM`s of the same `FRAGRANCE_VERSION`, which is exactly what's
needed to compute rating variance/consistency later.

### 3.8 Modeling Layer (schema placeholders — not built until Phase 3–5)

These tables are specified now so that Phase 1's schema doesn't foreclose them, but nothing
in Phase 1–2 needs to write to them.

```
MODEL_RUN
  id, model_name, model_version, computed_at, training_data_snapshot_ref

RECOMMENDATION_SCORE
  model_run_id → MODEL_RUN, evaluator_id → PERSON, fragrance_version_id → FRAGRANCE_VERSION
  predicted_liking        0–100
  information_value       0–100
  recommendation_type     enum: safe | discovery | diagnostic | reference | full_bottle_candidate
  explanation_text
  explanation_features    (structured — which notes/accords drove the score, with signed
                            weights, so "why" is answerable without re-deriving it)

PREFERENCE_FINGERPRINT
  evaluator_id → PERSON, computed_at, model_version
  dimension_scores         (per Note/Accord, a signed affinity + confidence)

EVALUATOR_SIMILARITY
  evaluator_a_id, evaluator_b_id → PERSON, computed_at, model_version
  overall_similarity, per_dimension_similarities
```

Keeping `predicted_liking` and `information_value` as two independent columns from day one
(rather than one "score" column extended later) is the one piece of future-proofing worth
calling out explicitly, since §15 calls it "central to the project."

---

## 4. Migration Implications

Because §1.1 established that **no real evaluation data exists in any database today**,
this is not a data-migration project in the usual sense — there's no `ALTER TABLE` dance
against production rows. The practical migration tasks are:

1. **Nothing to migrate out of the live app** — the in-memory 3-fragrance catalog and the
   `/ratings` endpoint's request/response shapes are demo fixtures, not data.
2. **Retire, don't port, the planning-doc schema** (`concept.md` / `tech-spec.md` /
   `ADR-004`'s `Fragrance`/`Reviewer`/`Evaluation` tables). Since none of it was ever built,
   there's no code depending on it to update — only documentation to revise (§7 below).
3. **Seed data entry, not migration, for real content**: the fragrances named in the
   request (Byron's legacy designer bottles, the Imaginary Authors set, RDZ discovery set,
   Hoshi Gato, Poesie oils, the Calibration 30 candidates, the canonical reference list,
   the known historical preferences like Aventish Orange Dusk) all need to be **entered
   fresh** into the new schema — as `HOUSE`/`FRAGRANCE`/`FRAGRANCE_VERSION`/`PHYSICAL_ITEM`
   rows and `HISTORICAL_PREFERENCE` rows respectively. None of this pre-exists in a
   structured form anywhere in the repo, so "migration" here just means "first data entry
   pass," ideally via the admin/library UI (Phase 2) rather than hand-written SQL.
4. **The Kaggle/Fragrantica import path** (ADR-002, still sound) becomes a **bulk seeder
   for `NOTE`/`ACCORD`/`FRAGRANCE`/`FRAGRANCE_VERSION` rows with `source_type =
   third_party_db` provenance**, not a seeder for a flat `family`/`subfamily` field. The
   importer needs to be written against the new schema; nothing from the old plan is
   reusable as code (it was never written), only as a source-selection decision.

Net effect: the project is in the fortunate position of being able to build the *right*
schema first, instead of retrofitting one. The only real "migration" risk is documentation
debt — planning docs that still describe the old model and would mislead future work if left
as-is (§7).

---

## 5. Which Parts of the Existing Plan Survive

| Existing decision | Verdict | Why |
|---|---|---|
| ADR-001: Docker Compose (Postgres + FastAPI + React) monolith | **Keep** | Infra choice, orthogonal to the domain model. |
| ADR-002: Tiered data acquisition (Kaggle → manual → Fragella) | **Keep, retarget** | Still the right sourcing strategy; the importer needs to write into the new normalized tables instead of the flat one, and should tag everything with `source_type = third_party_db`/`manufacturer_published` provenance. |
| ADR-003: OpenRouter LLM for recommendation explanations | **Keep the *idea*, defer the build, change the input contract** | Target §14 wants LLM narration of an *already-computed, interpretable* score (specific notes/accords with signed weights) — not a black box asked to invent a number. The current live `/ratings` endpoint does the latter; it should not be extended, but its `TEST_MODE` seam and OpenRouter plumbing are reusable once Phase 4 produces real `explanation_features` to narrate. |
| ADR-004: Weighted affinity scoring formula | **Redesign, not reuse** | The formula's structure (weighted feature contributions with a "veto" for strong dislikes) is a reasonable *starting point* for Phase 4's Predicted-Liking score, but it currently operates on `family`/`subfamily` enums and a single 0–1 output. It needs to operate over the Note/Accord feature space and emit two independent scores (§3.8), and account for confidence-weighting and repeated evaluations. |
| `concept.md` / tech-spec.md data model (single `Fragrance` table, 1–5 rating, no blind testing) | **Superseded** | Incompatible with almost every numbered requirement in the target (§5–§13). Recommend marking `concept.md` as a historical/superseded document once this review is agreed, rather than deleting it — it's useful context for *why* the project exists. |
| `docs/planning/backend/` FastAPI scaffold | **Discard** | Never wired up (imports a nonexistent `app.models`), and encodes the superseded schema. Not worth repairing. |
| Live `/ratings` endpoint (LLM-guesses-a-score) | **Isolate, don't extend** | Solves "would an AI like this," not "what did a person perceive." Repurpose later (Phase 4) as the mechanism that narrates a computed `explanation_features` payload, or drop it if it doesn't end up needed. |
| Live `/fragrances` in-memory catalog | **Replace** | Becomes a real read endpoint over `FRAGRANCE`/`FRAGRANCE_VERSION` once the DB exists. |
| Generic app infra (exceptions, logging, correlation, CLI, auth/rate-limit middleware) | **Keep unmodified** | Not domain-specific; the fragrance schema and routes sit on top of it. |

---

## 6. UI / Blind-Testing Workflow Review

There is currently no evaluation UI to review (§1.1) — the frontend is the unmodified
template. The relevant design work is therefore not "fix the blind-testing screen" but
"build one," guided by the three-mode structure the request already specifies (§24):

- **Quick Evaluation** (screening/blotter): must show only a `blind_label`, capture
  `SCREENING_OBSERVATION` fields, and complete in well under a minute per fragrance. No
  house, price, notes, family, popularity, calibration status, or other evaluators' scores
  should ever be present in the payload this screen receives — this needs to be enforced by
  the API response shape used for blind evaluations (a dedicated, minimal serializer), not
  by hiding fields client-side.
- **Full Wear Test**: unlocked once a fragrance is "worth further evaluation" from
  screening; captures `WEAR_OBSERVATION` at multiple checkpoints with real elapsed time,
  plus the `would_wear`/`would_buy` split.
- **Library/Admin**: everything else — `FRAGRANCE_VERSION_ROLE`, provenance/verification,
  `PHYSICAL_ITEM` inventory, `CALIBRATION_SET` management, and (later) `MODEL_RUN`/AI
  analysis views. Never shown to someone mid-evaluation.

The reveal step is a distinct screen/action: it takes a `locked_at` blind `EVALUATION`,
surfaces the real `FRAGRANCE_VERSION` metadata, and offers an optional post-reveal comment
that is written as a *new* `EVALUATION` row (`phase = post_reveal`,
`reveals_evaluation_id = <the blind row>`), never as an edit to the blind row.

Session generation (balanced randomization, ≤3 fragrances per sitting, avoiding
similar/related fragrances adjacent) is explicitly called out in the request as an
eventual capability, not an immediate one — the schema (`EVALUATION_SESSION`,
`CALIBRATION_COVERAGE`) supports it, but the actual balancing algorithm is Phase 2/3 work,
not Phase 1.

---

## 7. Documentation Follow-Up (once this is agreed)

- Add a new ADR (e.g. `ADR-005: Preference-Fingerprint Data Model`) recording the shift
  described here, referencing this document.
- Revise `tech-spec.md`'s "Data Model" section to match §3 of this document (or replace it
  with a pointer to this file plus the ADR).
- Update `roadmap.md`/`PROJECT-PLAN.md`'s phase definitions to match §8 below.
- Mark `concept.md` as historical context rather than an active spec (add a status banner
  at the top).

None of this is done yet — it's listed here so the follow-up isn't lost once the
architecture is agreed.

---

## 8. Staged Implementation Roadmap

Ordered so that no phase requires undoing work from an earlier one, and so real evaluation
data collection can start as early as possible without boxing in the later analytics.

### PHASE 1 — Foundation
*Must happen before substantial evaluation data is collected, because every later phase's
schema depends on it.*

- Wire up SQLAlchemy 2.0 + Alembic + Postgres (infra already provisioned by
  `docker-compose.yml`; nothing currently connects to it).
- Implement §3.1–§3.6: House/Fragrance/FragranceVersion/PhysicalItem, Note/Accord +
  provenance fields, FragranceVersionRole + CoverageDimension + CalibrationSet,
  Person, HistoricalPreference.
- Seed: canonical reference list (configurable, per §4 of the request), initial
  Calibration 30 candidates as they're finalized, and the known historical preferences
  already stated (Byron/Aventish Orange Dusk, Byron+Ariannah/Qasamat Ebhar, etc.).
- Minimal Library/Admin UI or CLI sufficient to enter/correct this data — doesn't need to
  be polished, since this UI mode is explicitly the "clutter is acceptable" one (§24).
- **Why now**: every later phase's tables have foreign keys into this layer; getting the
  identity/vocabulary/classification model right before entering real evaluations avoids
  ever having to re-key evaluation history against a redesigned catalog.

### PHASE 2 — Evaluation System
*Everything needed to actually run blind sessions and record what people perceive.*

- `EVALUATION_SESSION` / `EVALUATION` / `SCREENING_OBSERVATION` / `WEAR_OBSERVATION` /
  `PERCEIVED_NOTE`, blind/reveal split with immutability after `locked_at`.
- Quick Evaluation and Full Wear Test UI modes (§6 above); the blind-serializer contract
  that never leaks identity/metadata pre-reveal.
- Manual session creation (no balancing algorithm yet — an evaluator or admin just picks
  ≤3 physical items for a sitting).
- **Why before analytics**: Phases 3–5 have nothing to analyze without real evaluation
  data, and the RDZ Leyenda 21 reliability experiment (§12) only works if the blind
  mechanism is trustworthy from the first session.

### PHASE 3 — Analytics
*Read-only insight over accumulated evaluations — no recommendations yet.*

- Preference fingerprints per evaluator (aggregated Note/Accord affinities, confidence-
  weighted, incorporating repeated evaluations and `HistoricalPreference` as a separate
  weaker signal).
- Calibration/canonical coverage reporting ("you've evaluated 14 of 25 canonical
  references"; "the Calibration 30 is missing coverage of animalic/challenging").
- Evaluator consistency and fragrance rating variance (uses the repeated-evaluation
  capability built into the Phase 2 schema).
- Cross-evaluator comparison (§19) — similarity/disagreement by accord, never assumed from
  family relationship.
- **Why before recommendations**: predicted liking and information value (Phase 4/5) are
  both *derived from* the fingerprint and coverage-gap analysis this phase produces; building
  them first would mean guessing at inputs that don't exist yet.

### PHASE 4 — Recommendations
*Interpretable Predicted-Liking, using the Phase 3 fingerprint.*

- `MODEL_RUN` / `RECOMMENDATION_SCORE` populated with `predicted_liking` +
  `explanation_features` (named notes/accords with signed contributions) — start from a
  revised version of the ADR-004 weighted-affinity approach, but over the Note/Accord
  feature space instead of family/subfamily enums, with negative-signal amplification
  (§14's "veto") preserved.
- Recommendation types other than pure ranking: `safe`, `reference`,
  `full_bottle_candidate` become computable once fingerprint + coverage data exist;
  `discovery`/`diagnostic` need Phase 5's information-value axis to be meaningful, so they
  can be stubbed here and completed in Phase 5.
- LLM narration (reviving the ADR-003 OpenRouter integration) turns
  `explanation_features` into the "why" prose from §14/§18 — this is where the current
  `/ratings` endpoint's plumbing gets reused, with a fundamentally different input contract
  (structured feature attribution in, not a bare text description).
- Fragrance Profile Card generation (§18) as a cached summary derived from the fingerprint.

### PHASE 5 — Active Learning
*Information Value and sample prioritization — explicitly the least urgent, per the
request's own framing ("long-term goal, not necessarily an immediate implementation
requirement").*

- `information_value` scoring (model uncertainty + feature-space novelty +
  redundancy-with-existing-evaluations), completing the `RECOMMENDATION_SCORE` row and
  unlocking real `discovery`/`diagnostic` recommendation types.
- Expected-information-gain-per-cost acquisition metric, factoring in sample availability
  and cost.
- Balanced session-randomization algorithm for `EVALUATION_SESSION` generation (deferred
  from Phase 2, since it needs real fingerprint/coverage data to do anything smarter than
  random shuffling).

---

## 9. Open Questions for Agreement

**Status**: blocked on [PR #65](https://github.com/ByronWilliamsCPA/fragrance-rater/pull/65)
merging (removal of the legacy `docs/planning/backend`/`docs/planning/frontend` scaffold).
No implementation starts until that lands *and* the four questions below are answered.

### 9.1 What is the "person" entity actually called, and what does it model?

**The issue.** The superseded plan (`tech-spec.md`, ADR-004) has a `Reviewer` table: one
row per family member, existing purely to be the other end of an `Evaluation` foreign key.
The target spec (§1) never uses the word "reviewer" — it says "evaluator" throughout — but
it also needs the same table to be the `owner` on `PHYSICAL_ITEM` (§5: "Byron owns several
full bottles..."; §22: "additional... perfumes belonging to Veronica that are still being
inventoried"). Those two facts pull in different directions: Veronica's bottles are being
entered as inventory *before* she's necessarily evaluated anything, so "this table only
holds people who evaluate" isn't quite true from day one, even though in practice every
household member who owns a bottle will also end up evaluating.

**Your options:**

- **A — Table named `Evaluator`.** Matches the target document's own vocabulary exactly, so
  every reference in this review and in future code reads naturally ("evaluator_id",
  "evaluator profile"). `PHYSICAL_ITEM.owner_id` would still point at this same table (an
  owner is just an evaluator who happens to own something), which is a small naming
  inconsistency but a harmless one in practice, since nobody in this household owns
  fragrance who won't eventually be an evaluator.
- **B — Table named `Person`, with `evaluator_id`/`owner_id` as the role-specific foreign
  key names.** Slightly more general/correct (ownership and evaluation are modeled as two
  things a person can do, not one identity), and cheaply future-proofs against an edge case
  like "a fragrance Veronica owns but never gets around to evaluating" without it feeling
  like a misnamed table. Costs nothing extra in the schema — it's a naming and FK-column
  choice, not an additional table.
- **C — Keep `Reviewer`.** Minimizes the diff against the (already-superseded) planning
  docs' vocabulary. Doesn't fit the target spec's own language and would read oddly next to
  "blind evaluation," "evaluation session," etc.

**My recommendation**: **B**. It costs nothing structurally over A (same single table,
same relationships), it's more accurate to what the household is actually doing (owning
things and evaluating things are separate facts about a person), and it avoids the minor
awkwardness in A of an "Evaluator" row existing for someone before they've evaluated
anything. I'd reject C outright — reusing `Reviewer` would quietly drag the old,
superseded model's assumptions (one evaluation = one opinion, no blind/reveal distinction)
back into the new schema's vocabulary even if the columns changed underneath it.

### 9.2 What numeric convention do the bipolar/ordinal scales use?

**The issue.** Target §9 specifies bipolar dimensions (fresh↔rich, dry↔sweet, light↔heavy,
clean↔earthy, familiar↔unusual) and says they "should ideally use continuous or ordinal
scales rather than binary choices," without pinning down units. This needs a concrete,
consistent answer before `SCREENING_OBSERVATION`/`WEAR_OBSERVATION` can be built, because
it affects both the UI (slider vs. discrete buttons) and every later statistic computed
over these fields (averages, variance for the reliability work in Phase 3, feature vectors
for the fingerprint in Phase 3/4).

**Your options:**

- **A — 0–10 integer, endpoints labeled per dimension** (e.g., 0 = "Fresh," 10 = "Rich").
  Matches `initial_liking`'s existing 0–10 scale, so every screening field uses the same
  slider widget and the same statistical treatment. 11 discrete positions is enough
  resolution to see meaningful variation without implying false precision. The only
  wrinkle: which pole is 0 vs. 10 is an arbitrary convention that has to be documented once
  and then never violated (a later screen accidentally flipping "Fresh" and "Rich" would
  quietly corrupt historical comparisons).
- **B — Symmetric −5..+5 integer**, 0 = neutral/balanced. More intuitive for a *bipolar*
  framing specifically (0 reads as "right in the middle" without needing a separate
  documented convention for where "neutral" falls), and slightly nicer for later math (a
  fragrance's average dryness score across evaluators is directly signed). Costs a UI
  difference from the 0–10 `initial_liking`/wear-liking fields (those stay unipolar 0–10
  regardless of which option is picked here), so the app ends up with two scale families
  instead of one.
- **C — Continuous float** (e.g., 0.0–1.0 or −1.0..+1.0), closest to the spec's literal
  word "continuous." Gives the eventual fingerprint model maximal resolution, but humans
  can't reliably place a slider at 0.42 vs. 0.47, so the extra precision is manufactured,
  not real signal — and it works against the "Quick Evaluation must be fast and enjoyable"
  requirement (§24) by inviting evaluators to fuss over slider position.
- **D — 0–100**, matching the scale already specified for `predicted_liking`/
  `information_value` (§15), so "everything in the app is 0–100" becomes one rule instead
  of several. More resolution than A, same false-precision risk as C if evaluators are
  shown the raw number (a slider UI without a visible numeric readout mostly avoids this).

**My recommendation**: **A (0–10)** for every human-entered screening/wear dimension,
**1–5** for `confidence` (as the target spec itself already specifies for that field — no
decision needed there), and **0–100** reserved for computed model outputs only
(`predicted_liking`, `information_value` in Phase 4/5), never for raw human input. This
keeps a clean rule: *numbers a person drags a slider to are 0–10; numbers a model computes
are 0–100.* If the bipolar-vs-unipolar framing bothers you (i.e., you'd rather 0 always mean
"neutral" rather than "leftmost pole"), B is a completely reasonable alternative — it's a
genuine style preference at this point, not a correctness issue, so I'd go with whichever
reads more naturally to the people actually filling out the form.

### 9.3 Is a dedicated `CALIBRATION_SET` table worth building now?

**The issue.** §3.2 proposes `CALIBRATION_SET` / `CALIBRATION_SET_MEMBERSHIP` so that if the
Calibration 30's membership changes later, you can still answer "which 30 fragrances was
this evaluator's Calibration-30 session actually drawn from at the time," rather than only
being able to see today's `calibration` role flags. The request itself says membership "is
still being finalized," which is exactly the situation where either (a) building this now
pays off almost immediately, or (b) it's speculative complexity for a set that hasn't
stabilized enough to be worth versioning yet.

**Your options:**

- **A — Build it in Phase 1.** Two small tables, cheap to add now, expensive to backfill
  correctly later (reconstructing "what was in the Calibration 30 on date X" after the fact
  requires either good change-log discipline elsewhere or guesswork). If you expect to
  revise membership more than once (the request mentions ~24 existing + ~6 new candidates,
  which is already one revision in progress), this pays for itself the first time you need
  to ask "was fragrance Y in the set when Byron did his calibration pass."
- **B — Skip it entirely.** Use `FRAGRANCE_VERSION_ROLE` (role = `calibration`) as the only
  source of truth, with no versioned "set" concept at all. Simplest possible admin surface
  — a single checkbox per fragrance version. Historical reconstruction becomes indirect: you'd
  need to infer past membership from `EVALUATION_SESSION` timestamps plus whatever the role
  table looked like at that time, which only works if the role table itself never destructively
  overwrites (see next option).
- **C — Defer `CALIBRATION_SET`, but make `FRAGRANCE_VERSION_ROLE` append-only from day
  one** (new row + `is_current=false`/`superseded_by_id` on the old one, instead of an
  in-place `UPDATE`, matching the provenance-versioning discipline §3.5/§21 already
  recommends for `FRAGRANCE_NOTE`/`FRAGRANCE_ACCORD`). This gets most of B's simplicity
  (one table, not three) while preserving enough history to answer "what was flagged
  `calibration` as of date X" later via a timestamp query, without a dedicated set concept.
  `CALIBRATION_SET` remains a pure additive migration if named-set comparison ("v1 vs v2")
  ever becomes a real need.

**My recommendation**: **C**. It's the least schema for the most of the actual benefit:
you get historical recoverability (the real thing you want) without committing to a
set-membership UI/table before the Calibration 30 has even stabilized once. If, once
membership is finalized, you find yourself wanting to explicitly name and compare "the
original 30" against a later revision, A is a small additive change at that point — nothing
here forecloses it.

### 9.4 How much Library/Admin UI does Phase 1 actually need?

**The issue.** Phase 1's job is getting real data — houses, fragrances, versions, physical
items, the Note/Accord vocabulary, calibration/canonical roles, and the historical
preferences already known (Aventish Orange Dusk, Qasamat Ebhar, etc.) — into the new schema.
Target §24 explicitly treats Library/Admin as the mode where "clutter" is acceptable and
design investment matters least; the real design investment belongs in Phase 2's Quick
Evaluation screen. The question is just how much building happens in Phase 1 to get data
in, versus deferring even that to Phase 2.

**Your options:**

- **A — CLI/bulk-import only, no admin web UI in Phase 1.** Extend the CLI pattern the old
  plan already sketched (`fragrance-rater import kaggle`) with a `seed`/`import` command
  that loads houses/fragrances/versions/roles/notes from structured files (CSV/YAML), plus
  direct database access for one-off corrections. Fastest path to real data; zero UI
  investment spent on a mode that's explicitly low-priority. Downside: bulk text-file entry
  is more typo-prone than a form with autocomplete, and there's no browsing/searching UI
  until Phase 2.
- **B — A minimal but real admin web UI in Phase 1** (basic CRUD screens, possibly using an
  auto-generated admin panel rather than hand-built React). Easier day-to-day data entry and
  correction, and it's a head start on whatever the Phase 2 Quick Evaluation screen needs to
  read from (fragrance lookup, physical item selection). Downside: real build time spent on
  a screen the target spec itself says shouldn't get design attention, before any evaluation
  capability exists at all.
- **C — CLI/bulk-import for the initial big seed, plus a bare FastAPI CRUD API with no
  dedicated frontend yet.** Splits the difference: the *data layer's* read/write contract
  gets built in Phase 1 (so Phase 2 doesn't have to retrofit it), but no admin frontend
  screens get built until Phase 2, when they can share components/patterns with the
  evaluation UI instead of being designed twice.

**My recommendation**: **C**. It keeps Phase 1 scoped to "get the schema right and get real
data in" (its actual job), avoids spending build time on a UI mode the spec says should stay
minimal, and avoids the double-build risk of A (writing one-off CLI scripts now, then a
proper API layer in Phase 2 anyway).

---

Once these four are answered, the next step is implementing Phase 1 (schema + migrations +
seed data) — but that work is explicitly on hold until PR #65 merges, per your instruction.
