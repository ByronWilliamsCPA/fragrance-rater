# ADR-005: Controlled Calibration and Disclosure State

> **Status**: Accepted
>
> **Date**: 2026-09-11

## Context

Ordinary ratings alone cannot distinguish stable preference from context, recognition, order,
or measurement noise. Controlled programs need repeated blind observations and final holdouts
without losing the simpler family journal workflow.

The system must also prevent identity leakage through APIs and derived surfaces while preserving
all original observations.

## Decision

Use one canonical reviewer and fragrance-version catalog for ordinary and controlled workflows.
Controlled programs add immutable activated membership, randomized coded presentations,
append-only observations, stage locks, explicit skin-plan finalization, delayed reveal, and
separate post-reveal observations.

For each evaluator:

- non-holdout identities remain hidden until required blotter/repeat stages and planned skin
  stages are locked and the skin plan is finalized;
- holdout identities remain hidden until their own required stage is locked;
- participant responses never expose membership role, repeat link, selection evidence, or
  fragrance mapping before disclosure policy permits it;
- already known versions are marked previously revealed;
- blind corrections require a future append-only revision workflow.

Disclosure policy is a shared server-side service applied to history, profiles, recommendations,
explanations, caches, errors, exports, and future analytical views.

## Consequences

- Raw controlled evidence remains auditable and usable for prospective evaluation.
- Managers can retrieve physical-sample mappings; a manager who is also an evaluator cannot be
  made blind by software.
- Workflow state and authorization require more integration and end-to-end tests.
- Sample/session counts are data, not hard-coded application constants.

## Validation

- State-transition tests cover activation, enrollment, locking, reveal, and post-reveal append.
- Disclosure-matrix tests cover every direct and derived surface.
- Concurrent lock and observation attempts are exercised on PostgreSQL.
- Exact version evidence is required before program assignment.

## Related

- [ADR-006](adr-006-version-identity-and-source-provenance.md)
- [ADR-007](adr-007-preference-evidence-and-score-semantics.md)
- [ADR-008](adr-008-authentication-and-production-boundary.md)
- [ADR-009](adr-009-prospective-evaluation-and-checkpoints.md)
- [Controlled Calibration V1](../../calibration-v1.md)
