---
title: "ML Structure Review, September 2026"
schema_type: common
status: published
owner: core-maintainer
purpose: "Assess whether the data, features, labels, evaluation protocol, and code are structured to produce a successful learned preference model, and rank the structural changes needed."
tags:
  - planning
  - architecture
  - analysis
  - evaluation
  - research
---

> **Reviewed commit**: `83257f0` on `main` (2026-09-19) | **Review type**: read-only, evidence-anchored |
> **Companion**: [Architecture and Design Review 2026-09](architecture-review-2026-09.md) covers the
> application as a whole. This document covers only the machine-learning structure: the path from
> evaluator observations to a model that can be trained, frozen, evaluated prospectively, and
> compared against the current heuristic. **Authority**: advisory. Accepted items enter the plan
> through [PROJECT-PLAN.md](PROJECT-PLAN.md) change control and, where they alter a durable
> decision, an ADR amendment.

## 1. How to use this document

Section 2 is the verdict. Section 3 states the learning problem the way it must be declared before
any model is fit, with proposed declarations. Section 4 is the sample-size arithmetic that
constrains every later choice. Section 5 holds the findings by theme, each with a file and line
anchor. Section 6 is the target ML architecture. Section 7 is the ranked, sequenced list of
structural changes, which is the deliverable a future agent implements from. Section 8 lists the
owner's decisions. Appendices carry the flat dataset schema and the current data flow.

Finding IDs: `M-` pipeline and code structure, `X-` data, feature, and label structure, `L-`
learning-problem definition (this document's own). Severity: **Critical** means no learned model
can be built or trusted until it is fixed; **High** should land before F1 so the pilot collects
data in the right shape; **Medium** is needed before D4/D5; **Low** is hygiene.

Method: the governing documents (ADR-004, 007, 009, 010, 011, 013, the data-model gap analysis,
the baseline and holdout evidence, the measurement contract, the calibration guide) were read
first. Two independent reviews then covered the pipeline code and the stored data as a training
set. The supervisor read the scoring service, the manifest builder, the observation, checkpoint,
and prediction models, and the checkpoint route directly, and spot-checked every claim that
changes a conclusion.

## 2. Verdict

The project has built a careful **provenance ledger** for machine learning and no machine
learning. Immutability, holdout exclusion, reveal gating, one-time outcome linking, and typed
observation columns are real and enforced. But there is no model object, no feature vectorizer,
no dataset builder, no metric, no producer of predictions, and no ML dependency. Every
"prediction" the system stores is typed by a manager into a request body
(`api/calibration.py:402-426`, `api/predictions.py:41-52`). The frozen manifest and the scorer do
not even share a feature space: one keys notes by name, the other by id
(`preference_history.py:258-261` vs `recommendation_service.py:222,339`).

Seven structural facts decide whether a successful model is possible.

1. **The learning problem is undeclared.** ADR-009 requires a target, loss, eligibility, and
   decision rule before outcomes are collected. None is written down. Six candidate targets exist
   across three tables, two of them with the same name and different types (L-01, X-13).
2. **N is 33 labeled fragrance versions per evaluator against 200 to 1,668 note features.**
   Free per-note, per-evaluator weights are unidentifiable. Only a partially pooled model on a
   reduced basis of 10 to 30 dimensions with strong priors is viable. The current heuristic
   avoids the problem by never fitting, which also means it can never improve from data
   (Section 4).
3. **The item features are not a vocabulary.** Notes are case-sensitive free strings with no alias
   layer; the note category column holds pyramid position for Kaggle rows and olfactory family for
   Parfumo rows; accord names are free strings in a primary key with intensity fabricated from
   list order for one importer and measured for the other; family strings come from three
   vocabularies; subfamily is empty or a copy of family (X-01 to X-04, X-10, X-11).
4. **Leakage protection is one Python method.** No column, view, or table marks training
   eligibility. A trainer that joins the raw tables sees holdout labels, hidden-repeat links, and
   manager selection evidence (X-05, X-06, M-18).
5. **The heuristic is non-stationary and internally inconsistent.** Cumulative affinity sums grow
   with history, so the veto threshold and sigmoid saturation depend on how many ratings exist,
   not on preference strength; family and subfamily share one dictionary and double-count on
   collision; accord intensity enters quadratically (M-12, M-13, M-14).
6. **The evaluation design cannot be scored.** Hidden repeats are excluded from training and used
   for nothing; the protocol day the repeat design depends on is not stored; no code computes
   predicted-versus-observed error, rank correlation, or a noise ceiling (M-10, M-19, X-08).
7. **Context, the strongest per-person signal, is absent or unjoinable.** Season, occasion,
   sample provenance, and application are not captured; the eight perceptual dimensions and the
   perceived-notes list are captured but perceived notes are free text that cannot be joined to
   the catalog (X-07, X-15).

The good news is that the fixes are mostly additive and small, the data volume is tiny, and the
governing ADRs already say most of the right things. The risk is sequencing: D1's vocabulary work
and the gap analysis's remaining P0 items are scheduled after F1, so the pilot will collect data
in a shape that needs a backfill. Section 7 pulls the cheap, non-retrofittable items ahead of F1.

## 3. The learning problem, declared

Nothing below is currently written down anywhere. Each item is a proposal for the owner to accept,
amend, or reject (Section 8). Until they are accepted, "does the model work" has no meaning.

| Element | Proposed declaration | Rationale |
| :--- | :--- | :--- |
| Unit of prediction | One (evaluator, fragrance version) pair, in a declared stage | Matches ADR-007's one contribution per version and the holdout design |
| Primary target | Latest eligible pre-reveal `liking` (0 to 10), preferring locked skin over locked blotter, on its original scale | Already the selection rule in `preference_history.py:164-180`; the only scale the holdout outcome is measured on |
| Secondary targets | `would_wear` (0 to 10) and `would_buy` (0 to 10) from the same observation; never pooled with the boolean recommendation-feedback fields of the same name | ADR-007 and the P2 contract keep them separate |
| Ordinary ratings | A separate 1 to 5 outcome for the ordinary workflow, never mapped onto liking for evaluation; the `(liking - 5) / 2.5` map is a scoring convenience, not an equivalence | No inverse map exists; scales are not calibrated against each other |
| Feature basis | A versioned, low-dimensional representation of a fragrance version (20 to 30 dims): controlled accord vocabulary, Michael Edwards family as a versioned classification, note-family groups from a versioned alias and taxonomy layer, and later D2 co-occurrence factors | The only basis identifiable at N = 33 per evaluator |
| Model class | Partially pooled (hierarchical) linear or ordinal model: family-level coefficients fit on all evaluators, per-evaluator deviations shrunk toward them; affinity-v1 frozen as model version 1 in the same interface | Section 4 |
| Loss and metrics | Paired MAE on the 0 to 10 scale and Spearman rank correlation over each evaluator's holdouts, reported per evaluator and pooled with intervals, against a noise ceiling from hidden repeats; precision@k on interest as a funnel metric only | ADR-009 requires uncertainty and separate reporting |
| Splits | Development: baseline members. Validation: leave-one-out within baseline. Final holdout: the 10 HOLDOUT members per evaluator, never tuned on | ADR-009; internal splits of 33 rows are not meaningful |
| Decision rule | A candidate model replaces the baseline only if its pooled holdout MAE improves on affinity-v1 by more than the repeat-estimated noise, with the same eligibility set | ADR-009 adopt, revise, or stop |
| Baseline | affinity-v1 with its parameters serialized and hashed | Section 5.2 |

## 4. Sample-size reality

From the baseline evidence (`docs/planning/evidence/baseline-v3.1-universal-and-holdout.md`): 33
baseline fragrances, 6 with a hidden repeat (39 blotter presentation slots in 13 sessions of 3),
10 holdouts, 4 evaluators. Applying the manifest's own selection rules
(`preference_history.py:155-178`):

| Quantity | Per evaluator | Pooled |
| :--- | :--- | :--- |
| Presentations | 49 | 196 |
| Training-eligible presentations (minus holdouts and repeats) | 33 | 132 |
| Distinct fragrance versions with a usable label (one contribution each) | 33 | 132 |
| Skin-stage rows if every skin stage is planned (optional; can be zero) | up to 33 more | up to 132 more |
| Held-out versions | 10 | 40 |
| Hidden-repeat pairs | 6 | 24 |

Feature dimensionality: no dataset is committed, but the same Kaggle source has 1,668 distinct
notes with a median of 9 per fragrance (`docs/research/scent-chords-analysis.md`). Restricted to
the 43 baseline and holdout versions, expect roughly 150 to 250 distinct raw note labels before
alias normalization, times 3 or 4 if position is a dummy. So p is between about 200 and 1,668
against n = 33 per evaluator.

Consequences:

- **Viable**: a hierarchical linear or ordered-logit model on a 20 to 30 dimension basis with
  shared structure fit on n = 132 and per-evaluator deviations on n = 33 under a tight prior; ridge
  on note one-hot only with a group prior from a versioned taxonomy; a descriptive model of liking
  from the eight perceptual dimensions (n = 33, p = 8), which explains but cannot recommend an
  unsmelled fragrance.
- **Not viable**: boosting or forests on one-hot notes; matrix factorization over 4 users and 43
  items; learned note-pair interactions (the project's own research says so); learned embeddings
  from this data; any internal train and validation split inside the 33 beyond leave-one-out.
- **What the repeats buy**: 6 per evaluator is uninterpretable alone; pooled to 24 (which ADR-009
  sanctions for reliability only) it gives a test-retest ICC with an interval of roughly plus or
  minus 0.3. That reliability is the ceiling on any achievable out-of-sample R squared and must be
  quoted beside every model result. Because the design places each repeat's two presentations on
  different days but the schema does not store the day (X-08), the day effect is absorbed as
  noise and deflates the ceiling.
- **Holdout power**: 10 per evaluator, 40 pooled, on a 0 to 10 scale with a standard deviation
  near 2.5. Only large paired differences between strategies are detectable; expect directional
  decisions, which ADR-009 already anticipates.

The structural implication is that the effective sample size can only be raised by (a) pooling
across evaluators through a hierarchy, (b) reducing the feature basis through vocabulary and
taxonomy work, (c) adding cheap labels per encounter (pairwise comparisons within a session,
would-wear, scrub-off), and (d) using external structure (co-occurrence, taxonomy) as priors. Every
ranked change in Section 7 serves one of those four.

## 5. Findings

### 5.1 Problem definition and evaluation

| ID | Sev | Finding | Evidence | Structural change |
| :--- | :--- | :--- | :--- | :--- |
| L-01 | Critical | No declared target, loss, eligibility, or decision rule exists anywhere. Six candidate targets across three tables. | ADR-009 Decision; Section 3 | Accept or amend Section 3 as an ADR-009 amendment before any model is fit. |
| M-09 | Critical | No code path produces a prediction. `ModelCheckpoint.predictions` and `PredictionSnapshot.predicted_rating` and `input_manifest` are caller-supplied JSON; affinity-v1 never freezes a prediction of its own, so it has no prospective record to be judged on. | `api/calibration.py:402-426`; `api/predictions.py:41-52`; `schemas/prediction.py:39`; `schemas/calibration.py:119-123` | `predict_and_freeze(session, model_key, reviewer_id, fragrance_ids)` that runs a registered model over the eligible set and writes snapshots with a server-built manifest. |
| M-10 | Critical | No metric of any kind compares predicted to observed. `metrics()` reports counts and a mean ordinary rating. No error, rank correlation, precision@k, or noise ceiling exists in `src/`. | `services/recommendation_measurement_service.py:376-442`; repo-wide grep for rmse, spearman, ndcg, precision returns only correlation middleware | `ml/evaluate.py` computing paired MAE, Spearman, precision@k, each with n and an interval, over one shared eligible denominator. |
| M-11 | High | Two models cannot be compared under the same rules. `candidate_strategy` is a one-value `Literal`; `metrics()` returns `algorithm_versions` as a flat set with no per-model grouping. | `schemas/recommendation_measurement.py:17`; `services/recommendation_measurement_service.py:383` | Group reports by `(model_id, version)` over one denominator; registry-validated keys. |
| M-18 | High | Only HOLDOUT is enforced as a split. `ACTIVE_LEARNING`, `RETEST`, `OWNED_VALIDATION` exist in the role vocabulary and are read by no code. ADR-009 requires development, validation, and final-holdout roles declared before outcomes. | `preference_history.py:75-85`; `schemas/calibration.py:9-17` | One `split_for(membership)` function consumed by dataset building, scoring exclusion, and reporting. |
| M-19 | High | Hidden repeats are excluded from training and used for nothing. `repeat_of_id` is read only for setup validation and interleaving. | `preference_history.py:167`; `calibration_service.py:174-185,257` | `ml/reliability.py` computing within-evaluator repeat agreement as the noise ceiling. |
| X-08 | High | Protocol day and actual smelling time are not stored. `CalibrationSession.created_at` is schedule-generation time (every session in an enrollment shares one timestamp plus microseconds), and `context` is always `{}`. The repeat design's different-day property cannot be recovered as a covariate. | `services/calibration_service.py:276-286`; `models/calibration.py:88-89` | `CalibrationSession.occurred_on` and `Presentation.presented_at`; write real session context. |
| M-16 | Medium | `uncertainty` exists as a column and a schema field; nothing computes it. `MatchResult` has no uncertainty concept. | `models/prediction.py:120`; `schemas/prediction.py:34,141`; `recommendation_service.py:67-75` | Scorer returns `(point, interval, n_evidence)`; every report shows n. |

### 5.2 Model object, versioning, and reproducibility

| ID | Sev | Finding | Evidence | Structural change |
| :--- | :--- | :--- | :--- | :--- |
| M-03 | Critical | affinity-v1 is inline procedural code, not a model object. `calculate_match_score` is pure but declared `async` and bound to a service holding a session, so no sync trainer or evaluation loop can call it. No ML dependency exists (`numpy` is commented out). | `recommendation_service.py:115-124,318-402`; `pyproject.toml:70` | Extract a pure, sync `score(profile, features)` and a `Scorer` protocol (`fit`, `predict`, `params`, `version`); keep the async service as a thin adapter. |
| M-04 | High | `algorithm_version` is decoupled from the code that scores. The string lives on the measurement service; the weights, veto threshold, sigmoid clamp, and subfamily factor live elsewhere and are never serialized; checkpoints accept the version as free caller text. Editing a weight changes no recorded version. | `recommendation_measurement_service.py:49`; `recommendation_service.py:35-49,236,311,388-389`; `api/calibration.py:423` | `ModelSpec(model_id, version, params, param_digest)`; derive `algorithm_version` from it; persist params and digest on every run, checkpoint, and snapshot; a test fails when a tunable changes without a version bump. |
| M-02 | Critical | Manifest and scorer use different note identities. The scorer keys affinities by `Note.id`; the manifest freezes note names only. A frozen manifest cannot reconstruct the scorer's keys, and a rename silently breaks the join. | `recommendation_service.py:222,339,350`; `preference_history.py:258-261` | One `FeatureVectorizer` emitting both `note_id` and canonical name, with a `feature_space_version`, used by scorer and manifest alike. |
| M-05 | High | The frozen `input_manifest` is a separate computation from the scores stored beside it: `create_run` builds the manifest, then `get_recommendations` recomputes exclusions and builds the manifest again with different arguments. A concurrent write between them desynchronizes record from result. | `recommendation_measurement_service.py:69,77`; `recommendation_service.py:424,427,283-285` | Compute one `ScoringContext(excluded, manifest, profile, digest)` per run and thread it into scoring and freezing. |
| M-06 | High | The manifest includes locked pre-reveal rows from unrevealed programs, which scoring excludes. The record overstates model inputs and embeds blind-program identities in a run row. | `preference_history.py:146-161` (no reveal filter) vs `recommendation_service.py:274-281` | Per-row `eligibility` and `contributed` flags plus a manifest-level policy label. |
| M-07 | High | `ModelCheckpoint` cannot reproduce a training set: it stores only `enrollment_id`, `algorithm_version`, `created_at`, `manifest`, `predictions`. No exclusions, filters, feature-space or taxonomy version, params, or input hash. | `models/calibration.py:246-257`; ADR-009 | Add `exclusions`, `candidate_strategy`, `filters`, `feature_space_version`, `taxonomy_version`, `model_params`, `input_digest`. |
| M-08 | High | `predictions` is unvalidated JSON with no join key to the manifest; nothing requires a `fragrance_id`, a scale, or that the target is a holdout. | `schemas/calibration.py:119-123`; `api/calibration.py:425` | Typed `CheckpointPrediction(fragrance_id, target, value, scale, uncertainty)`; reject rows outside the enrollment's holdout set. |
| X-16 / X-17 | High | `SourceSnapshot` has no content hash, parser version, source revision, or license evidence (four of eight D1 items); `PredictionSnapshot.feature_snapshot_version` is a free string pointing at nothing. A manifest cannot be rebuilt bit-for-bit. | `models/calibration.py:260-271`; `models/prediction.py:109-111,128`; repo-wide grep for `content_hash`, `parser_version`, `taxonomy_version` returns nothing | Add the four columns; make `feature_snapshot_version` reference a `FeatureSnapshot` row carrying alias, taxonomy, and parser versions and a hash. |
| M-17 | Medium | Ranking is not deterministic under ties: the candidate query has no `ORDER BY`, so ties and float accumulation order follow database row order. | `recommendation_service.py:436-443,506` | `ORDER BY Fragrance.id`; sort by an explicit total key. |
| M-23 | Low | `training_manifest` re-reads live fragrances and silently drops soft-deleted ones, so a checkpoint built after a catalog cleanup is missing rows with no record. | `preference_history.py:236-252` | Record dropped ids under an explicit `exclusions` key. |

### 5.3 Feature vocabulary

| ID | Sev | Finding | Evidence | Structural change |
| :--- | :--- | :--- | :--- | :--- |
| X-01 | Critical | `Note.name` is the sole note identity, case-sensitive, with no alias or normalization layer. The Kaggle importer caches on `name.lower()` but queries and inserts exact case; Parfumo does an exact lookup. Nothing handles `oak moss` versus `oakmoss`, the fixture D1 names. | `models/fragrance.py:147`; `services/kaggle_importer.py:426-436`; `services/parfumo_scraper.py:1379-1387` | `NoteAlias(raw_label, canonical_note_id, mapping_version)` and a normalized unique key on `notes`; keep raw labels. Pull this D1 item ahead of F1. |
| X-02 | Critical | `Note.category` means pyramid position for Kaggle rows ("Top", "Heart", "Base") and olfactory family for Parfumo rows. The column is unusable as a grouping key. | `services/kaggle_importer.py:355-361`; `services/parfumo_scraper.py:1386,1481-1510` | Remove position from `category`; make it a foreign key into a controlled olfactory taxonomy; backfill Kaggle rows to NULL. |
| X-03 | Critical | `FragranceAccord.accord_type` is a free string inside the primary key; Parfumo lowercases, Kaggle preserves CSV case. | `models/fragrance.py:213`; `services/parfumo_scraper.py:1030-1032`; `services/kaggle_importer.py:316-323` | `accord_types` lookup; migrate to a foreign key. |
| X-04 | Critical | `FragranceAccord.intensity` is fabricated from list position by the Kaggle importer (`max(0.1, 1.0 - i * 0.15)`) and measured as a percentage by Parfumo; both are consumed identically. | `services/kaggle_importer.py:306-324`; `services/parfumo_scraper.py:1265-1271`; `preference_history.py:262-265` | Add `intensity_source` (measured, positional, absent) or NULL the positional values; never feed a fabricated weight as measured. |
| X-10 / X-11 | High | `primary_family` carries three vocabularies (docstring says Edwards; Parfumo writes lowercase family names including "oriental" and "unknown"; Kaggle writes the raw CSV value or "Unknown"). `subfamily` is empty for Parfumo and a copy of family for Kaggle, yet is a distinct manifest feature. | `models/fragrance.py:36-37,85-86`; `services/parfumo_scraper.py:1246,1252,1437-1475`; `services/kaggle_importer.py:254-256,272-273` | Build ADR-010's `ClassificationSystem` with Michael Edwards as row one (ADR-013 item 2); drop subfamily from the feature payload until a real source exists. |
| X-12 | High | Note position exists (3 values from Kaggle, 4 from Parfumo) but rank within position is not captured. | `models/fragrance.py:192`; `services/parfumo_scraper.py:1369-1373`; `services/kaggle_importer.py:355-358` | Add `FragranceNote.rank` and a controlled `position` enum. |
| X-15 | High | `perceived_notes` is a JSON list of free text emitted as a manifest feature; it cannot be joined to `Note`, so published-versus-perceived, the comparison the calibration design exists to produce, is impossible without text matching. | `models/calibration.py:234-236`; `preference_history.py:57,212` | `observation_perceived_notes` junction with a raw-label fallback (gap analysis step 3). |
| X-21 | Medium | `Fragrance.brand` is a free string written by three paths; brand is the natural second random effect in a hierarchical model and is unusable as one. | `models/fragrance.py:76` | `brands` lookup and `brand_id`. |
| M-12 | High | Family and subfamily share one affinity dictionary on write and read, so a subfamily string that collides with a family string is counted at 0.20 plus 0.10 on the same value. | `recommendation_service.py:234-236,362-363` | Namespace the keys; regression test for the collision. |
| M-13 | Medium | Accord intensity enters the score quadratically: profile accumulation multiplies by the rated fragrance's intensity and scoring multiplies again by the candidate's. | `recommendation_service.py:227,356` | Separate evidence weight from feature value in an explicit feature spec; record the choice in `ModelSpec.params`. |
| X-24 | Medium | External reference knowledge (Fragella lookups) is stored as JSON forbidden from write-back, so it is not joinable; ADR-004's `provider_term_mapping` does not exist. | `models/calibration.py:274-311` | Build `provider_term_mapping` so external terms become joinable concepts without contaminating catalog facts. |

### 5.4 Labels

| ID | Sev | Finding | Evidence | Structural change |
| :--- | :--- | :--- | :--- | :--- |
| X-13 | High | `would_wear` and `would_buy` are 0 to 10 integers on observations and booleans on recommendation feedback under identical names; a naive union coerces silently. | `models/calibration.py:217-218`; `models/recommendation_measurement.py:101-102` | Rename one pair or add an explicit scale column; never pool. |
| X-14 | High | `familiarity` is a 0 to 5 integer with no anchors, exists only on controlled observations, and is absent from `Evaluation`. First exposure is the largest identifiable confound in a four-person study. | `models/calibration.py:207`; ADR-010 marks this unimplemented | Controlled `familiarity` code on both tables (gap analysis step 2). |
| X-22 | Medium | No `scrubbed_off` or `time_to_scrub_minutes`; the non-detection CHECK forces `liking IS NULL`, so the strongest negatives are structurally label-free. | `models/calibration.py:139-141` | Add both columns; at N = 33 the strongest negatives are expensive to discard. |
| M-20 | Medium | Non-detection observations are discarded wholesale from the manifest, losing all twenty typed features and the "could not detect" label itself. | `preference_history.py:178-180` | Keep the row with `label = None, detected = False`; let the dataset builder decide. |
| X-23 | Medium | No `PairwiseComparison` and no general `BehavioralEvent`; wear, buy, and sampling exist only scoped to one impression. Pairwise preference cannot be reconstructed from independent ratings after the fact. | `models/recommendation_measurement.py:71-102` | Land both before F1 (gap analysis steps 11 and 12). Within-session pairwise comparisons are the cheapest way to multiply effective sample size. |
| M-15 | Medium | Cold start is a hard error below 3 contributions and every candidate scores exactly 0.5 at zero evidence; no population prior, family fallback, or shrinkage. | `recommendation_service.py:49,429-431` | `PopulationPrior` pooled across evaluators, blended by evidence count; keep the display gate, not the scoring gate. |

### 5.5 Leakage and training eligibility

| ID | Sev | Finding | Evidence | Structural change |
| :--- | :--- | :--- | :--- | :--- |
| X-05 | Critical | No `training_eligibility` column or view exists. Every rule (holdout, hidden repeat, pre-reveal, stage lock, worn-by) lives in one Python method; a trainer joining raw tables bypasses all of it. | `preference_history.py:75-85,101,155-178`; no `CREATE VIEW` in `alembic/` or `src/` | `training_eligibility` code on `evaluations` and `calibration_observations` plus a `v_training_rows` database view that materializes the same predicate. |
| X-06 | Critical | `Membership.role` and `repeat_of_id` sit on the table a trainer joins for `fragrance_id`, and the manifest emits `role` as a row key. | `models/calibration.py:54-57`; `preference_history.py:226` | Manager-only view for role and repeat linkage; strip `role` from the emitted manifest row in favor of an eligibility token. |
| X-18 | Medium | `PredictionService` has no holdout awareness; a snapshot's `input_manifest` is accepted verbatim and may contain holdout evidence. | `services/prediction_service.py` (no exclusion reference); `models/prediction.py:128` | Build the manifest server-side or validate it against `excluded_versions`. |
| X-19 | Medium | Nothing prevents writing an ordinary evaluation for an active holdout; it is filtered only on read. | `services/evaluation_service.py` (no write-side check) | Reject or auto-flag `WITHHELD` at write time. |
| M-21 | Medium | A version under blind, unrevealed controlled measurement is still recommendable and ratable ordinarily; only HOLDOUT is removed from candidates, so an ordinary encounter mid-program contaminates the controlled measurement. | `recommendation_service.py:445-449,464-477` | An `in_blind_program(reviewer_id)` set used for candidate generation and for a warning on ordinary entry. |
| X-25 | Low | `Membership.role` has no database CHECK; a direct write can produce a role the leakage filter does not recognize. | `models/calibration.py:54` | `CHECK (role IN (...))`. |

The scoring and LLM paths themselves are leak-clean: holdouts are removed regardless of
`exclude_rated`, controlled evidence enters the ordinary profile only after reveal, worn-by rows
are excluded everywhere, the run view omits the manifest, and the prompt sees strictly less than
the manifest (`recommendation_service.py:193-197,274-281,445-449`; `llm_service.py:213-250`).

### 5.6 Context, provenance, and identity

| ID | Sev | Finding | Evidence | Structural change |
| :--- | :--- | :--- | :--- | :--- |
| X-07 | High | The scenario and context domain is absent: season, occasion, time of day, weather, climate, sprays, container. | `models/calibration.py:88`; gap analysis rows XX-XXIX | Land the lookups and `ActualWearContext` before F1 so the pilot collects the data; defer the conditional model. |
| X-09 | High | Physical-sample provenance lives as ad hoc keys in `Membership.selection`; P1.1's validator demands `physical_sample_confirmed` with no column to hold it. | `models/calibration.py:59`; `scripts/validate_calibration_manifest.py:84-85` | Typed provenance columns on `Presentation` (gap analysis step 6). |
| X-20 | Medium | `concentration` accepts "Unknown" freely and both importers default to it, while assignment and the manifest validator reject it; catalog rows and program-eligible rows differ in identity strength with no column saying so. | `services/kaggle_importer.py:251`; `services/parfumo_scraper.py:1242`; `services/calibration_service.py:170-171` | `concentration_verified` or a status code so a feature builder can filter on identity strength. |
| M-22 | Low | Manifest rows carry no `reviewer_id` or split label, and ordinary versus controlled rows have disjoint key sets, so two evaluators' manifests cannot be concatenated. | `preference_history.py:135-145,220-235` | One `TrainingRow` with a uniform key set. |

### 5.7 Heuristic defects that would corrupt any comparison

| ID | Sev | Finding | Evidence | Structural change |
| :--- | :--- | :--- | :--- | :--- |
| M-14 | High | Both the veto and the sigmoid operate on an unnormalized cumulative sum that grows with history length; as N grows more notes cross the veto line and scores saturate toward 0 and 1. The scorer is non-stationary: the same preferences rank differently as history accumulates. | `recommendation_service.py:46,339-346,366-389` | Shrink per-key affinity by evidence count (`sum / (n + k)`); make the link scale a fitted parameter. |
| M-01 | Critical | No module yields `X, y`. The manifest returns heterogeneous dicts; ordinary rows have no `features` key; there is no vectorizer or target selection. | `preference_history.py:112-268` | `ml/dataset.py` with `build_examples()` and `to_arrays()`. |
| M-24 | Low | Controlled feature lookup is an N+1 query and the profile route builds the profile twice; harmless now, first bottleneck in a batch trainer. | `recommendation_service.py:299-306`; `api/recommendations.py:223,231` | Batch load; pass one profile down. |

Untested invariants worth noting: ADR-004's own success criterion ("adding a 1-star rating for a
fragrance with lemon lowers all lemon-containing recommendations") has no test; multi-candidate
ordering is never asserted; the veto and averaging interaction is untested; no metric can be
tested because none exists.

## 6. What is well done

The remediation must preserve these.

- **NULL-versus-zero is explicit at three layers** (schema docstring, API validation, database
  CHECK). This is the most commonly botched property of survey-derived ML data.
- **Encounters are atomic and append-only**; observations have no update route; feedback is
  append-only revisions; nothing overwrites history.
- **Subject, recorder, and worn-by are three separate fields**, with worn-by excluded from the
  manifest and a CHECK against self-reference.
- **Prediction and outcome scale mismatch is enforced**, outcome links are set exactly once under a
  row lock, and checkpoint creation closes after any holdout response. The prospective guarantee
  ADR-009 depends on is implemented.
- **The typed-column migration was done right**: 22 fields, 17 with CHECK bounds, legacy values
  quarantined not fabricated, a TypedDict so a rename is a type error.
- **Holdout semantics are conservative across both workflows**, holdout-and-training membership is
  rejected at write time, and the scoring and LLM paths do not leak.
- **Version identity is real**: partial unique index scoped to live rows, immutability after
  assignment, "Unknown" concentration rejected at assignment, GTIN cross-checked against evidence.
- **The project already knows most of the data gaps.** The gap analysis names accord and brand
  drift, the scenario gap, and the alias fixtures. This review mostly re-prioritizes work the team
  has already written down, and moves the non-retrofittable parts ahead of F1.

## 7. Structural changes, ranked and sequenced

Ordered by leverage per unit of work at family scale. Tiers are sequencing constraints, not
priorities within a tier. Each item names its findings so an agent can read the evidence first.

### Tier 0: Declare the problem (one review session)

Accept or amend Section 3 as an ADR-009 amendment: unit, primary target, secondary targets, feature
basis, model class, metrics, splits, decision rule, baseline. Nothing in Tier 1 onward should be
built against an undeclared target (L-01).

### Tier 1: Make the data trustworthy before F1 collects it

These are cheap, additive, and not retrofittable once pilot data exists.

1. **Training eligibility as schema** (X-05, X-06, X-19, X-25, M-18): `training_eligibility` on
   both evidence tables, a `v_training_rows` view materializing the current predicate, a
   manager-only view for role and repeat linkage, a CHECK on `role`, a write-time flag for ordinary
   evaluations of active holdouts, and one `split_for()` function.
   Acceptance: a test proves a raw-table join through the view cannot see a HOLDOUT label or a
   `repeat_of_id`; the manifest builder and the view agree on every row.
2. **Note alias and normalization layer** (X-01, X-02): `NoteAlias`, a normalized unique key on
   `notes`, `category` cleaned of position, both importers routed through one resolver.
   Acceptance: the D1 fixtures (`oak moss`/`oakmoss`, `vanille`/`vanilla`, ambiguous, unknown) pass;
   a re-import creates no duplicate notes.
3. **Controlled accords with intensity provenance** (X-03, X-04): `accord_types` lookup,
   `accord_type` as a foreign key, `intensity_source`.
   Acceptance: no accord string outside the lookup; positional intensities are marked and excluded
   from measured features by default.
4. **Protocol day, presentation time, and real session context** (X-08): `occurred_on`,
   `presented_at`, and a written `context`.
   Acceptance: the repeat-pair reliability computation can include a day term.
5. **Familiarity as a code on both tables, scrub-off columns, perceived-notes junction**
   (X-14, X-22, X-15).
   Acceptance: published-versus-perceived can be computed by join; strong negatives carry a label.
6. **Pairwise comparison and behavioral event tables, and the scenario lookups** (X-23, X-07,
   X-09): schema only, so the pilot captures them; UI exposure can follow.
   Acceptance: a within-session pairwise judgment and a rewear or purchase event can be stored with
   provenance.

### Tier 2: Turn the heuristic into a model and the ledger into a pipeline

- **(7)** **`ml/feature_space.py`, `FeatureVectorizer`** (M-02, M-12, M-13): one definition of a
   fragrance's feature vector, namespaced keys, both note id and canonical name, a
   `feature_space_version`; used by the scorer and the manifest.
- **(8)** **`ml/model.py`, `Scorer` protocol and `ModelSpec`, with `AffinityV1` as version 1**
   (M-03, M-04, M-14, M-16): pure sync scoring; serialized params with a digest; evidence-count
   shrinkage; the link scale as a parameter; `(point, interval, n_evidence)` output.
   Acceptance: a test fails when a tunable changes without a version bump; affinity-v1 with
   default params reproduces today's rankings on a fixture, and the ADR-004 lemon criterion is
   asserted.
- **(9)** **`ml/dataset.py`, `build_examples()` and `to_arrays()`** (M-01, M-20, M-22): uniform
   `TrainingRow`, explicit target selection, split label, non-detection retained.
   Acceptance: a notebook obtains `X, y, groups` for one evaluator with only a session.
- **(10)** **`ml/context.py`, `ScoringContext`** (M-05, M-06, M-23): exclusions, manifest, profile, and
  digest computed once per run and threaded into scoring and freezing; per-row `contributed`.
- **(11)** **Checkpoint service and schema** (M-07, M-08, X-16, X-17): move checkpoint creation out of
  the route; add exclusions, filters, feature-space and taxonomy versions, params, and input
  digest; typed predictions rejecting non-holdout targets; `SourceSnapshot` gains content hash,
  parser version, source revision, and license evidence; `FeatureSnapshot` rows.
- **(12)** **`predict_and_freeze()`** (M-09, X-18): a registered model runs over the eligible set and
  writes `PredictionSnapshot` rows with a server-built manifest; affinity-v1 gets its first
  prospective record.
- **(13)** **`ml/registry.py`** (M-11): registry-validated model keys replace the one-value `Literal` and
  the free checkpoint version string; reports group by `(model_id, version)`.

### Tier 3: Evaluate honestly

- **(14)** **`ml/reliability.py`** (M-19): repeat agreement per evaluator and pooled, with intervals; the
  noise ceiling every comparison is quoted against.
- **(15)** **`ml/evaluate.py`** (M-10): paired MAE and Spearman over holdouts per evaluator and pooled,
  precision@k on interest as a funnel metric, all with n and intervals over one shared
  denominator; a report template that states target, eligibility, model version, feature-space
  version, and ceiling.
- **(16)** **Determinism and performance** (M-17, M-24): ordered candidate query, total sort key,
  batched loads.

### Tier 4: Reduce the basis and add priors (D1 and D2, pulled forward where cheap)

- **(17)** **`ClassificationSystem` with Michael Edwards as row one** (X-10, X-11; ADR-013 item 2),
  `brands` lookup (X-21), `FragranceNote.rank` (X-12), `provider_term_mapping` (X-24).
- **(18)** **Population prior and hierarchical baseline** (M-15): a pooled prior blended by evidence
  count, then the first learned model as a partially pooled linear or ordinal model on the
  reduced basis, registered beside affinity-v1 and compared under Tier 3.
- **(19)** **D2 co-occurrence factors as a feature-space version**, once the vocabulary is stable.

Do not build: collaborative filtering, learned embeddings, note-pair interaction models, or any
nonparametric learner on one-hot notes, at this population size.

## 8. Decisions required from the owner

| # | Decision | Default if undecided |
| :--- | :--- | :--- |
| Q1 | Accept Section 3 as the declared learning problem, or amend it? In particular: primary target is skin-preferred pre-reveal liking; ordinary ratings stay a separate outcome. | Accept as an ADR-009 amendment. |
| Q2 | Pull the D1 alias and vocabulary work (Tier 1 items 2 and 3) ahead of F1, changing the plan's sequence? | Yes; the pilot otherwise collects fragmented features that need a backfill. |
| Q3 | Add pairwise comparison and behavioral event tables before F1 even though no UI exposes them yet? | Yes, schema only; they cannot be reconstructed later. |
| Q4 | Is `subfamily` retained as a feature? Today it is empty or a copy of family. | Drop from the feature payload until `ClassificationSystem` supplies a real value. |
| Q5 | Should the Kaggle positional accord intensities be NULLed or kept and marked? | Keep and mark `positional`; exclude from measured features by default. |
| Q6 | Is affinity-v1 to be frozen as version 1 with its current parameters, defects included, so the first comparison is against what the family actually experienced? | Yes; fix M-12, M-13, M-14 as version 2. |
| Q7 | Add an ML dependency set (`numpy`, `scipy`, and a small Bayesian or regularized-linear library) to the backend, or keep training in a separate package that imports the models? | Separate `ml/` package inside the repo with an optional dependency group; the API imports only the `Scorer` protocol. |
| Q8 | Will the household record within-session pairwise judgments during F1? It roughly triples labels per session at low cost. | Yes, one question per pair of adjacent samples. |

## Appendix A: Flat dataset schema (one row per evaluator, version, observation context)

Status: E exists, D derivable, M missing.

| Column | Source | Status |
| :--- | :--- | :--- |
| `evaluator_id`, `fragrance_version_id`, `version_key`, `concentration` | `reviewers.id`; `fragrances.id`, `version_key`, `concentration` | E |
| `concentration_verified` | | M (X-20) |
| `observation_id`, `workflow`, `program_id`, `session_id`, `session_position`, `presentation_id` | observation or evaluation id; derived; `calibration_enrollments.program_id`; `calibration_presentations.session_id`, `position`, `id` | E or D |
| `protocol_day`, `presented_at` | | M (X-08) |
| `observed_at`, `stage`, `phase`, `elapsed_minutes`, `recorded_by` | `calibration_observations.created_at`, `stage`, `phase`, `elapsed_minutes`, `recorded_by`; `evaluations.evaluated_at` | E |
| `same_session_cohort` | group by `session_id` | D |
| `liking_0_10`, `opening_liking_0_10`, `drydown_liking_0_10`, `would_wear_0_10`, `would_buy_0_10`, `artistic_appreciation_0_10` | `calibration_observations` | E |
| `detected`, `intensity_0_5`, `projection_0_5`, `longevity_minutes` | `calibration_observations` | E |
| `rating_1_5`, `longevity_rating_1_5`, `sillage_rating_1_5` | `evaluations` | E (separate scale) |
| `rec_interested_bool`, `rec_sampling_state`, `rec_would_wear_bool`, `rec_would_buy_bool` | `recommendation_response_revisions` | E (name collision, X-13) |
| `scrubbed_off`, `time_to_scrub_minutes` | | M (X-22) |
| `pairwise_preferred_over`, `behavioral_event` | | M (X-23) |
| `confidence_0_5`, `sweetness`, `freshness`, `density`, `dryness`, `clean_soapy`, `earthy_rooty`, `bodily_animalic`, `discomfort` (0 to 5) | `calibration_observations` | E |
| `familiarity_0_5` | `calibration_observations.familiarity` | E, ambiguous (X-14) |
| `familiarity_code`, `perceived_note_ids` | | M (X-14, X-15) |
| `perceived_notes_raw`, `likes`, `dislikes`, `reminds_me_of`, `comments` | `calibration_observations` | E (free text) |
| `note_onehot[*]`, `note_position` | `fragrance_notes` via `notes.name` | E, unnormalized (X-01, X-12) |
| `note_rank_within_position`, `note_family_group` | | M (X-12, X-02) |
| `accord_weights[*]` | `fragrance_accords` | E, uncontrolled and partly fabricated (X-03, X-04) |
| `primary_family`, `subfamily` | `fragrances` | E, three vocabularies (X-10, X-11) |
| `edwards_family_versioned`, `brand_id`, `ifra_material_id`, `note_cooccurrence_lift[*]` | | M (ADR-013, X-21, D2) |
| `perfumer_ids`, `launch_year`, `gender_target` | `calibration_version_perfumers`; `fragrances` | E |
| `season`, `occasion`, `time_of_day`, `weather`, `sprays`, `container`, `sample_source_type`, `sample_volume_ml`, `sample_batch_code` | | M (X-07, X-09) |
| `source_snapshot_id`, `source_url`, `retrieved_at`, `verification_status` | `calibration_source_snapshots` | E |
| `content_hash`, `source_revision`, `parser_version`, `license_evidence`, `alias_version`, `taxonomy_version`, `feature_space_version` | | M (X-16, X-17) |
| `algorithm_version`, `model_params_digest` | `calibration_checkpoints.algorithm_version`; | E, M (M-04) |
| `training_eligibility`, `split` | | M (X-05, M-18) |
| `membership_role`, `repeat_of_id` | `calibration_memberships` | E, leak risk (X-06) |
| `worn_by_reviewer_id` (must be NULL), `deleted_at` | `evaluations`, `fragrances` | E |

## Appendix B: Current data flow

```text
raw rows
  evaluations (1-5, evaluated_at, worn_by, deleted_at)
  calibration_observations (0-10 liking + 20 typed features)
  fragrances / fragrance_notes / notes / fragrance_accords
  calibration_memberships.role (HOLDOUT / HIDDEN_REPEAT)

(a) affinity score: DB-coupled, no HTTP
  excluded_versions(reviewer): role == HOLDOUT only            preference_history.py:75
  build_preference_profile: latest ordinary per version,
  controlled (liking-5)/2.5 only after reveal, averaged,
  accumulate note[id] / accord[type]*intensity /
  family[primary] and family[subfamily]*0.5                  recommendation_service.py:127-236
  calculate_match_score: veto < -3, mean note affinity,
  mean accord affinity*intensity, family/subfamily from the
  same dict, 0.4/0.3/0.2/0.1 weighted sum, sigmoid(clamp)   recommendation_service.py:318-389
  get_recommendations: candidate query without ORDER BY,
  holdouts removed, stable sort, top-N                       recommendation_service.py:404-506

(b) training manifest: importable, FastAPI-free, not a dataset
  ordinary rows {id, fragrance_id, workflow, scale, rating, observed_at, notes}
  controlled rows: PRE_REVEAL, not HIDDEN_REPEAT, stage locked, liking not null,
  no reveal filter; + features{21} + notes_text{4} + {stage, role, phase, program_id}
  source_features {version_key, concentration, family, subfamily,
  notes[{name, position}], accords[{name, intensity}]}      preference_history.py:112-268

(c) checkpoint: route only; manifest recomputed; predictions = caller JSON
                                                              api/calibration.py:402-426
(d) prediction snapshot: no producer; all fields caller-supplied
                                                              api/predictions.py:41-52
(e) outcome links: two unconnected mechanisms (PredictionSnapshot and
  RecommendationResponseRevision); no join between them
(f) metrics: counts and mean_ordinary_rating; no predicted-vs-observed
                                                              recommendation_measurement_service.py:278-442
```

## Related documents

- [Architecture and Design Review 2026-09](architecture-review-2026-09.md)
- [Authoritative Project Plan](PROJECT-PLAN.md)
- [Data Model Gap Analysis](data-model-gap-analysis.md)
- [ADR-004](adr/adr-004-recommendation-algorithm.md), [ADR-007](adr/adr-007-preference-evidence-and-score-semantics.md), [ADR-009](adr/adr-009-prospective-evaluation-and-checkpoints.md), [ADR-010](adr/adr-010-preference-learning-and-scenario-data-model.md), [ADR-013](adr/adr-013-external-ontology-and-standards-crosswalk.md)
- [Universal Baseline and Validation Holdout V3.1](evidence/baseline-v3.1-universal-and-holdout.md)
- [Recommendation Outcome Measurement](../measurement/recommendation-outcomes.md)
