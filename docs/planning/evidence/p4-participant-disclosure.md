---
title: "P4 Participant Disclosure Matrix"
schema_type: common
status: published
owner: core-maintainer
purpose: "Record participant-visible fields and concealment controls for the P4 gate."
tags:
  - planning
  - security
  - frontend
---

This matrix applies before the F1 family pilot. Verification uses synthetic records. The
`manager` value on the access endpoint is an application capability; “role” below means an
experimental membership role such as holdout or hidden repeat.

| Surface | Participant-visible data | Concealed data and control | Evidence |
| :--- | :--- | :--- | :--- |
| Home | Evaluator name, program name, aggregate lock progress, blind code, next action | No membership IDs, fragrance IDs, experimental roles, repeat links, selection evidence, or mappings are rendered | Frontend home test and participant-view API tests |
| Enrollment list | Accessible enrollment, reviewer, and program references needed to open work | Server filters to manager or assigned recorder; no membership records are returned | Calibration authorization tests |
| Enrollment detail before reveal | Blind code, session/position, lock state, skin-planned boolean, participant observations | `participant_view` allowlist omits fragrance identity, membership role, repeat link, selection reason, and mapping | Calibration disclosure tests |
| Enrollment detail after reveal | Exact fragrance identity for eligible presentations | Holdout identity remains concealed until its own blotter stage is locked; role/repeat/selection fields remain absent | Calibration reveal and holdout tests |
| Unified history | Ordinary encounters and accessible controlled observations; controlled identity only when allowed by participant view | No program mapping, membership role, repeat link, or selection reason | History authorization and concealment tests |
| Recommendation run | Ranked candidate identity, score type/value, immutable impression, participant feedback revisions | Holdouts are excluded by the service; no calibration role, repeat, mapping, or selection metadata is returned | Recommendation measurement API tests |
| Participant UI | Names, blind codes, progress, workflow status, and human-readable outcome choices | UUIDs remain request values only and are never printed; manager navigation and setup stay capability-gated | Frontend accessibility, route-denial, home, correction, and follow-up tests |

FastAPI authorization remains authoritative for every request. Frontend capability checks only
control presentation and cannot grant data access.
