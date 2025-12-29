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
| [ADR-002](./adr-002-data-source-strategy.md) | Data Source Strategy - Tiered Acquisition | Accepted | 2025-12-28 |
| [ADR-003](./adr-003-llm-integration.md) | LLM Integration - OpenRouter for Recommendations | Accepted | 2025-12-28 |
| [ADR-004](./adr-004-recommendation-algorithm.md) | V1 Recommendation Scoring Algorithm | Accepted | 2025-12-28 |

## Creating ADRs

### Automatic Generation

Run `/plan <project description>` to generate initial ADRs alongside other planning documents.

### Manual Creation

When making a new architectural decision:

```text
Create an ADR for [decision topic].
Use template: .claude/skills/project-planning/templates/adr-template.md
Save to: docs/planning/adr/adr-NNN-[decision-slug].md
```

## Naming Convention

ADRs follow this naming pattern:

```text
adr-NNN-short-description.md

Examples:
- adr-001-database-choice.md
- adr-002-auth-strategy.md
- adr-003-api-design.md
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
- **Deprecated**: No longer relevant
- **Superseded**: Replaced by another ADR

## Template Reference

See `.claude/skills/project-planning/templates/adr-template.md` for the full template structure.

## More Information

For additional guidance on creating and maintaining ADRs, refer to the Claude Code skills documentation in `.claude/skills/project-planning/`.
