---
title: "Roadmap"
schema_type: common
status: published
owner: core-maintainer
purpose: "Summarize the active Fragrance Rater delivery milestones."
tags:
  - project_management
  - roadmap
---

The [authoritative project plan](../planning/PROJECT-PLAN.md) owns scope, status, dependencies,
acceptance criteria, risk, and evidence. This page is a short navigation aid.

## Current version

**v0.1.0** is the initial release line. Controlled calibration is merged in `main` but remains
subject to the P1 deployment gate.

## Active sequence

| Milestone | Outcome | Status |
| :--- | :--- | :--- |
| P0 | Reconciled planning baseline | Complete |
| P1 | Calibration deployment, migration, recovery, and security readiness | Repository complete; external evidence pending through P6 |
| P2 | Recommendation impression, feedback, sampling, and outcome measurement foundation | Complete |
| P3 | Role-aware routed product foundation | Planned |
| P4 | Complete participant interface | Planned |
| P5 | Complete manager, reporting, and operations interface | Planned |
| P6 | Deployed synthetic rehearsal and pilot-readiness decision | Planned |
| F1 | Initial family pilot with actual perfumes | Planned after P6 |
| D1 | Versioned source, alias, and taxonomy foundation | Planned |
| D2 | Reproducible catalog statistics | Planned |
| D3 | Disclosure-safe post-reveal exploration | Planned |
| D4 | Candidate discovery pilot | Planned |
| D5 | Prospective comparison and strategy decision | Planned |

Actual pilot perfume testing cannot begin until P6 is complete. D1 cannot begin until F1 is
complete with a proceed-to-D1 decision. P1 evidence proceeds in parallel, while the product
sequence is P2 → P3 → P4 → P5; both paths join at P6.

## Planning documents

- [Project Vision](../planning/project-vision.md)
- [Authoritative Project Plan](../planning/PROJECT-PLAN.md)
- [Technical Specification](../planning/tech-spec.md)
- [Execution Roadmap](../planning/roadmap.md)
- [Architecture Decisions](../planning/adr/README.md)
