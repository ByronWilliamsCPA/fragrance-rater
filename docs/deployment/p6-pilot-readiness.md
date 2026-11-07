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
  digests. If the candidate deploys the published images, each digest passes the `cosign verify`
  command in [Image pinning and signing](image-signing.md) before it is recorded; base images are
  already pinned by digest in the repository, and Renovate keeps those pins current.
- Remote CI and the Python compatibility summary pass on that commit.
- P1 repository controls pass, and private locations exist for every pending P1 artifact.
- A verified synthetic manifest, dedicated test accounts, copies of the
  [printable evaluation and outage form](../printable-evaluation-form.md), and a rollback owner
  are ready.
- The target deployment has a verified backup and no active real pilot session.
- R7b (`docs/planning/PROJECT-PLAN.md` section 11a, the participant-facing blind-instrument build)
  has merged, the candidate commit includes that merge, and the candidate commit and image digests
  are the exact participant-instrument build F1 will use, recorded in the rehearsal evidence per
  `docs/planning/gates/p6.md` P6.3. This is a hard gate on P6.3: rehearsing against a pre-R7b
  build proves nothing about the instrument F1 will use.

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

Save each enrollment's manager-only evidence export (`GET
/api/v1/calibration/enrollments/{enrollment_id}/evidence-export`, signed in as a manager) to the private
evidence directory, then summarize it:

```bash
uv run python scripts/summarize_evidence_export.py --require-each-field-once \
  --expect-instrument <build commit SHA or release tag> /secure/path/export.json
```

The tool prints each captured field as `non-null/denominator`, counts `season_fit` and `setting_fit`
against skin-stage observations only, and counts quality flags and consent events. It also prints each
file's size and SHA-256 for the manifest in the rehearsal log. It exits 0 when every captured field
is non-null at least once and the program records the build you name, 1 when a field is null in every row
or the pin differs (an `unpinned-app-` fallback is refused), and 2 when a file is not a readable export
of the expected version. Pass several files to pool them, as F1 does across evaluators. The export holds
synthetic data only during this rehearsal, but it can still carry names and dates, so keep it private.

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

An empty `known_limitations` array cannot by itself distinguish a review that found nothing from a
step that was never done, so the record's `known_limitations_review` must then hold a completed note
(for example "reviewed, none identified"); the validator rejects an empty list without one. Record the
same note in the readiness decision so the closure record shows the review happened.

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

Two fields bind the rehearsal to the release. `r7b_build` names the commit and the application and
frontend image digests the P6.3 rehearsal exercised, and each must equal the same field of `release`: a
rehearsal that ran a different build says nothing about the build F1 will run, so a mismatch fails
the record. `artifacts.redacted_r7b_export` is the private reference to the saved R7b evidence
exports and their [summary](#p63-rehearse-the-synthetic-workflow).
