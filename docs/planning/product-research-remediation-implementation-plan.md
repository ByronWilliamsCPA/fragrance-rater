# Product, UX, Research, and ML Remediation: Implementation Plan

> **Status**: Draft, not yet approved | **Owner**: Core maintainer / product owner
> **Depends on**: PROJECT-PLAN.md v2.3 (authoritative), architecture-review-2026-09.md,
> ml-structure-review-2026-09.md, ml-decisions-2026-09.md, ADR-004/005/007/009/010/012/013/016
> **Produced by**: Independent verification of three new gap-analysis documents, three new
> research documents, and one uncommitted frontend feature, all authored in a single prior
> session directly on `main` before being moved to `feat/product-research-remediation-plan`.

## 1. Executive conclusion

The three gap-analysis documents (`user-roles-and-workflows-gap-analysis.md`,
`frontend-visual-and-usability-gap-analysis.md`, `preference-prediction-data-capture-assessment.md`)
are **factually accurate at the code level**: every claim independently spot-checked against
current routes, models, migrations, and tests matched. Their weakness is not correctness, it is
**staleness against `PROJECT-PLAN.md` and the two prior architecture/ML reviews**: most of what
they flag is not a new discovery, it is already-decided, already-scheduled work inside Milestone R
(sprints R3, R4, R6, R7, R8), none of which cite the architecture review or the ML structure
review. Treating this session's documents as a fresh remediation sequence would create a **parallel,
duplicate tracking system** that drifts from `PROJECT-PLAN.md`, the actual authority.

The uncommitted frontend code change (`EvidencePage.tsx` and its wiring) is **unrelated** to the
frontend gap-analysis document's findings: it implements none of them. It is a separate, solid,
low-risk static research page. The frontend UX remediation items (nav wrapping, scale-field
wrapping on phone, sticky calibration header, Home redesign) remain **fully outstanding**.

The research/marketing evidence work is in good shape: the two known-fabricated statistics
("86% less regret," "3.2× repurchase") are **not** presented as valid anywhere in the current
`EvidencePage.tsx`: they are named and explicitly rejected. The existing
`perfume-purchasing-research-validation.md` already did rigorous primary-source verification;
independent re-checking in this review did not surface any error in it.

The most material finding is in the ML/data domain: **season, setting, and application context
have no schema representation at all**, R7 (the sprint meant to add it) is scoped only as
"scenario lookups schema-only" (no label collection), and the data-capture assessment treats
season/setting as a required pre-baseline capability. This is a real, unresolved conflict between
two planning documents and needs an explicit owner decision before F1, not a silent default.

**Net recommendation**: fold this session's findings into the existing Milestone R sprint scopes
(primarily R2, R6, R7, R8) rather than creating new milestones, except for the handful of
genuinely new findings identified in Section 4 (decision register) and Section 6 (prioritized
findings), which need owner decisions to be routed correctly.

## 2. Verified current-state summary

| Area | Verified state | Evidence |
| :--- | :--- | :--- |
| Roles/authorization | Authentik identity threading exists (`core/auth.py`); durable reviewer-account link, cross-reviewer read scoping, and general admin/audit UI do not | roles-workflows-review; architecture-review S-05/B-10, Q5 |
| Frontend UX (pre-existing) | Nav wraps uncontrolled past ~6 links; 0-10 scale field wraps with no phone treatment; both confirmed live in code, unfixed | `layout.css:72-78`, `components.css:460-463` |
| Frontend UX (this diff) | New static `EvidencePage.tsx`, footer/About link only, `hiddenFromNav: true`; well-built, follows existing conventions; two minor follow-ups | frontend-ux-review FE-04/05/07/08 |
| ML/data schema | 15 linear Alembic migrations to head `7daf681ed339`; season/setting/exposure-timestamp/randomization/consent/data-dictionary all absent; eligibility view absent; `training_eligibility_code` exists but scoped to `fragrances` only | ml-data-review (full table in Section 6) |
| ML pipeline code | `ml/` package (7 modules) implements feature space, dataset builder, `predict_and_freeze`, registry, reliability, scorecards; no learned model fit; `affinity-v2` heuristic is default | ml-data-review DC-11, MS-06/07 |
| Fragella | Only `search()`/`usage()` implemented; `/match`/`/similar` absent; candidate/scoring separation intact; one low-severity "confidence" label leak in manager UI | fragella-review |
| Research evidence | Both fabricated statistics named and rejected in `EvidencePage.tsx`; all other displayed figures trace to real primary sources with existing caveats; MHC/HLA claim in the literature review is actually contradicted by a 2020 meta-analysis | research-evidence-review |
| BLaIR | Confirmed a generic e-commerce encoder benchmark (Amazon/Yelp/MovieLens), not a fragrance model; does not change milestone sequencing; supports one already-held principle (evaluate encoders in-domain) | blair-review |
| Build/test | `npm run build` clean; 182/182 Vitest unit tests pass; 32/32 Playwright accessibility tests pass (after working around an unrelated port-3000 collision); no horizontal overflow at 375px/1440px for 5 sampled routes | frontend-verification |
| Worktree hygiene | `main` in the primary working directory still carries the identical uncommitted diff as this worktree: not yet cleaned up, pending owner confirmation (see final session report, not this plan) | frontend-verification, git status |

## 3. Scope and explicit non-goals

**In scope for this plan**: reconciling the three new gap-analysis/assessment documents and three
research documents with `PROJECT-PLAN.md`; specifying the concrete schema, API, and frontend
changes needed to close pre-baseline-blocking gaps; specifying governance for research/marketing
evidence; specifying a BLaIR-informed semantic-encoder experiment plan for **after** first-party
data exists.

**Explicit non-goals** (do not build yet, see Section 27 for the full list): any learned model
beyond the existing heuristic scorers (that's R15, gated on R6+R8, itself gated on D5 entry);
Fragella `/match`/`/similar` implementation (milestone D4, gated on D2 and F1); preference-driver
attribution features (blocked by ADR-016 until after F1, by explicit ADR text); a semantic-encoder
candidate strategy (BLaIR-informed, but requires first-party data that does not exist yet);
personal collection/ownership tracking as a full feature (new scope, needs a milestone slot, not
built here); any visual-preference change flagged as subjective rather than a defect.

## 4. Decision register

Each decision below blocks at least one downstream implementation item. None are implemented by
this plan; each needs the product owner's explicit answer.

| ID | Decision | Options | Recommended default | Blocks |
| :--- | :--- | :--- | :--- | :--- |
| DEC-01 | Is season/setting/occasion a first-generation prediction input, or deferred? | (a) Widen R7 to collect a minimal season/setting/occasion label at observation time; (b) keep R7 schema-only and defer all context-conditioned prediction past F1 | (a): a minimal, coarse label (season + indoor/outdoor + solo/social) is cheap to collect now and cannot be reconstructed later; full scenario taxonomy can wait | R7 scope, DC-01, XD-01 |
| DEC-02 | Do the ten §13 data-contract items (data dictionary, instrument version, response-status vocabulary, randomization record, quality-vs-eligibility split, supersession, censoring, time-varying ownership, consent, release manifest) get their own sprint, or fold into R2/R6/R7/R8? | (a) New pre-baseline sprint (call it R16); (b) fold each item into the R-sprint that owns its table | (b), itemized in Section 23 phase table: avoids a 16th sprint and keeps each item next to the schema it modifies | R2, R6, R7, R8 scopes; DC-16..26 |
| DEC-03 | Reconcile `would_buy` placement: current UI asks it as a 0-10 skin-stage question; ADR-005's 2026-09-19 amendment implies it should move | Move `would_buy` out of the blind skin core into a separate, explicitly-labeled decision question with offer/scenario context fields, per DC-06 | Move it; keep the 0-10 scale for backward comparability but gate it behind a context capture (DEC-01) | R7, DC-06, `calibrationScales.ts:184` |
| DEC-04 | Does the assessment's P1 recommendation to add preference-driver features conflict with ADR-016 and should it be withdrawn? | ADR-016 status is `Proposed, requires maintainer decision, not implemented`, with 7 open questions and an explicit "should not land before F1" | Withdraw the assessment's P1 recommendation; defer to ADR-016's own resolution process, which is separately gated to not land before F1 | DC-14, XD-03 |
| DEC-05 | Route the two genuinely-new UX findings (WS-03 collection/ownership tracking, CAL-02 validated 33-fragrance baseline template) into a milestone | Neither exists in any R-sprint or ADR today | Add CAL-02 (baseline template validation) to R6/R7 scope (it's cheap, schema-adjacent); scope WS-03 (collection/ownership) as its own future milestone after F1: it's a full feature, not a gap fix | ROLES/WS review, PROJECT-PLAN §11a |
| DEC-06 | Relabel Fragella's raw `Confidence` field in the manager UI away from "confidence" | FRAG-01: low severity, but ADR-007 reserves that term project-wide | Rename to "Fragella match confidence" or similar, small frontend-only change | ProgramSetupPage.tsx:405-406 |
| DEC-07 | Should the three new gap-analysis documents be corrected in place to cross-reference the architecture review and Milestone R, or superseded by this plan? | (a) Annotate each doc with a pointer to this plan and the relevant R-sprint; (b) leave as-is and rely on this plan alone | (a): a future reader of the standalone docs should not re-discover findings as if new | docs/planning/README.md entries |
| DEC-08 | Cadence for the real-backend Playwright smoke tier (nightly vs. pre-deploy) | Carried over from P1.8, unresolved before this session too | Not re-decided here; flagged again because R13/R14 touch the same CI surface this plan's frontend items depend on | PROJECT-PLAN.md:200-203 |

## 5. Requirement-to-code traceability

| Product capability (from task brief) | Delivery path | Current state | Gap |
| :--- | :--- | :--- | :--- |
| Reviewing perfumes | P4 (complete) | Implemented | None |
| Recording ownership/collection state | Not in any milestone | **Absent** (WS-03) | New scope, DEC-05 |
| Controlled blind baseline of 33 perfumes | Milestone R5 (protocol, done), R6/R7 (schema) | Protocol decided; no template/count enforcement in UI (`session_size` defaults to 3, `ProgramSetupPage.tsx:475`) | CAL-02 |
| Core preference profile | P2 (complete, measurement); no profile-page UI | Computed, not surfaced as a page (PREF-01) | New frontend item, Section 10 |
| Future candidate recommendations | D4 (planned, gated) | Recommendation delivery/feedback (non-Fragella) implemented; Fragella candidate discovery absent | Tracked correctly as Planned |
| Recorder-vs-subject provenance | R3/R4 (in progress) | `recorded_by`/`reviewer_id`/`worn_by_reviewer_id` exist for evidence rows; cross-reviewer read scoping (Q5) not yet enforced | ROLES-03 (duplicate of S-05/B-10, already scheduled) |
| Admin workflows | R3/R4 (in progress), partial | Calibration admin strong; general reviewer/fragrance CRUD has no admin check at all | ADMIN-01 |

## 6. Prioritized findings with severity and evidence

Findings are grouped by domain and carry the originating subagent's stable slug. **Do not
re-file these as new issues**: cross-reference the slug in any tracker entry.

### Roles and workflows (roles-workflows-review)

| Slug | Summary | Classification | Severity | Notes |
| :--- | :--- | :--- | :--- | :--- |
| ROLES-01 | No durable Reviewer↔account link table | Partially implemented | High | `models/reviewer.py` has no account FK |
| ROLES-02 | Roles inferred client-side, not durable | Implemented as designed | High (by design) | `roleLabelFor(capabilities)` |
| ROLES-03 | Ordinary-encounter reads have no reviewer-scoping | **Duplicate of already-tracked S-05/B-10** | High, but already scheduled | Owner decision Q5 already made; work is R3 WS-2, not started |
| ROLES-04 | Acting-for-another lacks complete grant model outside calibration | Partially implemented | Medium | Same root cause as ROLES-03 |
| WS-03 | No personal collection/ownership tracking | **Confirmed missing, genuinely new** | High | Zero model/route/ADR references |
| WS-04 | No consumer catalog/browse route | Confirmed missing | Medium | 9-route table has no browse/detail route |
| CAL-02 | 33-fragrance baseline has no validated template | **Confirmed, not covered by any R-sprint** | High | `session_size` UI field defaults to 3, unconstrained |
| PREF-01 | No preference-library/profile page | Confirmed missing | High | Computed evidence exists, not surfaced |
| PREF-02 | Recommendations gate on `MIN_EVALUATIONS = 3`, not 33 | Confirmed, matches doc | Medium | `recommendation_service.py:47` |
| ADMIN-01 | Reviewer/fragrance CRUD has no admin/manager check | Confirmed | High | `api/reviewers.py`, `api/fragrances.py` |

### Frontend UX (frontend-ux-review)

| Slug | Summary | Classification | Severity |
| :--- | :--- | :--- | :--- |
| FE-01 | Uncommitted diff implements none of the gap-analysis remediation items | Scope mismatch, not a code defect | Critical (planning risk) |
| FE-02 | Nav wraps uncontrolled with 6 visible links, no phone collapse | Confirmed, unfixed | High |
| FE-03 | 0-10 scale field wraps with no distinct phone treatment | Confirmed, unfixed | High |
| FE-08 | `EvidencePage.tsx` stats section uses fragile hardcoded array indices into `sources` | Code smell | Low |
| FE-09 | AboutPage rewrap is whitespace-only | Non-issue | n/a |

### ML/data model (ml-data-review): see also Section 7-8

The full 26-item DC table, 10-item MS table, and 5-item XD conflict table are reproduced in
Sections 7, 8, and 15. Headline severities: **Critical**: DC-01 (season/setting absent), DC-02
(exposure metadata absent), DC-03/MS-04 (vocabulary unnormalized), DC-04/MS-02 (evidence-row
eligibility view absent), DC-05 (no true exposure timestamp). **High**: DC-06 (`would_buy`
placement conflict), DC-08 (pairwise/ranking schema absent), DC-15 (perceived notes unjoinable),
DC-16 through DC-25 (data-contract items, none in any sprint scope), MS-10 (no feature-snapshot
digest).

### Fragella (fragella-review)

| Slug | Summary | Severity | Blocks D4? |
| :--- | :--- | :--- | :--- |
| FRAG-01 | Manager UI labels Fragella's raw field "confidence," ADR-007 reserves the term | Low | No |
| FRAG-02 | All match/similar-discovery checklist items unimplemented, matching `Status: Planned` | Informational | Yes, by design |
| FRAG-03 | `fragella_lookup_service.py` uses stdlib logging, no correlation ID | Low | No (tracked as B-35) |

### Research/marketing evidence (research-evidence-review)

| Slug | Summary | Classification | Severity |
| :--- | :--- | :--- | :--- |
| RE-01 | "86% less regret" / "3.2× repurchase" | Unsupported (vendor marketing, no public methodology) | Critical if ever promoted to a stats display; currently correctly rejected in-page |
| RE-02 | MHC/HLA genotype framed as "most robustly documented" driver | **Contradicted** by 2020 meta-analysis | High: must not justify collecting genetic data |
| RE-03 | Ganti/JAAFR ~300-person purchase-driver ranking | Unsupported (circular regression) | Medium |
| RE-04 | Grech (2009) brand-personality thesis | Real but unpublished undergraduate thesis, too weak to generalize | Low |
| RE-05 | Doucé et al. ambient-scent study | Real, but store-ambience, not worn-perfume; out of scope for recommendation logic | Low |
| RE-06 | "GC-MS as ultimate ground truth" / "POM as ready foundation for recommendation" | Both overstate narrow chemistry/single-molecule findings into product claims | Medium |

### BLaIR (blair-review)

All nine working conclusions from the task brief were independently checked; none were found
Wrong. Two (#3, #5, #7-#9) need qualification: BLaIR is directionally supportive but does not
itself validate a fragrance-specific application. See Section 13 for the resulting experiment
plan.

## 7. Proposed target data model

Additive, backward-compatible changes only; no destructive migration of existing rows. Each item
below is scoped to the R-sprint that should own it per DEC-02.

| Change | Owning sprint | Rationale |
| :--- | :--- | :--- |
| `PresentationExposure` sub-table or columns on `Presentation`: `occurred_on` (date), `presented_at` (timestamptz), `evaluator_timezone`, `application_method`, `dose_sprays`, `sample_source_type` (decant/original/sample-card), `container_opened_on` | R7 | DC-02, DC-05: physical exposure identity is unrecoverable after the fact |
| `SessionContext` columns/table replacing the unused `CalibrationSession.context` JSON default: `season_code`, `setting_code` (indoor/outdoor), `social_code` (solo/social), free-text note | R7, gated on DEC-01 | DC-01: the single largest confirmed gap |
| `v_training_rows` view plus `training_eligibility_code`/`exclusion_reason` on `evaluations` and `calibration_observations` (not just `fragrances`) | R8 | DC-04/MS-02: do not let the existing `fragrances`-scoped column be mistaken for this |
| `NoteAlias`, `accord_types` lookup, `intensity_source` on `fragrance_accords`, `FragranceNote.rank` | R6 | DC-03/MS-04 |
| `PairwiseComparison`, `BehavioralEvent` tables | R7 | DC-08, DC-09 |
| `FeatureSnapshot` rows; `ModelCheckpoint` gains exclusions/filters/params/digest/taxonomy version | R8 | DC-19/MS-10 |
| Randomization/deviation record on `Membership`/`Presentation` (intended vs. actual order, seed) | R7 | DC-20 |
| Response-status enum (skipped / unable-to-assess / interrupted / not-asked / invalidated / technical-failure) replacing bare NULL on optional observation fields | R7 or R8 | DC-18 |
| Familiarity as a versioned code plus a prior-ownership boolean, replacing the bare 0-5 int | R7 | DC-24, ADR-005 amendment |
| `would_buy` relocated out of the blind skin-stage core into a decision block with scenario/offer fields | R7 | DC-06, DEC-03 |

## 8. Required data-dictionary additions

A machine-readable data dictionary (DC-16) does not exist and is not in any sprint's scope. Add
it as an R7 deliverable: one YAML or JSON file under `docs/data/` enumerating every evidence-table
column, its response-status vocabulary, valid range, and whether it is derived or captured.
Include instrument/questionnaire versioning (DC-17): bind `Program.version` (currently a bare
protocol name string) to a frozen set of question wordings and scale anchors, so a future protocol
change cannot silently reinterpret historical rows. A dataset-release manifest builder (DC-26),
covering encoder/feature/source versions, row counts, and exclusions, should accompany the first
real export, not before; define its schema now, build it before F1's first export.

## 9. API and service changes

- `api/evaluations.py`: add reviewer/manager authorization scoping to `list_evaluations` and
  `get_evaluation` (ROLES-03/S-05/B-10, R3 WS-2). No new endpoint; existing routes gain an
  identity-aware query filter.
- `api/reviewers.py`, `api/fragrances.py`: add admin/manager authorization checks to create/
  update/delete (ADMIN-01). Currently any authenticated identity can mutate catalog/reviewer
  data.
- New read-only endpoint surfacing the computed preference profile (backs PREF-01's frontend
  page); no new computation, `preference_history.py` already computes the data.
- `services/fragella_client.py`: add `match()`/`similar()` wrappers per ADR-004's amendment, only
  when D4 actually starts; not part of this plan's pre-baseline scope (FRAG-02).
- `ProgramSetupPage.tsx` / manager API: relabel the Fragella `confidence` field response key or
  its display text (DEC-06); no schema change needed, frontend-only fix is sufficient.

## 10. Frontend workflow and responsive-design changes

Unblocked by this review, still fully outstanding (FE-02, FE-03 from the original gap-analysis
doc, confirmed live and unfixed by this diff):

1. Nav: add a breakpoint that collapses the 6-link nav into a menu/bottom-nav below a declared
   width (`layout.css` around line 272). Affects `AppShell.tsx`.
2. Scale field: give 0-10 fields either horizontal scroll containment or a distinct phone layout,
   separate from 0-5 fields (`components.css:460-463`, `ScaleField.tsx`).
3. New preference-profile page (PREF-01): new route, reuses `page-heading`/`hero-statement`
   conventions already established by `EvidencePage.tsx`; loading/error states via existing
   `PageState.tsx` (unlike `EvidencePage`, this page fetches real per-user data and needs them).
4. `EvidencePage.tsx` follow-ups (both low severity, can batch with any nearby frontend PR):
   replace hardcoded `sources[n]` indices with named references (FE-08); confirm the two
   unlinked sources (Bawa & Shoemaker, Distel et al.) are an intentional ledger-only placement,
   not an oversight.
5. Relabel Fragella `confidence` field (DEC-06).

## 11. Accessibility requirements

No new accessibility defects were found. The existing 32-test Playwright a11y suite
(`e2e/accessibility.spec.ts`) already covers WCAG 2.2 AA including 2.5.8 target size, for all 9
routes including `/evidence`, in both light and dark themes, and passed in full during
verification (Section 5 caveat: only after routing around an unrelated port-3000 collision: flag
this to whoever owns local dev environment docs, since `npm run test:e2e` will silently produce
32 false failures for anyone with something else bound to port 3000). Any new page from Section 10
(preference profile, nav collapse, scale-field phone treatment) must add itself to
`accessibility.spec.ts`'s `routeChecks` before merge, per existing project convention.

## 12. Fragella integration plan

Not started, correctly so: D4 depends on D2 and F1, neither of which are close. When D4 begins,
build in this order, per the already-accepted ADR-004 amendment and the fragella-review checklist:

1. `match()`/`similar()` client wrappers with the same `FragellaErrorCode` discipline as `search()`.
2. `provider_term_mapping` table (vocabulary mapping) before any candidate is shown to a user.
3. Extend `RecommendationRun.source_snapshot` to hold full match/similar request/response for QC.
4. Candidate deduplication against the local catalog and across repeated calls.
5. Provenance/source-quality metadata on every candidate row, per ADR-011's precedent.
6. D5's prospective-linkage plumbing last, since it needs D4's candidate rows to exist first.

Hard constraint carried forward unchanged: Fragella's own signal (`SimilarityScore`, `Confidence`)
is never surfaced as or blended into the local "affinity score," and any UI text using the word
"confidence" for Fragella data must be relabeled first (DEC-06).

## 13. Semantic-encoder/BLaIR experiment plan

Not runnable yet: gated on first-party data existing at all. When it becomes relevant (post-F1,
likely alongside or after D2), the experiment must:

1. Build a small in-domain proxy benchmark (does encoder similarity between two fragrances'
   published notes/accords predict same-evaluator liking correlation better than `affinity-v2`?)
   rather than trusting MTEB or BLaIR's own leaderboard.
2. Evaluate prospectively against the same frozen holdouts ADR-009 already defines, never
   retrospectively.
3. Name `affinity-v2` and a simple popularity/profile baseline as the bar to beat.
4. Version every encoder input: model name/version, source text snapshot, pooling/transform
   method, feeding into the `FeatureSnapshot` mechanism from Section 7.
5. Enter any embedding feature as a low-dimensional, heavily shrunk input (e.g., a handful of PCA
   components) merged with structured taxonomy features; the ~33-43-fragrance sample size cannot
   support a high-dimensional fit.
6. Track popularity/catalog-coverage/small-producer exposure as separate metrics from preference
   accuracy; no such metric exists in BLaIR or locally today and would need to be built.

## 14. ML dataset and feature contracts

`FEATURE_SPACE_VERSION = "fs-v1"` (`ml/feature_space.py:25`) is the current versioning anchor.
Every schema change in Section 7 that adds a new evidence field must bump this version and update
`ml/dataset.py`'s builder in the same PR: do not let feature space drift silently ahead of the
version string (this is the same discipline R2's PostgreSQL parity test is meant to enforce for
schema, extended here to feature contracts).

## 15. Leakage controls

`ml/predict.py`'s `leakage_check()` and `ml/dataset.py`'s `split_for()` exist and are exercised,
but two schema-level gaps remain (MS-08, DC-19/MS-10, ROLES-03-adjacent):

- No DB-level enforcement prevents a trainer from joining raw tables and seeing HOLDOUT labels or
  `repeat_of_id` directly: the protection is currently code discipline only, not a database view
  boundary. `v_training_rows` (Section 7, R8) should be the only sanctioned read path for model
  training code, not the raw tables.
- `split_for()` maps `ACTIVE_LEARNING`/`RETEST`/`OWNED_VALIDATION`/`UNIVERSAL_BASELINE` all to
  `"DEV"` pending an ADR (MS-08): do not treat this as resolved; it needs its own decision before
  any of those split types carries real weight in evaluation.

## 16. Prospective evaluation protocol

ADR-009 already declares the learning problem (accepted, amended 2026-09-19). No change needed
here beyond what Section 13 and Section 15 require: any new predictive feature (embedding or
otherwise) is evaluated against frozen holdouts under ADR-009's existing rules, never tuned against
final holdout outcomes (this is already a release-blocking invariant in PROJECT-PLAN.md §6).

## 17. Research and marketing evidence governance

Adopt as a standing rule, not a one-time fix: **no percentage, ratio, or named-study claim reaches
product UI without an independently located primary source**, following exactly the process
`research-evidence-review` and the existing `perfume-purchasing-research-validation.md` already
used. Concretely:

- RE-01 ("86% less regret"/"3.2× repurchase") stays in the "debunked" framing in
  `EvidencePage.tsx:243` permanently: do not let a future edit move it into a stats display.
- RE-02 (MHC/HLA) must not be cited to justify any genetic-data collection decision.
- RE-03 (Ganti/JAAFR) must not be cited for purchase-driver ordering.
- Any new claim added to `EvidencePage.tsx` or similar marketing surfaces goes through the same
  verification pass before merge: add this as an explicit PR-checklist item for that file.

## 18. Privacy, consent, retention, and licensing considerations

DC-25 (consent contract) is unimplemented and out of any current sprint scope. This matters now
because ADR-005's 2026-09-19 amendment already mandates collecting illness/allergy/hunger/hormonal
session context: sensitive data with no consent model, retention policy, or field-level access
control yet. Route this into R7 alongside the `SessionContext` work from Section 7, since they
touch the same table; do not collect the sensitive fields before the consent contract exists.

Fragella licensing is already correctly documented (ADR-012, ADR-004): bounded lookup only, no
caching, no locally replicated catalog. No change needed; carry forward unchanged into any D4
work.

## 19. Migration and backfill strategy

All schema changes in Section 7 are additive (new nullable columns/tables); no backfill of
historical rows is required or possible for exposure timestamp, season/setting, or randomization
data that was never captured: those columns will be NULL for pre-migration rows and must be
excluded from any training view via the eligibility mechanism (Section 7), not defaulted or
guessed. This follows the existing release-blocking invariant: no guessed fragrance concentration
or version, extended here to no guessed context data either. R2 (naming conventions, PostgreSQL
parity test, `render_as_batch`) is the prerequisite for all of Section 7's migrations per
PROJECT-PLAN's own sequencing note 1: nothing here can land cleanly before R2 merges.

## 20. Testing strategy

- Every new schema addition carries R2's PostgreSQL parity test (`compare_metadata == []`) in the
  same PR, per Milestone R's definition of done.
- New frontend routes (preference profile) get Vitest unit coverage plus an
  `accessibility.spec.ts` entry, matching the existing pattern `EvidencePage.test.tsx` establishes.
- Authorization changes (ROLES-03, ADMIN-01) need both a positive and negative test per route,
  matching the existing `e2e/manager-authorization.spec.ts` pattern.
- Any new claim added to research/marketing surfaces needs no automated test (it's an editorial
  control, Section 17), but should be named in the PR description as "verified against: <source>."

## 21. Observability and operational requirements

FRAG-03 (stdlib logging without correlation ID in `fragella_lookup_service.py`) should be folded
into whatever PR touches that file next (already tracked as architecture-review B-35; no new
tracking needed). No other new observability gaps were found in this review.

## 22. Rollout and rollback strategy

All changes in this plan are additive schema and frontend-only changes; no destructive migration,
so rollback is standard Alembic downgrade plus a frontend revert. No feature flag infrastructure
is warranted for this scope (per the project's stated preference to avoid flags/compatibility
shims where a direct change suffices): these are pre-baseline schema/UI additions, not a live
production cutover.

## 23. Ordered implementation phases

Phase ordering follows PROJECT-PLAN's existing R-sprint sequence; this plan does not reorder
Milestone R, it specifies what lands *inside* each already-sequenced sprint.

| Phase | Sprint | Adds from this plan | Must land before F1? |
| :--- | :--- | :--- | :--- |
| 1 | R2 (not started) | Prerequisite only: no findings from this review land here directly, but nothing below can start until R2 merges | Yes |
| 2 | R3/R4 (not started) | ROLES-03/S-05/B-10 scoping fix; ADMIN-01 admin checks | Yes (P6-gating) |
| 3 | R6 (not started) | Vocabulary normalization (DC-03/MS-04); CAL-02 baseline-template validation (DEC-05) | Yes |
| 4 | R7 (not started) | Exposure metadata (DC-02), season/setting (DC-01, pending DEC-01), pairwise/ranking (DC-08), perceived-notes normalization (DC-15), randomization record (DC-20), familiarity-as-code (DC-24), `would_buy` relocation (DC-06/DEC-03), consent contract (DC-25/Section 18), response-status vocabulary (DC-18) | Yes: all irrecoverable-after-the-fact |
| 5 | R8 (not started) | Evidence-row eligibility view (DC-04/MS-02), `FeatureSnapshot`/checkpoint enrichment (DC-19/MS-10) | Yes |
| 6 | Frontend, any time after R3 | Nav collapse (FE-02), scale-field phone treatment (FE-03), preference-profile page (PREF-01), `EvidencePage` follow-ups (FE-08), Fragella confidence relabel (DEC-06) | No, but should land before F1 for usability, not correctness |
| 7 | Data dictionary/manifest (new, folds into R7/R8) | DC-16, DC-17, DC-26 | Yes for DC-16/17, before first export for DC-26 |
| 8 | Post-F1 | D4 (Fragella match/similar), preference-driver features (ADR-016, DEC-04), BLaIR-informed encoder experiment (Section 13), WS-03 collection/ownership as its own milestone (DEC-05) | No: explicitly deferred |

## 24. Dependencies and critical path

`R2 → {R3, R4 in parallel} → R6 → R7 → R8 → P6 go decision → F1`. This plan adds no new
cross-sprint dependency beyond what PROJECT-PLAN §11a sequencing note already states; DEC-01
(season/setting scope) is the one decision that, if answered "yes, widen R7," adds real scope to
an already-not-started sprint and should be resolved before R7 is estimated.

## 25. Acceptance criteria and release gates

No milestone in PROJECT-PLAN.md changes status as a result of this plan. This plan's items are
accepted into their respective R-sprint's existing definition of done (PROJECT-PLAN §11a): cited
findings marked resolved with a merge commit, plan/roadmap updated in the same PR, durable
decisions recorded as ADR amendments, full backend/frontend gates passing, schema changes carrying
the R2 parity test.

## 26. Risks and unresolved owner decisions

All eight items in Section 4's decision register are unresolved and block at least one phase in
Section 23. The single highest-risk one is DEC-01: if season/setting is required for F1's own
wear/buy prediction goals but R7 stays schema-only, F1 will collect a baseline that cannot support
the product's own stated milestone-3 objective, and that gap will not be discoverable until after
baseline collection has already started (XD-01).

## 27. Explicit "defer / do not build yet" list

- Fragella `/match`/`/similar` implementation and everything downstream of it (D4, D5).
- Any learned model beyond `affinity-v1`/`affinity-v2` heuristics (R15, gated on R6+R8, gated on
  D5 entry).
- Preference-driver attribution features (ADR-016, explicitly not before F1).
- Semantic-encoder/BLaIR-informed candidate strategy (Section 13): no first-party data exists yet
  to evaluate it against.
- Personal collection/ownership tracking (WS-03) as a full feature: real gap, but needs its own
  milestone slot, not a same-sprint bolt-on.
- Consumer catalog/browse journey (WS-04).
- A new pre-baseline "R16" sprint for the ten §13 data-contract items: folded into existing
  sprints per DEC-02 instead.
- Visual-preference items the frontend-ux-review classified as subjective rather than objective
  defects (not itemized here; see the original gap-analysis doc's own subjective/objective
  tagging).

## Appendix: source documents and agents

This plan synthesizes independent read-only review passes by seven subagents against the worktree
`feat/product-research-remediation-plan` (branch created from `main` at commit `bb768d8`,
2026-09-21): roles-workflows-review, frontend-ux-review, ml-data-review, fragella-review,
research-evidence-review, blair-review, and frontend-verification. Full per-domain reports are not
reproduced verbatim here; findings are cited by slug and can be traced back to the reviewing
agent's report retained in this session's transcript.
