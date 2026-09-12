---
title: "P5 Manager Authorization, Disclosure, and Cache Matrix"
schema_type: common
status: published
owner: core-maintainer
purpose: "Retained evidence that manager workflows disclose controlled data only to authorized identities."
tags:
  - planning
  - security
  - frontend
---

This matrix covers the manager surfaces used to prepare and operate the synthetic pilot. FastAPI
authorization remains the enforcement boundary; hidden navigation and human-readable controls are
usability measures.

| Surface | Manager result | Recorder/participant result | Cache and disclosure control | Evidence |
| :--- | :--- | :--- | :--- | :--- |
| Program membership | Exact version, role, repeat, group, and verification evidence | `403` | `private, no-store`; identity header in `Vary` | Calibration API lifecycle test |
| Enrollment list | All enrollments with names, progress, blockers, and recorder grants | Manager overview is `403`; shared participant list returns assigned rows only | Every identity-dependent list is `private, no-store`; identity header in `Vary` | Calibration API lifecycle test |
| Mapping and labels | Blind code to exact version and experimental role | `403`; mapping is absent from participant payloads | `private, no-store`; labels render only on the manager route | API authorization and frontend manager workflow tests |
| Checkpoints and metrics | Frozen model evidence and explicit metric contract | `403` | `private, no-store`; exported JSON is initiated by an authorized manager from the current response | Measurement API test |
| Operational events/status | Recent failures, recoveries, and affected evaluator names | Non-manager reads are `403`; assigned recorders can only append reviewer-scoped events | `private, no-store`; status contains operational guidance without hostnames, credentials, or exception text | Failure/recovery API test |
| Participant requests a cached manager URL | Server reauthorizes the request; no manager response is cacheable | Participant receives their policy-scoped response or `403` | `Cache-Control: private, no-store` prevents browser and intermediary reuse; `Vary` is defense in depth | Header assertions on participant and manager requests |
| Manager page or direct URL | Page loads only after verified manager capability | Direct `/programs` navigation redirects to participant calibration | API remains authoritative if client controls are bypassed | Frontend route/access tests |
| Error response | Actionable validation or authorization message | No mapping, version identity, secret, or infrastructure detail | Shared middleware applies the same private, no-store and identity-varying policy to authorized and denied reads; operational status uses fixed guidance | API lifecycle and UI retry tests |

Manager responses do not differ between configured manager identities, so manager-to-manager cache
partitioning is not required. The no-store policy is still applied consistently to reduce retained
controlled data on shared family devices.

The [synthetic manager-workspace capture](p5-manager-workspace.png) records the rendered manager
surface used for layout review. Its evaluator, program, and fragrance names are fixtures.
