# Fragrance Rater Execution Roadmap

> **Status**: Active mirror | **Updated**: 2026-09-11

The [Authoritative Project Plan](PROJECT-PLAN.md) owns scope, status, acceptance criteria,
risks, and evidence. This page is a compact execution view and must be updated from that plan in
the same pull request.

## Milestones

| Milestone | Outcome | Status | Entry gate | Exit gate |
| :--- | :--- | :--- | :--- | :--- |
| P0 | Reconciled planning baseline | Ready for review | Calibration merged | Governing documents agree and P1/P2 are implementation-ready |
| P1 | Calibration release readiness | Planned | P0 complete | Target PostgreSQL, recovery, proxy, disclosure, and operations evidence reviewed |
| P2 | Recommendation outcome measurement | Planned | P1 complete | Impressions, feedback, sampling, outcomes, and baseline metrics usable |
| D1 | Source and vocabulary foundation | Planned | P2 complete | Authorized snapshots and versioned alias/taxonomy mappings accepted |
| D2 | Reproducible catalog statistics | Planned | D1 complete | Deterministic statistics artifact and denominator tests accepted |
| D3 | Post-reveal exploration | Planned | D2 and P1 complete | Accessible, disclosure-safe evidence-layer profiles accepted |
| D4 | Candidate discovery pilot | Planned | D2 and P2 complete | Versioned candidates, availability, provenance, and diversity accepted |
| D5 | Prospective evaluation | Planned | D4 and P2 complete | Frozen comparison results and adopt/revise/stop decision recorded |

## Dependency path

```text
P0 → P1 → P2 → D1 → D2 ┬→ D3
                        └→ D4 → D5
```

## Immediate queue

1. Complete P0 documentation validation and review.
2. Decompose P1.1–P1.10 into sprint issues without weakening release-blocking invariants.
3. Run P1 against an isolated production backup clone and the target proxy topology.
4. Implement and baseline P2 before any D1 source or vocabulary work.

## Delivered historical scope

The former Phase 0–4 plan delivered the backend foundation, catalog and evaluation services,
imports, deterministic recommendations, optional LLM explanations, and the first React and
controlled-calibration workflows. Historical task checkboxes are not maintained because Git and
the [current-state ledger](PROJECT-PLAN.md#3-current-state-ledger) provide the implementation
record.

## Change control

- Status changes require an evidence link in the authoritative plan.
- New scope must belong to a named milestone.
- Durable policy or architecture changes require an ADR.
- D1 cannot begin until P0, P1, and P2 are complete.

## Related documents

- [Project Vision](project-vision.md)
- [Technical Specification](tech-spec.md)
- [ADR Index](adr/README.md)
- [Controlled Calibration V1](../calibration-v1.md)
