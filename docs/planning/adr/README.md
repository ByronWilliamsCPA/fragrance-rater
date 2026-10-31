---
title: "Architecture Decision Records"
schema_type: planning
status: published
owner: core-maintainer
purpose: "Index and documentation for Architecture Decision Records."
tags:
  - planning
  - architecture
  - decisions
---

This directory contains Architecture Decision Records (ADRs) for Fragrance Rater.

## What Are ADRs?

ADRs document significant architectural decisions along with their context and consequences. They help:

- Prevent architectural drift during AI-assisted development
- Provide rationale for technical choices
- Enable future developers to understand why decisions were made
- Maintain consistency across coding sessions

## ADR Index

| ADR | Title | Status | Date |
| --- | ----- | ------ | ---- |
| [ADR-001](./adr-001-initial-architecture.md) | Initial Architecture - Docker Compose Monolith | Accepted | 2025-12-28 |
| [ADR-002](./adr-002-data-source-strategy.md) | Data Source Strategy - Tiered Acquisition | Amended by ADR-006, ADR-012 | 2025-12-28 |
| [ADR-003](./adr-003-llm-integration.md) | LLM Integration - OpenRouter for Recommendations | Accepted | 2025-12-28 |
| [ADR-004](./adr-004-recommendation-algorithm.md) | V1 Recommendation Scoring Algorithm | Partially superseded by ADR-007; extended by 2026-09-15 amendment; scoring corrected by 2026-09-19 amendment (affinity-v2); `provider_term_mapping` target to be further generalized by ADR-017 (Proposed, 2026-09-24) | 2025-12-28 |
| [ADR-005](./adr-005-controlled-calibration.md) | Controlled Calibration and Disclosure State | Accepted; amended 2026-09-19 (protocol research reconciliation) and 2026-09-21 (exposure cardinality and would_buy permanence) | 2026-09-11 |
| [ADR-006](./adr-006-version-identity-and-source-provenance.md) | Version Identity, Source Provenance, and Vocabulary | Accepted | 2026-09-11 |
| [ADR-007](./adr-007-preference-evidence-and-score-semantics.md) | Preference Evidence and Score Semantics | Accepted | 2026-09-11 |
| [ADR-008](./adr-008-authentication-and-production-boundary.md) | Authentication and Production Trust Boundary | Accepted | 2026-09-11 |
| [ADR-009](./adr-009-prospective-evaluation-and-checkpoints.md) | Prospective Evaluation and Frozen Checkpoints | Accepted; amended 2026-09-19 (declared learning problem; repeat-benchmark terminology) and 2026-09-21 (mapping-holder evaluator excluded from training, retained in evaluation; `would_buy` as a post-reveal outcome), both confirmed by the product owner 2026-09-26 | 2026-09-11 |
| [ADR-010](./adr-010-preference-learning-and-scenario-data-model.md) | Preference-Learning and Scenario Data Model | Partially implemented (approved by product owner for the ML-testing slice); the scenario/pairwise/behavioral-event portions remain Proposed; amended by ADR-017 (2026-09-24) | 2026-09-12 |
| [ADR-011](./adr-011-worn-by-evidence-dimension.md) | Worn-By Evidence Dimension | Accepted | 2026-09-12 |
| [ADR-012](./adr-012-data-source-compliance-and-manufacturer-provenance.md) | Data Source Compliance - Parfumo Deprecation and Manufacturer Provenance | Accepted; amends ADR-002; `SourceSnapshot` provenance specified by the 2026-09-15 amendment is partially implemented: the schema columns have landed and the Parfumo write path now fails closed, but the amendment's listed follow-ups remain open; vendor-licensed data added as a source tier by the 2026-09-21 amendment | 2026-09-15 |
| [ADR-013](./adr-013-external-ontology-and-standards-crosswalk.md) | External Ontology and Standards Crosswalk | Accepted; amends ADR-004, ADR-010; amended by ADR-017 (2026-09-24) | 2026-09-15 |
| [ADR-014](./adr-014-frontend-e2e-and-accessibility-strategy.md) | Frontend E2E and Accessibility Testing Strategy | Accepted; amended 2026-09-19 to WCAG 2.2 AA | 2026-09-18 |
| [ADR-014](./adr-014-training-eligibility-and-unclassified-family.md) | Training Eligibility and the Unclassified Family Sentinel ⚠️ **duplicate number** | Proposed | 2026-09-19 |
| [ADR-016](./adr-016-per-dimension-preference-capture.md) | Per-Dimension Preference Capture and Perfumer as an Evaluable Dimension | Proposed, requires maintainer decision, not implemented; amended 2026-09-21 (permanence for the initial four F1 evaluators) | 2026-09-19 |
| [ADR-017](./adr-017-project-owned-faceted-olfactory-vocabulary.md) | Project-Owned Faceted Olfactory Vocabulary | Proposed; amends ADR-004, ADR-010, ADR-013 | 2026-09-24 |

> ⚠️ **Two records share the number ADR-014.** PR #103 merged
> `adr-014-frontend-e2e-and-accessibility-strategy.md` without adding a row here, so the index
> stopped at ADR-013 and PR #105 took 014 for an unrelated decision. Both are now in `main`.
> Renaming a merged record is the owner's call, not something to do incidentally, so both are
> listed rather than silently reconciled. ADR-016 has since been taken by a later, unrelated
> record (per its own numbering note); ADR-015 remains free, reserved for renumbering the
> training-eligibility record to resolve this clash. The project-owned-vocabulary record above
> could not use either free number without pre-empting that renumbering, so it takes the next
> free number, 017, instead.

## Creating ADRs

When making a new architectural decision:

1. Copy [adr-template.md](adr-template.md) to `adr-NNN-short-description.md` in this directory, using the next
   free number. Do not reuse or renumber an existing number (see the ADR-014 note above).
2. Fill in the sections, set the status to `Proposed`, and open a pull request.
3. Once the maintainer accepts it, change the status to `Accepted` and add a row to the index above in the same
   pull request.

Run `/plan <project description>` to generate initial ADRs alongside other planning documents.

## Naming Convention

ADRs follow this naming pattern:

```text
adr-NNN-short-description.md

Examples:
- adr-001-initial-architecture.md
- adr-008-authentication-and-production-boundary.md
```

## When to Create an ADR

Create an ADR when:

- Choosing technology stack or framework
- Deciding on architectural patterns
- Selecting third-party services or libraries
- Making security or performance trade-offs
- Any decision that would be expensive to reverse

## ADR Lifecycle

```text
Proposed → Accepted → [Deprecated | Superseded]
```

- **Proposed**: Under discussion
- **Accepted**: Decision made and in use
- **Deprecated**: No longer relevant; add a notice at the top and name the replacement if there is one
- **Superseded**: Replaced by another ADR; add a notice at the top that links the new record, and have the new
  record cite the old one under its alternatives

When a later ADR changes an accepted decision, update both records and this index so readers can follow the
supersession chain. Prefer a dated amendment note on the old record over rewriting its history.

## Best Practices

- Make decisions explicit, even when they seem obvious, and include the trade-offs and the alternatives rejected.
- Be concise and use examples or diagrams where they help.
- Document how the decision was actually implemented, and keep the record in step with the repository.
- Link ADRs with a relative path, for example `[ADR-008](adr-008-authentication-and-production-boundary.md)`.

## Template Reference

See the [ADR template](adr-template.md) for the full template structure. The template and the generic ADR
guide used to live in a second, separate ADR directory; R14 PR 3a merged both here so there is one location.
