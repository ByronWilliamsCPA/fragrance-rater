# Fragrance Rater: Authoritative Project Plan

> **Version**: 2.10 | **Status**: Active | **Updated**: 2026-11-07

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
| Parfumo capture | Deprecated (ADR-012, 2026-09-15) | `ParfumoScraper` and its CLI commands are deprecated per ADR-012 Decision 1: no new writes through this path are sanctioned. The module and CLI commands still exist in the codebase, but the write path now fails closed: since PR #125 (merged 2026-09-26), `ParfumoScraper.search_and_import` and `import_from_url` each raise `BusinessLogicError` as their first statement, before any network request or database access, and a unit test pins that behavior; the read-only `search()` listing is left in place. Actual code retirement is planned, not done, and is tracked as R9. P1.9's fixtures and parser coverage are retained as evidence of pre-deprecation work only. Baseline/holdout facts sourced solely from Parfumo are being re-verified against manufacturer confirmation and Wikidata per ADR-012 Decision 5; `SourceSnapshot`'s ADR-012 provenance columns (`source_type`, `permission_state`, `fields`, `source_reference`) and the nullable `source_url` landed in PR #125 (migration `a3f8c1d9e2b7`); `source_revision`, `content_hash`, `parser_version`, `license_evidence`, and `verified_by` landed in R8 PR 1 (#172 `96bcc5d`); the semantics questions in issues #129 and #130 were decided by the owner on 2026-11-01 and the issues are closed (the code half is #187 `bf5ca17`, which dropped `bounded_lookup` and defined the `source_reference` format) |
| Deterministic recommendations | Implemented | `affinity-v2` (shrunk, namespaced, stationary; ADR-004 amendment 2026-09-19) is the default scorer; `affinity-v1` retained for comparison; score is uncalibrated |
| Preference history | Implemented | Latest ordinary encounter per version plus eligible controlled evidence; holdouts are excluded |
| OpenRouter explanations | Implemented as optional enhancement | In-process bounded cache, deterministic fallback, and provider token/cost telemetry; live measurements require the F1 pilot |
| Controlled calibration | Merged, not deployment-verified | Program, enrollment, hidden repeat/holdout, presentation, observation, locking, reveal, and checkpoint flows exist |
| React product workflow | P5 complete | Participant, manager, reporting, and operations workflows are merged; the P6.3 deployed rehearsal was waived by the owner on 2026-11-27 (section 11) |
| Recommendation outcome measurement | Implemented, not pilot-verified | Immutable runs/impressions, append-only feedback, outcome links, operational events, and provenance-complete reports exist; real baselines belong to F1 |
| Worn-by ("on others") evidence dimension | Implemented, capture only | Optional `worn_by_reviewer_id` on `Evaluation` per ADR-011; excluded from affinity/training-manifest scoring until a future milestone folds it in |
| Verified 43-fragrance baseline manifest | Not available | Exact versions must be verified; no identities may be guessed |
| Live PostgreSQL calibration migration | Fresh-schema verified; production auto-migration added 2026-09-20 | Full upgrade reaches current head on PostgreSQL 16 (single head `736b7db082fb` on `main` as of 2026-11-07 (#187); after `c5a9e2d7f1b4` the chain runs `000091664cdd` (R6 PR 1, #151), `3f14014a49cb` (R7a PR 1, #160), `cd1e2375a2e4` (R7a PR 2, #161), `f74bf7ff9c2d` (R7b PR 1, #165), `620c8c861268` (R8 PR 1, #172), `4edb5c967539` (R8 PR 2, #181), `50c1f75abb15` (#182), `52e22be935d3` (#185) and `736b7db082fb` (#187); the earlier part of the chain runs `7daf681ed339` (reverified 2026-09-19), `a3f8c1d9e2b7` (PR #125), `2c8c3971bfd8` (R2 PR 1, #135), `df2f9646a280` (R2 PR 2, #136), `b7e3d91a4c2f` and `c5a9e2d7f1b4` (house intake, #137, re-parented onto R2); `alembic check` clean against an empty PostgreSQL 16 database at R2 PR 2 on 2026-10-02); a duplicate revision-id collision briefly broke `main`'s migration chain after the P5 audit until its 2026-09-13 fix (PR #80); R2 PR 1 added a PostgreSQL parity test and an enforced naming convention that catch this class of issue in CI. Separately, production itself had no automated migration step at all: no CI step, Dockerfile instruction, or entrypoint ran `alembic upgrade head` against it, until the first manager login 500'd on missing tables and PR #111 (2026-09-20) added `docker-entrypoint.sh` to run it on container start. That closes the automation gap going forward; it is not P1.3's required backup-clone evidence (no restore, no before/after inventory, no concurrency test), so P1 still requires a production backup-clone exercise |
| ML pipeline skeleton | Implemented, no learned model | `fragrance_rater.ml`: versioned feature space, model objects with digested parameters, dataset builder, repeat reliability, holdout scorecards, prospective prediction runner (ML structure review, Tier 2 and 3) |
| Review remediation and ML foundation | In progress; R1-R5 done; R6 PRs 1 and 2 merged (#151, #157), alias decisions no longer gate F1 (D1 prerequisite, owner decision 2026-11-26); R7a merged (#160, #161); R7b merged (#165, #167), with the consent text approved by the owner on 2026-11-01 (`family-consent-v1`); R8 PR 1 (schema: training eligibility, `v_training_rows`, source provenance, checkpoint reproduction) merged (#172); R8 PR 2 (readers on the view, option C eligibility promotion, manager linkage, immutability triggers, jsonb, UTC, `live()`, observation idempotency key, checkpoint reproduction) merged (#181; migration `4edb5c967539`), review follow-up #182 merged (migration `50c1f75abb15`). R8 is done; R13 is done (#168, #173, #174, #175); R14 is done: PRs 1, 2 and 3a merged as #170, #171 and #179, and PR 3b merged on 2026-11-06 as #192 `381d33c` (runtime hardening S-13, `BUILD_ENV` removal S-20) and #193 `8a0d038` (digest-pinned base images, cosign signing S-12); a deployer-side `cosign verify` is still owed | Milestone R (section 11a); sprints R1-R4 and R7a-R7b gate P6 closure (R7b via P6.3), R2 and R5-R8 gate F1; R13 and R14 also gate P6 for the scope named in their table rows (see sequencing note 6); open PR state is in section 11b |
| P6 and F1 entry (2026-11-27) | Owner waiver and `go` recorded; F1 program activated | P6.3 waived (F1 gate sign-off 18), not passed; P6.6 `go` recorded with the waivers (#239); P6.2 and P6.4 unrecorded, P6.1 and P6.5 partly done (section 11). F1 program v3.2 activated 2026-11-27 (section 12), with shared atomizer-label blind codes (F1 gate sign-off 19; the enrollment path for them, #243, is merged and not recorded as deployed) |
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
                                                                  └─ R1-R4, R7a-R7b, R13, R14 ops Remediation (P6 blockers)
                                                                      └─ P6 Pilot readiness
                                                                          └─ R2, R5-R8 ML foundation (F1 blockers)
                                                                              └─ F1 Family pilot
                                                                                  └─ D1 → D2 ┬→ D3
                                                                                              └→ D4 → D5
```

Milestone R (section 11a) was added on 2026-09-19 from the architecture and ML structure reviews.
Its P6-blocking sprints precede the P6 go decision; its F1-blocking sprints precede the first
pilot perfume. R9-R12 improve maintainability and can run in parallel with P6 evidence gathering
but do not gate it. R13 (end-to-end and accessibility harness, per architecture review Q13) and the secrets,
topology-validator, and backup items of R14 are the exceptions: their table rows gate P6, so they precede the P6
go decision (sequencing note 6). R14's documentation items gate nothing.

The diagram nests R2 and R5-R8 under P6 for brevity; it does not mean P6 must fully close before
they start. One ordering is load-bearing and is not optional: R7b (section 11a, the
participant-facing blind-instrument build) must merge before P6.3's synthetic rehearsal
(`gates/p6.md`), because F1's initial four evaluators get exactly one blind pass each, and a
rehearsal that validates an instrument F1 will not run proves nothing about the
instrument that matters. R8 may still land after the P6 go decision, since it is schema/service
work with no evaluator-facing UI. Recorded 2026-09-21 after a one-shot-blind-baseline review found
the diagram's literal ordering would let P6.3 rehearse against a pre-R7b instrument. Status on 2026-11-07: every sprint in
the P6-blocker node is merged (R7b's acceptance export is still owed; the P6.3 rehearsal it was to come from was waived on 2026-11-27, see section 11), and of the F1-blocker sprints R2, R5, R7a,
R7b and R8 are merged; R6's mechanism is merged, and its 43-version alias decisions no longer gate F1 (owner decision 2026-11-26;
they are a D1 prerequisite). The diagram shows
dependencies, not status.

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
| P1.1 | Exact baseline manifest | Every program member has verified brand, name, concentration/version key, source URL or source reference, verification evidence, and physical-sample confirmation; for decant samples the evidence is the decant source's record of the parent product plus a two-person label check, and physical-sample confirmation means the labelled decant is in hand and checked, with no manufacturer or packaging confirmation required (owner decision, 2026-11-01); unresolved identities remain unassigned. **Status, 2026-11-24:** manifest validated (49 entries) and closed on a single-checker pass by owner decision, so the two-person label check is still open. Four concentrations (H04, H07, H08, H09) rest on decant-source and retailer product pages and were not settled by the owner's recheck; the owner proceeded with them as an explicit exception, and all four have live catalog rows (a correction means a new row plus a soft-delete and a new manifest hash). No date is set for the second label check, and neither R6 nor F1 waits on it unless the owner decides otherwise; see the [verification record](evidence/p1-1-baseline-manifest.md) | Versioned manifest and verification report |
| P1.2 | Production backup clone | Record current Alembic revision and row counts; restore a production backup to an isolated PostgreSQL instance | Redacted restore log and pre-upgrade inventory |
| P1.3 | Live migration | Upgrade the clone through the declared Alembic head; preserve IDs, encounter counts, ratings, and timestamps; validate constraints and query plans | Migration log, before/after assertions, schema dump/hash |
| P1.4 | Concurrency | Concurrent ordinary encounter writes and controlled observation/lock attempts preserve all valid records and reject invalid state transitions deterministically | Automated PostgreSQL concurrency results at representative production cardinality; see the P1.4/P1.8 evidence note below for a first automated pass at non-representative scale |
| P1.5 | Rollback/recovery | Demonstrate restore from the verified pre-upgrade backup; do not use lossy downgrade or migration stamping | Timed restore drill and recovery checklist |
| P1.6 | Trust-boundary validation | Production requests traverse Authentik/Traefik; direct backend access from reachable networks cannot mutate data or expose calibration mappings | Deployed topology, port scan, bypass tests, role matrix |
| P1.7 | Blind disclosure audit | Search, history, profiles, recommendations, explanations, caches, errors, exports, and logs reveal no mapping, role, repeat, selection, or holdout information before policy allows | Automated disclosure matrix |
| P1.8 | Target-environment verification | Python 3.12, PostgreSQL 16, frontend build, backend tests, type checks, lint, security scans, and critical end-to-end flows pass | CI run and target-host smoke report. Frontend e2e/accessibility slice: partial, see P1.8 evidence below and `docs/planning/gates/p1.md`. Backend PostgreSQL 16 verification: automated by CI (`postgres-integration` job, landed by PR #118 on 2026-09-21), which `ci-gate` aggregates and so blocks merge through the required `CI Gate` check (see `docs/ci-gates.md` and the P1.4/P1.8 evidence note below); the target-host smoke report is still pending |
| P1.9 | Parfumo fixtures (superseded by ADR-012, 2026-09-15) | Historical: fixtures for requested metrics, status, related versions, similar fragrances, missing fields, and unknown concentration, retained as evidence of pre-deprecation parser coverage only. No further Parfumo fixture work is planned; scraper/CLI retirement is tracked as R9. PR #125 delivered part of the scope this row once deferred: the `SourceSnapshot` ADR-012 provenance columns landed and the Parfumo write path now fails closed, so what remains of that scope is R8's remaining columns and R9's code removal | Fixture provenance and parser coverage (historical); see R8/R9 for retirement work |
| P1.10 | Operations | Document health checks, logs, alerting, database growth, backups, secret rotation, external-service failure, and upgrade procedure | Operations runbook |

### P1.8 evidence: frontend e2e and accessibility testing, 2026-09-18

**Status: partial closure, not full closure.** The frontend e2e/accessibility test plan
(ADR-014, `docs/architecture/frontend-user-journeys.md`) closes P1.8's e2e-flow and
manager-route-authorization criteria for the frontend. It does not close P1.8 as a whole. Three
gaps below are recorded so the gate does not read as closed when it isn't: two
(`ProgramSetupPage`'s internal actions, frontend performance budgets) are permanent,
out-of-scope-for-this-plan gaps, not oversights; the third (`RatingsPage`'s correction-flow e2e
coverage) is a residual coverage gap surfaced by final cross-task review, not a deliberate scope
boundary.

- **E2E coverage for the four named flows: closed.** `frontend/e2e/` (13 Playwright tests:
  accessibility x7, blind-calibration, manager-authorization x3, log-an-encounter,
  recommendation-feedback) passes, covering ordinary entry (`/ratings`), blind calibration and
  reveal (`/calibration`), recommendation feedback and sampling (`/recommendations`), and program
  setup route access (`/programs`). Evidence: ADR-014 and the passing `frontend/e2e/` suite.
- **"Authorization and disclosure tests cover every manager route": closed for the one manager
  route's route-level boundary; the two backend invariants remain unverified in this
  environment.** `/programs` (`ProgramSetupPage`) is the only manager-only route. Its route-level
  authorization (redirect for a non-manager, access for a manager, graceful degradation when the
  API rejects a manager action with 403) is covered by `e2e/manager-authorization.spec.ts`. The
  two backend-invariant checks ADR-014 identifies (pre-reveal identity omission, non-manager 403
  on a manager-only endpoint) are implemented in the real-backend smoke tier
  (`playwright.smoke.config.ts`, `e2e-smoke/disclosure-and-authorization.spec.ts`) but have not
  been executed against a live backend in any sandbox to date (no Docker access); they are
  verified only by source-code reading. A spec that exists and is spec'd is not the same claim as
  a spec that has run against a live backend, and this entry does not conflate the two.
- **`ProgramSetupPage`'s internal manager actions beyond the authorization boundary: open, no
  coverage at any tier.** Program definition, reviewer enrollment, pilot operations, and pilot
  metrics beyond what `App.test.tsx` exercises (activation, catalog-version addition, the
  Fragella check) have no Vitest, Playwright-mocked, or Playwright-smoke coverage. See
  `docs/architecture/frontend-user-journeys.md`'s `/programs` row and its Known gaps section.
- **`RatingsPage`'s correction/edit flow: open at the e2e tier.** `e2e/log-an-encounter.spec.ts`
  covers creating a new journal encounter only; the correction form (`RatingsPage.tsx:213-259`)
  is covered at the Vitest tier only (`src/test/App.test.tsx`), with no Playwright-mocked or
  Playwright-smoke coverage. See `docs/architecture/frontend-user-journeys.md`'s `/ratings` row
  and its Known gaps section.
- **Frontend performance budgets (Section 19 definition of done): open, out of scope for this
  plan.** No task in the seventeen-task frontend e2e/accessibility plan (eighteen counting the
  Task 3b amendment) defined or measured a frontend performance budget. This remains unaddressed
  and unscheduled.
- **Frontend lint, type, test, and build checks pass: closed as of
  2026-09-18**, verified by running `npm run lint && npm run typecheck && npm run test:coverage
  && npm run build && npx playwright test` together for the first time across all seventeen
  prior tasks' combined output (eighteen counting the Task 3b amendment), not task by task: lint
  clean, typecheck clean, 40/40 Vitest unit tests
  passing (78.92% statement / 70.06% branch / 78.41% function / 80.42% line coverage), the
  production build succeeding, and 13/13 Playwright e2e tests passing. No regression appeared
  that any individual task's isolated check had missed. CI enforces this on every pull request
  via the `frontend` and `frontend-e2e` jobs in `.github/workflows/ci.yml`, both required by
  `ci-gate`.
- **Remaining open decision for the user:** whether to build CI wiring for the real-backend smoke
  tier's cadence (nightly or pre-deploy). The per-PR `frontend-e2e` job deliberately does not run
  it; this is a scope boundary this plan draws, not an oversight, and needs the user's
  confirmation before this frontend testing effort is treated as its own end point.

Backend Python 3.12/PostgreSQL 16 target-environment verification and the target-host smoke
report are unaffected by this frontend work and remain tracked separately in
`docs/planning/gates/p1.md`. P1.8 does not close on this evidence alone.

### P1 audit reconciliation: production migration gap and live-auth confirmation, 2026-09-21

A P1 audit prompted by the core maintainer ("several items marked not complete I thought were
complete") found that most P1 work packages were already precise in `docs/planning/gates/p1.md`'s
own table (repository deliverable done; external evidence against real infrastructure pending):
the confusion traced to this plan's narrative prose blurring that distinction, plus two items this
plan had not recorded at all:

- **Production ran with zero applied migrations until 2026-09-20.** PR #111 discovered that no
  CI step, Dockerfile instruction, or entrypoint had ever run `alembic upgrade head` against the
  production database. This surfaced when the first manager login 500'd on every Fragrance-touching
  endpoint from missing tables. `docker-entrypoint.sh` now runs the upgrade before the container's
  existing `CMD`. This is a real fix to a real gap that predates this plan version, recorded above
  in the current-state ledger. It closes the automation gap; it does **not** supply P1.3's
  required backup-clone restore, before/after inventory, or concurrency evidence, and it has not
  been evaluated for multi-replica startup races (this deployment currently runs a single
  instance, so the gap is not release-blocking today, but it should be checked before any
  horizontal scale-out).
- **The nginx trust boundary forwarded forged identity headers.** `frontend/nginx.conf` passed
  through whatever `X-Authentik-*` headers a client sent (architecture review S-01/S-02). R3 PR 1
  (#143, merged 2026-10-30) forwards them only from peers in `FRAGRANCE_TRAEFIK_CIDR` and proves it
  against a real nginx in `tests/integration/test_nginx_trust_boundary.py`. P1.6 still needs the
  deployed forged-header check that `docs/deployment/p1-release-readiness.md` now spells out; the
  repository code is no longer the gap.
- **A manager successfully logged in through Authentik at the live deployed URL on 2026-09-21.**
  This is real, positive evidence that the Authentik challenge is enforced end-to-end on the
  production host, the first confirmation of that outside a planned rehearsal. It is informal
  (no port scan, no direct-IP bypass attempt, no forged-header attempt, no role-matrix comparison
  across separate manager/participant Authentik accounts) and does not close P1.6 while the
  nginx forged-header gap above remains open. See also the 2026-09-18 production-deployment
  interim evidence under Milestone P6 (section 11), which this login corroborates but does not
  supersede.

`docs/planning/gates/p1.md`'s P1.3 and P1.6 rows now cross-reference this section so the gate
record does not read as silent on either finding.

### P1.3/P1.4/P1.8 evidence: local re-verification, a concurrency gate, and CI automation, 2026-09-21

Working to close the gaps the audit above surfaced:

- **Migration chain re-verified fresh.** `alembic upgrade head` against a clean local PostgreSQL
  16 database reaches the single head `7daf681ed339` cleanly on the checkout of that date (`main`'s head has since moved to
  `a3f8c1d9e2b7` with PR #125), and re-running `upgrade head` is a confirmed no-op. This reconfirms the 2026-09-19 re-verification
  on today's code; it remains fresh-schema evidence, not production-clone evidence.
- **A first automated concurrency gate.** `tests/integration/test_calibration_concurrency_postgres.py`
  (new, gated on `P1_DATABASE_URL` like the existing recommendation-measurement gate) exercises
  two real races against PostgreSQL row locking: two concurrent attempts to assign the same
  fragrance as a program's holdout (the `add_member` `with_for_update` lock correctly serializes
  them; the loser gets a clean 409, and exactly one membership row persists), and two concurrent
  enrollment attempts for the same reviewer (the `Enrollment` unique constraint prevents a
  duplicate row regardless of which failure shape the loser hits). Both pass. This is real
  evidence toward P1.4, run at toy scale on a throwaway database; it is not the "representative
  cardinality" concurrency pass P1.4's runbook section calls for, which needs production-like
  data volume, and it does not touch the observation/lock/reveal races the runbook also names.
- **PostgreSQL in CI landed through PR #118, not through this work.** A `postgres-integration` job was drafted for
  `.github/workflows/ci.yml` (full Alembic chain against a real PostgreSQL 16 service container,
  then the `P1_DATABASE_URL`-gated integration tests) but was removed before merge: it duplicated
  the scope of PR #118, which implements R1 ("CI truthfulness") end to end, including its own
  version of this same job. PR #118 has since merged, and `docs/ci-gates.md` records that `ci-gate` aggregates
  `postgres-integration`, so the "no PostgreSQL job in this repository" gap R1 names (architecture
  review S-11/F-01) is closed and the concurrency gate above now runs in CI. This item originally recorded the gap
  as open and tracked by #118; the sprint table's R1 row already recorded it as done.
- **A reusable pre/post-migration inventory tool.** `scripts/p1_migration_inventory.py` implements
  the runbook's "Restore and pre-upgrade inventory" and "Migration and data assertions" steps
  (row counts, timestamp ranges, duplicate natural keys, invalid foreign keys, and a redacted hash
  of every column for `fragrances`/`reviewers`/`evaluations`, one digest per column so an added
  column does not read as a violation but a changed value or a dropped column does) as one command
  instead of hand-run SQL, with a `--compare` mode that exits nonzero on any preservation
  violation. Reported by local testing (not re-verified in this reconciliation pass) to show no
  violations when nothing changed and to correctly detect a deliberately deleted row between the
  two snapshots. This does not gather P1.2/P1.3/P1.5 evidence by itself; it still needs to be run
  against an actual production backup restore, which requires the core maintainer's access to
  that backup.

None of this closes P1.2, P1.3, P1.5, P1.6's deployed evidence, P1.7's deployed evidence, or
P1.10: those still require the core maintainer's production/deployment access. The next concrete
step for each is to run `scripts/p1_migration_inventory.py` and the runbook's remaining manual
steps against a real backup restore.

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

**Status:** In progress; repository rehearsal kit prepared, external execution pending. On 2026-11-27 the owner waived P6.3 and the P6.6 `go` was recorded with waivers (see "Owner waiver of P6.3 and the P6.6 `go`, 2026-11-27" below); the gate records own the detail
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
criterion or `no-go` decision keeps F1 blocked. For the family pilot the owner recorded a **family MVP profile on
2026-11-25** that scales what "every criterion" requires (P1.4 and the P1.1 second check waived, one device, one light
synthetic dry run, one timed restore, a one-paragraph signed decision); the profile is the recorded owner change to
this sentence, it closes no gate and completes no evidence, and P6.6 `go` is still required. See
[`gates/p6.md`](gates/p6.md#family-mvp-profile-owner-decision-2026-11-25).

### Owner waiver of P6.3 and the P6.6 `go`, 2026-11-27

On 2026-11-27 the owner **waived** the P6.3 six-person synthetic rehearsal (F1 gate sign-off 18; see also
[`gates/p6.md`](gates/p6.md#owner-waiver-of-the-p63-rehearsal-2026-11-27) and the
[rehearsal log](evidence/p6-synthetic-rehearsal.md)). It is a waiver, **not a pass**: no six-person run, no observed
replacement-blotter count and no result for the four deliberate failures exists. The P6.6 decision `go` was recorded
at the owner's instruction (#239, [readiness record](evidence/p6-readiness-decision.md)) together with the waivers and
the open evidence: P6.2 and P6.4 are unrecorded, and P6.1 and P6.5 are partly done. This section records the status and
closes no gate item beyond what `gates/p6.md` records.

**R7b still owes its acceptance export.** The R7b P6.3 acceptance export from a synthetic run does not exist and is
still owed. The owner has not chosen how to evidence R7b instead; no substitute is recorded and R7b is not marked
done on this account.

**F1 program.** The F1 program is `v3.2` (id `a70dab0d-8581-4d3b-9e8d-ba597d784895`), activated 2026-11-27 with
`HOUSEHOLD` reveal policy, `INDIVIDUAL` blotters and 49 memberships, pinned to build `94f6cf22`. The `v3.1` program was
activated with the wrong reveal policy and is inert. All six real evaluators are enrolled with
`shared-triples-latin-rotation-v1`, and the holder is flagged non-blind on all sessions. The evaluator-to-label mapping
and the evidence files stay outside git.

**Shared blind codes in `v3.2` (2026-11-27).** The six enrollments were created with random per-evaluator blind codes.
The owner then decided that all six evaluators see one code per physical sample, equal to the atomizer label, and the
stored codes were replaced by a reviewed one-off data update ([F1 gate sign-off 19](gates/f1.md), which owns the
record, the accepted consequences and what is still owed). For `v3.2` the wrong-evaluator sheet check is therefore
procedural, not a server guard. PR #243 (merged 2026-11-27, `6635413`) adds the enrollment code path that sign-off 19(d)
said was not yet made: `label_scheme: "shared"` on `shared-triples-latin-rotation-v1` enrollments, where a program's
first shared enrollment supplies the codes and later ones inherit them, with no migration. Nothing in these documents
records #243 as deployed: the instrument pin stays `94f6cf22`, and the build and pin decision it needs is open and is
not made here.

**Manager screen.** PR #240 (merged 2026-11-27, `08ac9f5`) replaced the manager Program setup page with a fixed Family
pilot screen at `/programs` and moved the previous page to `/programs/advanced`. It is merged and **not deployed to
production**.

### Interim evidence: production deployment incident, 2026-09-18

An unplanned production deployment through Authentik/Traefik (PRs #100-102) surfaced and fixed
three real target-topology defects: the wrong Docker build stage was published, a Trivy
registry-scan CI bug blocked the fix, and an IPv6 `wget` healthcheck failure took the site fully
offline after redeploy. This is real P1.6/P6.2 target-topology exercise, but it was reactive, not
a planned rehearsal: it did not exercise the P6.3-P6.6 synthetic workflow, quality, operations, or
readiness-decision packages, and does not close any P6.1-P6.6 item on its own. Retained evidence
is in [the P6 gate record](gates/p6.md).

## 11a. Milestone R: Review remediation and ML foundation

**Objective:** Close the findings of the [Architecture and Design Review](architecture-review-2026-09.md)
and the [ML Structure Review](ml-structure-review-2026-09.md) that block the P6 go decision or the
first pilot perfume, and lay the ML foundation the owner's [ML decisions](ml-decisions-2026-09.md)
require before F1 collects data.

**Owner:** Core maintainer

**Status:** In progress. Completed on 2026-09-19: the ML pipeline skeleton (review Tier 2 items 7, 8, 9, 12,
13 and Tier 3 items 14, 15), `affinity-v2` as the default scorer (Q6), the ADR-009 learning-problem amendment
(Q1), and R5 (protocol research prompt run, reconciled as the ADR-005 protocol-research-reconciliation amendment,
closing Q8's session-structure and judgment-scale questions). R7a carries the resulting schema work; R7b carries
the resulting participant-instrument work (split 2026-09-21 after a one-shot-blind-baseline review, see the
sprint table below). Completed on 2026-09-21: R1 (CI truthfulness - see [`docs/ci-gates.md`](../ci-gates.md) for
the authoritative per-workflow record and its "Known residual gaps" section for what R1 deliberately left open,
including that `docker-publish.yml`'s CVE gate stays report-only and that Q9's default resolved only PyPI publishing
and the Python version matrix, not FIPS/SLSA/mutation-testing/semantic-release). Completed on 2026-10-21: R2
(PRs #135 and #136). Completed on 2026-10-30: R3 (PRs #143 and #144) and R4
(PR #149: disclosure leaks, audit trail, logging); see the sprint table.
In progress on 2026-10-30: R6 (PR 1, the vocabulary schema, merged as #151 `45e09fd`; PR 2, the alias curation tooling, merged as #157 `39ae231`; the 43-version decisions can now proceed against the P1.1 manifest, validated 2026-11-24, and no longer gate F1: owner decision 2026-11-26 makes them a D1 prerequisite). Completed on 2026-10-30: R7a (PRs #160, #161) and R7b PR 1 (#165). Completed on 2026-10-31: R7b PR 2 (#167; the P6.3 acceptance export is still owed), R8 (#172, #181, #182; owner choices A and B settled on 2026-11-01, see #185 and #187), and R13 (#168, #173, #174, #175). Completed on 2026-11-06: R14 (PRs 1, 2 and 3a as #170, #171, #179 with review fixes #177 and #178; PR 3b as #193 `8a0d038` and #192 `381d33c`).

**Depends on:** P5. **Blocks:** P6 closure (R1-R4, R7a-R7b via P6.3, R13, and R14's secrets, validator, and backup
items) and F1 (R2, R5-R8; R6's 43-version alias decisions excepted, a D1 prerequisite by owner decision
2026-11-26).

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
| R1 | CI truthfulness (done 2026-09-21) | Frontend lint, typecheck, test, and build job as a required check (already landed via PR #103/ADR-014; verified); remove `api/*`, `llm/*`, `main.py` from the coverage omit list (real coverage measured at 88.28% in this worktree on 2026-09-21, up from an earlier 87.09% reading as R1's remaining test work landed; no threshold change needed; per the ASGI coverage-measurement gap documented later in this row and in `docs/ci-gates.md`, treat this as a floor, not an exact count); container CVE gates on for CRITICAL and HIGH, matrixed to also scan the frontend image; a PostgreSQL job in this repository running `alembic upgrade head` and the integration marker with `P1_DATABASE_URL` (verified end-to-end against a real PostgreSQL 16; the `compare_metadata == []` parity test itself is still R2's, per sequencing note 1); unit tests for the uncovered measurement-service branches (52.76% to 92.46% real coverage; also surfaced and documented a coverage-measurement gap for code reached only through the FastAPI/ASGI test layer, see `docs/ci-gates.md`); `docs/ci-gates.md`; deleted `setup_github_protection.py` (Q8 default) and retired `publish-pypi.yml`/`python-compatibility.yml` with `requires-python` pinned to `==3.12.*` (Q9 default, partial - FIPS/SLSA/mutation/release.yml untouched, needing their own owner decision); deleted the placeholder `.semgrep.yml` (no ruleset was ever wired to it); dropped `scripts` from `[tool.bandit] exclude_dirs` (confirmed by line-count comparison that `scripts/validate_p6_readiness.py` was previously never actually scanned; clean on first real scan); aligned all 12 reusable-workflow SHA pins on `b7c661ec3bfeb04370ce3a9c748bd8c4e93bfe89` (S-11/F-01, S-09, S-10, G-02, G-06, G-11, S-22, S-29, S-26, S-30, D-06). PR #116 originally added its own `postgres-integration` CI job duplicating this scope; that job was removed from #116 rather than waiting on #118, so #118 landed the CI job that now also runs #116's Postgres-gated concurrency test suite. | P6 | Sonnet | Opus | 2 PRs |
| R2 | Migration tooling and schema safety (done 2026-10-21: PR 1 #135 merged as `329c648`, PR 2 #136 merged as `00f14d6`; see section 11b) | `naming_convention` on `Base.metadata`; `compare_type`, `compare_server_default`, `render_as_batch` in `alembic/env.py`; PostgreSQL parity test (`compare_metadata == []`); SQLite `foreign_keys` pragma in `conftest.py`; downgrade-raise assertions; one named-constraint migration renaming the 37 unnamed CHECKs, adding range CHECKs on `evaluations`, `IN` CHECKs on role, status, stage, phase, reconciling the six index names, adding the nine FK indexes, and changing the two `evaluations` cascades to `RESTRICT`; `alembic/README` and CONTRIBUTING rules (D-02, D-03, D-04, D-05, D-07, D-09, D-10, D-11, D-15, D-17, D-19, D-20, X-25). **PR 1 (tooling and naming, branch `feat/r2-migration-schema-safety`):** naming convention on `Base.metadata` with every CHECK named in the models; the three autogenerate flags, with the model metadata (and so the convention) applied only when comparing, never while historical migrations execute; migration `2c8c3971bfd8` renaming 84 constraints to the convention, renaming three legacy `idx_*` indexes and dropping the redundant `idx_fragrance_accords_fragrance`; `tests/integration/test_schema_parity_postgres.py` (structural parity, name parity, head round trip) in the `postgres-integration` job; the SQLite `foreign_keys` pragma on every shared test engine, with a negative control; the four restore-only downgrade assertions; `alembic/README`, CONTRIBUTING, and a ruff-clean `script.py.mako`. `alembic check` against a migrated PostgreSQL 16 now reports no operations. Closes D-03, D-04, D-05, D-07, D-11, D-17, D-19, D-20. Recount at PR 1: the chain produced 44 CHECKs, 20 with PostgreSQL-invented names, not the review's 37 of 41 (PR #125 added CHECKs after the review). The review's claim that autogenerate proposed spurious `DROP CONSTRAINT`s did not reproduce: Alembic does not compare CHECK constraints at all, which is why PR 1 adds a name-parity test. **PR 2 (constraints, branch `feat/r2-schema-constraints`, stacked on PR 1):** migration `df2f9646a280` adds the `evaluations` 1-5 range CHECKs (D-02); `IN` CHECKs on program status (`draft`, `active`), membership role (the seven `schemas.calibration.Role` values, with a unit test pinning the two together), observation stage, and observation phase (D-15, X-25); indexes on the nine unindexed FK columns (D-10); and `RESTRICT` on both `evaluations` FKs per architecture review Q17's default (D-09). `Fragrance.evaluations` and `Reviewer.evaluations` also drop their ORM `delete-orphan` cascade for `passive_deletes="all"`: without that, an ORM delete would have removed the evaluations itself before the database's RESTRICT could fire (shown by a negative-control test). The migration refuses to add a CHECK while any row violates it and names the rows; a PostgreSQL test proves the failed upgrade changes nothing. Closes D-02, D-09, D-10, D-15 (for role, status, stage, phase; the other enum-shaped columns D-15 lists stay unconstrained), and X-25 | F1; prerequisite for R6 and R7a | Opus | Sonnet tests | 2 PRs |
| R3 | Trust boundary in code (done 2026-10-30: #143 `4d31328`, #144 `10bd5d8`) | nginx resets `X-Authentik-*` unless the peer is Traefik; uvicorn `--proxy-headers` with the frontend network allow-list; limiter keyed on the verified username; `actor`, `manager`, `authorize_reviewer` moved to `core/auth.py`; one `require_identity()` on every mutating route and one recorder-or-manager check on every reviewer-keyed read (architecture review Q5 pending, default: no cross-reviewer reads); `environment`, `trusted_hosts`, and the `NoDecode` admin-list validator in `Settings`; docs routes and CORS defaults gated on environment; an `authentik_required=True` test suite; a deployed forged-header test added to P1.6 (S-01, S-02, S-03, S-05/B-10, S-06, B-11, S-17, S-18, S-19, S-23, B-27, S-25, F-02). **PR 1 (the edge, branch `feat/r3-edge-trust-boundary`):** nginx forwards `X-Authentik-*` and Traefik's `X-Forwarded-For`/`-Proto` only from peers in `FRAGRANCE_TRAEFIK_CIDR` and clears or resets them otherwise (owner chose this peer-subnet check over a Traefik shared secret or Authentik JWT verification, 2026-10-21); nginx refuses to start without the CIDR; uvicorn trusts forwarding headers only via `FORWARDED_ALLOW_IPS` (private app network plus the edge subnet); the limiter keys on the verified username before the client address; `Settings` gains `environment` and `trusted_hosts` and parses `CALIBRATION_ADMIN_USERNAMES` as JSON or comma form; production hides `/docs`, `/redoc`, `/openapi.json`, drops the development CORS origins, and requires `TRUSTED_HOSTS`; incoming correlation and tracing IDs are validated; a blank `X-Authentik-Username` now fails closed; the topology validator requires the new settings; ADR-008 amended. Closes S-01 (in code; the deployed forged-header check is P1.6's), S-02, S-17, S-18, S-19, B-27, S-25. **PR 2 (route authorization, branch `feat/r3-route-authorization`, stacked on PR 1):** `require_identity` (401 without a username whatever `AUTHENTIK_REQUIRED` says) on every route except health, the API root, and the R9-bound sample catalog; the owner's Q5 decision (2026-10-21): managers read every reviewer, recorders only reviewers whose enrollment lists them, others 403, applied to ordinary evaluations, recommendations, profile, and explain; billed routes need a named caller as well as the key; `actor`, `manager`, `authorize_reviewer` moved to `core/auth.py`; a route-table-driven 401 guard and read-policy matrix; ADR-008 amended again. Closes S-03 (attribution; key retirement stays R9/Q2), S-05/B-10, S-06, B-11, S-23, and F-02 (cited in the review summary without its own row; covered by S-05/B-10) | P6 | Opus | Sonnet tests | 2 PRs |
| R4 | Disclosure leaks, audit trail, logging (done 2026-10-30: #149 `f247d3a`) | Role-neutral 409 on holdout feedback; explanation only by persisted impression id; `log_audit_event` on activate, enroll, lock, reveal, mapping retrieval, checkpoint, prediction create and link; no-store by default under the API prefix; `setup_logging()` in lifespan; `SecretStr` keys and a redaction processor; two new rows in the P1.7 disclosure matrix (B-01, B-02, B-03, B-26, F-15, S-07, S-15). **PR (branch `feat/r4-disclosure-audit-logging`):** holdout feedback refused with a role-neutral 409, the reason logged server-side, and the reveal blocker no longer naming repeats (B-01); the catalog-ID explain route removed, and an impression whose fragrance became a holdout or was deleted explains exactly like a missing one (B-02); `audit_event` on activation, enrollment, stage and skin-plan locks, reveal, checkpoint, mapping retrieval (actor and enrollment, never contents), and prediction create and link (B-03); `private, no-store` with `Vary` on everything under `/api/v1` except the catalog (B-26); a server-sent `post_reveal_entry` per sample and a narrow `linkable-outcomes` endpoint replacing the full-history fetch (F-15); `setup_logging` in the lifespan (S-07); `SecretStr` keys and a redaction processor (S-15); the participant-reachable error paths added to the [P4 participant disclosure matrix](evidence/p4-participant-disclosure.md#participant-reachable-error-paths-r4), one row per path, covering the review's two new rows (409 bodies and 404 oracles); ADR-005 and ADR-008 amended | P6 | Sonnet | Opus | 1 PR |
| R5 | Protocol research reconciliation (done 2026-09-19) | Ran the [protocol research prompt](../research/scent-evaluation-protocol-research-prompt.md) on two deep-research models; recorded both results under `docs/research/`; verified a six-citation sample from each (sampled citations from one report checked out, the other showing real citation fabrication that a supplementary check found ran deeper than the sample alone showed; see the ADR-005 amendment) and reconciled by preferring the verified report; recorded the [2026-09-19 ADR-005 amendment](adr/adr-005-controlled-calibration.md#2026-09-19-amendment-protocol-research-reconciliation); session size and the 33/10/6 baseline structure are unchanged, daily load/calendar/scales/familiarity/`would_buy`/descriptors/ranking-analysis/order-balancing/session-context/skin-timepoints changed; schema changes handed to R7a (ML Decisions Q8) | F1 | Opus | Owner | 1 PR |
| R6 | Vocabulary foundation (in progress, 2026-10-30: PR 1 merged as #151 `45e09fd`, review-fix follow-up merged as #152 `54f5eda`, PR 2 merged as #157 `39ae231`, review fixes merged as #158 `de7084e`; the 43-version decisions can now proceed against the P1.1 manifest, validated 2026-11-24, and no longer gate F1: owner decision 2026-11-26 makes them a D1 prerequisite) | `NoteAlias` table with `mapping_version`, normalized unique key on `notes`, `Note.category` cleaned of pyramid position (Kaggle rows backfilled to NULL), `accord_types` lookup with `accord_type` as a foreign key, `intensity_source` on `fragrance_accords` with positional values excluded from measured features by default, one resolver used by both importers, `FragranceNote.rank`, scoped to the 43 baseline and holdout versions alongside P1.1 verification; D1 fixtures (`oak moss`/`oakmoss`, `vanille`/`vanilla`, ambiguous, unknown); `FEATURE_SPACE_VERSION` bump (X-01, X-02, X-03, X-04, X-12; ML Decisions Q2, Q5). Related work already merged: PR #127 (2026-09-26) delivered the project-owned `fr-core` olfactory vocabulary v0 under ADR-017 (Proposed, amends ADR-004, ADR-010, and ADR-013). It is the vocabulary asset R6's resolver and `NoteAlias` work will consume, not the R6 schema work itself. **PR 1 (schema, resolver, and importers; #151, branch `feat/r6-vocabulary-schema`):** migration `000091664cdd` adds `notes.name_key` (unique, normalized: case, accents, and separators removed), `note_aliases` (`raw_label`, `alias_key`, `canonical_note_id`, `mapping_version`, `origin`; active version `nm-v1`), `accord_types` with `fragrance_accords.accord_type` as a foreign key, `intensity_source` and `rank` on accords, `FragranceNote.rank`, and a CHECK on `position`; `Note.category` becomes nullable and loses `Top`/`Heart`/`Base`. The migration merges notes whose keys collide into the most-used spelling (absorbed spellings become `observed` aliases), lowercases accord codes, and flags a legacy Kaggle accord as `positional` when its intensity is on the importer's ladder, which fails safe: a real 85% from Kaggle is excluded from measured features, never the reverse. `VocabularyResolver` (`services/vocabulary.py`) is the one path from a raw label to a note or accord type; the Kaggle importer and the manual catalog service both use it, and an ambiguous label (a curated alias and the key lookup disagree) is skipped and logged, never merged by guesswork. `FEATURE_SPACE_VERSION` moves to `fs-v2`, adding `intensity_source` and `rank` to the vectors; the dataset's `accords` space keeps only measured weights and a new `accord_ranks` space keeps list order. The `affinity-v1` and `affinity-v2` digests change because the feature-space string is digested; their parameters do not, and the old digests are reproduced by naming `fs-v1`. ADR-017 is amended: R6 took `fs-v2`, so the layer-4 profile becomes `fs-v3`. Closes X-01, X-02, X-03, X-04, and X-12 in schema and writers. **PR 2 (alias curation mechanism; branch `feat/r6-alias-curation`):** `data/aliases/note-aliases-nm-v1.yaml` (`raw_label`, `canonical`, `evidence`, `decided_by`), the `fragrance-rater vocab aliases` commands (`validate`, `load`, `ambiguities`), and a pre-commit hook. The validator reports every violation (one decision per key, no chains, evidence and author required); the loader is a dry run unless `--execute --actor` is given, is all-or-nothing and idempotent, and blocks a decision whose canonical note is missing, that conflicts with an existing decision, or whose label already names a different note; every load is audited with the file's content hash. The committed file is empty: when PR 2 merged it could not hold the 43-version decisions because the verified baseline manifest did not exist yet (identities are not guessed); the manifest was validated on 2026-11-24, so those decisions can now be authored, before F1 | F1 | Opus | Sonnet tests | 2 PRs |
| R7a | Pairwise, behavioral, and context capture: schema and service (done 2026-10-30: schema merged as #160 `3acaead` and #161 `6d46a58`; the service writes, including `enroll()` recording the randomization, were delivered by R7b PR 1, #165 `eafb818`) | `PairwiseComparison`/rank-event and `BehavioralEvent` tables; typed sample-provenance columns on `Presentation`; real `occurred_on`, `presented_at`/`applied_at`, `observed_at`, and evaluator timezone (not schedule-generation or server-receipt time); `SessionContext` fields (illness, hunger, ambient odor, etc., per the ADR-005 amendment); familiarity recognition code plus a separate prior-ownership/exposure code on both evidence tables; `scrubbed_off`, `time_to_scrub_minutes`, `last_detected_elapsed_min`, `first_not_detected_elapsed_min`; a response-status code (completed/not_detected/skipped/unable_to_assess/interrupted/invalidated); randomization algorithm, seed, and intended position; a deviation/quality-flag table; a consent-event table (13.11); `instrument_version` (or frontend build SHA) on `programs`, written at activation; scenario/season and setting lookup columns (ML Decisions Q9); the R2 parity test; shapes adjusted to R5's result before merge (X-07, X-08, X-09, X-14, X-22, X-23; ML Decisions Q3, Q8, Q9) | F1 | Opus | Sonnet tests | 2 PRs |
| R7b | Pairwise, behavioral, and context capture: participant instrument v2 (code done 2026-10-31: PR 1, the backend write paths, merged as #165 `eafb818`; PR 2, the participant UI, `INSTRUMENT_VERSION` build wiring, Playwright e2e and WCAG 2.2 AA scans, and the API-level synthetic-run guard `tests/unit/test_api/test_r7b_synthetic_run.py`, merged as #167 `73d6bcc`; the acceptance export from a deployed synthetic run is still to be produced and attached to the P6.3 record (P6.3 was waived by the owner on 2026-11-27; the export is still owed and no substitute is chosen), the consent wording was approved by the owner on 2026-11-01) | Session-start context form gated by the R7a consent screen; blotter form writes the recognition + prior-ownership codes instead of the current 0-5 integer; skin flow presents fixed 10 min/1 h/4 h/8 h timepoints and stamps `applied_at`/`observed_at` from the client clock at submit (with an explicit `observed_at` field for recorder transcription); scrub-off controls; a per-response-group "unable to assess/skipped" control; a "flag a problem with this session or sample" control; end-of-session ranking of detected samples stored as one rank event over the eligible subset, never as independent pairwise rows (ADR-005 amendment, ML Decisions Q8); blind `would_buy` removed from the skin form (**owner decision 2026-10-30: `would_buy` stays on the form; the removal is not carried out**); 0/5/10 and 0/5 verbal anchors rendered; one or two coarse blind scenario/setting questions at the skin stage only, roughly 6 per evaluator (ML Decisions Q9), asked as multi-select (owner decision 2026-10-30; stored as `calibration_fit_choices` child rows, migration `f74bf7ff9c2d`). **Acceptance:** a synthetic run through the released UI (one enrollment, one session, one skin wear, one ranking, one flagged deviation) produces an export where every field above is non-null for at least one row; the export is attached to the P6.3 synthetic-rehearsal record (`gates/p6.md`) | F1; must merge before P6.3 (section 4) | Sonnet | Opus | 2 PRs |
| R8 | Training eligibility and provenance in schema (done 2026-10-31: PR 1 #172 `96bcc5d`, PR 2 #181 `64321e7`, review follow-up #182 `9d34a25`; the two PR 2 decisions were settled by the owner on 2026-11-01, see below; the ADR-012 columns and nullable `source_url` landed early in PR #125, see below) | `training_eligibility` on both evidence tables and a `v_training_rows` view; manager-only view for role and repeat linkage; `SourceSnapshot` gains `source_revision`, `content_hash`, `parser_version`, `license_evidence`, `verified_by`, the ADR-012 columns, and a nullable `source_url`; `ModelCheckpoint` gains exclusions, filters, feature-space and taxonomy versions, params, and input digest; typed checkpoint predictions; `FeatureSnapshot` rows; `predict.py` and `dataset.py` read the view (X-05, X-06, X-16, X-17, D-01, M-07, M-08). **Landed early in PR #125 (2026-09-26):** the four ADR-012 `SourceSnapshot` columns (`source_type`, `permission_state`, `fields`, `source_reference`), the nullable `source_url`, and the Parfumo write-path refusal. **Historical scope note (resolved 2026-11-01, see "Owner decisions of 2026-11-01"): the remaining `SourceSnapshot` scope was** what issues #129 (record the early delivery and settle the P1.1 source criterion; #125 relaxed the manifest validator to accept `source_reference`) and #130 (SourceSnapshot semantics: `bounded_lookup`, `source_type`/`permission_state` pairs, the `fields` allow-list, `source_reference` format, and the missing read-side consumer) describe; `source_revision`, `content_hash`, `parser_version`, `license_evidence`, and `verified_by` landed in PR 1 (#172), so what remained of that scope was the semantics those two issues asked the owner to decide, not columns; the owner decided them on 2026-11-01 and the code half is PR #187 (merged 2026-11-01). **Architecture-review WS-9 items not yet assigned to any sprint row, added here on 2026-10-21 so they are not lost (placement in R8 is proposed, pending owner confirmation):** database-level immutability enforcement for append-only observations, frozen checkpoints, activated membership, frozen predictions, and assigned identity (D-08, Q14; review default: `BEFORE UPDATE` triggers, or a tech-spec caveat stating enforcement is service-level); the `json` to `jsonb` type migration for the 22 JSON columns (D-12; the review says this is cheap before F1 data exists); UTC server defaults and a startup assertion that the database `TimeZone` is UTC (D-16, Q16); a shared soft-delete `live()` helper (D-21); and an idempotency key on controlled observation submission so a flaky-connection double-POST cannot create two rows (D-22, Q18; the review says to add it before F1). Source: `docs/planning/architecture-review-2026-09.md`, findings table and WS-9 **PR 1 merged as #172 (2026-10-31). PR 2 merged as #181 (2026-10-31), migration `4edb5c967539`; its review follow-up (#182) adds migration `50c1f75abb15` (`QualityFlag.training_outcome`, so a resolution that decided nothing keeps its rows held for a manager):** option C eligibility promotion (ordinary encounters `eligible` when saved by `EvaluationService.create`; controlled observations `eligible` when their stage is locked and no quality flag on the observation, its presentation, or its session is open; a raised flag demotes `unreviewed`/`eligible` rows to `questionable`; a manager resolution or `PUT /api/v1/training-eligibility/...` sets `eligible`/`withheld`/`invalidated` with a reason; automatic rules never touch `withheld`/`invalidated`; every change is a `training_eligibility_set` audit event); `ml/dataset.py`, `ml/predict.py`, and the checkpoint manifest read `v_training_rows` through `ml/training_view.py` (the view gained `revealed` and the latest-answer rule); `v_manager_linkage` and the manager-only `GET /api/v1/calibration/enrollments/{id}/linkage`; PostgreSQL `BEFORE` triggers for D-08; 19 `json` columns to `jsonb` (D-12); UTC server defaults and a startup `TimeZone` assertion (D-16); `models/soft_delete.py` `live()`/`is_live()` (D-21); a per-presentation observation idempotency key (a retry returns the original row with 200; the same key with different answers is a 409), sent by the observation form (D-22); checkpoints fill every M-07 column, a content-addressed `FeatureSnapshot`, and typed `CheckpointPrediction` rows restricted to the enrollment's holdouts. Retained evidence (branch, 2026-10-31; to be carried into the PR description): unit suite with coverage, the PostgreSQL integration suite on a fresh PostgreSQL 16 database, `alembic check` clean before and after a downgrade/upgrade round trip, the downgrade refusing on a keyed observation, and a negative control for each trigger, view change, and promotion rule. R8 is done. Two PR 2 choices were recorded for the owner and are now decided (A: option 2, #185; B: option 1, `program_id` stays `None`) (the other nine decisions from #172 stand at their chosen defaults unless the owner objects): `v_training_rows` carries a `revealed` column and trains on the latest pre-reveal observation of a presentation and stage, and `TrainingRow.program_id` is now `None` because the view does not expose it. The recommendation scorer and recommendation-measurement manifests deliberately still read the raw tables (product scoring, not training). | F1 | Opus | Sonnet tests | 2 PRs |
| R9 | Scaffold deletion | Remove `api/ratings.py`, `api/catalog_stub.py`, `llm/`, `middleware/auth.py`, the Postman workflow and collection (or retarget at `/api/v1`), `core/cache.py` and the `redis` dependency, `jobs/`, `utils/financial.py`, unused health checks, demo CLI commands; flag-gate the Parfumo scraper with a deprecation warning after moving GTIN evidence into `SourceSnapshot` (the scraper's write path is already fail-closed since PR #125, which is stricter than a deprecation warning, so the remaining work here is moving GTIN evidence and removing the deprecated module and CLI commands); rewrite the app description and README overview (G-03, G-07, B-21, B-22, B-23, B-24, B-30, F-04/F-22, B-34; architecture review Q1-Q4, Q12 pending, defaults apply) | none (maintainability) | Sonnet | Opus | 2 PRs |
| R10 | Backend consolidation | Services never commit; one `ProjectBaseError` handler; domain exceptions replace `reject()` and raw `HTTPException` in services; activation, skin planning, finalization, and checkpoint creation move into `CalibrationService` with checkpoint creation under the enrollment lock plus a PostgreSQL concurrency test; control-flow asserts replaced; N+1 and unbounded queries fixed; import size bounded; registry-validated `candidate_strategy` and checkpoint `algorithm_version` (B-04, B-05, B-07, B-08, B-09, B-14, B-15, B-16, B-17, B-25, B-29, B-33, B-35, B-31, M-11) | none | Opus | Sonnet tests | 3 PRs |
| R11 | Typed calibration contract and generated client | Pydantic response models with `response_model=` on all calibration routes; provenance fields (`algorithm_version`, `candidate_strategy`, `score_type`, `score_value`, `recorded_by`), `fragrance_name` and `fragrance_brand` on `EvaluationResponse`, RFC 3339 offsets on timestamps; client generated from `docs/api/openapi.json` and committed; a CI diff between the committed spec and a fresh export (F-03, F-04, F-05, B-13, F-20, Appendix A) | none | Sonnet | Opus | 2 PRs |
| R12 | Frontend decomposition and state | Split `ProgramSetupPage`; hoist `RecommendationCard`; typed route params with a not-found route; keyed data store with invalidation after mutations; 401 interceptor; per-action task state; error boundary; design tokens with dark mode; type-aware ESLint with `jsx-a11y`; server-side progress summary for Home (F-06 to F-09, F-12, F-16 to F-21, F-23 to F-26) | none | Sonnet | Opus | 3 PRs |
| R13 | End-to-end and accessibility harness (see sequencing note 8: substantially covered by PR #103) (done 2026-10-31: PR 1, the Vitest side, merged as #168 `b13f1f1`, delivers MSW so real axios errors reach component tests (F-11, `src/test/msw/server.ts`, `realErrors.test.tsx`), `vitest-axe` over every route (F-13, `routeAxe.test.tsx`, with a control that proves the scan catches a violation), and a 360 px reflow assertion in the mocked Playwright tier (`e2e/reflow.spec.ts`); PR 2 (#173 `198ec48`, review follow-ups #174 `e7c8ac6`; #175 `19ecf59` makes `real-stack-e2e` part of the CI Gate) adds the real-stack tier (`frontend/e2e-stack/`: forward-auth stub, trust-boundary, participant and manager journeys against the real backend on PostgreSQL; CI job `real-stack-e2e`), amends the P4/P5 gate records honestly, and fixes a history-name defect the tier found; P4.4 and P4.5 stay mocked-only) | Playwright with a compose-backed fixture and a forward-auth stub covering the five P4 journeys and the P5 manager journey with interruption and retry; MSW in Vitest; `vitest-axe` on every route; a 360 px assertion; P4 and P5 gate records re-closed or amended per architecture review Q13 (G-01, F-10, F-11, F-13) | P6 (per Q13) | Sonnet | Opus | 2 PRs |
| R14 | Operations, observability, and documentation (done 2026-11-06: PR 1, secrets and the topology validator (#170 `13d7e5e`, review fixes #177 `a7443a4`), delivers S-04 (both billed-endpoint secrets required by the prod override), S-08 (middleware name as an argument; single replica, manager allow-list, CORS, secrets and `TEST_MODE` assertions), S-16 (no literal weak credential in `.env.example`), S-27 (`TEST_MODE` refused in production), and the S-28 replica-comment and model-name drift; PR 2 delivers the scheduled backup service with verified dumps, retention with a floor and a healthcheck, and `scripts/verify_restore.py` (D-18; #171 `63ab34f`), and the topology validator now refuses a render without that service (#178 `0b34e87`); PR 3 was split: PR 3a, documentation consolidation, merged as #179 `02b7c36` (G-04, G-05, G-08, G-10, G-12, D-14); PR 3b merged as #192 `381d33c` (read-only root filesystem, `cap_drop: [ALL]` and `no-new-privileges` on the hardened services through the `x-hardened` block, validator checks, `BUILD_ENV` removed: S-13, S-20) and #193 `8a0d038` (base images and compose postgres images pinned by digest, Renovate `pinDigests`, keyless cosign signing in the publish workflow: S-12); a deployer-side `cosign verify` is still owed (`docs/deployment/image-signing.md`)) | Secrets plumbed from the prod override; topology validator extended; digest-pinned base images and cosign; runtime hardening; `.env.example` and build-arg fixes; scheduled backup with a restore check and `scripts/p1_migration_inventory.py` (merged in #116) and `scripts/verify_restore.py`; documentation consolidation (delete `CONFIG_TEMPLATES_SUMMARY.md`, archive `concept.md`, merge ADR directories, rewrite README, regenerate the CLAUDE.md structure section, supersede `SECURITY-FINDINGS.md`, update the gap analysis to v1.1) (S-04, S-08, S-12, S-13, S-16, S-20, S-27, S-28, D-18, G-04, G-05, G-08, G-10, G-12, D-14) | P6 for secrets, validator, and backups; none for docs | Sonnet (Haiku may be used only for read-only discovery of stale references) | Opus | 3 PRs |
| R15 | First learned model and comparison | Design spike: a written model spec for a partially pooled linear or ordinal model on the R6 reduced basis with a population prior, the evaluation plan against the repeat ceiling, and the decision rule instance; then `ml` optional dependency group (`numpy`, `scipy`, `scikit-learn`), the model registered beside `affinity-v2`, `predict_and_freeze` on the same holdouts, and a scorecard report; no tuning on holdouts (ML Decisions Q7; review Tier 4 items 17 and 18) | D5 entry; may start after R6 and R8 | Fable for the design spike (one session); Opus implements | Sonnet tests | 1 doc + 2 PRs |

### Sequencing

1. R1, then R2, in that order (R2's parity test needs R1's PostgreSQL job to be visible in CI).
2. R3 and R4 in parallel after R1; both must merge before the P6 go decision.
3. R5 is done; R6 after R2; R7a after R2 (R5's reconciliation is already available); R7b after
   R7a and before the P6.3 synthetic rehearsal (section 4, `gates/p6.md`); R8 after R6 and may
   land after the P6 go decision, since it carries no evaluator-facing UI.
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
- For R7b specifically: the synthetic released-UI export named in its row is produced and attached
  to the P6.3 rehearsal record before P6.3 is marked complete, and again before F1's first exposure
  if R7b changed after P6.3 last ran.

### F1 facilitated-format work items (decided 2026-11-24)

Decided by the product owner on 2026-11-24 (ADR-005 and ADR-009 amendments of that date). These items extend
the R2 enrollment and R7b participant-instrument surfaces for the six-evaluator facilitated F1 format; they
are tracked here as their own list rather than as a new numbered sprint, and they gate F1. Several of them
change what the participant or recorder screens do, so under this plan's existing rule that a participant-
instrument change after P6.3 voids P6.3, they must merge before P6.3 is executed (proposed consequence of
that rule, pending owner confirmation). **No sprint or milestone status above changes because of this list.**
Each item is marked done only when its pull request is merged, with the PR number added here. Status as of
2026-11-25: the protocol amendments (#212), non-blind flag (#213), shared-triple enrollment (#211), holdout gate and
household reveal (#214), sheet materials (#215), the session-scoped wizard (#216, `699a513`), the facilitated guides
and P6.3 scope (#217, `b027e0f`) and transcription timing (#218, `65202bd`) are merged. On 2026-11-25 the owner also
decided **group blotter mode** for F1 group sessions (one physical blotter per sample passed round the six evaluators,
shared codes and order, a 2 minute spray-to-first-smell ceiling, flag only); its code (#220, merged as `6774525`),
documentation (#219) and server-side safeguards (#221, merged as `2bcd3cc`) pull requests are listed below. **Later the
same day (2026-11-25) the owner tried the group procedure physically, got only two evaluators through in two minutes,
and abandoned group mode for F1: F1 returns to individual blotters, one per evaluator per sample, each evaluator
spraying their own, with the 2 minute ceiling kept and now counted per own blotter. The group code and safeguards stay
merged and unused (`INDIVIDUAL` is the default); the paper sheet moves to `v2.1` (wording only).** A merged item
is not gate evidence: no P6 or F1 gate changes because of it.

| Item | Scope | Status |
| :--- | :--- | :--- |
| Family MVP profile and F1 sign-offs (owner decision 2026-11-25) | The owner's scaled P6.1 to P6.6 scope for the family pilot (what is kept, what is waived, what is not scaled), the sign-offs now decided (scale wording, `would_buy` stays, paper retention 12 months, spray one spray from about 15 cm, no linked prediction required per holdout, no seat order, withdrawn and wrong-evaluator handling, minors consent without a guardian clause, 2-minute ceiling kept), and the trimmed pre-exposure declaration | Recorded in [`gates/p6.md`](gates/p6.md#family-mvp-profile-owner-decision-2026-11-25), [`gates/f1.md`](gates/f1.md) and [`gates/p1.md`](gates/p1.md) by the docs change that adds this row; **not gate evidence**: no P6, P1 or F1 item is closed by it, the P1.4 and P1.1 second-check waivers are recorded as owner decisions, and P6.6 `go` is still required |
| Docs: protocol amendments | ADR-005 and ADR-009 amendments, calibration-v1 and baseline-evidence randomisation wording, the F1 gate declaration, this plan, the blind-evaluation workflow | Merged (#212); not itself gate evidence |
| Non-blind quality flag | A quality-flag code for the holder's rows (needs a CHECK-constraint migration) and honoring it in the evidence export and training eligibility | Merged (#213), with the `spray_to_smell_ceiling_exceeded` code; the holder's rows leave blind-baseline training and stay in evaluation. Follow-up: `ml.reliability.pooled_reliability_both_ways` is not yet called by any report or export |
| Shared-triple enrollment | A manager-supplied session composition with per-session Latin-square rotation, random evaluator-specific codes, holdouts last, repeat separation validated, actual order persisted; the persistent-or-animalic limit enforced if the needed data exists | Merged (#211; the Latin-square order applies to individual mode, which F1 uses again; the unused group blotter mode below gives all evaluators the same order): `shared-triples-latin-rotation-v1`, manager-supplied session composition and persistent-sample list, random evaluator-specific codes (standard labels refused), a manager-only session-plan preview, actual order persisted; no migration |
| Shared blind labels at enrollment (#243, 2026-11-27) | `label_scheme: "shared"` for `shared-triples-latin-rotation-v1`: one blind code per physical sample for every evaluator, equal to the atomizer label; the first shared enrollment of a program supplies `membership_codes`, later enrollments inherit the recorded codes; the program's reveal policy must be `HOUSEHOLD` | Merged (#243, `6635413`): API contract in [tech-spec](tech-spec.md#calibration-enrollment-and-blind-code-contract), frontend Family pilot screen sends `label_scheme: "shared"` and holds no codes, no Alembic migration. Not recorded as deployed; the build and pin decision is open (F1 gate sign-off 19(d)). Not gate evidence |
| Holdout gate and household reveal | Server-side gate that refuses holdout observation writes until the enrollment has a checkpoint; a manager path to create the checkpoint; a program-level reveal policy that reveals all enrollments together only after every stage, the skin plans, the checkpoints and all holdouts are locked (per-enrollment reveal stays the default); correct phase labelling of holdout rankings | Merged (#214): per-sample `available` flag, `reveal_policy` (`ENROLLMENT` default, `HOUSEHOLD`), program readiness, program checkpoints and household reveal. **Holdouts now need a manager checkpoint in any program with holdouts, including the P6 rehearsal path**, until the wizard adds a button. Follow-ups: a withdrawn evaluator blocks the household reveal with no procedure; whether F1 requires a linked prediction per holdout is an owner decision |
| Session-scoped wizard | Frontend: no skin-plan step or inline skin-plan form in the blotter flow; session boundary screen; per-session ranking posted to the right session; holdout sequence after the checkpoint; household-reveal waiting screen; role-aware next-sample choice; corrected guidance text; a manager checkpoint action | Merged (#216, `699a513`): session-scoped screens, awaiting-checkpoint, household-wait and household-ready steps, and a manager checkpoint and household reveal panel in Program setup. Not rehearsed in P6.3 |
| Transcription and timing | Transcription of the paper sheet with the first-smell time sent as the presentation time, the finished time as the observation time, whole-minute elapsed time, session start, end and ranked times, per-session conditions, consent recorded once, and a guard that confirms the blind code printed on the sheet before a column is saved | Merged (#218, `65202bd`): the paper's first-smell, column-finished, session and ranking times reach the backend and are validated; the blind-code confirmation is enforced server side (a mismatch is a 409); a first smell past the ceiling raises `spray_to_smell_ceiling_exceeded`. At merge the ceiling constant was 5 minutes; group blotter mode changes it to 2. Not rehearsed in P6.3 |
| Sheet and spray sheet | Paper session sheet with its own version id, a separate conditions slip, the provisional ceiling wording (5 minutes when written, 2 minutes since the 2026-11-25 owner decision), a facilitator run sheet, and a spray-sheet generator whose identity-bearing output goes only to a gitignored path | Merged (#215): `facilitated-session-sheet v1.0`, `facilitated-conditions-slip v1.0`, run sheet, `scripts/make_spray_sheets.py`; all drafts until the P6.3 rehearsal. The group blotter documentation pull request moved the sheet to `v2.0` (a Blotter mode row is added to Part A; the slip stays `v1.0`); the individual-blotters revision moves it to `v2.1` (wording only, no recorded field changes); `v2.2` (2026-11-27, F1 gate sign-off 16) adds the pre-printed Atomizer row under the blind code row on the sheet and on each generated evaluator header (the generator's mapping gains a required `atomizer` column), because samples now sit in atomizers B01-B39 and H01-H10 that evaluators spray from; it records no new field, and the six P6.3 rehearsal headers must be reprinted with it. `facilitated-session-sheet v3.0` (owner decision 2026-11-27, drafted in a separate change set; proposed, not yet printed or used) is a major revision: one generic double-sided handwritten form, Intensity 0 meaning not detected (no Detected row), no "Not answering because" box, no consent or data classification field, and paper-only would wear, would buy, type of event and season answers. The F1 gate names it before first exposure and carries an open question on its item 4 (sheet and slip ids equal to the waived P6.3 ids) |
| Guides and rehearsal scope | Manager and participant guides for the facilitated variant; P6.2 and P6.3 scope for a six-person paper-plus-transcription rehearsal; template feedback | Merged (#217, `b027e0f`): guides, P6.2 and P6.3 scope, F1 declaration template, this plan, template feedback; not gate evidence |
| Group blotter mode, code (built, merged, NOT used by F1) | Program `blotter_mode` (`INDIVIDUAL` default, `SHARED_GROUP`), enrollment algorithm `shared-triples-group-blotter-v1` giving all evaluators the same blind code and order, automatic informational session flag `group_shared_blotter`, spray-to-first-smell ceiling 2 minutes (was 5) with each evaluator's sprayed/first-smell pair checked against it, `scripts/make_spray_sheets.py` is in the documentation row below | Merged: #220 (`6774525`). Also adds the `group_shared_blotter` flag as automatic and not hand-raisable, `ml.reliability.pooled_reliability_group_blotter_both_ways` (not yet called by any report or export), and a migration chained after `a7f3c2d91e04` |
| Group blotter mode, documentation and spray sheets (history) | Sheet `facilitated-session-sheet v2.0`, run sheet group procedure and replacement-blotter rule (both superseded by the individual-blotters revision, sheet `v2.1`), `scripts/make_spray_sheets.py --mode group`, guides, F1 and P6 gates, ADR-005 and ADR-009 amendments, calibration-v1 and blind-evaluation-workflow notes | Merged with this change: #219 (`docs/f1-group-blotter-procedure`, after #220); not gate evidence |
| Group safeguards, server side (built, merged, NOT used by F1) | In `SHARED_GROUP` programs: holdouts open only when every enrollment has a checkpoint; new enrollments refused once they have; holdout evidence times earlier than the opening checkpoint refused (422); `SHARED_GROUP` forces a `HOUSEHOLD` reveal; ceiling rule version `spray-to-smell-ceiling-v2`; readiness reports `blotter_mode`, `holdouts_open_program_wide` and `enrollments_missing_checkpoint` | Merged: #221 (`2bcd3cc`), no migration. Server cannot see when a blotter was physically smelled, so "no holdout smelled before every checkpoint exists" is a facilitator procedure (run sheet). Not rehearsed in P6.3; not gate evidence. After the owner's physical attempt on 2026-11-25 F1 does not use group mode, so these safeguards are retained and unused; in an individual program the holdout gate is per enrollment and the readiness view's `holdouts_open_program_wide` is always false |

Known gaps and questions carried by these items, not yet resolved:

- Follow-ups left open after #221 (all OPEN, none done): `ml.reliability.pooled_reliability_*` has no caller in any
  report or export; `training_manifest` (`preference_history.py`) ignores `training_eligibility`; the skin-plan
  endpoint (`POST /presentations/{id}/skin-plan`) has no server-side manager-role check; the wizard's `isOpen`
  (`frontend/src/routing/wizardSteps.ts`) treats a missing `available` as open; `docs/api/openapi.json` and
  `frontend/src/client/types.gen.ts` are stale against the merged API; the frontend reveal-policy dropdown may still
  offer `ENROLLMENT` for group programs (the server refuses it; moot while F1 does not use group mode).
- Gaps from the #221 review, with the owner's 2026-11-25 decision: there is no way to withdraw an enrollment and a
  withdrawn evaluator blocks the household reveal for everyone (verified in `DisclosureGate.household_blocker`); the
  owner decided no code change, the reveal waits and the owner decides what to do at that time. The second gap (in group mode a sheet
  entered under the wrong evaluator is not detected, because every enrollment shares the blind code) no longer
  applies to F1: with individual blotters the codes are per evaluator, so the blind-code guard refuses such a sheet
  (verified in code, `confirm_blind_code`; P6.3 attacks it; amended 2026-11-27: not for `v3.2`, whose codes are
  shared, so the check is procedural, F1 gate sign-off 19). The withdrawal gap is listed in the F1 gate and the P6.3
  scope.

- The `would_buy` removal that DEC-03 planned was not carried out (R7b row, owner decision 2026-10-30; see
  the ADR-005 and ADR-009 2026-11-24 amendments, pending owner confirmation of the leakage and analysis
  implications). In the facilitated format only the holder has a skin stage.
- The scale wording on the session sheet (v2.1) and the property guide (v1.0) was accepted by the owner on 2026-11-25
  (see the [F1 gate](gates/f1.md)); the formal sign-off record belongs in the private declaration.
- Not yet scoped: an evaluator-by-session progress view for the manager, room-contamination flags, more than
  four seeded reviewer records, a UI for the `model_training` and `aggregate_reporting` consent scopes, and a
  check that training paths honor `model_training` consent (today only the evidence export checks it).
- Calendar: at most two sessions (6 blotters) a day means 17 sessions need at least 9 test days.
- P6.3 must rehearse paper plus transcription in the six-person format, test that each of six evaluators spraying their
  own blotter can stay inside the provisional 2-minute spray-to-first-smell ceiling (including a fresh blotter, and
  how often one was needed), and confirm or replace it. Until then the ceiling is a working value. It is not the 2 minute clean-air interval of ADR-005, which
  is a different number.
- History: group blotter mode would have kept `group_shared_blotter` scores in training (flag only, owner decision
  2026-11-25, later the same day abandoned for F1). Its shared-code confound (order and seat position confounded with
  the score) does not arise with individual blotters, so no group-flag training or reliability split applies to F1.
- Owner decisions of 2026-11-25 (recorded in the [F1 gate](gates/f1.md)): the scale wording accepted, `would_buy` stays
  on the blind skin form, paper retention 12 months (the consent text's period), spray one spray from about 15 cm,
  pointed away from faces and other blotters, no linked prediction required per holdout, seat order not applicable,
  no code change for a withdrawn evaluator (the household reveal waits and the owner decides at that time), no change
  for a wrong-evaluator sheet beyond the blind-code confirmation and the facilitator's check, and no guardian clause
  added to the consent text. Decided separately on 2026-11-26 (recorded in the [F1 gate](gates/f1.md)): evaluators walk
  up to the vials as they are ready to spray their own blotter and the facilitator does not schedule turns at the
  vials; P6.3 observes it.

### Post-F1 follow-up: evaluator login linkage (proposed 2026-11-27)

**Status:** Proposed; not started; no owner design decision yet. It does not gate P6 or F1, and it changes no gate,
sprint or milestone status. It is tracked here as its own item, not as a numbered sprint (the convention of the F1
facilitated-format work items above), so the Milestone R sprint list stays R1-R15.

**Scope.** Nothing in this item changes program `v3.2`, the F1 procedure, the F1 instrument or the pinned build. For
F1 only the single recorder login transcribes every evaluator's sheets (owner decision, 2026-11-27, consistent with
[F1 gate sign-off 19](gates/f1.md)). Any code from this item needs a new build and the owner's explicit decision under
the build-freeze rule, so it cannot reach F1 participants unless the owner chooses that.

**Owner requirement (2026-11-27), for after F1.** Evaluators must be linkable to their own logins, and mixed entry must
be possible: the facilitator may enter some of an evaluator's sessions, and that evaluator may enter others herself.

**Entry gate.** F1 evidence reviewed, and an owner decision on the Proposed amendment in
[ADR-008](adr/adr-008-authentication-and-production-boundary.md#proposed-amendment-2026-11-27-linking-logins-to-reviewers).
No implementation starts before both.

**Design principle (proposed).** Link a reviewer to a provider-neutral external identity, an (issuer, subject) pair,
not to an Authentik username. The owner's recollection (2026-11-27, not verified in the repo, recorded in ADR-008) is that
the original reason for keeping login and reviewer independent was not wanting an app that others may eventually use to
depend on the owner's personal Authentik account; the repo itself documents only the R3 scope trade-off.

**What exists today.** Verified against the code at `6635413`; the parts not verified are listed as open questions
below.

- The only link between a non-manager login and an evaluator is `Enrollment.recorder_usernames` (a JSON list on the
  enrollment). It is written when the enrollment is created and no route or service in `src/` changes it afterward, so a
  change after enrollment is a manual SQL edit. The `Reviewer` model has no login column.
- The coupling to avoid: authorization matches the `X-Authentik-Username` header value, trimmed and otherwise exact and
  case-sensitive (`username in recorder_usernames`). The identity object also carries the `X-Authentik-Uid` and
  `X-Authentik-Email` headers, but nothing in `src/` uses them for authorization, and there is no token, JWKS or OIDC
  verification code in the backend.
- `CalibrationService.enrollment` refuses a non-manager who is not listed, and the presentation- and session-keyed
  paths (`target`, `session_target`) go through it. A manager passes the check by being on
  `CALIBRATION_ADMIN_USERNAMES` (`core/auth.py`). The same list is the read grant for the evaluator's history (ADR-008,
  R3 amendment, Q5).
- Every listed login has identical rights: read the blind view, start and end sessions, write observations, lock stages,
  plan skin tests, lock the skin plan, record and withdraw the reviewer's consent. Mapping, checkpoints and household
  reveal are manager-only. There is no participant role.
- The frontend decides paper-transcription mode from the program's reveal policy alone (`isTranscribed` in
  `frontend/src/content/transcription.ts` returns true for `HOUSEHOLD`). The backend `observe_once` never reads the
  reveal policy or any entry mode, so nothing on the server distinguishes a facilitator's transcription from an
  evaluator's own entry.
- A single-enrollment reveal on a `HOUSEHOLD` program is refused server-side
  (`DisclosureGate.require_enrollment_reveal_allowed`), and the household reveal is manager-only. Under shared blind
  codes one evaluator's reveal would unblind the others, so reveal must stay manager-controlled for any shared-code
  program.
- `start_session` refuses a second start, but `CalibrationSession` records no actor (it has `started_at`, `ended_at`
  and the timezone, with no `started_by` or `recorded_by`), and a different listed login can still write observations
  to a started session.
- Observations have no uniqueness on presentation, stage and phase. A second submission with a new or no idempotency
  key appends a row, and the table is append-only by database trigger. `v_training_rows` keeps the latest `PRE_REVEAL`
  observation per presentation and stage (by `created_at`, then `id`, ignoring rows marked `invalidated`), whoever wrote
  it, and counts a stage only once it is locked. So until the stage is locked a later entry silently supersedes an
  earlier one.
- `Observation.recorded_by` is stored, but `observation_payload` (used by the evidence export) omits `recorded_by`,
  `training_eligibility` and `idempotency_key`, so the export cannot show who entered a row.
- The audit trail (`log_audit_event`) covers program, enrollment, consent, lock, reveal, checkpoint and mapping actions.
  The observation, exposure, session start and session end routes emit none.

**Design (proposal, options and trade-offs; nothing here is decided).**

1. Where the link lives. Option A: a mapping table, for example `reviewer_identities`, keyed by
   (issuer, subject) and unique on that pair, linking an external identity to a reviewer (a reviewer may have several
   identities, and one identity several reviewers, which a guardian with minors needs); the participant role itself
   lives on the enrollment, so a link alone grants nothing. It is provider-neutral and fits history and recommendation
   reads, at the cost of a new personal-data mapping with its own removal rules. Option B: a per-enrollment list beside
   `recorder_usernames` (for example `participant_usernames`). It reuses the existing shape and scopes the grant to one
   program, but it keeps the username coupling, repeats for every enrollment and gives no person-level view. Option C:
   a login column on `Reviewer`. It is the simplest and the least flexible (one login per reviewer, no guardian case)
   and it couples the reviewer row to one provider. The ADR-008 amendment asks the owner to choose; Option A is the one
   that follows the design principle.
2. A participant role with narrow rights: the evaluator's own blind view, start and end of her own sessions, and her own
   observations and exposure stamps. No consent recording, reveal, skin-plan, mapping or stage lock unless a
   justification is written down; guardian consent for minors stays with the manager.
3. An entry mode computed on the server, independent of the reveal policy, and enforced in `observe_once`, so the
   client cannot choose it. Whether it is stored per session or per observation is open.
4. Session ownership stamped when a session starts (who, and self-entered versus facilitator-transcribed), with writes
   from a different login rejected except by a manager. This is what makes mixed entry safe, at the cost of a manager
   step to hand a session across.
5. `recorded_by` and the entry source added to the evidence export, and audit events added for observation, exposure,
   session start and session end writes.
6. An explicit correction path, so that a second pre-lock entry for the same presentation and stage is never a silent
   replacement: either refuse a second entry and offer a correction that links to the row it replaces, or keep both and
   require a stated reason. This interacts with the `v_training_rows` supersession rule and needs review against the R8
   dataset rules.
7. Delivery: an Alembic migration, a backend change, a frontend change and a new frontend build. Check
   `alembic heads` before adding the revision.
8. The ADR-008 amendment, and a review of the [F1 gate sign-off 19](gates/f1.md) consequences afterward. Under shared
   codes a facilitator's transcription still cannot catch a sheet entered under the wrong evaluator (the blind code is
   the same for everyone), so that consequence stays procedural for transcribed entry; a participant identity that sees
   only its own enrollment would remove it for self-entry.

**Phasing (proposal).**

- First slice: family evaluators, who are already inside the owner's Authentik, are linked through Authentik. This
  does not conflict with the owner's concern, provided the stored key is the provider-neutral (issuer, subject) pair
  (for Authentik, its issuer and the stable user id, not the username string) and the matching code has one seam where a
  second provider could be added. Built in the first slice: the identity mapping table and the (issuer, subject)
  extraction from the forwarded headers, the participant role on the enrollment, the server-computed entry mode,
  session ownership, the export and audit changes and the correction path, with the migration and a new build.
- Deferred until outsiders are actually in scope: a path for people outside the owner's Authentik. Options, with
  trade-offs. Supabase Auth (the obvious candidate given the owner's earlier app): a managed hosted IdP, quick to adopt,
  but a second system and vendor, and it would hold participants' emails. Any generic OIDC provider: provider-neutral and
  swappable, but the backend must carry token verification and its operation. Authentik enrollment or invitation flows:
  no new system, but it keeps outsiders inside the owner's Authentik, which is the coupling the owner wants to avoid for
  a shared app. Designed for now (the key is (issuer, subject)), built later.

**Acceptance criteria (draft, for owner review).**

- An evaluator signs in as herself, sees only her own blind view, and can enter her own sessions. A different evaluator's
  login and a manager's behave as the ownership rule says.
- A mixed-entry program (some sessions transcribed by the facilitator, some entered by the evaluator) exports one
  row per observation with `recorded_by` and the entry source, and no row silently replaces another.
- Reveal, mapping, checkpoints and consent for minors remain manager-only, and a participant identity cannot reach them.
- Reads follow ADR-008 Q5: a linked participant reads only her own reviewer's evidence.
- Trust boundary: the forwarded-header path is unchanged and a client cannot supply identity headers through it. Any
  token-based path verifies signature (JWKS), issuer, audience and expiry in the backend itself and is covered by tests
  that forged, expired, wrong-audience and wrong-issuer tokens are refused.
- Authorization-matrix and disclosure tests cover the new role on every route in the existing matrix.

**Evidence (to be retained).** The ADR-008 decision, the migration and its test, the extended authorization matrix, an
export of a mixed-entry program, and the owner's acceptance. None exists yet.

**Open questions (not verified, do not assume).**

- Whether Option A, B or C, and whether one identity may map to several reviewers (guardian with minors).
- Whether entry mode and session owner are stored per session, per observation or both.
- Which (issuer, subject) Authentik supplies in this deployment (the forwarded `X-Authentik-Uid` is read today but
  unused, and its stability and the issuer value are not verified).
- The trust-boundary design for any token path: where verification lives, how JWKS keys are fetched and rotated, and how
  the path is kept separate from the forwarded-header path.
- Privacy, for owner decision: a hosted identity provider would hold participants' emails, including minors', while the
  fragrance and evaluation data stay in the owner's PostgreSQL (authentication only). Whether a minor may have an
  identity of her own, and what guardian consent and the existing consent text must say about it, is open; this item
  draws no legal conclusion.
- Whether any tooling outside `src/` writes `recorder_usernames` (only `src/` was searched).
- Whether the exposure route should be treated as part of the participant role.

### Post-F1 follow-up: blotter-stage would-wear, would-buy and event-type capture (proposed 2026-11-27)

**Status:** Proposed; not started; the owner has decided the F1 paper treatment (below) but not the post-F1 design. It
does not gate P6 or F1, and it changes no gate, sprint or milestone status. It is tracked here as its own item, not as a
numbered sprint, so the Milestone R sprint list stays R1-R15.

**Owner decision (2026-11-27).** The F1 evaluator paper sheet (new version `v3.0`) asks, per sample at the blind blotter
stage, three questions the application does not record at that stage today: Would wear (0 to 10, Never to Definitely),
Would buy (0 to 10, Never to Definitely) and Type of event (multi-select: work or school, at home, social outing,
formal event, outdoor activity, something else, none of these, cannot judge). The same sheet also asks Season on its
back, with the same status (added to this item by the v3.0 procedure change set, see below): Season (`season_fit`; multi-select: spring, summer, fall, winter, year-round, none of these, cannot judge). For F1 these answers are paper only: they
are scanned, the originals are retained under the existing paper-retention sign-off, and they are not entered in the
application. The application is to be changed after F1 to capture them natively, and whether season is to be keyed
after F1 is an open owner question (below).

**Scope.** Nothing in this item changes program `v3.2`, the F1 procedure, the F1 instrument or the pinned build. Any
code from this item needs a new build and the owner's explicit decision under the build-freeze rule, so it cannot reach
F1 participants unless the owner chooses that. The sheet and run-sheet changes themselves belong to a separate change
set; this item records only what the application has to do about them.

**Entry gate.** F1 evidence reviewed, and an owner decision on the Proposed amendments in
[ADR-005](adr/adr-005-controlled-calibration.md#2026-11-27-proposed-amendment-blotter-stage-would-wear-would-buy-and-event-type)
and [ADR-009](adr/adr-009-prospective-evaluation-and-checkpoints.md#2026-11-27-proposed-amendment-blotter-stage-wear-and-buy-are-a-separate-measure).
No implementation starts before both.

**What the application does today (verified against the code at `a2f240c`, 2026-11-27).**

- **Would wear and would buy are accepted, stored and exported at the blotter stage already.** `ResponseInput` carries
  both as optional integers from 0 to 10 with no stage rule; the `Observation` columns and their range CHECK
  constraints have no stage condition; `observe_once` writes whatever the input carries; the evidence export emits both
  whatever the stage; and a unit test stores a blotter-stage observation with `would_wear` 9 and `would_buy` 7. What is
  missing at the blotter is the form: `blotterGroups` in `frontend/src/content/calibrationScales.ts` lists neither,
  only `skinGroups` does, and the observation panel sends a null for a field it does not render.
- **Type of event is refused at the blotter stage.** `validate_capture_fields` raises `setting_fit is asked at skin stage
  only` for a non-empty `setting_fit` on a non-skin stage, and a test (`test_blotter_rows_never_carry_fit`) pins it.
  The eight codes the sheet offers equal the existing `SettingFit` codes (`work_school`, `home`, `social_outing`,
  `formal_event`, `outdoor_activity`, `other`, `none`, `cannot_judge`), the same standalone and duplicate rules would
  apply, and the `FitChoice` table has no database stage CHECK (it relies on the service). So the refusal is a schema
  rule, not a storage limit.
- **Season is refused at the blotter stage in the same way.** `validate_capture_fields` runs the same check for
  `season_fit` and `setting_fit`: a non-empty list on a non-skin stage is refused (`season_fit is asked at skin stage
  only`), so season is stage-gated by the schema validator at the blotter stage exactly like `setting_fit`. The options
  are `spring`, `summer`, `fall`, `winter`, `year_round`, `none` and `cannot_judge` (`SeasonFit`), a duplicate is refused,
  and the schema makes only `none` and `cannot_judge` stand alone. Instrument v0.5 says (in its response rules) to choose individual
  seasons OR year-round OR none OR cannot judge, so v0.5 treats `year_round` as exclusive and the schema does not; that
  mismatch is an open question below. v0.5 also already lists `BL-SEASON` as an optional blotter worksheet item with the
  same option codes and a distinct stage identity.
- **An Intensity of 0 needs no application change.** The sheet's rule that a circled Intensity 0 means not detected is
  entered through the existing not-detected rule: `detected` false, `intensity` 0, `liking` empty and `response_status`
  `not_detected`, which `ResponseInput` already enforces (a not-detected row must have intensity 0 and no liking).
- **The paper-only answers cannot be entered after F1 through any existing path.** A pre-reveal write to a locked stage
  is refused (`Stage is locked; original responses are retained`), and F1 locks every blotter stage before the
  household reveal. The `post-reveal` route accepts a write after reveal, but it is the wrong provenance (an informed
  observation, not the blind answer), `v_training_rows` excludes it (only `phase = 'PRE_REVEAL'` reaches the view), and
  it still carries `setting_fit` only under the skin-stage rule. Observations are append-only (PostgreSQL trigger
  `fr_observation_append_only` allows only `training_eligibility` to change), and no correction route exists. A quality
  flag carries a code and free text, not typed values, and an INFORMATIONAL flag changes nothing. Re-writing the
  PRE_REVEAL row is not an option either: `v_training_rows` hides an earlier same-stage PRE_REVEAL answer once any later
  one that is not `invalidated` exists, so a late row with a null liking would silently remove the original liking
  answer from training.
- **Entering them natively would pool two different measures unless guarded.** `ml/dataset.py` lists `would_wear` and
  `would_buy` among `TARGETS` and `_controlled_row` reads them from the observation features whatever the stage;
  `services/preference_history.py` includes both as features; `ml/training_view.py` forwards both; and
  `CHECKPOINT_TARGET_SCALES` and `CheckpointPrediction` identify a target by name and scale with no stage. A blotter
  would-wear is a hypothetical judgment of a smell strip; a skin would-wear follows wearing the sample. They must not
  share a feature or target name. Holdouts and hidden repeats are blotter-stage presentations, so the checkpoint
  tables are exposed to the same ambiguity. X-13 already forbids pooling the 0 to 10 observation columns with the
  boolean recommendation-feedback fields of the same names.

**What native capture needs (change inventory, not a design).**

| Area | Change |
| :--- | :--- |
| Schema (`schemas/calibration.py`) | Relax the blotter refusal for event type and, if the owner decides to key it, season; keep every other stage rule; keep the duplicate and standalone `none` and `cannot_judge` rules; decide the blotter field names so a blotter value cannot be read as a skin value |
| ORM and migration | Wear and buy columns exist. Event type can reuse `FitChoice` (no stage CHECK), so a forward-only native option needs no table change; any late-entry option (below) needs a new column or table, a migration, and care with the append-only trigger and `v_training_rows` |
| Service (`calibration_service.py`) | `observe_once` stage handling; for any late-entry option, a new entry type allowed after lock that must not supersede the original answer |
| Frontend | A blotter wear, buy and event group in `blotterGroups`; the observation panel `save()` and its numeric-field loop; the paper transcription wizard and `PaperSheetFields.tsx`; `transcription.ts` completeness; existing tests `instrumentChoices.test.ts` and `SampleObservationR7b.test.tsx` |
| Evidence export | A new `EXPORT_VERSION` if the stage-qualified fields change the row shape (it is `r7b-evidence-v1` today), with the measure named in each row |
| Training and checkpoints | Stage-qualified feature and target names in `ml/dataset.py`, `ml/training_view.py`, `services/preference_history.py`, and the target identity in `CheckpointPrediction`; eligibility for blind-baseline training versus values from the non-blind mapping holder (the holder's rows stay `questionable` under the `non_blind` flag and never reach the view, unchanged) |
| Tests | Schema, service, API, frontend, export, and a no-pooling test that a blotter value never reaches a skin target; the existing `test_blotter_rows_never_carry_fit` is replaced, not deleted |
| Release | A new build, a new instrument pin, and the owner's explicit decision under the build-freeze rule |

**Options and trade-offs.**

- **Option A, native capture before lock, stage-qualified, forward only.** Allow the three fields on the blotter form
  and in the schema, store them on `Observation` and `FitChoice`, qualify them by stage everywhere they are read, and
  apply this to the next program. Evaluators answer while the blotter stage is still open, so no late path is needed.
  Smallest change, no new table, no weakening of the append-only trigger or the supersession rule, and the pooling
  guard is the main work. Cost: the five F1 evaluators' paper values are never in the database.
- **Option A2, A plus a supplementary-observation entry type that may be added after lock.** Would carry F1's paper
  values into `Observation`. It needs a new column, a migration, an exception in the lock rule and in the append-only
  trigger, and an exemption from same-stage supersession in `v_training_rows` (otherwise the late row hides the
  original liking answer, as above). Largest blast radius on the evidence-integrity machinery for a one-time backfill of
  five evaluators.
- **Option B, a separate append-only `paper_supplement` table keyed by presentation.** Holds a source of `paper`, a scan
  reference, who entered it and when, and the three values with event-type child rows. It can be entered after lock or
  reveal, leaves `Observation`, the trigger and `v_training_rows` untouched, and cannot pool by construction. Cost: a
  new model, schema, service, route, transcription screen, export section, audit events, authorization-matrix rows,
  migration and tests, used once for F1 and then redundant once Option A exists.
- **Option C, accept paper only for F1 and capture natively from the next program.** This is Option A with no backfill,
  and it is the owner's stated minimum.

**Recommendation (proposed, for owner decision).** Option A, with Option C as its F1 treatment: native, stage-qualified
capture before lock for later programs, and the F1 paper values stay on paper unentered and retrievable from the scans.
It is the smallest change that does what the owner asked, it leaves the append-only and supersession machinery alone,
and it makes the no-pooling rule structural. Option A2 is not recommended. Option B is the choice only if the owner
later wants the five evaluators' F1 values in the database for analysis; decide that after the F1 evidence review shows
whether the values are worth entering, and do not build it speculatively. This is a recommendation about design
risk, not a measured result.

**How F1 analysis treats the paper-only values meanwhile.** They are not in the database, not in the evidence export,
not in any training row, not in the checkpoint manifest and not in any F1 completeness count. They exist only on the
retained scans and originals, so any later look at them is a manual, per-evaluator reading and is reported separately,
never merged with the skin-stage `would_wear` and `would_buy` columns.

**Blotter wear and buy are a different measure.** A blotter-based hypothetical would-wear or would-buy answers "would you
wear or buy this, from a smell strip", with no skin, no drydown and no wearing experience, while a skin-stage answer
follows wearing the sample. Instrument v0.5 already separates the blotter and skin trial outcomes (`BL-TRY` and the
"distinct outcomes" note) and ML Decisions Q9 keeps the skin-stage fit fields off the blotter for the same reason. The two
measures are never pooled, never share a feature or target name, and are reported with their own n. ADR-005 and ADR-009
carry the Proposed amendments. Liking stays the primary target.

**Acceptance criteria (draft, for owner review).**

- The blotter form captures would wear, would buy and event type (and season, if the owner decides to key it) for an
  evaluator, and the paper transcription wizard does the same, with the sheet's scale anchors, eight event codes and
  seven season codes.
- A blotter value is stored under a stage-qualified name and is not readable as a skin-stage value in
  `v_training_rows`, `ml/dataset.py`, the feature snapshot, the evidence export or the checkpoint manifest, shown by a
  test that fails if they are pooled.
- The append-only trigger, the stage lock and the same-stage supersession rule are unchanged (Option A), or the exception
  is the minimum the owner approved (Option A2), with a test of each.
- Existing skin-stage behavior, including `would_buy` on the skin form and the skin-stage-only rule for `season_fit`
  and `setting_fit`, is unchanged, and the full existing suite passes.
- The mapping holder's blotter values are excluded from blind-baseline training exactly as the holder's other values are.
- The F1 paper-only values are documented as unentered, with the scan location and retention period, in the F1 evidence
  review.

**Evidence (to be retained).** The owner decision on the two Proposed amendments, the migration and its test (if any
option needs one), the no-pooling test, a sample export showing the stage-qualified fields, the new instrument pin and
build, and the owner's acceptance. None exists yet.

**Open questions (not verified, do not assume).**

- Whether `src/fragrance_rater/consent/family-consent-v1.md` and the F1 gate sign-offs about consent and minors cover
  collecting purchase and wear opinions. The consent text lists "how strong it smelled, how much you liked it, and
  whether it felt familiar" as examples of answers and does not mention purchase, wear or event opinions; this item
  draws no legal conclusion, and the sheet change is another change set's.
- The added time and fatigue per sample. The owner's figures are about 25 answers per sample rising to 28 or more for children (not
  counted in the repository); whether that is acceptable is a facilitator and owner question the dry run can
  inform.
- Whether season (`season_fit`) is to be keyed after F1 at all. The sheet asks it on paper, and the options and the
  stage rule are as above. If it is keyed, whether it shares the `FitChoice` season dimension with the skin stage or has
  its own, so that a blotter season can never be read as a skin-stage `season_fit` (the same question as for event type
  below), and how `year_round` exclusivity is settled: v0.5 treats `year_round` as exclusive, the schema makes only `none`
  and `cannot_judge` exclusive, and the sheet ticks `year_round` alone, so the schema either tightens or the instrument
  loosens.
- Whether the paper-retention and scan sign-off in the F1 gate (12 months, destroyed with the database) covers these
  fields as written, or needs a wording check.
- Whether the F1 gate's rule that the sheet and slip ids equal the P6.3-rehearsed ids (waived on 2026-11-27) needs a
  note for a `v3.0` sheet. That gate is outside this item.
- Whether Option B is wanted once the F1 scans exist, and whether event type at the blotter should reuse the
  `setting` dimension of `FitChoice` or get its own dimension so it cannot be read as a skin-stage `setting_fit`.
  ML Decisions Q9 and the instrument v0.5 divergence row both say `setting_fit` is not collected on the blotter, while
  v0.5 lists `BL-SETTING` as optional on the blotter worksheet; that conflict is pre-existing and is not resolved here.
- The current Alembic head was not re-verified for this item (the plan states `736b7db082fb` as of 2026-11-07); check
  `alembic heads` before adding any migration.
- A phrase the owner attributed to ADR-005, that a blotter smell is not a wearing experience, was not found verbatim in the
  repository; instrument v0.5, ML Decisions Q9 and the ADR-005 2026-11-24 skin-stage-only text are the closest sources.

## 11b. Integration status as of 2026-11-07

This section records state and proposes actions. It does not change any milestone gate. Items under "pending owner
approval" are **proposed only**: the owner has not approved closing pull requests, deleting branches, resetting local
`main`, or pushing, and none of those has been performed. Sources are the 2026-10-21 repository and GitHub state, refreshed on 2026-11-07;
items not re-verified are marked.

### Main state

- This section began as a 2026-10-21 snapshot and was refreshed on 2026-11-07. When refreshed, `origin/main` was at
  `bf9be17` (#196) with the single Alembic head `736b7db082fb` (#187); the chain from `c5a9e2d7f1b4` is listed in the
  Live PostgreSQL migration row of section 3, and the merged ledger below names each later revision.
- **The 2026-10-19 dependency-advisory block is cleared.** #140 (`932c211`) bumped `mako` to 1.4.3, `certifi` to
  2026.10.19, and `virtualenv` to 21.14.12. The CI, Container Security, SBOM and Security Scan, and Postman API Tests
  runs on `main` for `5d26c34` all passed. The Security Analysis push run for `f5baecc` shows `cancelled`, and no
  completed run for that commit was re-verified here (#132 merged on its second enqueue after a cancelled merge-group run).
- Checks that were red or failing on `main` and are not required contexts, as of 2026-11-07: (a) the Documentation
  Pages deploy failure is resolved: #166 (`0578c71`) disabled the deploy because Pages is unavailable for the
  organization, and the Documentation workflow passes on `main`. (b) Mutation Testing still reports `startup_failure`
  on its weekly runs (runs 37 to 40, last seen 2026-11-01, the last two still under the older `74cfc8e9`
  reusable-workflow pin); the next scheduled run is the first under the current pin, and the cause is not triaged.
  (c) Container Security went red at `381d33c` (#192) on Hadolint `DL3025` for the shell-form `HEALTHCHECK` in both
  Dockerfiles. It was the first run under reusable-workflow pin `79bf84c7` (adopted by #169, whose pull request did
  not run this workflow because its path filter omits the workflow file). #195 (`fbfdc8c`) fixed it and the workflow
  passes on `main` again.
- Merge rules (organization rulesets): required contexts are Security Gate Validation, Dependency & Standards
  Validation, Check REUSE Compliance, and CI Gate; strict up-to-date policy; signed commits; linear history; squash
  merge queue; zero required approvals; delete-branch-on-merge on.
- **Merging to `main` does not deploy.** There is no deploy workflow; `docker-publish` only builds, pushes and signs images (keyless cosign, #193).
  The R2 migrations therefore have not run against production.
- Before this plan's last substantive edit (PR #124, 2026-09-26) the ledger omitted: #116 P1 migration inventory
  tooling and concurrency tests; #118 R1 CI truthfulness; #119 guided calibration entry routing; #120 public Evidence
  page and product-research reconciliation; #121 semantic-release `commit_parser` fix; #122 Actions pin; #124 F1
  data-capture addendum and blind-baseline resequencing; #125 ADR-012 `SourceSnapshot` provenance columns (the Parfumo
  write path now fails closed); #127 `fr-core` olfactory vocabulary v0 (ADR-017); #128 blind-evaluation instrument
  v0.5 and web-workflow documents; #133 Renovate lock-file exemption; #134 `pyjwt` 2.15.1 CVE fix.

### Merged ledger (snapshot through #132 on 2026-10-21; updated through 2026-11-07, in merge order)

| PR | Commit | Result and what remains |
| :--- | :--- | :--- |
| #135 | `329c648` | R2 PR 1: naming convention, schema parity tests, FK-enforcing fixtures; migration `2c8c3971bfd8` |
| #136 | `00f14d6` | R2 PR 2: evidence CHECKs, nine FK indexes, `evaluations` RESTRICT; migration `df2f9646a280`. **Pre-deploy gate (P1.3):** its CHECK preflight is atomic and refuses to add a CHECK while any row violates it, and migrations run at container start (PR #111), so a violating row blocks startup. Run the preflight against a production backup clone before deploying |
| #139 | `0cf7d80` | `vite` 8.3.3 security fix (dev server only) |
| #140 | `932c211` | `mako`, `certifi`, `virtualenv` advisory bumps; `main` unblocked |
| #141 | `326f01b` | Renovate rule holding `requires-python` updates (Python stays 3.12). #123 was closed in favor of it. The rule's matcher is not yet confirmed by a live Renovate run: the earlier rule matched `depTypes` `["python"]`, not the `requires-python` type |
| #126 | `87333a0` | GitHub Actions update, including the new organization reusable-workflow pin |
| #142 | `a3d49cd` | `test(calibration)`: the `Vary` assertion uses `in` instead of equality |
| #137 | `5d26c34` | House intake form and manager review, adapted to R2: migrations `b7e3d91a4c2f` then `c5a9e2d7f1b4`, re-parented onto `df2f9646a280`, constraint names aligned to the R2 convention. No sprint home; proposed home D1; not an F1 gate. **Deploy check:** Traefik must forward `X-authentik-groups` for the group fence; verify in the homelab, as without it the fence has no effect and offboarding relies on disabling the Authentik account |
| #132 | `f5baecc` | Lock-file maintenance (`starlette` 1.9.0, `sqlalchemy` 2.1.6), merged on the second enqueue after a cancelled Security Analysis merge-group run |
| #143 | `4d31328` | R3 PR 1 (2026-10-30): edge trust boundary. **Deploy note:** production requires `FRAGRANCE_TRAEFIK_CIDR`, or Compose refuses to render and nginx refuses to start; the deployed forged-header check belongs to P1.6 |
| #144 | `10bd5d8` | R3 PR 2 (2026-10-30): route authorization per the owner's Q5 decision. **Behavior change accepted by the owner:** a household member with no recorder assignment gets 403 on history and recommendations until a manager enrolls them as a recorder |
| #145 | `0d74024` | Documentation refresh that created this section |
| #146 | `0d9c77c` | GitHub Actions update |
| #151 | `45e09fd` | R6 PR 1 (2026-10-30): `notes.name_key`, `note_aliases` (`nm-v1`), `accord_types`, `intensity_source` and `rank`, one `VocabularyResolver` for both writers, `fs-v2`; closes X-01, X-02, X-03, X-04, X-12 in schema and writers. It also carried the R4 status docs first proposed in #150 (merged separately on 2026-10-30; its content is a subset of this ledger). **Deploy note:** the migration merges colliding notes and runs at container start; take a backup first. **The merged migration had defects that #152 fixed in place; do not deploy `45e09fd` without `54f5eda`** |
| #152 | `54f5eda` | R6 review follow-up (2026-10-30): unicode-safe note keys, accord-collapse provenance, duplicate note spellings. Edits migration `000091664cdd` in place, safe only while no database ran `45e09fd`'s version |
| #157 | `39ae231` | R6 PR 2 (2026-10-30): versioned alias file (empty until the verified manifest exists), `vocab aliases validate/load/ambiguities`, audited all-or-nothing loader, pre-commit hook. **Do not deploy `39ae231` without `de7084e`:** `ruamel-yaml` was a dev-only dependency, so the production CLI fails at import; fixed in #158 |
| #158 | `de7084e` | R6 PR 2 review fixes (2026-10-30): `ruamel-yaml` as a runtime dependency, audit emitted after commit, whitespace-only actor refused, `.yml` hook coverage, test gaps |
| #160 | `3acaead` | R7a PR 1 (2026-10-30): capture shape, schema only. Migration `3f14014a49cb`: `calibration_session_contexts`, `calibration_rank_events` and `calibration_rank_entries` (a pairwise judgment is a two-entry rank event), `behavioral_events`, real session, presentation, and observation timing with evaluator timezone, typed sample provenance, response-status, recognition, and prior-ownership codes, scrub-off and interval-longevity fields. Nothing writes to it yet |
| #161 | `6d46a58` | R7a PR 2 (2026-10-30): provenance and governance, schema plus the activation write. Migration `cd1e2375a2e4`: `consent_events` and `calibration_quality_flags` (both append-only), randomization algorithm and seed on enrollments and `intended_position` on presentations, `Program.instrument_version` written at activation (`INSTRUMENT_VERSION`, else `unpinned-app-<version>`), skin-stage-only `season_fit` and `setting_fit`. **Resolved by R7b:** `enroll()` writes the randomization record and consent and flags are written (PR 1, #165), season and setting became multi-select child rows (migration `f74bf7ff9c2d`), and `INSTRUMENT_VERSION` is wired into compose and the frontend build (PR 2) |
| #138 | `2f6d971` | Selectable standard or random blind label scheme at enrollment (pilot tooling for P6 and F1; no plan home). Merged 2026-10-30. When this ledger first listed it, it was held on an owner ruling about session-grouping leakage from standard labels, the `App.test.tsx` expectation, and a CodeRabbit thread on the label prefix; the pull request records how they were resolved |
| #149 | `f247d3a` | R4 (2026-10-30): role-neutral holdout answers, impression-only explanations, calibration and prediction audit trail (kept at any `LOG_LEVEL`), no-store by default, server-owned disclosure state, logging configured, `SecretStr` keys with redaction. **API removal:** `GET /recommendations/{reviewer_id}/{fragrance_id}/explain` |
| #150 | `04c28d4` | Docs: recorded R4 and R6 PR 1 as merged (subset of this ledger) |
| #148 | `af41ed5` | Renovate: `@types/node` v26 (frontend dev dependency) |
| #153 | `aa11a1e` | CI: `persist-credentials: false` on checkouts, deprecated security-workflow inputs dropped |
| #154 | `fe11664` | Docs: residual stale references from the repo-inconsistencies review |
| #155 | `799f661` | Docs: still-open ideas from reviewed `claude/*` branches (idea register) |
| #156 | `3fc6a05` | Docs: Fragella API integration notes (batching, slug encoding, field shapes) |
| #159 | `d0a51e5` | Docs: recorded #158 as merged |
| #162 | `3b0d3ce` | Docs: recorded R7a schema (#160, #161) as merged |
| #165 | `eafb818` | R7b PR 1 (2026-10-30): backend write paths for instrument v2, migration `f74bf7ff9c2d` (`calibration_fit_choices`); `enroll()` records the randomization, consent and quality flags are written |
| #166 | `0578c71` | CI: GitHub Pages deploy disabled (Pages unavailable for the organization), docs build kept; also `pyasn1` 0.6.5 for four advisories |
| #167 | `73d6bcc` | R7b PR 2 (2026-10-31): participant instrument v2 UI, `INSTRUMENT_VERSION` build wiring, e2e and WCAG 2.2 AA scans, synthetic-run guard test. The acceptance export from a deployed synthetic run is still owed (P6.3 waived 2026-11-27, no substitute chosen) |
| #168 | `b13f1f1` | R13 PR 1: MSW, `vitest-axe` on every route, 360 px reflow test |
| #170 | `13d7e5e` | R14 PR 1: both billed-endpoint secrets required by the prod override, stricter topology validator, `TEST_MODE` refused in production, no literal weak credential in `.env.example` (S-04, S-08, S-16, S-27, S-28) |
| #171 | `63ab34f` | R14 PR 2: scheduled `backup` service, verified dumps, retention floor, `scripts/verify_restore.py` (D-18) |
| #172 | `96bcc5d` | R8 PR 1 (2026-10-31): training eligibility, `v_training_rows`, source provenance, checkpoint schema; migration `620c8c861268` |
| #173 | `198ec48` | R13 PR 2: real-stack tier with forward-auth stub |
| #174 | `e7c8ac6` | R13 review follow-ups |
| #175 | `19ecf59` | `real-stack-e2e` is part of the CI Gate |
| #176 | `443e15f` | Frontend: revealed identities stay on screen after a guided reveal (no sprint home) |
| #177 | `a7443a4` | R14 PR 1 review fixes |
| #178 | `0b34e87` | Topology validator requires the `backup` service |
| #179 | `02b7c36` | R14 PR 3a: documentation consolidation (G-04, G-05, G-08, G-10, G-12, D-14) |
| #180 | `8945a34` | API: `get_db` commits before the response is sent (`scope="function"`, FastAPI >= 0.121; no sprint home) |
| #181 | `64321e7` | R8 PR 2: readers on `v_training_rows`, triggers, jsonb, UTC, idempotency key; migration `4edb5c967539`. **Deploy note:** runs at container start, take a backup first |
| #182 | `9d34a25` | R8 review follow-up; migration `50c1f75abb15` |
| #183 | `001139c` | Removed the withdrawn PYSEC-2022-42969 pip-audit ignore (S-14) |
| #184 | `a1dc3c0` | Docs: R7b, R8, R13, R14 progress |
| #185 | `f207f26` | R8 choice A: an invalidated later answer no longer supersedes in `v_training_rows`; migration `52e22be935d3` |
| #186 | `966a48c` | `family-consent-v1` approved with the owner's final wording |
| #187 | `bf5ca17` | `bounded_lookup` dropped, excluded snapshots ignored in the GTIN check, `source_reference` format defined; migration `736b7db082fb`; closes #130 |
| #188, #189, #190 | `874d01a`, `7cea198`, `63a7f6d` | Docs: owner's 2026-11-01 decisions, review fixes, decant label-check proof accepted for P1.1, OpenRouter zero data retention recorded |
| #193 | `8a0d038` | R14 PR 3b (S-12): base images, uv 0.9.26 and compose postgres images pinned by digest; Renovate `pinDigests`; keyless cosign sign jobs (`docs/deployment/image-signing.md`, `tests/unit/test_image_pinning.py`). Merged before #192 despite the numbering |
| #191 | `54e88e6` | Lock file maintenance |
| #163 | `54b516a` | CI: security-analysis cancels only superseded pull request runs (merged 2026-11-06) |
| #164 | `7de145b` | Docs: ledger records the deleted backup branches and dropped stash |
| #169 | `2c71998` | GitHub Actions update; every reusable-workflow caller moves from `74cfc8e9` to `79bf84c7`. Container Security did not run on this PR (path filter omits the workflow file) and went red on the next Dockerfile change, #192; fixed by #195 |
| #192 | `381d33c` | R14 PR 3b (S-13, S-20): `x-hardened` (read-only root, `cap_drop: [ALL]`, `no-new-privileges`) on app, frontend, db and backup; `BUILD_ENV` removed; validator and tests. **Deploy notes:** db runs as 70:70; the bind-mounted `backup_database.sh` must be world-readable and executable on the host (no `DAC_OVERRIDE`); a file-level restore needs a chown (`docs/deployment/backup-and-restore.md`) |
| #195 | `fbfdc8c` | Exec-form `HEALTHCHECK` in both Dockerfiles; clears the Hadolint DL3025 finding that turned Container Security red on `main` at `381d33c` (the Hadolint step is advisory, not a required context) |
| #196 | `bf9be17` | Docs: R14 recorded as done and the status mirrors refreshed (plan v2.10, roadmap, `CLAUDE.md`, planning README) |

### Open pull request ledger

| PR | Branch | Purpose and plan home | Status |
| :--- | :--- | :--- | :--- |
| #194 | `renovate/docker-images` | Renovate digest refresh for the pinned base and compose postgres images (S-12 pins); gates nothing | Open. Required checks were green. Its Container Security job failed on the same Hadolint finding #195 fixed on `main`, so the branch needs updating to pick that up. The advisory `review / Baseline Triage Review` check errored at its API call on every pull request; its caller workflow has since been removed. Review the digests before merge |

Issue #5 is the Renovate dashboard.

### Proposed merge order

Each step needs a green re-run of the required checks.

Only #194 is open (above). Before the next deploy, run the P1.3 CHECK preflight against a production backup clone (a
violating row blocks container start; see the #136 row), then take a backup (the R6 to R8 migrations run at container
start and the chain head is `736b7db082fb`) and deploy a commit at or after `381d33c`, which carries both halves of R14 PR 3b
(hardening and signed images). The production override also refuses to render without both API keys, the `backup`
service and `FRAGRANCE_TRAEFIK_CIDR`.

### Pending owner approval

None of the following has been performed or approved: the branch cleanup below, a fast-forward of local `main`, the
rebase and split of `docs/fragella-api-reference`, and the Scentineer documentation pair.

### Local and remote branch reconciliation

State only. No deletion has been performed or approved.

- **Remote branches still present on 2026-11-07** (`git ls-remote --heads`): `feat/r13-real-stack` (PR #173),
  `feat/r6-alias-curation` (PR #157) and `feat/r6-vocabulary-schema` (PR #151), each for a merged pull request, and
  `renovate/docker-images` (PR #194). Deleting the three merged ones needs the owner after confirming no unmerged commit
  remains. The local-clone items below (stale local `main`, `docs/fragella-api-reference`, the Scentineer pair) cannot be
  verified from CI and remain owner items.
- **Historical, resolved by 2026-11-07 (these no longer exist on `origin`); merged by content (the pull request merged):**
  `chore/gitignore-and-adr-crosslinks` (#95), `chore/renovate-hold-blocked-majors` (#113), `claude/r1-sprint-6slwgt`
  (#118), `docs/bandit-finding-count-accuracy` (#109), `docs/ml-architecture-data-capture-addendum` (#124),
  `docs/panel-web-handoff` (#128), `docs/project-plan-refresh-2026-09` (#108),
  `docs/protocol-research-reconciliation` (#107), `fix/bump-trivy-registry-scan-sha` (#101),
  `fix/docker-publish-permissions` (#94), `fix/frontend-docker-default-build-target` (#100),
  `fix/frontend-healthcheck-ipv4` (#102), `fix/pr110-followups` (#110), and `fix/source-snapshot-provenance-fields`
  (#125). Duplicate pointers `pr107-head`, `pr108-head`, `pr105tmp`, `pr-109-check`, `pr-120-review`, and `pr120tmp` are
  also candidates, with moderate confidence (matched by subject and SHA, not by full diff); re-verify content before
  deleting. Branches for pull requests merged on 2026-10-21 join this list by pull request state, not by diff:
  `chore/renovate-hold-requires-python` (#141), `feat/house-intake-form` (#137), `feat/r2-schema-constraints` (#136),
  `fix/deps-mako-certifi-advisories` (#140), and `test/vary-header-assertion` (#142).
- **Needs an owner decision before deletion:** `renovate/major-react-monorepo` (commit `489c9b7`, a three-line
  eslint-disable in `frontend/src/pages/HomePage.tsx` absent from `main`) and `pr116-check` (likely superseded by #116,
  not provable).
- **Resolved 2026-10-30:** `renovate/github-actions` (tip `bbb5d25`) and `backup/pr125-pre-rebase` (tip `a8c394b`) were
  deleted, and `stash@{0}` was dropped (stash commit `07bdfb3`). The backup branch's other four commits had landed
  through #121 and #125; its one unlanded document was deliberately kept out of this public repository.
- **Remote-only `claude/*` review branches (no pull request), reviewed 2026-10-30:** the documents were not landed
  because main's ADRs, this plan, and the architecture review supersede them; the still-open ideas are captured in
  the [idea register](review-branch-idea-register.md). Source tip SHAs for recovery: architecture review
  (`claude/fragrance-app-architecture-8i6v4i`) `307ee845`; dataset concept (`claude/fragrance-dataset-concept-w2qvwa`)
  `e1995db1`; plan-vs-implementation review (`claude/project-plan-implementation-review-t1ht0j`) `440b9a4f`, remote
  branch already deleted; repo-inconsistencies review (`claude/repo-inconsistencies-review-45w1ao`) `b78c1425`, its
  still-needed fixes are in a separate PR. Those remote branches no longer exist on `origin` (2026-11-07).
- **Local `main` is stale** (22 commits behind `origin/main`); its one ahead commit `f29dfc7` is already in
  `origin/main` as `2fc4e65` (#121). A fast-forward or reset is safe after owner approval.
- **`docs/fragella-api-reference`** (the checkout of the primary clone, no upstream) is 7 commits ahead of `main` and
  holds the Fragella API reference, the OpenAPI spec, and the 43 of 43 baseline and holdout resolution evidence.
  [The catalog coverage evidence](evidence/baseline-v3.1-catalog-coverage.md) on `main` shows 0 of 33 and does not
  reflect that unpushed work. The two denominators measure different sets (33 is the unique baseline fragrances, 43
  adds the 10 holdouts) and different things (rights-cleared coverage versus identity resolution); neither figure is
  restated here. The branch will conflict with `docs/fragella-api.md` and the `mkdocs.yml` navigation on `main` (#128
  added a 69-line version). Two uncommitted files belong together:
  `docs/research/scentineer-presentation-reference.md` (untracked) and an edit to
  `docs/planning/frontend-visual-and-usability-gap-analysis.md`. Proposed: rebase onto `main`, resolve, open one
  documentation pull request for the Fragella work and a separate one for the Scentineer pair. That review must check
  the vendor-data and spoiler-content rules (no spoiler content, outreach letters stay local-only) before anything is
  pushed.

### Owner decisions of 2026-11-01 and the issues they close

- **R8 choice A (option 2):** an `invalidated` later answer no longer supersedes an earlier one in `v_training_rows`;
  a later `unreviewed`, `questionable` or `withheld` answer still does. Merged as #185 (migration `52e22be935d3`).
- **R8 choice B (option 1):** `TrainingRow.program_id` stays `None`; no change.
- **Consent wording approved** with the owner as the contact (PR #186). The approved text discloses that short
  preference summaries with the evaluator's name may go to OpenRouter, and that the manager deletes every backup copy
  when the evaluation database is deleted; `docs/deployment/backup-and-restore.md` has the retirement steps. Only the
  `session_context` scope is enforced in code and offered in the participant UI; the three use-choices are
  manager-mediated.
- **Procurement:** all 43 fragrances are procured, as decants from an initial split between sources. There is no
  manufacturer packaging, so identity evidence rests on the decant source's provenance plus a two-person label check
  (P1 runbook, "Source reference format and decant verification"). The owner accepted that lighter proof for P1.1 on
  2026-11-01 (decants need no manufacturer or packaging confirmation). The manifest was authored and validated on
  2026-11-24 and P1.1 closed on a single-checker pass by owner decision; the second label check stays open (see the
  [verification record](evidence/p1-1-baseline-manifest.md)).
- **OpenRouter:** zero data retention is enforced at the API-key level (owner, 2026-11-01). The consent text relies on
  it, so P1.10 confirms it on the production key.
- **Outreach:** brand outreach and vendor outreach are both complete with no replies. A second wave is a separate
  decision.
- **#129:** the P1.1 criterion now reads "source URL or source reference" (table above); the early R8 delivery is
  recorded in the R8 row. Closed.
- **#130:** `bounded_lookup` dropped, `excluded_no_new_writes` rows no longer block the GTIN conflict check, and
  `source_reference` is `who | YYYY-MM-DD | evidence or scope` (PR #187). The pairs table and `fields` allow-list were
  already enforced. Closed with #187.
- **#131:** reconciled by the dated amendment in ADR-012 (2026-11-01). Closed.

### Critical path to F1

Restated from the gate records; no gate text changes here.

R2 (#135, #136), R3 (#143, #144), R4 (#149), R7a (#160, #161), R7b's code (#165, #167), R8 (#172, #181, #182, with the owner choices in #185 and #187), R13 (#168, #173, #174, #175) and R14 (#170, #171, #177, #178, #179, #192, #193) are done (R7b is code-complete only: its acceptance export is still owed; the P6.3 deployed synthetic run it was to come from was waived on 2026-11-27 and no substitute is chosen); no unmerged sprint item gates P6. Before
any deploy of R2 or R3: the P1.3 backup-clone CHECK preflight, `FRAGRANCE_TRAEFIK_CIDR` set to the live Traefik subnet (a value that excludes Traefik makes nginx clear the identity headers, so every protected request returns 401; check it with the P1.6 steps in the [P1 runbook](../deployment/p1-release-readiness.md#production-topology)), and Traefik forwarding
`X-authentik-groups` (#137), both API keys set (the production override refuses to render without them), the bind-mounted `backup_database.sh` readable and executable by everyone on the host (mode `755`; the backup container runs without `DAC_OVERRIDE`), and, if the published images are deployed, `cosign verify` of each digest per `docs/deployment/image-signing.md`. Then P6.1 through P6.6 with a recorded `go`: the `go` was recorded on 2026-11-27 with the P6.3 waiver (section 11); as of that record P6.2 and P6.4 are unrecorded and P6.1 and P6.5 are partly done, the 2026-09-18 incident is interim evidence only and does not substitute for P6.2's device
matrix, and any participant-instrument change after P6.3 voids P6.3. Then the F1 pre-exposure declaration with R8 (done) complete (R6's 43-version
alias decisions can be authored against the P1.1 manifest but no longer gate F1; they are a D1 prerequisite by
owner decision 2026-11-26), then F1, then a `proceed to D1` decision.
P1.1 is closed: the manifest was validated on 2026-11-24 on a single-checker pass by owner decision (the second label check is still open; see the [verification record](evidence/p1-1-baseline-manifest.md)). All 43 fragrances are procured as decants and the owner accepted the decant label-check proof on 2026-11-01. The committed coverage evidence still shows 0 of 33 baseline fragrances with rights-cleared notes.

## 12. Milestone F1: Initial family perfume pilot

**Objective:** Observe real family use of the complete product and establish honest baseline
values before discovery work.

**Owner:** Product owner and core maintainer

**Status:** Planned; the P6.6 `go` was recorded on 2026-11-27 with the P6.3 waiver (section 11) and the F1 program `v3.2` is activated with six evaluators enrolled
**Depends on:** P6
**Evidence:** [F1 Initial Family Pilot Gate](gates/f1.md)

### F1 facilitated format (decided 2026-11-24)

The product owner decided on 2026-11-24 that F1 runs with six evaluators in a facilitated, paper-first
format: shared session triples with a per-evaluator rotated order, random per-evaluator blind codes (one blotter per evaluator per sample, each evaluator spraying their own; a group blotter variant tried later on 2026-11-25 was abandoned; amended 2026-11-27: `v3.2` uses one shared code per physical sample equal to the atomizer label, F1 gate sign-off 19), one recorder login
transcribing the paper sheets, skin tests for the non-blind holder only, and one household reveal after the
holdouts. Protocol: ADR-005 and ADR-009, both amended 2026-11-24. Pre-exposure declaration additions:
[`gates/f1.md`](gates/f1.md). Work items: [section 11a](#f1-facilitated-format-work-items-decided-2026-11-24).
As decided on 2026-11-24, F1 status was **Planned; blocked on P6**; the P6 entry state on 2026-11-27 (P6.3 waived, P6.6 `go` recorded with waivers) is in section 11.

### F1 acceptance criteria

- The pilot declares its dates, evaluators, exact physical samples, algorithm version, candidate
  strategy, source snapshot, exclusions, and stopping conditions before first exposure.
- Family members use only the released UI for pilot tasks; support interventions and workflow
  failures are logged.
- Reports retain interest, response coverage, sampling conversion, post-sample liking, wear/buy,
  availability, coverage, variety, and connectivity/recovery counts with denominators.
- The review records usability problems separately from fragrance or algorithm outcomes.
- Before first exposure, the R7b synthetic-run export is attached (or re-attached, if R7b changed
  since P6.3 last ran) and the blind-instrument version is recorded, per `gates/f1.md`'s
  blind-baseline instrument completeness row. F1's evaluators (four in the original design, six in the facilitated
  format) each get exactly one blind pass;
  a field this criterion would have caught cannot be recovered afterward.
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
| F1's blind pass runs on a schema-only instrument (fields exist in the database but nothing in the released UI writes them) | High as scoped before 2026-09-21 | Critical: irreversible for the initial four evaluators, whose pre-reveal exposures (blotter, hidden-repeat blotter, and skin) all fall within F1's single blind pass; three of them provide blind observations, and the mapping-holder's rows are non-blind (next row) | Product owner | R7b's synthetic released-UI export (section 11a) and the P6.3 re-rehearsal requirement (`gates/p6.md`) |
| The F1 mapping-holder is also one of the evaluators (one of four in the original design, one of six in the facilitated format) | Standing decision: the holder evaluates and is flagged non-blind. Confirmed for this pilot (2026-09-21); training exclusion confirmed by the product owner 2026-09-26; carried unchanged into the six-evaluator facilitated format decided 2026-11-24, where the holder also sprays, times, transcribes, verifies and controls the reveal (`gates/f1.md`) | High for that evaluator's rows only | Product owner | That evaluator's rows are flagged non-blind and excluded from blind-baseline model training but remain in evaluation, with per-evaluator metrics still reporting that evaluator and the pooled repeat benchmark reported both including and excluding their pairs (24 and 18 for four evaluators, 36 and 30 for six), per `gates/f1.md` and the [ADR-009 2026-09-21 amendment](adr/adr-009-prospective-evaluation-and-checkpoints.md#2026-09-21-amendment-mapping-holder-evaluator-excluded-from-training-retained-in-evaluation) and [2026-11-24 amendment](adr/adr-009-prospective-evaluation-and-checkpoints.md#2026-11-24-amendment-six-evaluator-facilitated-f1-format); the other evaluators are unaffected. The earlier facilitated-plan draft treated holder-as-evaluator as unconfirmed; that was a contradiction with this row, resolved here by the standing 2026-09-21 decision, and no new decision is needed for it. The name of the holder is recorded in the pre-exposure declaration, not in this repository |

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
