---
title: "Controlled calibration V1"
schema_type: common
status: published
owner: core-maintainer
purpose: "Define the controlled calibration workflow, data policy, and deployment constraints."
tags:
  - development
  - architecture
---

**Implementation state:** Merged in `main` at commit `0d85747`; target PostgreSQL,
backup/restore, concurrency, and production proxy validation remain the P1 release gate in the
[authoritative project plan](planning/PROJECT-PLAN.md#6-milestone-p1-calibration-release-readiness).

Ordinary ratings and controlled measurements share existing reviewer and fragrance IDs.
The catalog row is the canonical version in this release. Its version key, concentration,
name and brand distinguish versions; identity fields become immutable once assigned to a
program. Parent house/product tables and physical inventory management remain follow-up
work rather than a second catalog.

## Product decisions

- Every ordinary POST creates a dated encounter, retaining earlier ratings on the existing
  1–5 scale. Existing PATCH corrects one encounter; DELETE soft-deletes one encounter.
  Optional `evaluated_at` accepts an offset or UTC. Original IDs and dates are preserved.
- For each evaluator, baseline identities stay hidden until all non-holdout blotter stages,
  repeats, and planned skin stages are locked and the skin plan is explicitly finalized.
  An intentionally empty skin plan can be finalized. Post-reveal responses append records.
- Holdout identities remain hidden until their own blotter stage is locked. Their ratings
  remain excluded from training across ordinary and controlled workflows. V1 intentionally
  has no release-to-training switch.
- A holdout sample is closed until a checkpoint exists for its enrollment: the server refuses
  its exposure, observations, stage locks, a session start, and a session ranking with a 409
  that does not name the role, and the participant payload marks it `available: false`.
  Programs without holdouts are unaffected.
- A program's `reveal_policy` is `ENROLLMENT` (the default, per-evaluator reveal as above) or
  `HOUSEHOLD`, chosen while the program is a draft. A `HOUSEHOLD` program refuses the
  per-evaluator reveal; a manager reveals every enrollment together, atomically, once each one
  has its baseline locked, its skin plan finalized, a checkpoint, and its holdout stages locked.
  `reveal_blocker` then adds `CHECKPOINT`, `HOLDOUT`, and `HOUSEHOLD_WAIT` (this evaluator is
  done, another is not). A revealed household takes no new enrollments.
- Already revealed versions encountered in another program are marked PREVIOUSLY_REVEALED;
  they are not silently treated as naive training observations.

## Configuration and workflow

Set `CALIBRATION_ADMIN_USERNAMES` to a JSON array of verified Authentik usernames, for example
`["experiment-manager"]`. Empty is the secure default. Existing Authentik/Traefik forward-auth
remains the trust boundary: do not expose the backend directly. Local calibration requests
also need a named recorder header; no anonymous manager bypass exists.

Use Program setup to create a draft, add exact catalog version IDs with verification evidence,
link hidden repeats to their baseline membership IDs, activate the definition, and enroll
reviewers with explicit recorder usernames. Membership additionally accepts an optional `gtin`
(the physical bottle's barcode): when the fragrance's own recorded source evidence (e.g. a
Parfumo scrape) already carries a `gtin`, a conflicting entered value is rejected outright rather
than stored alongside the disagreement - see `fragrance_rater.utils.gtin` and
`CalibrationService._check_gtin_against_source_evidence`. A barcode match is stronger identity
evidence than any text-based source comparison; its absence is not itself a problem, since many
sources never publish one. One recorder can record for several evaluators.
Program activation freezes membership; enrollment independently randomizes presentation order
per evaluator (the default) and assigns blind labels under one of three schemes chosen at enrollment
(`label_scheme`):

- `standard` (default): `E{enrollment}-S{session}-{position}`, for example `E01-S1-2`. Labels are
  readable and quick to write on vials. Order is still randomized per evaluator, so a label
  carries no identity signal. It does reveal session grouping, which the participant already sees.
  Session numbers also run baseline first and holdout last, so the `S` number discloses whether a
  session is baseline or holdout. Only identities are blinded, never that partition. This is an
  accepted trade-off for the default (decision recorded 2026-10-30); use `random` for any trial
  where that partition must stay hidden.
- `random`: an independent 8-character hex code per presentation, with no structure at all.
  Facilitated F1 programs (below) must use this scheme or `shared`, not `standard`.
- `shared` (added in #243, shared-triples only): one blind code per physical sample, the same for every evaluator, such
  as an atomizer label. It needs a program whose reveal policy is `HOUSEHOLD`, because one evaluator's own reveal would
  unblind the others. A program's first shared enrollment supplies the code for every sample (`membership_codes`, API
  only); later enrollments inherit those codes. The contract and its refusals are in the
  [technical specification](planning/tech-spec.md#calibration-enrollment-and-blind-code-contract).

**Facilitated format (F1, decided 2026-11-24).** Independent per-evaluator shuffles remain the default
for every program. The six-evaluator facilitated F1 format instead uses shared triples: all evaluators
smell the same three fragrances in the same session, and the order inside each session is rotated per
evaluator (a per-session rotation through a balanced Latin square), so no fragrance is always first. Each
evaluator's actual order is persisted per presentation. Holdouts remain a separate final block, hidden repeats are the
same program-level set for every evaluator, and blind codes are random and evaluator-specific. The
`standard` scheme must not be used here: with shared triples its `S` number identifies the session
for every evaluator and so discloses holdout status to all of them. Skin tests are not part of
facilitated sessions, and identities are revealed once for the whole program after all holdouts are
locked. The protocol rationale is in the
[ADR-005 2026-11-24 amendment](planning/adr/adr-005-controlled-calibration.md#2026-11-24-amendment-six-evaluator-facilitated-f1-format).
**Individual blotters (F1, 2026-11-25).** F1 uses one blotter per evaluator per sample: each evaluator has their own
coded blotters and sprays their own, the mapping holder helps the other five keep blotters, trays and sheets organized
and does not evaluate in those sessions, and the holder's own evaluations run separately. Blind codes are
evaluator-specific and the Latin-square rotation above applies. The ceiling from an evaluator's own spray to that
evaluator's own first smell is 2 minutes (provisional, tested in P6.3), with a fresh blotter of the same sample when
that evaluator's window passes unsmelled. The 2 minute clean-air interval between samples is a different number and is
unchanged. A group blotter mode (one blotter per sample passed round the six evaluators) was decided and built earlier
the same day, tried physically, and abandoned because it got two evaluators through in two minutes; its code is merged
and unused. See the
[ADR-005 2026-11-25 addendum](planning/adr/adr-005-controlled-calibration.md#2026-11-25-addendum-group-blotter-mode-abandoned-for-f1-individual-blotters-return).

**Shared codes in the F1 program (2026-11-27).** The statements above that blind codes are random and
evaluator-specific describe what enrollment generates. For the F1 program (`v3.2`) the owner decided on 2026-11-27 that
all six evaluators see one shared code per physical sample, equal to the label on the atomizer, with repeats keeping
distinct codes. The stored codes were replaced in production by a reviewed one-off data update, with no code change,
build or deploy (no label scheme is stored; the stored marker is `shared_blind_code`). The `shared` scheme above (#243)
later made that shape enrollable in code; it is merged and not recorded as deployed. The consequence for the workflow
is that the server's blind-code check can no longer tell one evaluator's sheet from another's in that program, so the
wrong-evaluator check is procedural (one recorder, one evaluator's sheets at a time). The decision, the accepted
consequences and what remains owed are in the [F1 gate sign-off 19](planning/gates/f1.md); the protocol note is in the
[ADR-005 2026-11-27 note](planning/adr/adr-005-controlled-calibration.md#2026-11-27-note-shared-blind-codes-equal-to-the-atomizer-label-in-the-f1-program).

Enrollment support for shared triples, the household reveal and the holdout gate are work items in the
[project plan](planning/PROJECT-PLAN.md#f1-facilitated-format-work-items-decided-2026-11-24), which records which have
merged (shared triples, the household reveal, the holdout gate and `label_scheme: "shared"` all have); the independent
per-evaluator shuffle and the per-enrollment reveal remain the defaults.

Repeats are interleaved with baseline stimuli with separation where the number of stimuli
permits it. Small diagnostic/test definitions may have insufficient stimuli for the usual
separation; this is not a general experimental-design optimizer.

Managers retrieve `/api/v1/calibration/enrollments/{id}/mapping` to label physical samples.
This route exposes the mapping and is restricted to managers. Participant routes never return
fragrance IDs, experimental roles, repeat links, or selection evidence before reveal. Skin
selection reasons are not returned to participants, because they may contain identity clues.
A manager who is also an evaluator can know the mapping; software cannot undo that exposure.

The Calibration screen captures blotter and elapsed skin observations, independent 0–5
perceptual dimensions, 0–10 liking/wear/buy/appreciation, perceived notes and free text.
Unanswered values are NULL; answered zero remains zero. Non-detection requires intensity zero
and liking NULL. Submitted responses are append-only; stage locks stop additional blind
responses. V1 has no blind-response correction endpoint: a future correction workflow must
preserve revisions, authorship and reasons.

The current 43-fragrance/49-presentation baseline is not seeded: its complete version-resolved
manifest was not present in the repository. Add the verified list through program setup/API;
no catalog identities were guessed from fragrance names. Sample counts and session sizes are
not hard-coded.

## Shared history and modeling

`/api/v1/calibration/history/{reviewer_id}` returns every ordinary encounter and accessible
controlled observation with its workflow and scale; it reuses the participant disclosure policy.
`PreferenceHistoryService` centralizes holdout exclusions and creates frozen training manifests.

The ordinary recommendation model uses the latest live ordinary encounter per version, so
frequent re-rating does not overweight a fragrance. Locked controlled responses are usable in
experimental manifests before reveal, but ordinary recommendation summaries incorporate them
only after reveal, avoiding premature source-feature disclosure. Hidden repeats and post-reveal
responses are excluded from baseline training. A later non-detection does not resurrect an
older liking score at the same presentation/stage.

The first recommendation adapter prefers skin to blotter, takes the latest eligible selected
observation, converts 0–10 liking to -2..2 affinity using `(liking - 5) / 2.5`, and averages that
with the latest ordinary affinity when both exist. This explicit conversion, defined by `affinity-v1`
and inherited unchanged by the default `affinity-v2` (ADR-004 2026-09-19 amendment), preserves
raw scales and limits each version to one contribution. It is not a statistically calibrated
liking predictor or confidence estimate.

Manager checkpoint endpoints store algorithm version, timestamp, exact input values and source
feature snapshots, and supplied predictions. Prospective checkpoint creation closes once that
enrollment has any holdout response; on a `HOUSEHOLD` program it also waits for the blind
baseline (skin plan, blotters, planned skin stages). `GET /programs/{id}/readiness` reports each
enrollment's `checkpoint_blocker` and `reveal_blocker`, and `POST /programs/{id}/checkpoints`
freezes a checkpoint for every ready enrollment that has none, with one prospective prediction per
program holdout from a registered model, in one transaction. Results can be retrieved without
reconstructing mutated source data. Automatic checkpoint scheduling, calibrated predictions, active learning, reliability
statistics and validation dashboards remain follow-up work. Selection metadata and generic groups
are stored now, but no active-learning algorithm is claimed.

## Source metadata

Parfumo imports resolve existing records by source URL, preserve an exact display title when
available, stop defaulting unknown concentration to EDP, and preserve flat notes separately from
heart notes. Source snapshots append parsed evidence with retrieval timestamp and unverified
status. Multiple perfumers are persisted through a version link table. Source refresh does not
rewrite evaluator responses or assigned version identity.

The parser still needs live fixtures for all requested community metrics, production status,
related versions and similar fragrances. Missing metrics are not fabricated. Historical imported
EDP concentrations are not retrospectively certified; assignment requires explicit verification
of the actual version. Source snapshots are not a claim that every Parfumo field is now parsed.

## Migration and rollback

The new Alembic revision is `c731b42e9a01`, following `b954e9888344`. It drops ordinary-rating
uniqueness, widens version uniqueness, adds the version key with a legacy default, and creates
controlled/source tables. It does not delete or rewrite existing ratings.

Back up the production database and confirm its current Alembic revision before deployment.
The old `88627796b194` migration has a safety amendment removing destructive deduplication.
Older databases with duplicate rows now stop at the legacy unique constraint instead of losing
history. Such databases need a preservation-aware reconciliation/upgrade procedure before they
can advance. Do not delete encounters or stamp past migrations merely to make that step pass.
Databases that already ran the destructive historical migration need an older backup to recover
previously deleted records.

Downgrade deliberately refuses a lossy collapse of encounter history or removal of experimental
records. Restore a verified pre-upgrade backup when rollback is necessary. No deployed database
was accessed or migrated during this implementation.

## Verification

Tests cover repeated encounter retention, canonical version coexistence, immutable assigned
identity, controlled capture/locking/reveal, recorder/manager access, source preservation, holdout
exclusion and frozen manifests. The additive migration is exercised against populated SQLite
previous-head tables; PostgreSQL upgrade SQL is compiled through Alembic. A live PostgreSQL
migration/concurrency gate must still run before deployment: the local environment cannot start
PostgreSQL under a non-root system account. Frontend build, lint and participant workflow tests
are included. CI should use the committed frontend lockfile.
