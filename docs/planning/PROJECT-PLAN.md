# Fragrance Rater: Authoritative Project Plan

> **Version**: 2.1 | **Status**: Active | **Updated**: 2026-09-11

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
`7f0884fb3fd5a5faa5178952ae4ef1f08792d010` on 2026-09-11. P0-P2 implementation and review
evidence are retained in the linked gate records and PR #70.

| Capability | State | Evidence or remaining limitation |
| :--- | :--- | :--- |
| Docker Compose, FastAPI, PostgreSQL, React | Implemented | Development and production Compose files exist; production network exposure needs P1 validation |
| Fragrance, reviewer, and ordinary evaluation CRUD | Implemented | Ordinary POST retains dated encounters; update and soft delete operate on one encounter |
| Kaggle import | Implemented | Production dataset quality and rights remain source-specific |
| Parfumo capture | Partially implemented | Source snapshots and exact titles are preserved; representative live fixtures and full field coverage remain P1/D1 work |
| Deterministic recommendations | Implemented | Weighted affinity with veto; score is uncalibrated |
| Preference history | Implemented | Latest ordinary encounter per version plus eligible controlled evidence; holdouts are excluded |
| OpenRouter explanations | Implemented as optional enhancement | In-process bounded cache, deterministic fallback, and provider token/cost telemetry; live measurements require the F1 pilot |
| Controlled calibration | Merged, not deployment-verified | Program, enrollment, hidden repeat/holdout, presentation, observation, locking, reveal, and checkpoint flows exist |
| React product workflow | P4 complete; P5 review pending | Participant workflows are merged; manager and operations workflows await review before the P6 rehearsal |
| Recommendation outcome measurement | Implemented, not pilot-verified | Immutable runs/impressions, append-only feedback, outcome links, operational events, and provenance-complete reports exist; real baselines belong to F1 |
| Verified 43-fragrance baseline manifest | Not available | Exact versions must be verified; no identities may be guessed |
| Live PostgreSQL calibration migration | Fresh-schema verified | Full upgrade reaches current head on PostgreSQL 16; P1 still requires a production backup-clone exercise |
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
                                                                  └─ P6 Pilot readiness
                                                                      └─ F1 Family pilot
                                                                          └─ D1 → D2 ┬→ D3
                                                                                      └→ D4 → D5
```

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

**Status:** Implementation complete; review pending
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

**Status:** Planned
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
- [Plan vs. Implementation Review, 2026-09-12](reviews/2026-09-12-plan-vs-implementation-review.md)
