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
| Frontend | React 19, TypeScript, Vite | P3-P4 implemented; P5-P6 complete operations before F1 |
| API | FastAPI, Python | Validation, access policy, workflow orchestration, scoring, import |
| Data | PostgreSQL 16, SQLAlchemy 2, Alembic | Catalog, evidence history, controlled programs, checkpoints |
| Authentication edge | Authentik forward-auth through Traefik | Verified production identity and access boundary |
| Optional external services | OpenRouter and authorized metadata sources | Explanations and catalog enrichment |

State management: local component state only, no external state-management library. Routing: a custom type-safe route union (`frontend/src/routing/routes.ts`), not React Router. Testing: Vitest + React Testing Library for unit/component tests, Playwright for mocked e2e plus a real-backend smoke tier (ADR-014), `@axe-core/playwright` + `eslint-plugin-jsx-a11y` for accessibility (ADR-014).

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

`Fragrance` also carries two house-confirmable facts outside version identity: `line` (collection)
and `market_status` (the house's commercial status, distinct from D4 sample availability).
`FragranceGtin` links each barcode to exactly one version and cites the `SourceSnapshot` that
established it. The house intake form maps every field onto these or onto layer-1 declared labels
([house intake design](../superpowers/specs/2026-10-02-house-intake-design.md)).

`Note`, `FragranceNote`, and `FragranceAccord` represent normalized catalog features while
preserving source-specific evidence separately. Parent product/house modeling and inventory
management are outside current scope.

Writers never look a note up by exact name. Every path that turns a source label into a `Note` or
an `AccordType` goes through `VocabularyResolver` (`services/vocabulary.py`):

- A `Note` is identified by `name_key`, the label with case, accents, and separators removed, so
  `Oak Moss` and `oakmoss` are one note. `Note.name` keeps the first spelling verbatim.
- `NoteAlias` rows resolve spellings under a mapping version (`nm-v1`). A `curated` row is a
  decision a person made (`vanille` means `vanilla`); an `observed` row only keeps a spelling that
  already normalized to the note. If a curated alias and the key lookup name different notes, the
  label is ambiguous: the writer skips it and a person settles it. Nothing is merged by guesswork.
- Curated aliases are decisions, not data entry. They live in a versioned, reviewed file
  (`data/aliases/note-aliases-nm-v1.yaml`: `raw_label`, `canonical`, `evidence`, `decided_by`) that
  `fragrance-rater vocab aliases validate` checks (one decision per key, no chains, evidence and
  author required, every violation reported) and a pre-commit hook enforces. `vocab aliases load`
  compares the file with the database and is a dry run unless `--execute --actor NAME` is given. A
  load is all-or-nothing and idempotent: a decision whose canonical note is missing, that conflicts
  with an existing decision, or whose label already names a different note is *blocked*, and one
  blocked decision blocks the whole load. `vocab aliases ambiguities` lists the labels the resolver
  refuses to guess at. The file is empty until the verified baseline manifest exists (P1.1).
- `Note.category` is an olfactory family or NULL, never a pyramid position. Position is
  `FragranceNote.position` (`top`, `heart`, `base`, `flat`), and `FragranceNote.rank` is the
  source's order within it.
- `FragranceAccord.accord_type` is a foreign key to the `accord_types` lookup. Each accord has an
  `intensity_source` (`measured`, `positional`, or `absent`) and a `rank` in its source's list. A
  positional intensity is order, not strength, and is excluded from measured features by default.

### Ordinary evidence

Each `Evaluation` POST creates a dated encounter on the original 1–5 scale. PATCH corrects one
encounter. DELETE soft-deletes one encounter. Storage retains repeated encounters; recommendation
policy selects contributions separately.

An `Evaluation` optionally carries `worn_by_reviewer_id` (ADR-011): NULL (default) means the
rating is "on me"; a different reviewer's id means `reviewer_id` is recording an "on others"
opinion, e.g. a partner's reaction to how a fragrance smells on the other. This dimension is
captured and returned through the same CRUD surface but is explicitly excluded from affinity
scoring and training-manifest input until a future milestone extends ADR-007's adapter to use it.

### Controlled evidence

The controlled domain contains:

- `Program` and immutable activated `Membership` definitions.
- `Enrollment`, randomized `CalibrationSession`, and coded `Presentation` records.
- Append-only `Observation` records with original 0–5 and 0–10 scales.
- Hidden repeats, baseline members, and holdouts.
- Stage locks, skin-plan finalization, reveal state, and post-reveal observations.
- `ModelCheckpoint` records containing frozen manifests and supplied predictions.

Unanswered values are NULL. Answered zero is data. Non-detection has intensity zero and no liking
score. Structured perception fields (sensory dimensions, temporal liking, `would_wear`/
`would_buy`, perceived notes, free-text comments) are typed columns on `Observation`, not an
untyped blob, so they are directly usable as ML features and labels
(see [ADR-010](adr/adr-010-preference-learning-and-scenario-data-model.md)).

### ML prediction snapshots

`PredictionSnapshot` freezes one model's predicted rating for one evaluator/fragrance pair before
the real outcome is known (model/version, feature-manifest, predicted value, uncertainty), and
records at most one later append-only link to the `Evaluation` or `Observation` that tests it.
The frozen prediction is never recomputed in place. Manager-gated routes live under
`/api/v1/predictions`.

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
| Recommendations | List and profile under `/api/v1/recommendations` |
| Recommendation measurement | Runs, impression explanation, linkable outcomes, append-only responses, metrics, and operational events under `/api/v1/recommendation-measurement`; explanations exist only for a persisted impression (architecture review B-02) |
| Import | Kaggle import under `/api/v1/import/kaggle` |
| Calibration programs | Create/list, add members, activate, and enroll |
| Calibration enrollments | List/get, mapping, skin-plan lock, reveal, and checkpoints |
| Calibration presentations | Blind/post-reveal observations, stage lock, and skin planning |
| Shared history | `/api/v1/calibration/history/{reviewer_id}` |
| Predictions | Create, link outcome, and list under `/api/v1/predictions` (manager-gated) |

The unversioned compatibility routes are legacy surfaces and must be inventoried before removal.
P2 adds versioned recommendation measurement routes. All route changes update generated OpenAPI in
the same pull request.

### Calibration enrollment and blind code contract

`POST /api/v1/calibration/programs/{program_id}/enroll` is manager-only and returns `201` with the new enrollment id.
Generated OpenAPI is the field reference; this section records the blind-code rules (ADR-005 owns the protocol).

- `randomization_algorithm`: `system-random-shuffle-v1` (default), `shared-triples-latin-rotation-v1`, or
  `shared-triples-group-blotter-v1` (`SHARED_GROUP` programs only; unused by F1).
- `label_scheme`: `standard` (readable `E01-S1-2` labels; refused with either shared-triples algorithm), `random`
  (independent 8-character hex code per presentation), or `shared`. Unset means `standard` for the independent shuffle
  and `random` for shared-triples sessions. The scheme is a request value only: no column or audit field stores it. What
  persists is `Presentation.shared_blind_code`.
- `label_scheme: "shared"` (added in #243) requires `shared-triples-latin-rotation-v1` and a program whose effective
  reveal policy is `HOUSEHOLD`. Every evaluator then holds one blind code per physical sample, identical across
  evaluators, and each presentation is stored with `shared_blind_code = true`.
- `membership_codes` (membership id to code) is accepted only with `label_scheme: "shared"`. Each code matches
  `^[A-Z0-9-]{1,24}$` and codes are distinct. A program's first shared enrollment must supply a code for every
  membership of the program and no others. Later shared enrollments inherit the codes already recorded by the program's
  earlier enrollments and may omit the map; a supplied map must equal the recorded one.
- Error cases. Schema validation returns `422` for `shared` with another algorithm, `membership_codes` without
  `shared`, duplicate or malformed codes, and `standard` with a shared-triples algorithm. The service returns `422` when
  a first shared enrollment omits `membership_codes` or the map does not cover exactly the program's memberships. It
  returns `409` when the reveal policy is not `HOUSEHOLD`; when a supplied map differs from the recorded codes; when
  earlier enrollments hold non-shared codes, disagree among themselves, give one code to two samples, or do not cover
  the session template; when a supplied code is already an individual presentation's code; and when a program that
  already holds shared codes is enrolled on a shared-triples algorithm without `label_scheme: "shared"`. All of these are decided before any row is
  added.
- Uniqueness. `UNIQUE (session_id, blind_code)` and `UNIQUE (session_id, position)` hold within a session. A partial
  unique index on `blind_code` where `shared_blind_code` is false covers individual codes across the table. Shared codes
  are not compared across programs, so two programs may both use a code such as one atomizer label; nothing looks a
  presentation up by blind code across programs, and a lookup that does must be scoped by program.
- Template provenance. `Enrollment.randomization_seed` stores `rotation=<k>;template=sha256:<digest>`, plus
  `;generated=<seed>` when the server generated the session template (absent when a manager supplied it). It does not
  store a manifest hash.
- Blind-code confirmation. When a transcription client sends `confirmed_blind_code`, a write is refused with `409`
  unless it matches the stored code (compared trimmed and case-insensitively); omitting it skips the check. With shared
  codes the check still catches the wrong sample but cannot tell one evaluator's sheet from another's, so catching a
  sheet entered under the wrong evaluator is procedural in such a program (F1 gate sign-off 19).

### Evaluator login linkage (Proposed, post-F1)

Current contract, verified against the code at `6635413`: a non-manager login acts for an evaluator only if it is listed
in `Enrollment.recorder_usernames`, set at enrollment and not changed by any route afterward. Every listed login has the
same rights (blind view, session start and end, observations, stage locks, skin plan, consent), `Reviewer` has no login
column, and the server records no entry mode and no session owner. `Observation.recorded_by` is stored but is not in the
evidence export, and observation and session writes emit no audit event. Reviewer identity and `recorded_by` stay
independent (see the trust boundary above). Authorization matches the `X-Authentik-Username` header value exactly
and case-sensitively; the forwarded uid and email are read but not used for it, and the backend has no token
verification.

Proposed target, not decided and not part of the F1 instrument: a link from a provider-neutral external identity (an
(issuer, subject) pair, not an Authentik username) to the reviewer it may act for, a
participant role with narrower rights than a recorder, a server-computed entry mode, session ownership with a manager
hand-off, `recorded_by` and entry source in the export, audit events for those writes, and an explicit correction path
in place of silent supersession. Options and trade-offs are in
[PROJECT-PLAN section 11a](PROJECT-PLAN.md#post-f1-follow-up-evaluator-login-linkage-proposed-2026-11-27); the policy
change is the Proposed amendment in
[ADR-008](adr/adr-008-authentication-and-production-boundary.md#proposed-amendment-2026-11-27-linking-logins-to-reviewers).
Reveal, mapping and checkpoints stay manager-only, and any token-based path must verify signatures in the backend and
leave the forwarded-header trust boundary intact. This section changes no current contract.

### Blotter-stage would wear, would buy and event type (Proposed, post-F1)

Current contract, verified against the code at `a2f240c`: `would_wear` and `would_buy` are optional 0 to 10 typed columns
on `Observation` with no stage condition, and the schema, service and evidence export accept and emit them at any stage,
but the blotter form (`blotterGroups`) does not ask them and only the skin form does. `setting_fit` and `season_fit`
(`FitChoice` rows; season options `spring`, `summer`, `fall`, `winter`, `year_round`, `none`, `cannot_judge`) are refused
at the blotter stage by `validate_capture_fields`, which stage-gates season exactly as it does `setting_fit`. A circled
Intensity 0 on the F1 paper sheet means not detected and maps to the existing rule (`detected` false, `intensity` 0,
`liking` empty, `response_status` `not_detected`), so it needs no application change. A pre-reveal write to a locked stage is
refused, observations are append-only, and `v_training_rows` hides an earlier same-stage pre-reveal answer once a later
one that is not invalidated exists. The dataset, preference-history, training-view and checkpoint code read
`would_wear` and `would_buy` by name with no stage, so a blotter value stored today would be read as a skin-stage value.

Proposed, not decided and not part of the F1 instrument (the F1 paper sheet asks these three, and season, at the blotter
stage and the answers stay on paper; whether season is keyed after F1 is open, and v0.5 treats `year_round` as exclusive
where the schema makes only `none` and `cannot_judge` exclusive): a blotter-stage would wear, would buy and event type
(and season, if keyed) that are a distinct measure from the
skin-stage fields, stored and read under stage-qualified names, never pooled with them, with the observation field list,
the blotter stage rules, the export version and the checkpoint target identity changed together. No late-entry path for
a locked stage exists, and none is proposed here. Options and trade-offs are in
[PROJECT-PLAN section 11a](PROJECT-PLAN.md#post-f1-follow-up-blotter-stage-would-wear-would-buy-and-event-type-capture-proposed-2026-11-27);
the policy change is the Proposed amendment in
[ADR-005](adr/adr-005-controlled-calibration.md#2026-11-27-proposed-amendment-blotter-stage-would-wear-would-buy-and-event-type)
and [ADR-009](adr/adr-009-prospective-evaluation-and-checkpoints.md#2026-11-27-proposed-amendment-blotter-stage-wear-and-buy-are-a-separate-measure).
This section changes no current contract.

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
- Enforcement (R8 PR 2, architecture review D-08/Q14): on PostgreSQL, `BEFORE` triggers refuse an
  update or delete of a controlled observation (except its `training_eligibility`), a checkpoint, its
  typed predictions, a feature snapshot, a prediction snapshot (except setting its outcome link once),
  any membership of an active program, and the identity columns of a fragrance a membership
  references. Programs and source snapshots remain service-enforced only. SQLite (unit tests only)
  has no triggers.
- Time (D-16/Q16): timestamps are naive UTC; server defaults are `timezone('utc', now())`, and the
  API refuses to start when the PostgreSQL session `TimeZone` is not UTC (`ConfigurationError`).
- Training input (X-05/X-06): trainers and checkpoint manifests read `v_training_rows` only; the
  role, repeat, and blind linkage it omits is readable only through the manager-only
  `GET /api/v1/calibration/enrollments/{id}/linkage` (backed by `v_manager_linkage`).

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

Release verification uses Python 3.12 and PostgreSQL 16. This is a self-hosted, personal-use
application, not a published package, and `requires-python = "==3.12.*"` pins the only Python
version this project builds, tests, or deploys against. `.github/workflows/python-compatibility.yml`,
which ran the suite across a matrix of Python versions, was retired in R1 (architecture review
G-06/Q9) because that multi-version signal never matched a real support commitment; there is no
other supported Python version for a multi-version gate to protect. CI and release verification
both gate on Python 3.12 alone.

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
- [Data Model Gap Analysis](data-model-gap-analysis.md)
