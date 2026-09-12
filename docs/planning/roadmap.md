# Fragrance Rater Execution Roadmap

> **Status**: Active mirror | **Updated**: 2026-09-11

The [Authoritative Project Plan](PROJECT-PLAN.md) owns scope, status, acceptance criteria,
risks, and evidence. This page is a compact execution view and must be updated from that plan in
the same pull request.

## Milestones

| Milestone | Outcome | Status | Entry gate | Exit gate |
| :--- | :--- | :--- | :--- | :--- |
| P0 | Reconciled planning baseline | Complete | Calibration merged | Governing documents agree and later gates are implementation-ready |
| P1 | Calibration release readiness | Repository controls complete; external evidence pending through P6 | P0 complete | Target PostgreSQL, recovery, proxy, disclosure, operations, and target-UI evidence reviewed |
| P2 | Recommendation measurement foundation | Complete | P0 complete | Impressions, feedback, sampling, outcomes, events, and provenance-complete metrics implemented |
| P3 | Product UX foundation | Complete | P0 and P2 complete | Routed shell and accessibility baseline accepted |
| P4 | Participant experience | Complete | P3 complete | Participant workflows require no IDs or API tools |
| P5 | Manager and operations experience | Review pending | P4 complete | Setup, mapping, enrollment, progress, reveal, reporting, and operational workflows usable through UI |
| P6 | Integrated pilot readiness | Planned | P1 controls, P2, and P5 complete | P1 evidence, deployed device matrix, synthetic rehearsal, operations drill, and `go` decision accepted |
| F1 | Initial family perfume pilot | Planned | P6 complete | Real-use evidence reviewed and a proceed-to-D1 decision recorded; revise/extend/stop leaves F1 open |
| D1 | Source and vocabulary foundation | Planned | F1 complete | Authorized snapshots and versioned alias/taxonomy mappings accepted |
| D2 | Reproducible catalog statistics | Planned | D1 complete | Deterministic statistics artifact and denominator tests accepted |
| D3 | Post-reveal exploration | Planned | D2 and P1 complete | Accessible, disclosure-safe evidence-layer profiles accepted |
| D4 | Candidate discovery pilot | Planned | D2 and F1 complete | Versioned candidates, availability, provenance, and diversity accepted |
| D5 | Prospective evaluation | Planned | D4, P2, and F1 complete | Frozen comparison results and adopt/revise/stop decision recorded |

## Dependency path

```text
P0 ┬→ P1 ----------------------------------------------┐
   └→ P2 → P3 → P4 → P5 ------------------------------┤
                                                       └→ P6 → F1 → D1 → D2 ┬→ D3
                                                                              └→ D4 → D5
```

## Immediate queue

1. Review and merge the P5 manager, reporting, and operations workflows implemented with synthetic data.
2. Continue non-UI P1 evidence: physical manifest, authorized fixtures, backup clone, migration,
   concurrency, and recovery.
3. Run P6 on the final deployed UI and close all remaining P1 evidence.
4. Begin F1 with actual pilot perfumes only after the P6 go decision.

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
- No actual pilot perfume testing begins before P6 is complete.
- D1 cannot begin until F1 is complete.

## Related documents

- [Project Vision](project-vision.md)
- [Technical Specification](tech-spec.md)
- [ADR Index](adr/README.md)
- [Controlled Calibration V1](../calibration-v1.md)
- [Data Model Gap Analysis](data-model-gap-analysis.md)
