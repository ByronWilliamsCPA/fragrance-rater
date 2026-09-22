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
| [Data Model Gap Analysis](data-model-gap-analysis.md) | Reviews the schema against preference-learning, scenario, and future-ML requirements; captured as ADR-010, partially implemented |
| [Architecture and Design Review 2026-09](architecture-review-2026-09.md) | Advisory critical review of design, architecture, and evidence integrity with sequenced remediation workstreams; proposes work, does not change plan status |
| [Repository Inconsistencies Review 2026-09](repo-inconsistencies-review-2026-09.md) | Advisory audit of documentation-vs-documentation and documentation-vs-code inconsistencies across ADRs, planning docs, and CLAUDE.md; proposes work, does not change plan status |
| [User Roles and Workflows Gap Analysis](user-roles-and-workflows-gap-analysis.md) | Advisory product audit of evaluator, recorder, and administrator workflows with tracked findings and candidate remediation; proposes work, does not change plan status |
| [Frontend Visual and Usability Gap Analysis](frontend-visual-and-usability-gap-analysis.md) | Advisory evaluator-centered review of visual direction and desktop/phone usability with prioritized remediation; proposes work, does not change plan status |
| [ML Structure Review 2026-09](ml-structure-review-2026-09.md) | Advisory review of whether data, features, labels, evaluation protocol, and code can produce a successful learned preference model, with ranked structural changes |
| [Preference-Prediction Data Capture Assessment](preference-prediction-data-capture-assessment.md) | Future-data-scientist audit of perfume, evaluator, context, behavior, Fragella, and milestone data requirements for liking, wear, and purchase prediction |
| [Perfume-Purchasing Research Validation](../research/perfume-purchasing-research-validation.md) | Claim-level validation of the two LLM-generated purchasing research reports and the bounded changes they support in the data-capture assessment |
| [ML Decisions 2026-09](ml-decisions-2026-09.md) | Options and recommendations for the eight decisions the ML review requires, with the owner's recorded answers |
| [Product Research Remediation Implementation Plan](product-research-remediation-implementation-plan.md) | Reconciles the roles/workflows, frontend, and ML/data gap-analysis documents with the authoritative plan and Milestone R; specifies concrete schema, API, frontend, and evidence-governance changes with traceable IDs; not yet approved |

When documents disagree, stop implementation and reconcile them. Code demonstrates current
behavior but does not silently supersede an accepted ADR.

## Current sequence

```text
P0 ┬→ P1 Calibration release readiness --------------------------┐
   └→ P2 Measurement foundation → P3 UX → P4 Participant → P5 Manager
                                                                    └→ R1 ┬→ R2
                                                                            └→ R3 ┴→ R4
                                                                                    └→ P6 Pilot readiness
                                                                                        └→ F1 Family pilot
                                                                                            └→ D1 → D2 ┬→ D3
                                                                                                        └→ D4 → D5
```

P1 evidence can proceed alongside P3-P5, but P6 must close P1 against the final deployed UI.
No actual pilot perfume testing begins before P6. D3 and D4 may overlap after D2; D1 cannot
begin until F1 is complete.

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
