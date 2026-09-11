# ADR-007: Preference Evidence and Score Semantics

> **Status**: Accepted
>
> **Date**: 2026-09-11

## Context

The system holds repeated ordinary 1–5 encounters and controlled 0–10 liking observations.
Counting every record equally would overweight frequently repeated versions. Converting raw
history into one blended table would also erase provenance and make later models difficult to
audit.

The original plan called a sigmoid-transformed affinity percentage “accuracy,” although it is
not a calibrated probability or predicted rating.

## Decision

Preserve every observation on its original scale and select model contributions independently.
For the `affinity-v1` adapter:

- use the latest live ordinary encounter per reviewer/version;
- use the latest eligible controlled observation, preferring skin to blotter;
- map controlled liking with `(liking - 5) / 2.5`;
- average ordinary and controlled affinity when both are eligible;
- limit each fragrance version to one contribution;
- exclude holdouts, hidden repeats, and post-reveal responses from baseline training;
- incorporate controlled evidence into ordinary summaries only after reveal.

Continue the deterministic note/accord/family weighted score and veto as an interpretable
ranking baseline. Label the 0–100 display value “affinity score.” Do not label it probability,
confidence, predicted liking, or accuracy.

Measure recommendation interest, sampling, post-sample liking, would-wear, and would-buy as
separate events and outcomes.

## Consequences

- Storage history and model policy can evolve independently.
- Frequent re-rating does not automatically increase a version's influence.
- The first adapter is intentionally heuristic and does not establish statistical calibration.
- New aggregation or calibration policies require a versioned adapter and prospective comparison.

## Validation

- Tests cover latest-encounter selection, scale boundaries, ordinary/controlled combination,
  non-detection, reveal state, holdout exclusion, and one contribution per version.
- UI and API schemas identify score type.
- P2 reports response coverage and denominators with interest rates.
- D5 freezes predictions before holdout outcomes and reports uncertainty.

## Supersedes

This ADR supersedes ADR-004 where ADR-004 says every evaluation contributes cumulatively or treats
the resulting display percentage as predictive accuracy. ADR-004 remains the decision for
deterministic weighted affinity and veto scoring.

## Related

- [ADR-004](adr-004-recommendation-algorithm.md)
- [ADR-005](adr-005-controlled-calibration.md)
- [ADR-009](adr-009-prospective-evaluation-and-checkpoints.md)
