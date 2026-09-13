# Data Model Gap Analysis: Preference Learning, Controlled Evaluation, and Future ML

> **Status**: Draft for core-maintainer review | **Version**: 1.0 | **Updated**: 2026-09-12
>
> **Author**: Claude Code, on request
>
> **Scope**: Reviews the schema audited at the current-state ledger commit
> (`7f0884fb3fd5a5faa5178952ae4ef1f08792d010` plus the branch under review) against the full
> requirement set for canonical identity, controlled evaluation, scenario/context modeling,
> pairwise preference, behavioral outcomes, and future ML/recommendation work.

This document is analysis and a proposed plan; it did not itself change any model, migration,
schema, or route at the time it was written. Where this analysis recommends a durable decision,
it is captured as [ADR-010](adr/adr-010-preference-learning-and-scenario-data-model.md).

> **2026-09-12 update**: the product owner asked to begin ML testing against recommendation/
> liking projections. Two things below are now **implemented** (migration `9ded7f54996c`; see
> ADR-010's implementation-status note for exact scope): promoting the scalar/text
> `calibration_observations.responses` fields to typed columns (§6 Step 1, Risk 1), including
> quarantining, rather than fabricating or crashing on, any legacy value that predates a new
> column's bound, and adding a new, standalone `PredictionSnapshot` entity (§4). That
> `PredictionSnapshot` entity is separate from, and does not fulfill, the still-deferred
> `ModelCheckpoint.predictions` decomposition discussed at §XXXVII and in the §6 Deferred list
> below; see ADR-010's implementation-status note for the distinction between the two. §6 Steps 2
> and 3 (familiarity as a controlled code; normalizing `perceived_notes` against `Note`) were part
> of the same original recommendation but are **not** implemented: `familiarity` keeps its
> original ambiguous numeric scale and `perceived_notes` ships as a typed JSON array of free
> text, not yet normalized. Every other recommendation in this document, including the remaining
> P0 items (brand/accord lookup tables, sample provenance, `training_eligibility`), remains
> unimplemented and still requires core-maintainer review before it proceeds, per
> [ADR governance](adr/README.md) and the [Project Plan](PROJECT-PLAN.md) change-control rules.

**Priority labels in this document (P0/P1/P2) are the review's own prioritization scale**
("required before baseline" / "required before adaptive ML" / "safe to defer") **and are
distinct from the repository's milestone names P0-P6.** Where a repository milestone is meant,
it is written as "milestone P1", "milestone D1", etc.

---

## 1. Existing Schema Summary

### 1.1 Catalog domain (`src/fragrance_rater/models/fragrance.py`)

| Table | Key fields | Notes |
| :--- | :--- | :--- |
| `fragrances` | `id`, `name`, `brand`, `concentration`, `version_key`, `launch_year`, `gender_target`, `primary_family`, `subfamily`, `intensity`, `data_source`, `external_id`, `parfumo_url`, `created_at`, `updated_at`, `deleted_at` | Per ADR-006, this row is the canonical **version** identity: brand + name + concentration + version_key distinguish formulations. It plays the role the requirements call both "Fragrance" and "FragranceVariant." `brand` is a free-text string, not a foreign key. `primary_family`/`subfamily` are free strings following one hard-coded taxonomy (Michael Edwards Wheel), not a versioned/pluggable classification system. Soft-deleted via `deleted_at`; unique on `(name, brand, concentration, version_key)` scoped to live rows. |
| `notes` | `id`, `name` (unique), `category`, `subcategory` | Normalized note vocabulary. No alias table, no parent hierarchy beyond one `category`/`subcategory` string pair, no versioning. |
| `fragrance_notes` | `id`, `fragrance_id`, `note_id`, `position` (`top`/`heart`/`flat`/`base`) | Junction with pyramid position; unique on `(fragrance_id, note_id, position)`. No provenance/source/confidence per row; it inherits only the parent fragrance's single `data_source`. |
| `fragrance_accords` | `fragrance_id`, `accord_type` (free string), `intensity` (0.0-1.0) | `accord_type` is **not** backed by a controlled vocabulary table: any string is accepted. No source/confidence per row. |

### 1.2 People and ordinary evidence (`models/reviewer.py`, `models/evaluation.py`)

| Table | Key fields | Notes |
| :--- | :--- | :--- |
| `reviewers` | `id`, `name`, `created_at`, `deleted_at` | Plays the "Evaluator" role. Deliberately has no link to Authentik identity (see `Evaluation.recorded_by` below). |
| `evaluations` | `id`, `fragrance_id`, `reviewer_id`, `rating` (1-5), `notes` (free text), `longevity_rating` (1-5), `sillage_rating` (1-5), `evaluated_at`, `created_at`, `deleted_at`, `recorded_by` | **This is the atomic ordinary encounter.** No unique constraint on `(reviewer_id, fragrance_id)`: a reviewer may rate the same fragrance any number of times, and each POST creates a new row (`evaluation_service.create`); PATCH corrects one existing encounter in place rather than creating a new one; DELETE soft-deletes one encounter. `recorded_by` is intentionally independent of `reviewer_id` (who typed vs. whose palate). There is no `sample_id`, no familiarity state, no scenario/context data, and no purchase-intent field on ordinary encounters. |

### 1.3 Controlled calibration domain (`models/calibration.py`)

This module already implements most of what the requirements call "Experiment," "Encounter,"
and "Dataset role":

| Table | Key fields | Maps to requirement concept |
| :--- | :--- | :--- |
| `calibration_programs` | `id`, `name`, `version`, `status`, `locked_at` | Experiment |
| `calibration_memberships` | `id`, `program_id`, `fragrance_id`, `role` (`UNIVERSAL_BASELINE`/`HIDDEN_REPEAT`/`HOLDOUT`/`ACTIVE_LEARNING`/`RETEST`/`OWNED_VALIDATION`/`OTHER`), `repeat_of_id`, `group_name`, `selection` (JSON) | ExperimentAssignment + Dataset role. `HOLDOUT` role plus `PreferenceHistoryService.excluded_versions()` is the leakage-prevention mechanism (see §1.5). `selection` is an **unstructured JSON dict** used today to carry ad hoc per-membership metadata. |
| `calibration_enrollments` | `id`, `program_id`, `reviewer_id`, `recorder_usernames`, `skin_plan_locked_at`, `revealed_at`, `revealed_by` | Per-evaluator experiment participation and disclosure gate |
| `calibration_sessions` | `id`, `enrollment_id`, `context` (JSON), `created_at` | Ordered batch of presentations |
| `calibration_presentations` | `id`, `session_id`, `membership_id`, `blind_code`, `position`, `skin_reason`, `blotter_locked_at`, `skin_locked_at` | Blind/session-scoped stimulus. `blind_code` is unique globally so repeats get independent codes (hidden-repeat support). No structured "container/delivery format", "sprays", or physical-sample provenance fields; see §1.6. |
| `calibration_observations` | `id`, `presentation_id`, `stage` (`BLOTTER`/`SKIN`), `phase`, `elapsed_minutes`, `detected`, `intensity` (0-5), `liking` (0-10), `responses` (**JSON**), `recorded_by`, `created_at` | **This is the atomic controlled encounter/evaluation** (append-only; "no update route exists for submitted observations" per the model docstring). Only `stage`, `phase`, `elapsed_minutes`, `detected`, `intensity`, and `liking` are first-class typed/constrained columns. Everything else the `ResponseInput` schema validates, namely `confidence`, `sweetness`, `freshness`, `density`, `familiarity`, `dryness`, `clean_soapy`, `earthy_rooty`, `bodily_animalic`, `discomfort`, `opening_liking`, `drydown_liking`, `would_wear`, `would_buy`, `artistic_appreciation`, `projection`, `longevity_minutes`, `perceived_notes`, `likes`, `dislikes`, `reminds_me_of`, and `comments`, is validated once at the API boundary and then written wholesale into the single `responses` JSON column (`calibration_service.py:262-270`, `Observation(..., responses=data.model_dump(mode="json"))`). See §3 (Risk 1): this is the single most consequential finding in this review. |
| `calibration_checkpoints` | `id`, `enrollment_id`, `algorithm_version`, `manifest` (JSON), `predictions` (JSON) | Frozen model snapshot per ADR-009, immutable and never recomputed in place. This is a coarse-grained precursor to the deferred `ModelCheckpoint.predictions` decomposition (see §XXXVII), distinct from the now-implemented, standalone `PredictionSnapshot` entity; predictions here remain an undifferentiated JSON list rather than one row per fragrance/model/uncertainty. |
| `calibration_source_snapshots` | `id`, `fragrance_id`, `source_url`, `verification_status`, `retrieved_at`, `payload` (JSON) | Source provenance (III) for external/reference data, distinct from evaluator perception. |
| `calibration_perfumers` / `calibration_version_perfumers` | `name` (unique) / `fragrance_id`, `perfumer_id`, `source_url` | Perfumer is already relational, many-to-many, with per-attribution `source_url`. No confidence field. |

### 1.4 Recommendation measurement domain (`models/recommendation_measurement.py`)

| Table | Key fields | Maps to requirement concept |
| :--- | :--- | :--- |
| `recommendation_runs` | `id`, `reviewer_id`, `algorithm_version`, `candidate_strategy`, `filters` (JSON), `input_manifest` (JSON), `source_snapshot` (JSON), `created_at`, `recorded_by` | Immutable generation event: this **is** most of the general prediction-snapshot concept for the ranking/scoring side (distinct from the now-implemented `PredictionSnapshot` entity, which covers calibration-side predicted ratings). `candidate_strategy` is currently a single literal (`"catalog-affinity"`), not yet the richer selection-objective taxonomy (XXXIX). |
| `recommendation_impressions` | `id`, `run_id`, `fragrance_id`, `rank`, `score_type`, `score_value` (0-1), `explanation_version`, `shown_at` | Persisted exactly once per `(run, fragrance)`; immutable after creation. |
| `recommendation_response_revisions` | `id`, `impression_id`, `revision`, `interested`, `sampling_state` (`PLANNED`/`ACQUIRED`/`SAMPLED`/`UNAVAILABLE`), `unavailable_reason`, `outcome_evaluation_id`, `outcome_observation_id`, `would_wear`, `would_buy`, `created_at`, `recorded_by` | Append-only revisions; outcome links reference an existing `Evaluation` or `Observation` rather than copying data. This is the only place `would_wear`/`would_buy` exist as first-class typed columns today, and only in the context of a specific recommendation impression, not as a general behavioral event. |
| `llm_invocations` | latency/cache/cost/token telemetry | Not a preference-learning concept, but shows the established pattern for model/version/cost provenance. |
| `pilot_operational_events` | `event_type` (`CONNECTIVITY_FAILURE`/`MANUAL_RECOVERY`) | Operational, not preference data. |

### 1.5 Business logic that matters for this review

- `PreferenceHistoryService` (`services/preference_history.py`) builds the ML-facing training
  manifest. It:
  - excludes any fragrance version with an active `HOLDOUT` membership for the reviewer, across
    ordinary and controlled workflows (leakage prevention, §XIV);
  - takes the single latest live ordinary encounter per fragrance version (repeats retained in
    storage, but only the newest contributes, per ADR-007);
  - takes the single latest eligible, locked, pre-reveal controlled observation per
    `(presentation, stage)`, excluding `HIDDEN_REPEAT` role rows from training;
  - **passes `observation.responses` (the untyped JSON blob) straight into the frozen training
    manifest** (`preference_history.py:139`), so today's "immutable, reproducible" manifest is
    reproducible in the sense that the blob doesn't change, but not in the sense that a future
    ML pipeline can rely on stable, named, typed fields inside it.
- `evaluation_service.py` confirms ordinary encounters are POST-append/PATCH-correct/DELETE-soft;
  no dedup-by-fragrance overwrite exists.
- `core/vocabulary.py` is the *only* controlled-vocabulary module in the codebase today, and it
  covers exactly one value: `gender_target`. No equivalent module exists for accords, seasons,
  occasions, familiarity, confidence, positive/negative drivers, or classification systems.

### 1.6 Frontend contracts (`frontend/src/api/types.ts`)

Frontend types are a thin, faithful mirror of the backend: `Encounter` (ordinary), `Sample`
(presentation), `Observation` (`phase`, `stage`, `elapsed_minutes`, `liking`, `comments` only,
even narrower than the backend's `responses` blob), `RecommendationImpression`/`RecommendationRun`/
`RecommendationResponse`, `Metrics`. There is no scenario, season, occasion, pairwise, or
behavioral-event concept anywhere in the frontend, confirming these are genuinely unimplemented
rather than implemented client-side only.

### 1.7 API surface

Confirmed via `src/fragrance_rater/api/*.py` and the technical specification: fragrances,
reviewers, evaluations, recommendations (+ measurement), Kaggle import, calibration
programs/enrollments/presentations, and shared history. No scenario, pairwise, or behavioral-event
routes exist. `POST /ratings` (LLM-backed) mentions "season" only inside a free-text prompt hint
string sent to the LLM, not a structured field.

---

## 2. Requirement-to-Schema Matrix

Statuses: **Complete**, **Partial**, **Missing**, **Needs clarification**.
Priorities: **P0** (before controlled baseline data collection), **P1** (before adaptive/ML
work), **P2** (roadmap / safe to defer).

| # | Requirement | Existing Support | Current Entity/Field | Gap | Recommended Change | Priority |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| I | Brand identity | Partial | `Fragrance.brand` (free string) | No stable `brand_id`, no aliases; three ingestion paths (manual/Kaggle/Parfumo) can drift on spelling | Add `brands` lookup table + nullable `Fragrance.brand_id`; keep `brand` string during transition | P0 |
| I | Fragrance (parent concept) | Complete | `Fragrance` (name, launch_year, data_source, timestamps) | None material | N/A | N/A |
| I | Fragrance Variant distinct from Fragrance | **Needs clarification (deliberate)** | `Fragrance.concentration` + `version_key` on the same row | ADR-006 explicitly collapses fragrance+variant into one canonical version row "through D5." This is a documented decision, not an oversight. | Do not split now; revisit only if a post-D5 ADR reopens ADR-006 | P2 |
| II | Physical sample/source provenance | Partial | `Membership.selection` (JSON), `Presentation` locks/blind_code | Vendor, source type, volume, acquisition/decant date, batch code, container/delivery format are only representable as ad hoc keys inside an untyped `selection` JSON dict | Promote a fixed set of typed, nullable sample-provenance columns (see §4, `PhysicalSample`) | P0 |
| III | Descriptive-data provenance (manufacturer/retailer/reference/internal/model/evaluator) | Partial | `Fragrance.data_source`, `SourceSnapshot.verification_status` | Provenance is per-fragrance, not per-fact (a note or accord inherits the parent's single source rather than having its own) | Acceptable for now; revisit per-fact provenance only if D1 needs finer granularity | P2 |
| IV | Perfumer (relational, multi, provenance) | Complete | `Perfumer`, `VersionPerfumer` | No `confidence` column (optional per spec) | Add optional `confidence` to `VersionPerfumer` only if analysis needs it | P2 |
| V | Notes: normalized vocabulary, position, provenance | Partial | `Note`, `FragranceNote` | No alias/synonym table, no parent hierarchy beyond one category/subcategory pair; ADR-006 already schedules this for milestone D1 | Defer to milestone D1 as planned; do not duplicate | P2 |
| V | Accords: controlled taxonomy separate from notes | Partial | `FragranceAccord.accord_type` (free string) | No lookup table; any string is accepted; no source/confidence per accord row | Add `accord_types` reference table (code/label/sort_order/active), non-breaking | P0 |
| V | Ingredients distinct from notes | Complete (N/A) | Not modeled | No ingredient data exists in the system; nothing to conflate | No action: correctly out of scope | N/A |
| VI | Structured backend sensory/structural features (sweetness, freshness, etc. as *published* facts) | Missing | Only evaluator-perceived sensory fields exist, and only inside `Observation.responses` (controlled workflow) | No entity holds a backend/reference feature value distinct from evaluator perception | Add `FeatureDefinition`/`FeatureValue` (or defer until D1/D2 needs it) | P1 |
| VII | Performance (longevity/projection/sillage/intensity): backend vs. evaluator-observed | Partial | `Evaluation.longevity_rating`/`sillage_rating` (evaluator, ordinary); `Observation.projection`/`longevity_minutes` (evaluator, controlled, buried in JSON) | No backend/reference performance estimate anywhere; evaluator-observed values exist but are split across two differently-scaled, differently-stored places | Promote controlled performance fields to typed columns (see Risk 1); do not add backend reference estimates until a source for them exists | P0 (typed columns) / P2 (backend estimates) |
| VIII | Multiple classification systems | Missing | `Fragrance.primary_family`/`subfamily` (hard-coded Michael Edwards Wheel strings) | No `ClassificationSystem` entity; only one taxonomy, unversioned | Introduce `ClassificationSystem` + `FragranceClassification` mapping before D1 external taxonomies are ingested | P1 |
| IX | Evaluator identity, not a taste-profile-of-record | Complete | `Reviewer` | None: no stored "current taste profile" field exists; profile is correctly always derived | N/A | N/A |
| X | Encounter as atomic observation (no destructive overwrite) | Complete | `Evaluation` (ordinary), `Observation` (controlled) | None: verified in `evaluation_service.py` and the `Observation` docstring ("append-only... no update route") | N/A | N/A |
| XI | Familiarity, recorded per encounter | **Needs clarification** | `Observation.familiarity` (0-5 int, controlled only) | Numeric scale does not map cleanly to the required categorical states (never/smelled/sampled/worn/owned/formerly owned/unknown); does not exist at all on ordinary `Evaluation` | Add a controlled `familiarity` code column to both `evaluations` and (replacing the ambiguous int) `calibration_observations` | P0 |
| XII | Protocol/experiment types | Complete | `Membership.role` | Role vocabulary differs slightly from the requirement's suggested list (e.g. no explicit "universal baseline" vs. "ordinary encounter" vs. "comparison" split) but is extensible and covers the essential distinctions (baseline/hidden repeat/holdout/active learning/retest/owned validation) | No change required; extend `Role` literal only if a new protocol type is actually needed | P2 |
| XII | Blindness/information-state | Complete | `Enrollment.revealed_at`, disclosure-policy service (per ADR-005) | None material for current scope | N/A | N/A |
| XII | Presentation metadata (container, sprays, application time, order, randomization) | Partial | `Presentation.position`; stage (`BLOTTER`/`SKIN`) | Sprays, application time, container/delivery format not modeled | Add optional columns only if a controlled protocol needs them; not currently blocking | P2 |
| XIII | Experiment as first-class entity | Complete | `Program`, `Membership` | None | N/A | N/A |
| XIV | Dataset role / leakage prevention | Complete | `Membership.role = HOLDOUT"`, `PreferenceHistoryService.excluded_versions()`, ADR-009 checkpoint-freeze rule | None: holdouts are declared prospectively and structurally excluded, matching the strongest form of this requirement | N/A | N/A |
| XV | Core preference (liking) separate from descriptive rating | Complete | `Evaluation.rating` (1-5), `Observation.liking` (0-10) | None: liking is already distinct from descriptive note/accord data | N/A | N/A |
| XV | Evaluator confidence on overall liking | Partial | `Observation.confidence` (0-5 int, buried in JSON) | Not a first-class column; not present on ordinary `Evaluation` at all | Promote to typed column (controlled); optionally add to ordinary evaluations | P0 (controlled) / P2 (ordinary) |
| XVI | Temporal (opening/mid/drydown) liking | Partial | `Observation.opening_liking`/`drydown_liking` (buried in JSON); `elapsed_minutes` gives a real timestamp reference | Not first-class columns | Promote to typed columns (Risk 1 fix) | P0 |
| XVII | Published vs. evaluator-perceived notes/accords | Partial | Published: `FragranceNote`/`FragranceAccord`. Perceived: `Observation.perceived_notes` (a free-text `list[str]`, buried in JSON) | Perceived notes are free strings, not linked to the `Note` vocabulary, so "did the evaluator perceive bergamot" cannot be joined against "is bergamot a published note" without text matching | Normalize `perceived_notes` into a join against `Note` (nullable "unmatched free text" fallback preserved) | P1 |
| XVIII | Evaluator-perceived sensory dimensions | Partial | `Observation.{sweetness,freshness,density,dryness,clean_soapy,earthy_rooty,bodily_animalic,discomfort}` (buried in JSON) | Not first-class columns | Promote to typed columns (Risk 1 fix) | P0 |
| XIX | Controlled positive/negative drivers ("too sweet" vs. "is sweet") | Missing | `Observation.likes`/`dislikes` (free text, buried in JSON) | No controlled vocabulary distinguishes a descriptive trait from an excess/deficiency judgment | Add a small controlled `evaluation_driver` vocabulary + junction table; keep free text as a supplement, not a replacement | P1 |
| XX-XXIX | Scenario/context domain in full (seasons, climate, occasion, desired effect, hypothetical suitability vs. actual wear context, scenario outcome, user-observed performance in context) | **Missing** | None | This entire domain does not exist in the schema, API, or frontend today | Add `Season`, `ClimateBand`, `Occasion`, `DesiredEffect` lookup tables; `ScenarioSuitability` (hypothetical) and `ActualWearContext` (observed) entities keyed to an encounter | P1 |
| XXX | Scrub-off event | Missing | Inferable only indirectly (`detected=False` + short `elapsed_minutes` + low/absent `liking`) | No explicit strong-negative label | Add optional `scrubbed_off` (bool) + `time_to_scrub_minutes` to the controlled observation once promoted to typed columns; do not infer from rating alone | P1 |
| XXXI | Pairwise preference as first-class entity | **Missing** | None (only inferable post hoc from independent numeric ratings) | No `A vs. B` record exists anywhere | Add `PairwiseComparison` entity | P1 |
| XXXII | Behavioral events (rewear, purchase funnel, wishlist, gift, finished, repurchase) | Partial | `RecommendationResponseRevision.sampling_state`/`would_wear`/`would_buy` (scoped to one recommendation impression only); repeat `Evaluation` rows are an implicit re-wear signal | No general-purpose behavioral-event log independent of a recommendation impression (e.g. a spontaneous repurchase, a gift given, a bottle finished, unprompted by any recommendation) | Add `BehavioralEvent` entity | P1 |
| XXXIII | Purchase intent (separate from liking, with format) | Partial | `RecommendationResponseRevision.would_buy` (bool, recommendation-scoped only) | No general intent scale (no/unlikely/maybe/likely/yes/already owned), no format (sample/decant/travel/bottle) | Add `purchase_intent` code + `purchase_format` code to `BehavioralEvent`, generalized beyond recommendations | P1 |
| XXXIV | Raw free-text comments preserved even with LLM extraction | Complete (N/A) | `Evaluation.notes`, `Observation.{likes,dislikes,reminds_me_of,comments}` | No LLM extraction pipeline reads or rewrites evaluator comments today, so nothing currently violates the requirement; but comments are currently buried in the `responses` JSON on the controlled side, which the same Risk 1 fix should preserve as-is (typed `Text` columns, not deleted) | Carry raw-text columns forward unchanged when promoting `responses` fields | P0 (as part of Risk 1 fix) |
| XXXV | Missingness vs. zero vs. not-asked/skipped/unsure/N-A | Partial | Controlled: NULL = unanswered, documented explicitly in the tech spec ("Answered zero is data... non-detection has intensity zero and no liking score"). Ordinary: NULL used the same way for optional fields. | No explicit `NOT_ASKED`/`SKIPPED`/`UNSURE`/`UNABLE_TO_EVALUATE` distinction; all collapse to NULL today | Acceptable for current UI (quick-rating vs. structured-diagnostic distinction already governs which fields are asked); revisit only if analysis needs to distinguish "not asked" from "skipped" | P2 |
| XXXVI | Confidence (selected subjective fields) | Partial | `Observation.confidence` (single generic field, buried in JSON, controlled only) | Not per-field (not available for note identification, scenario fit, or pairwise comparisons, since pairwise comparisons do not exist yet) | Promote existing field to a typed column; add `confidence` to `PairwiseComparison` when introduced | P0 (existing field) / P1 (new entities) |
| XXXVII | Prediction snapshots (immutable, pre-observation) | Partial | `ModelCheckpoint.predictions` (JSON list, immutable per ADR-009); `RecommendationImpression` (immutable, typed, per-fragrance); the new, standalone `PredictionSnapshot` entity (implemented; calibration-side predicted ratings; see ADR-010) | `RecommendationImpression` already satisfies most of this requirement for ranking output, and the new `PredictionSnapshot` entity now covers frozen calibration-side predicted ratings. `ModelCheckpoint.predictions` itself is still a JSON blob, not one row per fragrance/model/uncertainty | Decompose `ModelCheckpoint.predictions` into typed rows (the deferred "`ModelCheckpoint.predictions` decomposition," distinct from the already-implemented `PredictionSnapshot` entity) once a second consumer of typed predictions exists (currently only D5 needs this) | P1 |
| XXXVIII | Recommendation records | Complete (with one gap) | `RecommendationRun`/`RecommendationImpression`/`RecommendationResponseRevision` | `candidate_strategy` does not yet distinguish recommendation *type* (likely-to-love/diagnostic/exploratory/challenge/scenario-specific/value/group); only one strategy literal exists today | Extend `candidate_strategy`/add `recommendation_type` when milestone D4 introduces more than one strategy | P2 (tracked by milestone D4) |
| XXXIX | Selection objective (EXPLOIT/EXPLORE/INFORMATION_GAIN/...) | Missing | `candidate_strategy` literal | No objective taxonomy exists; not needed until more than one candidate strategy exists | Add when milestone D4 is implemented | P2 (tracked by milestone D4) |
| XL | Training eligibility / data quality status | Partial | `Membership.role` (`HOLDOUT` etc.) fully covers calibration eligibility; no equivalent status exists for ordinary `Evaluation` rows | An ordinary encounter cannot be marked `WITHHELD`/`INVALIDATED`/`QUESTIONABLE` (e.g., a contaminated sample) | Add optional `training_eligibility` code to `evaluations`, default `ELIGIBLE` | P1 |
| XLI | Feature/taxonomy versioning | Partial | `algorithm_version`, `score_type`, `prompt_version` strings exist as ad hoc version tokens; ADR-006 already commits to versioned alias/taxonomy mappings for milestone D1 | No `TaxonomyVersion`/`FeatureSchemaVersion` entity yet | Implement as scoped in milestone D1; do not duplicate ahead of it | P2 (tracked by milestone D1) |
| XLII | Facts vs. derived vs. inferred distinguishable | Partial (structural, not explicit) | Table/module boundaries already separate raw observation (`Evaluation`/`Observation`) from derived scoring (`recommendation_service.py`) from model inference (`ModelCheckpoint`/`RecommendationImpression`) | No explicit `value_type` flag exists anywhere, but none is currently needed; the separation is real and enforced by which table a value lives in | No action; do not add a formal flag without a concrete cross-cutting query need | P2 |
| XLIII | Embeddings with metadata | Missing | Not modeled | Correctly out of current scope; no embeddings are produced anywhere in the codebase yet | Defer; design an `Embedding` entity only when milestone D2/D3 first needs one | P2 |
| XLIV-XLV | Layered frontend UX on shared backend; multi-select/single-select/numeric/free-text control types | Partial | Quick-rating (`Evaluation`) and controlled-diagnostic (`Observation`) workflows already exist as genuinely different frontend surfaces over related backend concepts | The scenario domain (XX-XXIX) has no UI surface yet because it has no backend surface yet | Build UI once the underlying scenario/pairwise/behavioral-event tables exist | P1/P2 (follows backend work) |
| XLVI | First-class-variable test applied consistently | Partial | Most catalog/experiment concepts pass this test already | `Observation.responses` JSON is the one clear violation: `would_wear`, `would_buy`, `opening_liking`, `drydown_liking`, sensory dimensions, `perceived_notes`, and `confidence` are all filterable/aggregable/ML-relevant variables currently sitting in an opaque blob | Fix as Risk 1 (§3) | P0 |
| XLVII | ML outputs the model must eventually support | Partial | Deterministic affinity scoring (ADR-004/007); `RecommendationImpression` for ranking measurement | Intrinsic "Like given User and Fragrance" scoring exists; contextual, pairwise, wear-probability, and purchase-behavior targets have no input data to train on yet | Direct consequence of closing the P1 items above (scenario, pairwise, behavioral events, typed sensory/temporal fields) | P1 |
| XLVIII | Avoid premature overengineering | Complete | N/A | The existing team has already resisted building active learning, collaborative filtering, or a feature store ahead of need (confirmed by ADR-009 and the milestone plan explicitly deferring these to post-D5 decisions) | No action: hold this discipline for the recommendations below too | N/A |

---

## 3. Modeling Risks

1. **Rich controlled-observation data is buried in an untyped JSON column (highest-priority risk).**
   `calibration_observations.responses` currently holds `confidence`, `sweetness`, `freshness`,
   `density`, `familiarity`, `dryness`, `clean_soapy`, `earthy_rooty`, `bodily_animalic`,
   `discomfort`, `opening_liking`, `drydown_liking`, `would_wear`, `would_buy`,
   `artistic_appreciation`, `projection`, `longevity_minutes`, `perceived_notes`, `likes`,
   `dislikes`, `reminds_me_of`, and `comments`: every one of these passes the "first-class
   variable" test in §XLVI (they are already validated, bounded, and clearly intended to be
   filtered/aggregated/used as ML features/labels), yet none of them can be indexed, constrained,
   filtered in SQL, or joined today. `PreferenceHistoryService.training_manifest()` forwards the
   raw blob straight into the frozen ML-facing manifest (`preference_history.py:139`), so the
   "immutability" ADR-009 promises for checkpoints does not currently extend to stable, named
   fields inside that blob; a future consumer must still parse an unversioned dict shape. This
   is squarely the situation §XLVI warns against, and it is actively accumulating: every
   controlled observation recorded before this is fixed becomes historical data that needs a
   backfill rather than a clean read.
2. **Physical-sample/source provenance is free-form JSON, not typed fields.**
   `Membership.selection` (`dict[str, str | float | None]`) is the closest thing to "physical
   sample provenance" today (vendor, source type, volume, batch, container). Milestone P1.1
   ("Exact baseline manifest") explicitly requires physical-sample confirmation before program
   assignment, so this JSON dict is about to become load-bearing for real baseline data
   collection without ever having been reviewed as a controlled vocabulary.
3. **`accord_type` and `brand` are uncontrolled strings feeding ML features.**
   `preference_history.py` reads `fragrance.accords` (`accord_type`, free string) straight into
   the frozen `source_features` payload used for scoring. Any spelling drift between the manual,
   Kaggle, and Parfumo ingestion paths (already documented as a real risk in `core/vocabulary.py`'s
   own doc comment, which fixed exactly this class of bug for `gender_target`) will silently
   fragment what should be the same accord or brand into multiple values.
4. **Familiarity is an ambiguous numeric scale that doesn't exist on ordinary encounters at all.**
   `Observation.familiarity` (0-5 int) does not map onto the required categorical states (never
   smelled / sampled / worn / owned / formerly owned / unknown), and ordinary `Evaluation` rows
   have no familiarity concept whatsoever, yet familiarity is explicitly time-varying (§XI) and
   is exactly the kind of variable that would silently bias a "first exposure" model if left
   unrecorded on the far larger volume of ordinary encounters.
5. **No first-class scenario/context data exists anywhere.** Every claim in §XX-XXIX
   (hypothetical suitability vs. actual wear context, season, climate, occasion, desired effect,
   scenario outcome) is currently unimplementable without a schema change. This is a real gap
   relative to the roadmap's stated ML outputs (`P(Like | User, Fragrance, Scenario)`,
   `P(Wear | ...)`), but it is not a defect in what exists: the team has correctly not
   pre-built a scenario UI ahead of a backend for it.
6. **Pairwise comparisons and general behavioral events do not exist.** Both are prerequisites
   named directly in the roadmap's stated future ML outputs (`P(A>B | ...)`, revealed-preference
   modeling from re-wears/purchases). Neither can be retrofitted from existing tables without
   guessing: pairwise preference cannot be reconstructed after the fact from two independent
   numeric ratings, and a rewear/repurchase/gift event is not the same signal as a repeated
   ordinary rating.
7. **No data-leakage risk currently found in the holdout mechanism.** This is a positive finding
   worth stating explicitly given how much of this review is about gaps: `Membership.role =
   'HOLDOUT'` plus `PreferenceHistoryService.excluded_versions()` plus the ADR-009 rule that
   closes checkpoint creation after any holdout response together implement the requirement
   correctly today. No change is recommended here.
8. **No reproducibility risk currently found in recommendation predictions.**
   `RecommendationImpression` rows are immutable, uniquely constrained per `(run, fragrance)`,
   and store `score_type`/`score_value`/`rank`/`explanation_version` at the time shown: a
   genuine prediction snapshot for the ranking side of the system. The gap is narrower than it
   first appears: only `ModelCheckpoint.predictions` (used for calibration-side checkpoints) is
   still a JSON blob rather than typed rows.
9. **Historical data that could become unusable for ML if left alone**: every `Observation` row
   recorded between now and whenever Risk 1 is fixed will need a backfill migration rather than
   a clean read. The cost of leaving this unfixed grows with every day of real (milestone P1/F1)
   data collection, which is the basis for this review's P0 priority on Risk 1 specifically.
10. **No risk found distinguishing published vs. evaluator-perceived characteristics at the
    accord/family level**: `FragranceAccord`/`primary_family`/`subfamily` are unambiguously
    "published" (attached to `Fragrance`), and `Observation.perceived_notes`/sensory fields are
    unambiguously evaluator-side. The only weakness is that perceived notes are free text rather
    than linked to the `Note` vocabulary (§XVII), which is a normalization gap, not a conflation
    risk.

---

## 4. Proposed Target Entity Model

Names below reuse existing repository entities wherever they already fill a role, and introduce
new entities only where §2 found a **Missing** or structurally inadequate **Partial**. Existing
names are kept (no renaming of `Fragrance`, `Evaluation`, `Reviewer`, `Program`, `Membership`,
etc.) to honor "prefer extending existing structures" and avoid an unnecessary rename migration.

```text
Brand (new) ──< Fragrance (existing; = Fragrance + FragranceVariant per ADR-006)
                   │
                   ├──< FragranceNote >── Note (existing)
                   ├──< FragranceAccord >── AccordType (new lookup)
                   ├──< VersionPerfumer >── Perfumer (existing)
                   ├──< FragranceClassification (new) >── ClassificationSystem (new)
                   └──< SourceSnapshot (existing)

Reviewer (existing)
   │
   ├──< Evaluation (existing; ordinary Encounter+Evaluation)
   │       + familiarity code (new column)
   │       + training_eligibility code (new column)
   │
   ├──< Program >── Membership >── Enrollment >── CalibrationSession >── Presentation (existing)
   │                   (Experiment)  (ExperimentAssignment)                  │
   │                     + PhysicalSample fields (new, on Membership/Presentation)
   │                                                                          └──< Observation (existing; controlled Encounter+Evaluation)
   │                                                                                 + typed columns replacing `responses` JSON (Risk 1 fix)
   │                                                                                 + scrubbed_off / time_to_scrub_minutes (new)
   │
   ├──< ScenarioSuitability (new; hypothetical, keyed to an Evaluation or Observation)
   │       >── Season / ClimateBand / Occasion / DesiredEffect (new lookups, multi-select)
   │
   ├──< ActualWearContext (new; observed, keyed to an Evaluation or Observation)
   │       + scenario outcome fields
   │
   ├──< PairwiseComparison (new)
   │
   ├──< BehavioralEvent (new; rewear/wishlist/purchase-funnel/gift/finished/repurchase)
   │       + purchase_intent / purchase_format codes
   │
   ├──< RecommendationRun >── RecommendationImpression >── RecommendationResponseRevision (existing)
   │
   └──< ModelCheckpoint (existing) ──< ModelCheckpoint.predictions decomposition (deferred; distinct from the implemented `PredictionSnapshot` entity; P1, only once a second consumer needs typed rows)
```

Deliberately **not** introduced now (see §2/§3 for rationale): a separate `FragranceVariant`
table (ADR-006 defers this through milestone D5), a general `PhysicalSample` table as a full
first-class entity (typed columns on the existing `Membership`/`Presentation` rows are enough
until sample tracking outgrows one program), an `Embedding` table (nothing produces embeddings
yet), and a `TaxonomyVersion`/`FeatureSchemaVersion` entity ahead of milestone D1 (which already
owns this).

---

## 5. Controlled Vocabulary Plan

| Vocabulary | Lookup table vs. enum | Initial values | Stable code | Sort/active | Priority |
| :--- | :--- | :--- | :--- | :--- | :--- |
| Concentrations | Keep as free string (already effectively a code: `EDT`/`EDP`/`Parfum`/etc.); do not force a lookup table given ADR-006's "unknown concentration remains unknown" rule | n/a | n/a | n/a | P2 |
| Sample/source types | New lookup (`sample_source_types`) | manufacturer sample, official discovery set, retailer sample, decant, owned bottle, unknown | snake_case code | sort_order, active | P0 |
| Container/delivery format | New lookup (`sample_containers`) | spray atomizer, dab vial, rollerball, retail bottle | snake_case code | sort_order, active | P0 |
| Experimental protocols | Existing `Membership.role` Literal | already covers baseline/hidden repeat/holdout/active learning/retest/owned validation | Python `Literal` (matches existing pattern) | n/a (extend literal only if needed) | P2 |
| Blindness states | Existing `Enrollment.revealed_at` + disclosure-policy service | fully blind / revealed | n/a | n/a | N/A |
| Fragrance phases | Existing `Observation.stage`/`phase` | blotter/skin; pre/post reveal | n/a | n/a | N/A |
| Accords | New lookup (`accord_types`) | woody, aromatic, citrus, green, floral, rose, white floral, fruity, aquatic/marine, amber, vanilla/vanillic, musk, powdery, gourmand, spicy, leathery, smoky, resinous, earthy, animalic, mineral, soapy, aldehydic; seeded from the distinct values already in `fragrance_accords` | snake_case code | sort_order, active | P0 |
| Sensory dimensions | Existing `Observation` fields (promote to typed columns) | sweetness, freshness, density, dryness, clean_soapy, earthy_rooty, bodily_animalic, discomfort (already validated 0-5 in `ResponseInput`) | Python attribute names (already stable) | n/a | P0 |
| Positive/negative drivers | New lookup (`evaluation_drivers`) + junction | too sweet/too dry/too powdery/.../unpleasant note/unwanted association/performance issue/other, with a `polarity` (positive/negative) and `is_intensity_complaint` flag to keep "is sweet" distinct from "too sweet" | snake_case code | sort_order, active | P1 |
| Seasons | New lookup (`seasons`) + junction, multi-select | Spring, Summer, Fall, Winter | snake_case code | sort_order, active | P1 |
| Climate bands | New lookup (`climate_bands`) + junction, multi-select, separate from season | hot, warm, mild, cool, cold | snake_case code | sort_order, active | P1 |
| Occasions | New lookup (`occasions`) + junction, multi-select | Casual/Everyday, Work/Office, School, Date Night, Social/Night Out, Formal Event, Gym/Exercise, Outdoors, Travel, Home/Relaxing, Bedtime, Special Occasion | snake_case code | sort_order, active | P1 |
| Desired effects | New lookup (`desired_effects`) + junction, multi-select | clean, fresh, energetic, relaxed, comforting, confident, professional, elegant, romantic, sexy, playful, distinctive, bold, understated, luxurious | snake_case code | sort_order, active | P1 |
| Projection/performance bands | Existing numeric fields (`intensity`, `projection`, `longevity_minutes`); add a display-band mapping in the API layer rather than a stored column, since the underlying numeric value is the fact and the band is derived | n/a | n/a | n/a | P2 |
| Familiarity | New controlled code, replacing the ambiguous `Observation.familiarity` int and adding the same code to `Evaluation` | never_smelled, smelled_before, sampled_before, worn_before, currently_owned, formerly_owned, unknown | snake_case code | sort_order, active | P0 |
| Confidence | Single shared scale wherever confidence appears | low, medium, high | snake_case code | sort_order | P0 (promote existing) / P1 (new entities) |
| Behavioral event types | New lookup (`behavioral_event_types`) | sampled, wore, rewore, wishlisted, removed_from_wishlist, bought_sample, bought_decant, bought_travel, bought_bottle, finished_sample, finished_bottle, repurchased, gifted, sold, gave_away | snake_case code | sort_order, active | P1 |
| Recommendation objectives (selection objective) | New lookup, only when milestone D4 introduces more than one strategy | EXPLOIT, EXPLORE, INFORMATION_GAIN, VALIDATION, HOLDOUT, BOUNDARY_TEST, COUNTEREXAMPLE | UPPER_SNAKE code (matches existing `sampling_state` convention) | n/a | P2 (tracked by milestone D4) |
| Dataset roles | Existing `Membership.role` (calibration); add `training_eligibility` for ordinary `Evaluation` (see §2 row XL) | see protocol row above | n/a | n/a | P1 |

All new lookup tables follow the repository's existing conventions: `id` (UUID string,
matching every other table), `code` (stable, snake_case, never renamed), `display_label` (may
change freely), `sort_order` (int), `active` (bool, default true; deactivate rather than
delete so historical rows referencing an old code remain valid). This directly satisfies §XLI
("stable backend codes should remain stable even if UI labels change") without introducing a
new pattern the codebase doesn't already use (`core/vocabulary.py` establishes the precedent for
simple cases; a table is warranted here because these vocabularies are expected to grow and be
managed data, not just a fixed compile-time `Literal`).

---

## 6. Migration Plan

All migrations below are additive and preserve every existing row, following the same pattern
already used in this repository's own migration history (e.g. `d3c65c9cf212_add_soft_delete...`,
`5d2e7c9f9c92_add_surrogate_pk_to_fragrance_notes...`): add nullable columns/tables first,
backfill, then tighten constraints only where safe.

**Sequence (P0, before controlled baseline data collection scales up under milestone P1/F1):**

- **Step 1 (IMPLEMENTED, migration `9ded7f54996c`): add typed columns to
  `calibration_observations`** for `confidence`, `sweetness`, `freshness`, `density`,
  `familiarity` (kept as the original numeric scale here; superseded by the new controlled code
  proposed in step 2 below, which remains unimplemented), `dryness`, `clean_soapy`,
  `earthy_rooty`, `bodily_animalic`, `discomfort`, `opening_liking`, `drydown_liking`,
  `would_wear`, `would_buy`, `artistic_appreciation`, `projection`, `longevity_minutes`, `likes`
  (Text), `dislikes` (Text), `reminds_me_of` (Text), `comments` (Text). Together with
  `perceived_notes` (also part of this step; see below), this is 22 typed columns in total: 17
  carry database-level CHECK-constraint bounds, and the remaining 5 (the four Text columns above
  plus the JSON `perceived_notes`) are validated at the API layer only, not at the database
  level. As actually shipped, the
  legacy `responses` (JSON) column is **not** kept as an audit copy: every existing row is
  backfilled from it into the new typed columns (validating each value against its column's
  bound first and leaving an individual field NULL with a printed warning naming the row and
  field, rather than aborting the whole migration, if a legacy value predates that bound, for
  example from a since-tightened API validator), and the column is dropped in the same migration.
  This
  was judged safe because no accumulated production history exists yet to preserve a dual-write
  window for (see the current-state ledger); do the same backfill-then-drop only when that same
  condition holds for a future migration. `perceived_notes` gets its own step (3) because it
  needs a join table, not a scalar column; it currently ships as a typed JSON array of free-text
  labels (also part of Step 1's implemented migration), not yet normalized.
- **Step 2 (NOT IMPLEMENTED): add a `familiarity` controlled-code column** to both
  `calibration_observations`
  (replacing the ambiguous int, after backfill/mapping) and `evaluations` (new, nullable, NULL =
  not asked). Add the `familiarity_states` lookup table.
- **Step 3 (NOT IMPLEMENTED): normalize `perceived_notes`** into a new
  `observation_perceived_notes` junction
  table against the existing `notes` table, keeping a nullable `raw_label` text column per row
  for any perceived term that does not match the controlled vocabulary (never silently dropped).
- **Step 4: add `brands` lookup table** + nullable `Fragrance.brand_id` FK. Backfill by grouping
  distinct existing `Fragrance.brand` strings; leave ambiguous/near-duplicate names unresolved
  (nullable `brand_id`) rather than guessing merges, per the "leave uncertain historical values
  null" instruction. Keep the `brand` string column and existing unique index untouched.
- **Step 5: add `accord_types` lookup table**, seeded from the distinct values already present
  in `fragrance_accords.accord_type`. Add it as a reference table only in this pass (no FK
  constraint yet on `fragrance_accords.accord_type`, to avoid a breaking migration if any
  existing row's value needs review first); tighten to an FK in a later, separately reviewed
  migration once the vocabulary is confirmed complete.
- **Step 6: add sample-provenance columns** to `calibration_memberships` and/or
  `calibration_presentations` (exact placement depends on whether provenance is per-membership
  or per-physical-unit; recommend per-`Presentation` since that is the concrete physical
  stimulus a session presents): `sample_source_type` (code, nullable), `sample_container` (code,
  nullable), `sample_volume_ml` (nullable), `sample_acquired_at` (nullable date),
  `sample_decanted_at` (nullable date), `sample_batch_code` (nullable string). Add the two new
  lookup tables from §5. Backfill from `Membership.selection` JSON where a value maps cleanly;
  leave the rest null.
- **Step 7: add `training_eligibility` code column** to `evaluations` (default `ELIGIBLE`), and
  the corresponding lookup table.

**Sequence (P1, before adaptive/ML work in milestones D1/D4/D5):**

- **Step 8**: add `seasons`, `climate_bands`, `occasions`, `desired_effects` lookup tables and
  their multi-select junction tables against `evaluations` and `calibration_observations`.
- **Step 9**: add `ScenarioSuitability` (hypothetical judgment: fit rating, wear-likelihood,
  confidence, linked to an encounter) and `ActualWearContext` (observed: actual
  occasion/season/climate band/numeric temperature/humidity band/indoor-outdoor/time-of-day/
  formality/activity level, plus scenario-outcome fields: expectation-vs-actual label,
  would-wear-again).
- **Step 10**: add `evaluation_drivers` lookup table + junction (positive/negative reasons,
  with a polarity and an "is this an intensity complaint" flag).
- **Step 11**: add `PairwiseComparison` (evaluator, two encounter/fragrance references,
  preferred/tie, dimension, strength, confidence).
- **Step 12**: add `BehavioralEvent` (evaluator, fragrance/variant reference, event type,
  occurred_at, optional format/quantity, recorded_by), generalizing the recommendation-scoped
  `would_wear`/`would_buy`/`sampling_state` already on `RecommendationResponseRevision` (which
  stays as-is: it answers "what happened to this specific recommendation," a narrower and
  still-useful question `BehavioralEvent` does not replace).
- **Step 13**: add `ClassificationSystem` + `FragranceClassification` mapping table so
  `primary_family`/`subfamily` become one row in a versioned, pluggable system rather than the
  only system; keep the existing string columns as the default system's materialized values so
  no existing query breaks.
- **Step 14**: add `scrubbed_off`/`time_to_scrub_minutes` to the now-typed
  `calibration_observations`.

**Deferred (P2, tracked by an existing milestone or genuinely not yet needed):**

- `FeatureDefinition`/`FeatureValue` for backend-published sensory features (no source of this
  data exists yet).
- `ModelCheckpoint.predictions` decomposition (deferred; distinct from the already-implemented,
  standalone `PredictionSnapshot` entity described in ADR-010): single JSON consumer
  today; revisit when milestone D5 needs typed rows.
- `TaxonomyVersion`/alias tables (explicitly milestone D1's job; do not duplicate ahead of it).
- Recommendation `selection_objective` taxonomy (milestone D4's job; only one candidate strategy
  exists today).
- Any `FragranceVariant` split from `Fragrance` (ADR-006 governs; would need its own ADR to
  reopen).
- `Embedding` storage (nothing produces embeddings yet).

Every migration above is purely additive (new nullable columns/tables) except step 5's eventual
FK-tightening follow-up, which is explicitly called out as a separate, later, reviewed migration.
None of them touch `evaluations.rating`, `Observation.liking`/`intensity`/`detected`, soft-delete
semantics, or any existing unique constraint; all currently-passing tests and all existing rows
remain valid throughout.

---

## 7. API and Frontend Impact

- **API schemas** (`schemas/calibration.py`): `ResponseInput` keeps its current field set and
  validation (`ge`/`le` bounds are already correct); only the *storage* target of each field
  changes from "one key in a JSON dict" to "one typed column." This is the rare migration where
  the request/response contract at the API boundary does not need to change at all; only
  `calibration_service.py`'s persistence code and `preference_history.py`'s manifest assembly
  change. `perceived_notes` gains a resolved/unresolved split in the response (matched note IDs
  vs. raw unmatched labels) once normalized.
- **ORM models**: `Observation` gains the typed columns in §6 step 1; `Evaluation` gains
  `familiarity` and `training_eligibility`; `Fragrance` gains `brand_id`; `FragranceAccord` gains
  no column changes in the P0 pass (only a new sibling lookup table). New models are added for
  every new entity in §4/§6, following existing conventions (`String(36)` UUID PKs via a shared
  `identifier()`/`uuid4()` helper, `ondelete="RESTRICT"` for anything append-only/auditable,
  `ondelete="CASCADE"` only for genuinely dependent rows like existing note/accord junctions).
- **Validation**: new `StrictInput`-style Pydantic models (`extra="forbid"`) for every new
  request shape, matching `schemas/calibration.py`'s existing pattern, so a typo'd field is
  rejected at the API boundary rather than silently dropped.
- **Frontend types** (`frontend/src/api/types.ts`): `Observation` type gains the newly-typed
  fields (currently it only exposes `phase`/`stage`/`elapsed_minutes`/`liking`/`comments`, even
  narrower than the backend's JSON blob today, so this is a net expansion of what the UI *can*
  show, not a breaking change to what it already shows). New types for `ScenarioSuitability`,
  `ActualWearContext`, `PairwiseComparison`, `BehavioralEvent` are added only alongside their
  first UI surface (milestone P1/adaptive work), not speculatively.
- **Filtering/search**: `FragranceSearchParams` is unaffected in the P0 pass. Once `brand_id`
  and `accord_types` exist, search can optionally filter by them without removing the existing
  free-text `brand`/`primary_family` filters.
- **Import/export**: `kaggle_importer.py` and `parfumo_scraper.py` continue writing the existing
  string `brand`/`accord_type` columns unchanged; they may optionally also resolve/create a
  `brand_id` once that table exists, but this is not required for the P0 migrations to be safe.
- **Recommendation interfaces**: no change required for the P0 pass. `RecommendationRun`/
  `RecommendationImpression`/`RecommendationResponseRevision` already satisfy the immediate
  requirements; only the P2-tracked `selection_objective`/`recommendation_type` work (owned by
  milestone D4) touches this surface.

Ordinary quick-rating workflows (`POST /evaluations`) are untouched by every P0 migration in this
plan: the new columns land on `calibration_observations`, `evaluations` (additively), and new
tables, none of which change the existing `EvaluationCreate`/`EvaluationResponse` contract's
required fields.

---

## 8. Testing Requirements

Recommended tests, mapped to the task's required proof points:

1. **Multiple encounters retained**: extend `tests/unit/test_services` (or add an integration
   test) asserting two `POST /evaluations` for the same `(reviewer_id, fragrance_id)` produce two
   distinct rows with distinct `id`s and both remain readable after the second POST.
2. **Hidden repeat references its group without revealing identity**: assert a `Presentation`
   whose `Membership.role == "HIDDEN_REPEAT"` and `repeat_of_id` set is excluded from
   `PreferenceHistoryService.training_manifest()` while a non-repeat, non-holdout member of the
   same fragrance is retained; assert the participant-facing API never exposes `repeat_of_id` or
   `role` (extends the existing disclosure-matrix test family from milestone P1.7).
3. **Holdout withheld from training**: assert `PreferenceHistoryService.excluded_versions()`
   contains a fragrance with an active `HOLDOUT` membership, and that `training_manifest()` omits
   any row for that fragrance even when an eligible ordinary or controlled observation exists.
4. **EDT/EDP evaluated independently**: assert two `Fragrance` rows sharing `name`/`brand` but
   differing `concentration` each accept their own `Evaluation` rows and each appears
   independently in `PreferenceHistoryService` output (already implied by the existing
   `uq_fragrance_version` index; add an explicit regression test if one does not already exist).
5. **Published vs. perceived accords/notes cannot be conflated**: assert `FragranceAccord`
   (published) and the new typed `Observation.perceived_notes`/sensory columns (perceived) are
   read from different tables/columns in `preference_history.py`'s `source_features` (published)
   vs. `responses`-derived (perceived) payload, and that a test fixture with deliberately
   different published-vs-perceived values for the same fragrance shows both values distinctly
   in the API response.
6. **Seasons/occasions support multiple selections**: once §6 step 8 lands, assert the junction
   tables accept more than one row per encounter and that no comma-delimited string
   representation is used anywhere in the request/response/storage path.
7. **Hypothetical suitability vs. actual wear context are distinct**: once §6 step 9 lands,
   assert `ScenarioSuitability` and `ActualWearContext` are separate tables/routes and that
   writing one never mutates or is inferable from the other.
8. **Prediction snapshots survive later model updates**: extend the existing ADR-009 checkpoint
   tests: create a `ModelCheckpoint`, then change reviewer evidence or re-run scoring, and assert
   the original checkpoint's `manifest`/`predictions` are byte-for-byte unchanged on re-read.
9. **Historical evaluations are not overwritten**: assert `PATCH /evaluations/{id}` changes only
   the targeted row's mutable fields and never creates or deletes a sibling row; assert
   `evaluated_at`/`created_at`/`id` are stable across a PATCH.
10. **Raw comments survive any future LLM extraction**: once an extraction pipeline exists, add
    a test asserting the original `Evaluation.notes`/`Observation.comments` text is byte-for-byte
    unchanged after an extraction run, with extracted structure stored in a separate table
    carrying `source_comment_id`/model/version/timestamp. (No such pipeline exists yet; this test
    should be added alongside the first PR that introduces one, not before.)
11. **Missing values are not converted into zeros**: extend the existing detection-validator
    test (`ResponseInput.validate_detection`) to also cover the newly-typed columns once
    promoted: assert a NULL `opening_liking`/`would_wear`/etc. round-trips as NULL through the
    API and database, never as `0` or `false`.
12. **Controlled vocabularies retain stable codes if labels change**: for each new lookup table
    in §5, add a test that updates a row's `display_label` and asserts every row referencing its
    `code` (via FK or stored code string) is unaffected, and that querying by `code` still
    resolves correctly.

All new tests should run against PostgreSQL where they exercise a constraint, migration, or
concurrent-write behavior, per the existing "Definition of Done" in the Project Plan (§19)
requiring PostgreSQL-specific behavior to be tested in PostgreSQL, not only SQLite.

---

## Final Output

### A. Current Readiness

**YES, WITH REQUIRED CHANGES.**

The existing architecture is unusually well-prepared for this roadmap relative to a typical
"add a rating field" fragrance app: encounters are already atomic and non-destructive (§X),
experiments/holdouts/blind state are already first-class and structurally leak-proof (§XII-XIV),
source and perfumer provenance are already relational (§III-IV), and recommendation
impressions/outcomes are already immutable and auditable (§XXXVII-XXXVIII). None of the most
architecturally expensive problems (a single mutable rating per fragrance, no holdout concept, no
provenance model) are present.

However, the schema should **not** begin scaling up real controlled baseline data collection
(milestone P1.1 / F1) without the P0 changes in §6, because the single largest concrete risk this
review found, `calibration_observations.responses` burying `would_wear`, `would_buy`,
opening/drydown liking, sensory dimensions, perceived notes, and confidence inside one untyped
JSON column, then forwarding that blob unchanged into the frozen ML training manifest, gets more
expensive to fix for every day of data collected under the current shape. Fixing it now is a
small, purely additive, backward-compatible migration; fixing it after months of real family pilot
data would require an irreversible-feeling backfill of production history.

### B. Required Before Baseline (P0)

- Promote `calibration_observations.responses` JSON fields to typed, constrained columns
  (§6 step 1): the single highest-priority item in this review.
- Add a controlled `familiarity` code to both `evaluations` and `calibration_observations`
  (§6 step 2).
- Normalize `perceived_notes` against the `Note` vocabulary (§6 step 3).
- Add `brands` lookup + `Fragrance.brand_id` (§6 step 4).
- Add `accord_types` lookup table, non-breaking (§6 step 5).
- Add typed physical-sample-provenance columns to replace ad hoc `Membership.selection` JSON
  keys (§6 step 6).
- Add `training_eligibility` to `evaluations` (§6 step 7).

### C. Required Before Adaptive Sampling / ML (P1)

- Full scenario/context domain: seasons, climate bands, occasions, desired effects,
  `ScenarioSuitability` vs. `ActualWearContext`, scenario outcomes (§6 steps 8-9).
- Controlled positive/negative driver vocabulary, distinct from plain descriptive traits
  (§6 step 10).
- `PairwiseComparison` as a first-class entity (§6 step 11).
- `BehavioralEvent` generalized beyond recommendation-scoped outcomes, with purchase
  intent/format (§6 step 12).
- `ClassificationSystem`/`FragranceClassification` to support more than one taxonomy
  (§6 step 13).
- `scrubbed_off` explicit negative-behavior label (§6 step 14).

### D. Safe to Defer (P2)

- Splitting `FragranceVariant` out of `Fragrance` (governed by ADR-006; would need its own ADR
  to reopen).
- A full `PhysicalSample` entity beyond typed columns on `Membership`/`Presentation`.
- `FeatureDefinition`/`FeatureValue` for backend-published sensory characteristics (no data
  source for these exists yet).
- `ModelCheckpoint.predictions` decomposition (deferred; distinct from the already-implemented,
  standalone `PredictionSnapshot` entity described in ADR-010): defer until a second
  consumer needs typed rows, expected at milestone D5.
- Recommendation `selection_objective`/`recommendation_type` taxonomy (owned by milestone D4).
- `TaxonomyVersion`/alias/embedding infrastructure (owned by milestones D1-D3; do not duplicate
  ahead of them).
- Per-fact (rather than per-fragrance) source provenance granularity.

### E. Recommended Implementation Sequence

1. §6 steps 1-3 together, as one PR: promote `Observation.responses` to typed columns, add
   `familiarity`, normalize `perceived_notes`. These three are tightly coupled (all touch the
   same table and the same backfill script) and are the review's single highest-priority item.
2. §6 steps 4-5, as one PR: `brands` and `accord_types` lookup tables. Independent of step 1;
   can proceed in parallel if reviewed separately.
3. §6 steps 6-7, as one PR: physical-sample provenance columns and `training_eligibility`.
   Directly unblocks milestone P1.1's baseline-manifest requirement with typed data instead of
   free-form JSON.
4. Re-run the milestone P1 exit-gate evidence review (P1.1-P1.10) against the updated schema
   before real baseline data collection scales up, since P1.1 explicitly depends on the
   provenance fields this sequence adds.
5. §6 steps 8-10 (scenario domain + drivers), as one PR, once milestone P3-P5 UI work has
   capacity to expose them; these are additive and do not block anything already planned before
   them.
6. §6 step 11 (`PairwiseComparison`), independently, whenever the product decides to collect
   pairwise data (no existing milestone currently plans this; treat as a new, small milestone or
   fold into milestone D4's candidate-evaluation work).
7. §6 step 12 (`BehavioralEvent`), independently, ideally before milestone F1 so real pilot
   rewear/purchase signals are captured in the correct shape from day one rather than
   retrofitted after the pilot.
8. §6 step 13 (`ClassificationSystem`), timed to precede milestone D1's external-taxonomy
   ingestion, since D1 will otherwise need to force external taxonomies into the single hard-coded
   `primary_family`/`subfamily` pair.
9. §6 step 14 (`scrubbed_off`) can ride along with step 1 or land later; it has no dependents.
10. Defer everything in §D until the milestone that already owns it (D1, D4, D5) begins.

No step above requires a broad rewrite. Every step is additive, and the gap analysis in §2-§3
found no case where the existing architecture cannot be evolved safely; the recommendation is
incremental extension, exactly as the review's framing requires.

---

## Related documents

- [ADR-010 (Partially implemented): Preference-Learning and Scenario Data Model](adr/adr-010-preference-learning-and-scenario-data-model.md)
- [ADR-006: Version Identity, Source Provenance, and Vocabulary](adr/adr-006-version-identity-and-source-provenance.md)
- [ADR-007: Preference Evidence and Score Semantics](adr/adr-007-preference-evidence-and-score-semantics.md)
- [ADR-009: Prospective Evaluation and Frozen Checkpoints](adr/adr-009-prospective-evaluation-and-checkpoints.md)
- [Authoritative Project Plan](PROJECT-PLAN.md)
- [Technical Specification](tech-spec.md)
