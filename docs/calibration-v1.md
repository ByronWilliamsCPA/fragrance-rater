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
Program activation freezes membership; enrollment independently randomizes codes and order.
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
with the latest ordinary affinity when both exist. This explicit `affinity-v1` heuristic preserves
raw scales and limits each version to one contribution. It is not a statistically calibrated
liking predictor or confidence estimate.

Manager checkpoint endpoints store algorithm version, timestamp, exact input values and source
feature snapshots, and supplied predictions. Prospective checkpoint creation closes once that
enrollment has any holdout response. Results can be retrieved without reconstructing mutated
source data. Automatic checkpoint scheduling, calibrated predictions, active learning, reliability
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
