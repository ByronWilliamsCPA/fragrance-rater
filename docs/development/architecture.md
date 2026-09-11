---
title: "Architecture"
schema_type: common
status: published
owner: core-maintainer
purpose: "Orient contributors to the current Fragrance Rater architecture."
tags:
  - development
  - architecture
---

Fragrance Rater is a self-hosted React, FastAPI, and PostgreSQL application. It supports a
personal encounter journal, deterministic recommendations, optional LLM explanations, and
controlled blind calibration programs.

## Components

| Component | Responsibility |
| :--- | :--- |
| React frontend | Ordinary ratings, calibration observations, and manager program setup |
| FastAPI application | API validation, workflow state, authorization, scoring, and imports |
| PostgreSQL | Catalog, ordinary history, controlled observations, source snapshots, checkpoints |
| Traefik and Authentik | Required production request and identity boundary |
| OpenRouter | Optional recommendation explanations |
| Authorized catalog sources | Optional metadata import and refresh |

## Core boundaries

- Canonical fragrance versions are distinct from raw source snapshots.
- Ordinary and controlled observations preserve original scales and provenance.
- Model contribution policy is separate from stored history.
- Blind disclosure policy applies to direct routes and derived surfaces.
- Deterministic scoring works without OpenRouter.
- Production does not expose a backend path that bypasses Authentik/Traefik.

## Governing documents

- [Technical Specification](../planning/tech-spec.md)
- [Authoritative Project Plan](../planning/PROJECT-PLAN.md)
- [Architecture Decision Records](../planning/adr/README.md)
- [Controlled Calibration V1](../calibration-v1.md)

Those documents replace the earlier template-level package sketch.
