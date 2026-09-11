# Fragrance Rater Planning

This directory contains the governing documents for Fragrance Rater.

## Document authority

| Document | Purpose |
| :--- | :--- |
| [Project Vision](project-vision.md) | Defines the problem, outcomes, scope, principles, and success measures |
| [Authoritative Project Plan](PROJECT-PLAN.md) | Owns sequence, status, acceptance criteria, risks, audit disposition, and evidence |
| [Technical Specification](tech-spec.md) | Defines current and target architecture contracts and invariants |
| [Execution Roadmap](roadmap.md) | Provides a compact mirror of project-plan milestones |
| [ADR Index](adr/README.md) | Records durable architectural and policy decisions |
| [Controlled Calibration V1](../calibration-v1.md) | Defines the implemented controlled workflow and its deployment constraints |

When documents disagree, stop implementation and reconcile them. Code demonstrates current
behavior but does not silently supersede an accepted ADR.

## Current sequence

```text
P0 Planning baseline
 → P1 Calibration release readiness
 → P2 Recommendation outcome measurement
 → D1 Source and vocabulary foundation
 → D2 Reproducible catalog statistics
 → D3 Post-reveal exploration
 → D4 Candidate discovery pilot
 → D5 Prospective evaluation
```

D3 and D4 may overlap after D2. D1 cannot begin until P0, P1, and P2 are complete.

## Current architecture

The application is a self-hosted React, FastAPI, and PostgreSQL stack. It preserves repeated
ordinary encounters, supports controlled blind blotter and skin evaluation, generates
deterministic affinity recommendations, optionally explains them with OpenRouter, and retains
source/checkpoint provenance.

Production uses Authentik forward-auth through Traefik. Core workflows must continue without
external metadata or LLM services.

## Planning rules

- Every work package has an owner, dependency, measurable acceptance criteria, and evidence
  location.
- Product interest, actual sampling, liking, wear, and buy outcomes are measured separately.
- Affinity scores are not described as probabilities or calibrated predictions.
- Raw source labels, evaluator perception, and model interpretation remain separate.
- Exact concentration/version identity, blind disclosure, holdout exclusion, and frozen
  checkpoints are release-blocking invariants.
- External assets require recorded source, revision, hash, and reuse rights before adoption.
- PostgreSQL-specific behavior is tested in PostgreSQL.

## Historical material

The original five-phase plan and concept document describe how the project began. They are
historical references and must not be used to schedule current work. The authoritative plan's
current-state ledger replaces their task checkboxes.
