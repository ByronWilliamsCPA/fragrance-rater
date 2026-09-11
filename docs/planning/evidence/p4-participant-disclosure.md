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

**Home.** Participants see evaluator and program names, aggregate progress, blind codes, and a safe
next action. The UI does not render membership or fragrance IDs, experimental roles, repeat links,
selection evidence, or mappings. Frontend home and participant-view API tests retain evidence.

**Enrollment list.** Participants see the reviewer and program references needed to open accessible
work. The server filters assignments to managers or assigned recorders and returns no membership
records. Calibration authorization tests retain evidence.

**Enrollment detail before reveal.** Participants see blind codes, session position, lock state,
skin-plan state, observations, and a disclosure-safe reveal blocker. The `participant_view` allowlist
omits fragrance identity, membership roles, repeat links, selection reasons, and mappings.
Calibration disclosure tests retain evidence.

**Enrollment detail after reveal.** Participants see exact fragrance identity only when eligible.
A holdout identity stays concealed until its own blotter stage is locked. Role, repeat, and selection
fields remain absent. Calibration reveal and holdout tests retain evidence.

**Unified history.** Participants see ordinary encounters and accessible controlled observations.
Controlled identity appears only when allowed by the participant view. Program mappings, membership
roles, repeat links, and selection reasons remain absent. History authorization tests retain evidence.

**Recommendation run.** Participants see ranked candidate identity, scoring, immutable impressions,
and feedback revisions. The service excludes holdouts and returns no calibration role, repeat,
mapping, or selection metadata. Recommendation measurement API tests retain evidence.

**Participant UI.** Participants see names, blind codes, progress, workflow status, and readable
outcome choices. UUIDs remain request values and are not printed. Manager setup remains
capability-gated. Frontend accessibility and workflow tests retain evidence.

FastAPI authorization remains authoritative for every request. Frontend capability checks only
control presentation and cannot grant data access.
