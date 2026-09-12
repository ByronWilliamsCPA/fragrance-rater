---
title: "P6 pilot readiness"
schema_type: common
status: published
owner: core-maintainer
purpose: "Run the final authenticated synthetic rehearsal and record the decision before family testing."
tags:
  - deployment
  - validation
  - planning
---

P6 is the hard boundary before F1 uses actual pilot perfumes. Run this procedure against the
release candidate deployed through the target Authentik and Traefik topology. Use unmistakably
synthetic people, samples, observations, and outcomes. Repository and local test results support
the gate but do not replace target-host evidence.

## Evidence handling

Create a private, access-controlled directory outside the repository. Record the release commit,
immutable image digests, operator, UTC start and end times, deployment host, database version,
browser and device versions, and redaction rules. Store screenshots, browser traces, exports,
logs, manifests, backup artifacts, and signed records there.

Files committed to the repository must contain no credentials, session values, personal data,
blind codes, mappings, real observations, source payloads, or infrastructure identifiers. The
templates linked below retain pass/fail summaries and private evidence references only.

## Entry check

Stop before rehearsal unless all items pass:

- P0 and P2-P5 are complete in the authoritative plan, and P1 repository controls pass.
- The candidate is a specific commit from `main`, with immutable application and frontend image
  digests.
- Remote CI and the Python compatibility summary pass on that commit.
- P1 repository controls pass, and private locations exist for every pending P1 artifact.
- A verified synthetic manifest, dedicated test accounts, copies of the
  [printable evaluation and outage form](../printable-evaluation-form.md), and a rollback owner
  are ready.
- The target deployment has a verified backup and no active real pilot session.

Record the entry result in the [readiness decision](../planning/evidence/p6-readiness-decision.md).

## P6.1 Close P1 against the candidate

Run the [P1 release-readiness procedure](p1-release-readiness.md) against the candidate and target
topology. Complete the physical manifest, backup-clone migration, PostgreSQL concurrency,
recovery, network isolation, disclosure, authorized fixture, smoke, and operations evidence.
Update the P1 gate only after its private artifacts are reviewed.

## P6.2 Run the authenticated device matrix

Use the [device matrix](../planning/evidence/p6-device-matrix.md). Test the actual supported family
devices and browsers through the public TLS route. Include distinct participant, recorder, and
manager sessions, sign-out/sign-in account changes, expired sessions, direct API attempts, and
narrow portrait viewports. A device is supported only when every critical journey passes.

## P6.3 Rehearse the synthetic workflow

Use the [synthetic rehearsal log](../planning/evidence/p6-synthetic-rehearsal.md). Begin with a
fresh synthetic program and finish with the redacted metrics export. Exercise program definition,
exact versions, repeats and holdouts, activation, enrollment, labels, blind observations, locks,
skin planning, reveal, post-reveal entry, ordinary history, recommendation runs, explanations,
feedback revisions, sampling, outcome linkage, reporting, and operational failure/recovery.

Perform an interruption after a saved response and a retry of one consequential action. Confirm
that the saved state remains correct and no duplicate impression, response revision, or reveal
transition appears.

## P6.4 Run the quality gate

Use the [quality report](../planning/evidence/p6-quality-report.md) on every critical page.

- Complete each journey with the keyboard and inspect focus order, focus visibility, labels,
  validation announcements, confirmation dialogs, and recovery messages.
- Run automated accessibility checks and manually verify headings, landmarks, contrast, zoom at
  200 percent, reduced motion, and screen-reader names.
- Test supported portrait and landscape sizes without horizontal scrolling, clipped controls, or
  hidden required content.
- Record authenticated navigation and action latency. A critical interaction fails if it exceeds
  the declared target or times out, even when a retry later works.
- Repeat disclosure checks in the visible UI, network responses, caches, exports, print views,
  errors, and structured logs.

## P6.5 Rehearse operations

Use the [operations drill](../planning/evidence/p6-operations-drill.md). Restore the verified
backup into an isolated target-compatible database, measure recovery time and recovery point,
verify row-count and redacted-hash invariants, and rehearse rollback at the documented decision
point. Exercise one connectivity failure and one optional LLM-provider failure. Core capture,
history, and deterministic recommendations must remain available or follow the printed manual
procedure.

Confirm alert delivery, log correlation, disk and database growth signals, backup schedule and
retention, and named owners for restore and secret rotation. Rotate only designated test secrets
during the rehearsal; record ownership and evidence without committing secret values.

## P6.6 Record the decision

Review the [participant guide](../guides/pilot-participant.md),
[manager guide](../guides/pilot-manager.md), all five P6 evidence records, the completed P1 gate,
and every known limitation. The core maintainer records `go` or `no-go` in the
[readiness decision](../planning/evidence/p6-readiness-decision.md).

Only `go`, with every P6.1-P6.6 item passed and no unresolved release-blocking limitation, closes
P6. A missing artifact, failed criterion, stale deployment, or `no-go` keeps F1 blocked. Any
candidate change after the decision invalidates affected evidence and requires an impact review
and rerun before actual perfume testing.

Copy `data/pilot/p6-readiness.template.json` to the private evidence directory and complete it
from the reviewed records. Validate the closure contract before signing:

```bash
uv run python scripts/validate_p6_readiness.py /secure/path/p6-readiness.json
```

The validator checks completeness and consistency; it does not determine whether an observation
is truthful or whether a private artifact is sufficient. The core maintainer must review those
artifacts before recording `go`.
