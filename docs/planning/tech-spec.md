# Technical Specification: Fragrance Rater

> **Status**: Active baseline | **Version**: 2.0 | **Updated**: 2026-09-11

## Purpose and authority

This specification describes the architecture present after the controlled-calibration merge and
the contracts required through D5. Detailed controlled-workflow rules live in
[Controlled Calibration V1](../calibration-v1.md). Delivery status and gates live in the
[Project Plan](PROJECT-PLAN.md). ADRs govern decisions that are expensive to reverse.

Generated OpenAPI is the route-level implementation reference. This document defines system
boundaries and invariants rather than duplicating every request field.

## Runtime architecture

| Layer | Technology | Responsibility |
| :--- | :--- | :--- |
| Frontend | React 19, TypeScript, Vite | P3 routed, role-aware foundation implemented; P4-P6 complete participant, manager, reporting, and operational workflows before F1 |
| API | FastAPI, Python | Validation, access policy, workflow orchestration, scoring, import |
| Data | PostgreSQL 16, SQLAlchemy 2, Alembic | Catalog, evidence history, controlled programs, checkpoints |
| Authentication edge | Authentik forward-auth through Traefik | Verified production identity and access boundary |
| Optional external services | OpenRouter and authorized metadata sources | Explanations and catalog enrichment |

Docker Compose remains the deployment unit on Unraid. Core capture, history, and deterministic
recommendations must continue when optional services are unavailable.

## Deployment trust boundary

Production traffic must follow:

```text
Client → TLS/Traefik → Authentik forward-auth → frontend/API → PostgreSQL
```

Requirements:

- `AUTHENTIK_REQUIRED=true` in production.
- The backend is not reachable through a host port or network path that bypasses Traefik.
- Forwarded identity headers are trusted only from the authenticated proxy path.
- Manager access comes from `CALIBRATION_ADMIN_USERNAMES`; an empty list grants no manager.
- `reviewer_id` identifies whose experience is recorded. `recorded_by` identifies the
  authenticated person entering it; they are intentionally not one-to-one.
- Mapping and checkpoint management routes require manager authorization.
- Participant disclosure is enforced server-side and reused by history and derived surfaces.
- Production topology and bypass behavior are tested in P1.

## Data domains

### Canonical catalog

`Fragrance` is the canonical version record through D5. Brand, display name, concentration, and
version key distinguish versions. Unknown concentration remains unknown. Once assigned to a
controlled program, identity fields are immutable.

`Note`, `FragranceNote`, and `FragranceAccord` represent normalized catalog features while
preserving source-specific evidence separately. Parent product/house modeling and inventory
management are outside current scope.

### Ordinary evidence

Each `Evaluation` POST creates a dated encounter on the original 1–5 scale. PATCH corrects one
encounter. DELETE soft-deletes one encounter. Storage retains repeated encounters; recommendation
policy selects contributions separately.

### Controlled evidence

The controlled domain contains:

- `Program` and immutable activated `Membership` definitions.
- `Enrollment`, randomized `CalibrationSession`, and coded `Presentation` records.
- Append-only `Observation` records with original 0–5 and 0–10 scales.
- Hidden repeats, baseline members, and holdouts.
- Stage locks, skin-plan finalization, reveal state, and post-reveal observations.
- `ModelCheckpoint` records containing frozen manifests and supplied predictions.

Unanswered values are NULL. Answered zero is data. Non-detection has intensity zero and no liking
score.

### Source evidence

`SourceSnapshot` records append raw/parsed evidence, retrieval time, verification state, and
source identity. Source refresh may add evidence but must not rewrite evaluator observations or
assigned canonical identity. `Perfumer` and `VersionPerfumer` preserve multiple attributions.

D1 adds versioned alias and taxonomy mapping entities. These mappings must never replace raw
source labels or evaluator wording.

### Recommendation measurement

P2 adds first-class recommendation runs, impressions, interest responses, sampling states, and
links to subsequent outcomes. A persisted impression is required before feedback. Outcome links
reference existing observations rather than copying or rewriting them.

P3-P6 are product-interface gates over these contracts. They require routed and resumable pages,
verified capability-driven navigation, complete participant and manager workflows, responsive
and accessible interaction, explicit failure/recovery states, and a deployed synthetic rehearsal.
F1 is the first stage allowed to collect outcomes from actual pilot perfumes.

Required provenance includes algorithm version, candidate strategy, rank, score type, source
snapshot, frozen input manifest, timestamp, and recorder.

## Evidence and disclosure invariants

- Ordinary, controlled, source, and model evidence retain separate provenance.
- Raw rating scales remain unchanged.
- The latest eligible ordinary encounter contributes at most once per version to the current
  `affinity-v1` profile.
- The latest eligible controlled observation prefers skin over blotter and maps liking to
  affinity with `(liking - 5) / 2.5`.
- When both ordinary and eligible controlled evidence exist, their affinities are averaged so a
  version still contributes once.
- Holdout versions are excluded from training across ordinary and controlled workflows.
- Hidden repeats and post-reveal observations do not become baseline training rows.
- Controlled evidence enters ordinary summaries only after reveal.
- Participant routes do not disclose fragrance identity, role, repeat link, selection evidence,
  or mapping before policy allows.
- A version revealed in another program is marked previously revealed rather than represented as
  naive.

## Recommendation architecture

The deterministic scoring service:

1. builds the eligible per-version preference history;
2. aggregates note, accord, family, and subfamily affinity;
3. applies a strong-dislike veto;
4. calculates a weighted raw affinity; and
5. transforms it to a bounded display score.

The display percentage is an affinity score. It is not a probability, confidence score, expected
0–10 rating, or evidence of statistical calibration.

OpenRouter generates optional explanations after deterministic scoring. Failure returns a local
fallback. Cache entries must be invalidated when reviewer evidence changes and must not bypass
blind disclosure. P2 measures model name/version, prompt version, calls, latency, failures, cache
hits, and estimated cost.

D4 adds candidate retrieval as a stage before evaluator-specific selection. Similarity, novelty,
uncertainty, availability, and cost remain separate quantities.

## API surface

The current generated API includes:

| Domain | Routes |
| :--- | :--- |
| Health | `/health/live`, `/health/ready`, `/health/startup` |
| Fragrances | List/get/create/update/delete under `/api/v1/fragrances` |
| Reviewers | List/get/create/delete/seed under `/api/v1/reviewers` |
| Evaluations | List/get/create/update/delete under `/api/v1/evaluations` |
| Recommendations | List, profile, and explanation under `/api/v1/recommendations` |
| Import | Kaggle import under `/api/v1/import/kaggle` |
| Calibration programs | Create/list, add members, activate, and enroll |
| Calibration enrollments | List/get, mapping, skin-plan lock, reveal, and checkpoints |
| Calibration presentations | Blind/post-reveal observations, stage lock, and skin planning |
| Shared history | `/api/v1/calibration/history/{reviewer_id}` |

The unversioned compatibility routes are legacy surfaces and must be inventoried before removal.
P2 adds versioned recommendation measurement routes. All route changes update generated OpenAPI in
the same pull request.

## D1 source and vocabulary contract

Every source or vocabulary snapshot records:

- stable source identifier and revision;
- retrieval timestamp;
- content hash;
- license or explicit permission evidence;
- raw label and source-specific classification;
- parser/mapping version;
- verification state and reviewer;
- exclusions or transformation parameters.

Alias mappings are many-to-one only after review. Mapped duplicates count once per fragrance for
statistics. Chemically or perceptually distinct terms are not merged merely because their names
are similar.

## D2 statistical contract

For a declared eligible population of size `N`, note totals `nA`, `nB`, and pair count
`nAB`:

```text
expected_pair_count = nA * nB / N
lift = nAB * N / (nA * nB)
partner_share = nAB / nA
```

All counts and `N` come from the same filtered, alias-resolved, within-fragrance-deduplicated
snapshot. Undefined denominators return an explicit undefined result. Results report support and
the versioned support/shrinkage policy.

## Performance and reliability budgets

| Behavior | Target |
| :--- | :--- |
| Ordinary CRUD API | Under 200 ms p95 on target deployment |
| Recommendation scores | Under 500 ms p95, excluding LLM |
| Calibration save/lock | Under 500 ms p95 under expected family concurrency |
| Frontend initial load | Under 2 seconds on the supported home/mobile path |
| Blind disclosure | Zero unauthorized fields or derivable mappings |
| Data loss | Zero accepted ordinary or controlled observations lost during upgrade |
| External failure | Core capture/history/scoring remains available |

D2 and D3 must define artifact-size and visualization budgets before implementation.

## Migration and recovery

- Back up and record the live revision and row inventory before schema changes.
- Test upgrades on an isolated PostgreSQL restore before production.
- Preserve IDs, timestamps, scales, authorship, and source provenance.
- Rehearse restore; do not rely on a lossy downgrade.
- Backfills are idempotent, support dry-run collision reports, and record mapping/source versions.
- Frozen programs, source snapshots, checkpoints, and outcome records are immutable except through
  explicit revision workflows.

## Testing strategy

### Required layers

- Unit tests for validation, scoring, mapping, and state transitions.
- API integration tests for authorization and error contracts.
- PostgreSQL tests for migrations, constraints, transaction behavior, and concurrent writes.
- Frontend component tests plus end-to-end ordinary, calibration, recommendation, and feedback
  journeys.
- Property/fixture tests for alias collisions, sparse pairs, filtered denominators, exact versions,
  duplicate notes, unknown values, and minimal-note fragrances.
- Deployed security tests for proxy bypass, role enforcement, and mapping disclosure.
- Accessibility, keyboard, mobile, and optional-service failure tests.

### Blind disclosure matrix

Every change affecting data access checks catalog search, ordinary history, controlled history,
profiles, recommendation lists, explanations, caches, errors, logs, exports, and new analytical
views.

### Supported environment

Release verification uses Python 3.12 and PostgreSQL 16. Tests under other supported Python
versions remain useful, but do not replace the target-environment gate.

## Observability

P1 defines operational logging, health checks, backup status, migration evidence, and security
events. P2 adds recommendation runs, response coverage, outcome linkage, LLM calls/cost, cache
behavior, and external-service latency/failures. Logs must exclude secrets, private response
bodies, blind mappings, and holdout identity.

## Documentation synchronization

Each implementation pull request updates:

- generated OpenAPI for route/schema changes;
- the project-plan status and evidence link;
- user and operations guidance;
- the governing ADR when a durable decision changes; and
- calibration or measurement protocols when workflow semantics change.

## Related documents

- [Project Vision](project-vision.md)
- [Authoritative Project Plan](PROJECT-PLAN.md)
- [Execution Roadmap](roadmap.md)
- [ADR Index](adr/README.md)
- [Controlled Calibration V1](../calibration-v1.md)
