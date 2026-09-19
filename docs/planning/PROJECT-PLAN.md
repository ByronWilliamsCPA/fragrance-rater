# Fragrance Rater: Authoritative Project Plan

> **Version**: 2.2 | **Status**: Active | **Updated**: 2026-09-19

## 1. Planning authority

This document is the execution authority for work after the controlled-calibration merge.
The [vision](project-vision.md) defines the product outcome, the
[technical specification](tech-spec.md) defines current and target contracts, and accepted ADRs
define durable architecture decisions. If those sources disagree, implementation pauses until
the documents and decision records are reconciled. Current code is evidence of implementation
state; it does not silently supersede an accepted decision.

The historical Phase 0–4 outline has been retired as an execution plan. Its delivered
capabilities are summarized below. The [roadmap](roadmap.md) is a compact view of this plan and
must not introduce independent scope or status.

## 2. Product objective

Help each family evaluator make better fragrance choices by:

1. preserving ordinary and controlled experience accurately;
2. resolving observations to exact, verified fragrance versions;
3. building explainable preference evidence without overstating certainty;
4. generating useful and varied candidates; and
5. measuring post-sample outcomes prospectively against declared baselines.

Interest in a recommendation is a funnel metric. Actual blind liking, willingness to wear, and
willingness to buy are outcome measures. An affinity percentage is not a probability or a
predicted rating.

## 3. Current-state ledger

**Audited repository baseline:** branch `main`, merge commit
`1c9bc2af9b3bf948c0ddda5b863fc8faae71e056` on 2026-09-12. P0-P5 implementation and review
evidence are retained in the linked gate records and PRs #70-#74.

| Capability | State | Evidence or remaining limitation |
| :--- | :--- | :--- |
| Docker Compose, FastAPI, PostgreSQL, React | Implemented | Development and production Compose files exist; production network exposure needs P1 validation |
| Fragrance, reviewer, and ordinary evaluation CRUD | Implemented | Ordinary POST retains dated encounters; update and soft delete operate on one encounter |
| Kaggle import | Implemented | Production dataset quality and rights remain source-specific |
| Parfumo capture | Partially implemented | Source snapshots and exact titles are preserved; P1.9 added authorized representative fixtures and parser coverage for requested metrics, production status, similar fragrances, missing fields, and unknown concentration; concentration-variant ("related version") data is confirmed AJAX-only on the live site and is intentionally not fabricated |
| Deterministic recommendations | Implemented | `affinity-v2` (shrunk, namespaced, stationary; ADR-004 amendment 2026-09-19) is the default scorer; `affinity-v1` retained for comparison; score is uncalibrated |
| Preference history | Implemented | Latest ordinary encounter per version plus eligible controlled evidence; holdouts are excluded |
| OpenRouter explanations | Implemented as optional enhancement | In-process bounded cache, deterministic fallback, and provider token/cost telemetry; live measurements require the F1 pilot |
| Controlled calibration | Merged, not deployment-verified | Program, enrollment, hidden repeat/holdout, presentation, observation, locking, reveal, and checkpoint flows exist |
| React product workflow | P5 complete | Participant, manager, reporting, and operations workflows are merged; deployed rehearsal remains P6 work |
| Recommendation outcome measurement | Implemented, not pilot-verified | Immutable runs/impressions, append-only feedback, outcome links, operational events, and provenance-complete reports exist; real baselines belong to F1 |
| Worn-by ("on others") evidence dimension | Implemented, capture only | Optional `worn_by_reviewer_id` on `Evaluation` per ADR-011; excluded from affinity/training-manifest scoring until a future milestone folds it in |
| Verified 43-fragrance baseline manifest | Not available | Exact versions must be verified; no identities may be guessed |
| Live PostgreSQL calibration migration | Fresh-schema verified | Full upgrade reaches current head on PostgreSQL 16; P1 still requires a production backup-clone exercise |
| ML pipeline skeleton | Implemented, no learned model | `fragrance_rater.ml`: versioned feature space, model objects with digested parameters, dataset builder, repeat reliability, holdout scorecards, prospective prediction runner (ML structure review, Tier 2 and 3) |
| Review remediation and ML foundation | In progress | Milestone R (section 11a); sprints R1-R4 gate P6 closure, R2 and R5-R8 gate F1 |
| Candidate discovery and catalog statistics | Planned | D1–D5 |

Status terms:

- **Implemented** means present in `main`, not necessarily deployed.
- **Deployment-verified** requires evidence from the target topology and database.
- **Complete** requires the milestone exit gate and retained evidence.

## 4. Delivery sequence

```text
P0 Planning baseline
 ├─ P1 Release evidence ------------------------------------------┐
 └─ P2 Measurement foundation → P3 UX → P4 Participant → P5 Manager
                                                                  └─ R1-R4 Remediation (P6 blockers)
                                                                      └─ P6 Pilot readiness
                                                                          └─ R2, R5-R8 ML foundation (F1 blockers)
                                                                              └─ F1 Family pilot
                                                                                  └─ D1 → D2 ┬→ D3
                                                                                              └→ D4 → D5
```

Milestone R (section 11a) was added on 2026-09-19 from the architecture and ML structure reviews.
Its P6-blocking sprints precede the P6 go decision; its F1-blocking sprints precede the first
pilot perfume. R9-R14 improve maintainability and can run in parallel with P6 evidence gathering
but do not gate it.

P1 evidence may be gathered while P3-P5 are implemented, but its deployed UI, disclosure, and
smoke checks use the final P6 candidate. No family member evaluates an actual pilot perfume
until P6 closes. F1 establishes the real-use baselines previously assigned to P2. D1 begins only
after F1 evidence is reviewed. D3 and D4 may overlap after D2's snapshot and statistical
contracts are frozen.

## 5. Milestone P0: Planning baseline

**Objective:** Establish one accurate, traceable plan before additional product implementation.

**Owner:** Core maintainer

**Status:** Complete

**Evidence:** [P0 Planning Baseline Gate](gates/p0.md)
**Depends on:** Controlled-calibration merge

### Deliverables

- Vision v2 covering ordinary capture, controlled calibration, discovery, and prospective
  evaluation.
- Current-state ledger tied to an audited commit.
- Authoritative execution sequence with pre-D1 release and measurement gates.
- Updated technical specification describing the current trust boundary, data domains, and APIs.
- Superseding or amending ADRs for calibration, identity/provenance, evidence aggregation,
  authentication, and prospective evaluation.
- A traceability matrix connecting product outcomes, milestones, evidence, and release gates.
- A disposition for every finding from the planning audit.
- Published navigation to the calibration design and all current ADRs.

### Exit criteria

- [x] Vision, plan, roadmap, technical specification, calibration guide, and ADR index agree.
- [x] Historical documents are clearly non-authoritative.
- [x] Every unresolved item has a milestone, owner, acceptance criterion, and evidence location.
- [x] Documentation builds in strict mode.
- [x] Planning Markdown passes the repository lint rules.
- [x] P1 and P2 have implementation-ready entry and exit criteria.

## 6. Milestone P1: Calibration release readiness

**Objective:** Prove the merged calibration and encounter-history implementation is safe to
deploy on the real PostgreSQL and Authentik/Traefik topology.

**Owner:** Core maintainer

**Status:** Repository controls implemented; external evidence pending through P6

**Depends on:** P0
**Blocks:** F1. P1 repository controls are required to enter P6; full P1 evidence is completed
and reviewed as P6.1 before P6 can close.

### Work packages

| ID | Work | Acceptance criteria | Retained evidence |
| :--- | :--- | :--- | :--- |
| P1.1 | Exact baseline manifest | Every program member has verified brand, name, concentration/version key, source URL, verification evidence, and physical-sample confirmation; unresolved identities remain unassigned | Versioned manifest and verification report |
| P1.2 | Production backup clone | Record current Alembic revision and row counts; restore a production backup to an isolated PostgreSQL instance | Redacted restore log and pre-upgrade inventory |
| P1.3 | Live migration | Upgrade the clone through the declared Alembic head; preserve IDs, encounter counts, ratings, and timestamps; validate constraints and query plans | Migration log, before/after assertions, schema dump/hash |
| P1.4 | Concurrency | Concurrent ordinary encounter writes and controlled observation/lock attempts preserve all valid records and reject invalid state transitions deterministically | Automated PostgreSQL concurrency results |
| P1.5 | Rollback/recovery | Demonstrate restore from the verified pre-upgrade backup; do not use lossy downgrade or migration stamping | Timed restore drill and recovery checklist |
| P1.6 | Trust-boundary validation | Production requests traverse Authentik/Traefik; direct backend access from reachable networks cannot mutate data or expose calibration mappings | Deployed topology, port scan, bypass tests, role matrix |
| P1.7 | Blind disclosure audit | Search, history, profiles, recommendations, explanations, caches, errors, exports, and logs reveal no mapping, role, repeat, selection, or holdout information before policy allows | Automated disclosure matrix |
| P1.8 | Target-environment verification | Python 3.12, PostgreSQL 16, frontend build, backend tests, type checks, lint, security scans, and critical end-to-end flows pass | CI run and target-host smoke report |
| P1.9 | Parfumo fixtures | Add authorized representative fixtures for requested metrics, status, related versions, similar fragrances, missing fields, and unknown concentration | Fixture provenance and parser coverage |
| P1.10 | Operations | Document health checks, logs, alerting, database growth, backups, secret rotation, external-service failure, and upgrade procedure | Operations runbook |

### Release-blocking invariants

- No destructive reconciliation of historical encounters.
- No guessed fragrance concentration or version.
- No direct backend path that bypasses the authenticated proxy in production.
- No participant-visible blind mapping or holdout leakage.
- No mutation of frozen program membership, source snapshot, or model checkpoint.
- A failed external source or LLM leaves capture, history, and deterministic scoring usable.

### P1 exit gate

P1 is complete only when P1.1–P1.10 have evidence reviewed by the core maintainer. Passing
SQLite tests or compiling PostgreSQL SQL is insufficient.

## 7. Milestone P2: Recommendation outcome measurement

**Objective:** Implement the durable measurement contract needed by the complete UI and later
family pilot.

**Owner:** Core maintainer

**Status:** Complete

**Depends on:** P0
**Blocks:** P3, P4, P5, P6, and D5

### Measurement events

| Event | Required fields |
| :--- | :--- |
| Recommendation run | Reviewer, timestamp, algorithm/version, frozen input manifest, source snapshot, candidate strategy, filters |
| Impression | Run, candidate, rank, score type/value, explanation version, shown timestamp |
| Interest response | Impression, interested/not interested, response timestamp, recorder |
| Sampling state | Impression, planned/acquired/sampled/unavailable, timestamp, optional reason |
| Outcome link | Impression and subsequent ordinary or controlled observation, with no rewriting of the observation |
| Decision response | Would wear and would buy, stored separately from liking |

### Metric contract

- Interest rate = positive interest responses / all explicit interest responses.
- Response coverage = explicit interest responses / eligible impressions.
- Sampling conversion = sampled recommendations / eligible impressions.
- Post-sample liking is reported on its original scale and by declared threshold when a binary
  view is needed.
- Wear and buy responses are separate outcomes.
- Coverage, variety, concentration/house repetition, and unavailable-candidate rates accompany
  usefulness metrics.
- Every report declares exclusions, time window, reviewer population, model version, candidate
  strategy, and denominators.
- Small samples show counts and uncertainty; they do not use “accuracy” without a defined target
  and prediction rule.

### P2 acceptance criteria

- [x] A recommendation impression is persisted before feedback can be recorded.
- [x] Repeated views do not silently create duplicate impressions; the event policy is explicit.
- [x] Feedback can be changed only through an auditable revision policy.
- [x] An outcome can be linked to a later encounter without changing raw encounter data.
- [x] Blind and holdout rules apply to feedback queries and reports.
- [x] An admin report shows response coverage as well as positive-response rate.
- [x] A family evaluator can record interest on mobile without adding more than one interaction.
- [x] LLM call count, latency, cache hit rate, failure rate, token usage, and provider-reported cost are measurable.
- [x] Connectivity failures and offline/manual recovery can be recorded and reported.

Real baseline values and observed connectivity behavior are F1 outcomes. They are deliberately
excluded from P2 completion so implementation does not force family members onto an incomplete
interface.

## 8. Milestone P3: Product UX foundation

**Objective:** Replace the single-component prototype with a stable, role-aware application
foundation before expanding user workflows.

**Owner:** Core maintainer

**Status:** Complete
**Depends on:** P0 and P2
**Evidence:** [P3 Product UX Foundation Gate](gates/p3.md)

### P3 acceptance criteria

- Route-backed pages preserve useful URLs, reload state, and browser navigation.
- Authenticated identity and evaluator, recorder, and manager capabilities drive navigation and
  controls without exposing privileged data.
- Shared layout, form, status, confirmation, and error components replace duplicated page logic.
- Loading, empty, retry, validation, API failure, and optional-service degradation states are
  explicit and usable.
- The shell works at 360 CSS pixels, supports keyboard navigation and visible focus, and passes
  the declared automated accessibility baseline.
- API access uses generated or equivalently typed contracts with one error-handling policy.
- Frontend architecture and test strategy support feature-level components and end-to-end tests.

## 9. Milestone P4: Participant experience

**Objective:** Let a family evaluator complete every ordinary, calibration, recommendation, and
follow-up task through a guided interface without API tools or raw identifiers.

**Owner:** Core maintainer

**Status:** Complete
**Depends on:** P3
**Evidence:** [P4 Participant Experience Gate](gates/p4.md)

### P4 acceptance criteria

- A participant can understand current assignments and resume the next valid calibration step.
- Catalog search, ordinary encounter entry, correction/history, and validation are complete on
  mobile and desktop.
- Blind blotter and skin workflows explain progress, lock consequences, and reveal eligibility.
- Recommendation cards support interest, sampling state, later outcome linkage, would-wear, and
  would-buy revisions through the UI.
- Saved recommendation runs reopen without duplicate impressions and clearly distinguish a new
  set from an existing set.
- Participant pages never require UUID entry and never reveal manager-only mapping, role,
  repeat, selection, or holdout data.
- End-to-end tests cover ordinary entry, blind calibration, recommendation feedback, sampling,
  and later outcome linkage, including interruption and retry.

## 10. Milestone P5: Manager and operations experience

**Objective:** Let an authorized manager prepare, operate, observe, and close the family program
without direct database changes or ad hoc API calls.

**Owner:** Core maintainer

**Status:** Complete
**Depends on:** P3 and P4
**Evidence:** [P5 Manager and Operations Experience Gate](gates/p5.md)

### P5 acceptance criteria

- Managers create programs, select exact catalog versions, assign roles/repeats, validate the
  definition, activate it, enroll evaluators, and manage sessions using names and search.
- Mapping and printable labeling views are manager-only, minimize disclosure, and never appear
  in participant navigation or payloads.
- Progress views show completion, locks, reveal readiness, missing work, and safe next actions.
- Destructive or irreversible transitions require context-specific confirmation and return a
  reviewable result.
- Managers can view and export recommendation metrics with window, population, exclusions,
  denominators, algorithm version, strategy, and source snapshot.
- Connectivity failure/recovery entry and operational status are available without exposing
  secrets or private payloads.
- Authorization and disclosure tests cover every manager route, cache, error, export, and UI
  state.
- The disclosure matrix includes a participant requesting a cached manager response and records
  the `no-store`, policy-aware cache key, or equivalent control used to prevent cross-role reuse.

## 11. Milestone P6: Integrated pilot readiness

**Objective:** Prove the complete deployed product is safe and usable with synthetic/demo data
before any family member evaluates an actual pilot perfume.

**Owner:** Core maintainer

**Status:** In progress; repository rehearsal kit prepared, external execution pending
**Depends on:** P1 repository controls, P2, and P5
**Evidence:** [P6 Integrated Pilot Readiness Gate](gates/p6.md)

### P6 acceptance criteria

- P1.1-P1.10 external evidence is complete against the release candidate and target topology.
- A production-like deployment passes participant, recorder, and manager journeys through
  Authentik/Traefik on supported desktop and family mobile devices.
- Synthetic/demo data exercises program setup, labels, blind observations, locks, reveal,
  ordinary history, recommendations, feedback revisions, sampling, synthetic outcomes,
  reporting, and recovery without using pilot perfumes or real family outcomes.
- Accessibility, keyboard, disclosure, responsive, performance, and failure-recovery checks pass
  for every pilot-critical page.
- Backup/restore, logs, alerts, secret rotation ownership, and printable/manual outage procedures
  are rehearsed.
- Participant and manager instructions are complete, and the core maintainer records a go/no-go
  decision for F1.

P6 closes only when every criterion passes and the recorded decision is `go`. Any failed
criterion or `no-go` decision keeps F1 blocked.

## 11a. Milestone R: Review remediation and ML foundation

**Objective:** Close the findings of the [Architecture and Design Review](architecture-review-2026-09.md)
and the [ML Structure Review](ml-structure-review-2026-09.md) that block the P6 go decision or the
first pilot perfume, and lay the ML foundation the owner's [ML decisions](ml-decisions-2026-09.md)
require before F1 collects data.

**Owner:** Core maintainer

**Status:** In progress. Completed on 2026-09-19: the ML pipeline skeleton (review Tier 2 items 7,
8, 9, 12, 13 and Tier 3 items 14, 15), `affinity-v2` as the default scorer (Q6), the ADR-009
learning-problem amendment (Q1), and the protocol research prompt (Q8).

**Depends on:** P5. **Blocks:** P6 closure (R1-R4) and F1 (R2, R5-R8).

### Model selection for sprints

Each sprint names the model that leads it, following the Model Selection table in `CLAUDE.md`.
The rule: Haiku only for read-only retrieval (file scanning, structure mapping, lookups) and
never for editing files or preparing deliverables; Sonnet for well-specified implementation,
including documentation; Opus where a mistake is expensive to reverse (schema, security boundary,
cross-cutting refactors, or design that later agents build on); and Fable only for the one design
spike where the reasoning itself is the deliverable. A sprint's review model is one tier above its
lead where the lead is Sonnet. Every sprint reads its cited findings before starting and updates this plan,
the review's implementation-status section, and the relevant ADR in the same pull request.

### Sprints

| ID | Sprint | Scope (findings) | Gate | Lead | Review | Size |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| R1 | CI truthfulness | Frontend lint, typecheck, test, and build job as a required check; remove `api/*`, `llm/*`, `main.py` from the coverage omit list; container CVE gates on for CRITICAL and HIGH; a PostgreSQL job in this repository running `alembic upgrade head`, the parity test from R2, and the integration marker with `P1_DATABASE_URL`; unit tests for the uncovered measurement-service branches; `docs/ci-gates.md`; delete or correct `setup_github_protection.py` (S-11/F-01, S-09, S-10, G-02, G-06, G-11, S-22, S-29, S-26, S-30, D-06) | P6 | Sonnet | Opus | 2 PRs |
| R2 | Migration tooling and schema safety | `naming_convention` on `Base.metadata`; `compare_type`, `compare_server_default`, `render_as_batch` in `alembic/env.py`; PostgreSQL parity test (`compare_metadata == []`); SQLite `foreign_keys` pragma in `conftest.py`; downgrade-raise assertions; one named-constraint migration renaming the 37 unnamed CHECKs, adding range CHECKs on `evaluations`, `IN` CHECKs on role, status, stage, phase, reconciling the six index names, adding the nine FK indexes, and changing the two `evaluations` cascades to `RESTRICT`; `alembic/README` and CONTRIBUTING rules (D-02, D-03, D-04, D-05, D-07, D-09, D-10, D-11, D-15, D-17, D-19, D-20, X-25) | F1; prerequisite for R6 and R7 | Opus | Sonnet tests | 2 PRs |
| R3 | Trust boundary in code | nginx resets `X-Authentik-*` unless the peer is Traefik; uvicorn `--proxy-headers` with the frontend network allow-list; limiter keyed on the verified username; `actor`, `manager`, `authorize_reviewer` moved to `core/auth.py`; one `require_identity()` on every mutating route and one recorder-or-manager check on every reviewer-keyed read (architecture review Q5 pending, default: no cross-reviewer reads); `environment`, `trusted_hosts`, and the `NoDecode` admin-list validator in `Settings`; docs routes and CORS defaults gated on environment; an `authentik_required=True` test suite; a deployed forged-header test added to P1.6 (S-01, S-02, S-03, S-05/B-10, S-06, B-11, S-17, S-18, S-19, S-23, B-27, S-25, F-02) | P6 | Opus | Sonnet tests | 2 PRs |
| R4 | Disclosure leaks, audit trail, logging | Role-neutral 409 on holdout feedback; explanation only by persisted impression id; `log_audit_event` on activate, enroll, lock, reveal, mapping retrieval, checkpoint, prediction create and link; no-store by default under the API prefix; `setup_logging()` in lifespan; `SecretStr` keys and a redaction processor; two new rows in the P1.7 disclosure matrix (B-01, B-02, B-03, B-26, F-15, S-07, S-15) | P6 | Sonnet | Opus | 1 PR |
| R5 | Protocol research reconciliation | Run the [protocol research prompt](../research/scent-evaluation-protocol-research-prompt.md) on a deep-research model; record the result under `docs/research/`; reconcile session size, daily load, calendar spread, judgment scales, ranking procedure, repeat placement, and session-context fields with the calibration guide, the baseline evidence, and the data model; record changes as an ADR-005 amendment; hand schema changes to R7 (ML Decisions Q8) | F1 | Opus | Owner | 1 PR |
| R6 | Vocabulary foundation | `NoteAlias` table with `mapping_version`, normalized unique key on `notes`, `Note.category` cleaned of pyramid position (Kaggle rows backfilled to NULL), `accord_types` lookup with `accord_type` as a foreign key, `intensity_source` on `fragrance_accords` with positional values excluded from measured features by default, one resolver used by both importers, `FragranceNote.rank`, scoped to the 43 baseline and holdout versions alongside P1.1 verification; D1 fixtures (`oak moss`/`oakmoss`, `vanille`/`vanilla`, ambiguous, unknown); `FEATURE_SPACE_VERSION` bump (X-01, X-02, X-03, X-04, X-12; ML Decisions Q2, Q5) | F1 | Opus | Sonnet tests | 2 PRs |
| R7 | Pairwise, behavioral, and context capture | `PairwiseComparison` and `BehavioralEvent` tables; typed sample-provenance columns on `Presentation`; `occurred_on`/`presented_at` and a written session `context`; familiarity as a code on both evidence tables; `scrubbed_off` and `time_to_scrub_minutes`; the end-of-session ranking prompt in the calibration page yielding three pairwise rows; scenario lookups schema-only; shapes adjusted to R5's result before merge (X-07, X-08, X-09, X-14, X-22, X-23; ML Decisions Q3, Q8) | F1 | Sonnet | Opus | 2 PRs |
| R8 | Training eligibility and provenance in schema | `training_eligibility` on both evidence tables and a `v_training_rows` view; manager-only view for role and repeat linkage; `SourceSnapshot` gains `source_revision`, `content_hash`, `parser_version`, `license_evidence`, `verified_by`, the ADR-012 columns, and a nullable `source_url`; `ModelCheckpoint` gains exclusions, filters, feature-space and taxonomy versions, params, and input digest; typed checkpoint predictions; `FeatureSnapshot` rows; `predict.py` and `dataset.py` read the view (X-05, X-06, X-16, X-17, D-01, M-07, M-08) | F1 | Opus | Sonnet tests | 2 PRs |
| R9 | Scaffold deletion | Remove `api/ratings.py`, `api/catalog_stub.py`, `llm/`, `middleware/auth.py`, the Postman workflow and collection (or retarget at `/api/v1`), `core/cache.py` and the `redis` dependency, `jobs/`, `utils/financial.py`, unused health checks, demo CLI commands; flag-gate the Parfumo scraper with a deprecation warning after moving GTIN evidence into `SourceSnapshot`; rewrite the app description and README overview (G-03, G-07, B-21, B-22, B-23, B-24, B-30, F-04/F-22, B-34; architecture review Q1-Q4, Q12 pending, defaults apply) | none (maintainability) | Sonnet | Opus | 2 PRs |
| R10 | Backend consolidation | Services never commit; one `ProjectBaseError` handler; domain exceptions replace `reject()` and raw `HTTPException` in services; activation, skin planning, finalization, and checkpoint creation move into `CalibrationService` with checkpoint creation under the enrollment lock plus a PostgreSQL concurrency test; control-flow asserts replaced; N+1 and unbounded queries fixed; import size bounded; registry-validated `candidate_strategy` and checkpoint `algorithm_version` (B-04, B-05, B-07, B-08, B-09, B-14, B-15, B-16, B-17, B-25, B-29, B-33, B-35, B-31, M-11) | none | Opus | Sonnet tests | 3 PRs |
| R11 | Typed calibration contract and generated client | Pydantic response models with `response_model=` on all calibration routes; provenance fields (`algorithm_version`, `candidate_strategy`, `score_type`, `score_value`, `recorded_by`), `fragrance_name` and `fragrance_brand` on `EvaluationResponse`, RFC 3339 offsets on timestamps; client generated from `docs/api/openapi.json` and committed; a CI diff between the committed spec and a fresh export (F-03, F-04, F-05, B-13, F-20, Appendix A) | none | Sonnet | Opus | 2 PRs |
| R12 | Frontend decomposition and state | Split `ProgramSetupPage`; hoist `RecommendationCard`; typed route params with a not-found route; keyed data store with invalidation after mutations; 401 interceptor; per-action task state; error boundary; design tokens with dark mode; type-aware ESLint with `jsx-a11y`; server-side progress summary for Home (F-06 to F-09, F-12, F-16 to F-21, F-23 to F-26) | none | Sonnet | Opus | 3 PRs |
| R13 | End-to-end and accessibility harness (see sequencing note 8: substantially covered by PR #103) | Playwright with a compose-backed fixture and a forward-auth stub covering the five P4 journeys and the P5 manager journey with interruption and retry; MSW in Vitest; `vitest-axe` on every route; a 360 px assertion; P4 and P5 gate records re-closed or amended per architecture review Q13 (G-01, F-10, F-11, F-13) | P6 (per Q13) | Sonnet | Opus | 2 PRs |
| R14 | Operations, observability, and documentation | Secrets plumbed from the prod override; topology validator extended; digest-pinned base images and cosign; runtime hardening; `.env.example` and build-arg fixes; scheduled backup with a restore check and `pre_migration_inventory.py` and `verify_restore.py`; documentation consolidation (delete `CONFIG_TEMPLATES_SUMMARY.md`, archive `concept.md`, merge ADR directories, rewrite README, regenerate the CLAUDE.md structure section, supersede `SECURITY-FINDINGS.md`, update the gap analysis to v1.1) (S-04, S-08, S-12, S-13, S-16, S-20, S-27, S-28, D-18, G-04, G-05, G-08, G-10, G-12, D-14) | P6 for secrets, validator, and backups; none for docs | Sonnet (Haiku may be used only for read-only discovery of stale references) | Opus | 3 PRs |
| R15 | First learned model and comparison | Design spike: a written model spec for a partially pooled linear or ordinal model on the R6 reduced basis with a population prior, the evaluation plan against the repeat ceiling, and the decision rule instance; then `ml` optional dependency group (`numpy`, `scipy`, `scikit-learn`), the model registered beside `affinity-v2`, `predict_and_freeze` on the same holdouts, and a scorecard report; no tuning on holdouts (ML Decisions Q7; review Tier 4 items 17 and 18) | D5 entry; may start after R6 and R8 | Fable for the design spike (one session); Opus implements | Sonnet tests | 1 doc + 2 PRs |

### Sequencing

1. R1, then R2, in that order (R2's parity test needs R1's PostgreSQL job to be visible in CI).
2. R3 and R4 in parallel after R1; both must merge before the P6 go decision.
3. R5 as soon as the research result is available; R6 after R2; R7 after R5 and R2; R8 after R6.
4. R9 after the architecture review's Q1-Q4 and Q12 are decided (defaults apply if undecided).
5. R10 after R3 and R9; R11 after R10; R12 after R11; R13 any time after R1.
6. R14 operations items before the P6 decision; documentation items whenever capacity allows.
7. R15 after R6 and R8, before D5.
8. R13 is substantially, not fully, covered by PR #103 (merged 2026-09-19; ADR-014), which
   landed while this Milestone R plan was in review. Before starting R13, check ADR-014 and
   PR #103's own stated residual gaps first and rescope R13 to just what remains, rather than
   redoing the harness: the smoke tier has never been run against live Docker infrastructure,
   the P1.8 gate (not P4/P5) is the one recorded closed, and PR #103 names three explicit
   out-of-scope items (frontend performance budgets, `ProgramSetupPage`'s internal manager
   actions beyond the authorization boundary, and `RatingsPage`'s correction flow at the e2e
   tier).

### Definition of done for an R sprint

- The cited findings are marked resolved in the review's implementation-status section with the
  merge commit.
- This plan's status line and the roadmap mirror are updated in the same pull request.
- Any durable decision is recorded as an ADR or ADR amendment.
- The full backend and frontend gates pass; a schema change carries the R2 parity test.
- No P6 or F1 gate is marked closer to complete without the retained evidence its gate record
  names.

## 12. Milestone F1: Initial family perfume pilot

**Objective:** Observe real family use of the complete product and establish honest baseline
values before discovery work.

**Owner:** Product owner and core maintainer

**Status:** Planned
**Depends on:** P6
**Evidence:** [F1 Initial Family Pilot Gate](gates/f1.md)

### F1 acceptance criteria

- The pilot declares its dates, evaluators, exact physical samples, algorithm version, candidate
  strategy, source snapshot, exclusions, and stopping conditions before first exposure.
- Family members use only the released UI for pilot tasks; support interventions and workflow
  failures are logged.
- Reports retain interest, response coverage, sampling conversion, post-sample liking, wear/buy,
  availability, coverage, variety, and connectivity/recovery counts with denominators.
- The review records usability problems separately from fragrance or algorithm outcomes.
- The core maintainer retains a redacted evidence export and records a decision. Only a
  proceed-to-D1 decision completes F1 for sequencing; revise, extend, or stop keeps D1 blocked.

## 13. Milestone D1: Source and vocabulary foundation

**Objective:** Create a reproducible, licensed vocabulary and source layer without erasing raw
labels or changing assigned identities.

**Owner:** Core maintainer

**Status:** Planned
**Depends on:** F1

### D1 deliverables and acceptance criteria

- Versioned alias sets and taxonomy mappings are separate from raw source labels and evaluator
  perception.
- Ambiguous terms remain unresolved until explicitly reviewed.
- Every adopted asset records origin, revision, retrieval time, license/permission evidence,
  snapshot hash, and applicable attribution/share-alike obligations.
- Alias application deduplicates equivalent mapped notes within a fragrance for statistics while
  preserving every source label.
- Unknown concentration stays unknown.
- Same-name concentration variants coexist and remain distinct.
- Assigned program identity fields remain immutable.
- A preservation-aware migration/backfill plan includes dry-run counts, collision reports,
  rollback by restore or reversible mapping version, and idempotency checks.
- Fixtures cover `oak moss`/ `oakmoss`, `vanille`/ `vanilla`, ambiguous labels, exact
  matches, unknown terms, and sparse/minimalist fragrances.

### Decisions due before implementation

| Decision | Default |
| :--- | :--- |
| Reuse Scent chords code | Independently implement unless an explicit software license or permission is obtained |
| Import its Fragrantica-derived corpus | Do not import until intended use and upstream rights are reviewed |
| Adopt Parfica assets | Pilot only identified assets under their individual licenses and pinned revisions |
| Use one global family taxonomy | Preserve source-specific classifications and explicit mapping versions |

## 14. Milestone D2: Reproducible catalog statistics

**Objective:** Produce reviewable frequency and association statistics from one declared eligible
population.

**Owner:** Core maintainer

**Status:** Planned
**Depends on:** D1

### D2 acceptance criteria

- Note totals, pair counts, population size, filters, exclusions, taxonomy version, alias version,
  and source hash come from the same snapshot.
- Aliases are resolved and notes deduplicated within each fragrance before counting.
- Raw frequency, partner share, observed-minus-expected, and lift are labeled distinctly.
- Zero or undefined denominators return explicit states.
- Minimum support or shrinkage policy is versioned and shown with results.
- Filter changes recompute every denominator.
- Minimalist fragrances remain eligible where the product use case requires them.
- A regression fixture has subset prevalence different from whole-corpus prevalence.
- The build is deterministic from authorized inputs and produces a manifest plus artifact hash.
- Performance budgets are defined for preprocessing, artifact size, API latency, and frontend
  loading before implementation is accepted.

## 15. Milestone D3: Post-reveal exploration

**Objective:** Help evaluators understand a fragrance after reveal while maintaining clear
evidence boundaries.

**Owner:** Core maintainer

**Status:** Planned
**Depends on:** D2 and P1

### D3 acceptance criteria

- Profile sections separately label published source data, evaluator perception, and model
  interpretation.
- Pyramid rank is not rendered as ingredient percentage.
- Raw and beyond-chance association views name the displayed statistic and population.
- Every visual has an accessible list or table and supports keyboard and mobile use.
- Offline/local assets are available for core profile use.
- External links or embeds are post-reveal only. Any iframe message validates both origin and
  source, uses a narrow schema, and sends no evaluator data.
- New APIs, caches, summaries, and exports reuse the central disclosure policy.

## 16. Milestone D4: Candidate discovery pilot

**Objective:** Generate useful candidates from published-note similarity and controlled contrasts
without claiming that similarity predicts liking.

**Owner:** Core maintainer

**Status:** Planned
**Depends on:** D2 and F1

### D4 acceptance criteria

- Candidate strategies include a declared baseline, similar published-note profiles, and
  controlled contrasts.
- Each candidate records retrieval algorithm/version, source snapshot, score type, score,
  shared/contrasting features, filters, selection reason, and model run.
- Concentration variants remain distinct.
- Exact identity and sample availability are verified before experimental assignment.
- Predicted liking, novelty, uncertainty, availability, and cost remain separate fields.
- The UI labels set-based retrieval as “Similar published note profile.”
- Candidate generation cannot access final holdout outcomes.
- Coverage and variety thresholds prevent a narrow set of houses, families, or notes from
  dominating without explicit justification.

## 17. Milestone D5: Prospective evaluation

**Objective:** Determine whether candidate discovery improves real post-sample outcomes over the
existing affinity approach.

**Owner:** Core maintainer

**Status:** Planned
**Depends on:** D4, P2, and F1

### D5 acceptance criteria

- Development, validation, and final holdout roles are declared before outcomes are collected.
- Candidate choices, algorithms, input manifests, source snapshots, and predictions are frozen
  before eligible holdout responses.
- Existing affinity, discovery strategy, and any simple baseline use the same eligibility and
  outcome definitions.
- Results report interest, response coverage, sampling conversion, post-sample liking,
  wear/buy outcomes, coverage, variety, and unavailable candidates separately.
- Repeats estimate within-evaluator reliability without being treated as independent samples.
- Analysis reports counts and uncertainty appropriate for four evaluators.
- Final holdout outcomes are never used to tune aliases, thresholds, filters, or weights reported
  against those outcomes.
- A written decision records whether to adopt, revise, or stop each candidate strategy.

## 18. Cross-cutting definition of ready

A work package may enter implementation only when:

- the user outcome and non-goals are explicit;
- dependencies and governing ADRs are accepted;
- data classification and blind-disclosure impact are reviewed;
- schema/API/UI contracts and migration implications are described;
- source rights are recorded for every required external asset;
- measurable acceptance criteria and evidence locations exist;
- target environment, fixtures, performance budget, and rollback/recovery path are identified;
- the work is small enough to complete and review within one sprint or is split further.

## 19. Cross-cutting definition of done

- Acceptance criteria pass with retained evidence.
- Backend and frontend lint, type, test, and build checks pass as applicable.
- PostgreSQL-specific behavior is tested in PostgreSQL when relied upon.
- Security and blind-disclosure tests cover new endpoints, caches, exports, and logs.
- Migrations preserve raw observations and have a tested recovery path.
- OpenAPI, user documentation, operations guidance, plan status, and ADRs are updated.
- Accessibility and mobile checks cover user-facing changes.
- Performance and external-service degradation meet the declared budgets.
- Code review is complete and the change is merged.

## 20. Traceability matrix

| Product outcome | Delivery path | Evidence |
| :--- | :--- | :--- |
| Preserve trustworthy experience history | P1, P4-P6, ADR-005, ADR-007 | Migration inventory, UI history/disclosure tests, restore drill |
| Resolve exact fragrance versions | P1, D1, ADR-006 | Verified manifest, collision report, immutable-assignment tests |
| Produce explainable profiles | D1–D3, ADR-006/007 | Snapshot manifests, statistic fixtures, accessible profile tests |
| Provide a usable family product before testing | P3-P6 | Role-aware UI tests, synthetic rehearsal, pilot-readiness decision |
| Recommend useful and varied candidates | P2, F1, D4 | Impression/outcome records, coverage and variety reports |
| Demonstrate improvement prospectively | F1, D5, ADR-009 | Baseline export, frozen checkpoints, holdout analysis, adoption decision |
| Protect family and blind data | P1 and every later milestone, ADR-008 | Proxy bypass and disclosure matrices |
| Maintain low-touch self-hosting | P1 operations and all degradation criteria | Runbook, health checks, backup/restore evidence |

## 21. Risk register

| Risk | Probability | Impact | Owner | Mitigation and trigger |
| :--- | :--- | :--- | :--- | :--- |
| Migration loses or blocks encounter history | Medium | Critical | Core maintainer | Backup-clone rehearsal and restore drill before deployment |
| Backend bypasses Authentik/Traefik | Medium | Critical | Core maintainer | Remove or isolate direct exposure; deployed bypass test blocks release |
| Blind identity leaks through a derived surface | Medium | Critical | Core maintainer | Central policy plus route/cache/export/log disclosure matrix |
| Baseline manifest maps the wrong concentration | Medium | High | Experiment manager | Two-source/physical verification; unresolved versions remain unassigned |
| Recommendation work optimizes interest instead of liking | High | High | Product owner | P2 separates metric types; F1 records real outcomes before D1 |
| Small sample produces unstable conclusions | High | High | Product owner | Counts, uncertainty, repeats, frozen baselines, modest claims |
| Source rights do not permit intended reuse | Medium | High | Core maintainer | D1 rights record and safe defaults; retain manual/source-link alternatives |
| Alias mapping merges distinct concepts | Medium | High | Core maintainer | Versioned mappings, raw labels, collision review, reversible reprocessing |
| Filtered statistics mix denominators | Medium | High | Core maintainer | Same-population calculation contract and subset regression fixture |
| External sources or OpenRouter fail | Medium | Medium | Core maintainer | Local capture/scoring fallback, timeouts, rate limits, observability |
| Prototype UI causes invalid or abandoned pilot data | High | High | Core maintainer | P3-P6 complete and pass a synthetic rehearsal before F1 |
| Family participation or feedback coverage is low | Medium | High | Product owner | P4 one-interaction feedback and F1 response-coverage/workflow observation |
| Mobile/home connectivity prevents use | Medium | Medium | Core maintainer | P6 rehearses failure handling; F1 measures failures and retains manual recovery |
| Scope expands into advanced ML too early | Medium | Medium | Product owner | D5 decision gate; active learning and calibrated claims remain out of scope |

## 22. Audit finding disposition

This table preserves the complete P0 review so later sprints do not lose its constraints.

| Finding | Disposition |
| :--- | :--- |
| Plan was pinned to `ff026ef` and called merged calibration pending | Corrected by the current-state ledger and P1 deployment distinction |
| Frontend was described as a scaffold | Corrected; current UI baseline and missing recommendation flow are explicit |
| Vision omitted controlled calibration and prospective evaluation | Vision v2 now includes both |
| “80% interesting” was called accuracy | Reclassified as an interest metric; P2 defines measurement and F1/D5 define actual outcome evaluation |
| Recommendation feedback did not exist despite being a success dependency | P2 implements durable measurement; P4 exposes the complete workflow before F1 collects data |
| The measurement gate placed family testing before a complete product UI | P3-P6 now require participant, manager, reporting, deployment, and synthetic rehearsal readiness before F1 |
| Accepted ADRs diverged from implementation | ADR-005 through ADR-009 amend or supersede the affected decisions |
| Technical specification said no authentication | Corrected to the Authentik/Traefik trust boundary |
| Production Compose could expose backend port 8000 | P1.6 requires topology correction/validation and a bypass test |
| D0 mixed merged code with unfinished release work | Replaced by P1 work packages and deployment evidence |
| D1–D5 lacked owners, entry/exit gates, and retained evidence | Added throughout this plan |
| Source licensing and taxonomy choices had no decision deadline | Decisions are required before D1 implementation |
| Alias/source changes lacked migration and backfill policy | Added to D1 acceptance criteria |
| Live PostgreSQL migration and concurrency were unverified | P1.2–P1.4 are release-blocking |
| Backup and recovery were described but not rehearsed | P1.5 requires a restore drill |
| Calibration design was missing from documentation navigation | P0 adds it to published navigation |
| Test plan depended heavily on SQLite | Definition of done and P1 require PostgreSQL for PostgreSQL behavior |
| Blind tests did not enumerate every derived surface | P1.7 covers search, history, profiles, recommendations, explanations, caches, errors, exports, and logs |
| Plan lacked observability and external-service degradation | P1.10 and P2 metrics add operations, cost, latency, failures, and cache behavior; P6 rehearses them |
| Plan lacked mobile/accessibility acceptance criteria | P3-P6 and D3 include mobile and accessible workflows |
| Plan did not define candidate availability or diversity | D4 records availability and enforces coverage/variety reporting |
| Plan did not define prospective comparison protocol | ADR-009 and D5 specify frozen strategies, inputs, outcomes, and reporting |
| Historical roadmaps remained easy to mistake for current work | Roadmap is replaced with a compact mirror of this authority |
| Local targeted recommendation test hung under Python 3.14 | P1.8 requires deterministic verification on supported Python 3.12 and PostgreSQL 16 |
| LLM explanations could be mistaken for core ranking | Vision and ADR-003 retain deterministic ranking and optional explanation behavior |
| Explanation/cache behavior needed reproducibility and leakage treatment | P1.7 and P2 require cache disclosure, version, latency, failure, and cost evidence |
| Match scores could be presented as probabilities | Vision, plan, ADR-007, and D3 require honest affinity labels |
| Published notes, perceived notes, and model interpretations could be conflated | Vision, ADR-006, D1, and D3 separate these layers |
| Small-support lift could be misleading | D2 requires support, denominator handling, and versioned filtering/shrinkage |
| External iframe integration could leak data | D3 restricts it to post-reveal and validates origin/source with no evaluator payload |
| Generic YAML validation rejected supported `!ENV` and Compose `!reset` tags | P1 narrowed the generic hook exclusion; dedicated validators remain active |
| Strict JSON validation treated TypeScript JSONC configuration as JSON | P1 excludes only the JSONC TypeScript configuration files |
| Existing shebang maintenance scripts were not executable | P1 corrected their executable modes and the repository-wide hook passes |
| The FIPS workflow declared a string default for a Boolean dispatch input | P1 corrected the type and the workflow schema validator passes |

## 23. Evidence locations

Milestone evidence belongs under `docs/planning/gates/<milestone>.md` with the date, environment,
commit, commands/procedure, result, reviewer, and any redactions. Machine-generated artifacts may
live outside Git when sensitive or large, but their hash and controlled storage location must be
recorded in the gate report.

Production backups, secrets, raw private responses, and blind mappings must not be committed.

## 24. Change control

- Update this plan in the same pull request when scope, sequence, status, or a gate changes.
- Record expensive-to-reverse technical or policy changes in an ADR.
- Record deferred work in a named milestone rather than prose such as “future.”
- A milestone becomes complete only when its evidence is reviewed.
- Any exception to a release-blocking invariant requires an explicit ADR and product-owner
  decision; schedule pressure is not sufficient.

## 25. Related documents

- [Project Vision](project-vision.md)
- [Technical Specification](tech-spec.md)
- [Execution Roadmap](roadmap.md)
- [ADR Index](adr/README.md)
- [Controlled Calibration V1](../calibration-v1.md)
- [Scent Chords Analysis](../research/scent-chords-analysis.md)
- [Data Model Gap Analysis](data-model-gap-analysis.md) (preference learning, scenario modeling,
  and future ML; captured as ADR-010, partially implemented)
