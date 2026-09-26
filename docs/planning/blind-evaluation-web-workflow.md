---
title: "Web-first blind evaluation workflow"
schema_type: common
status: draft
owner: core-maintainer
purpose: "Translate the proposed 0.5 instrument into participant tasks, organizer controls and an implementation sequence."
tags:
  - frontend
  - development
  - planning
---

Prepared September 25, 2026 against repository baseline `56397d6` and
[FR-PANEL draft 0.5](../measurement/blind-evaluation-instrument-v0.5.md).
**Confirmed direction:** conduct evaluation through the web UI; paper is a
version-matched backup and a way to review the process. The screen/state
design below is proposed. It does not release a protocol, change the
application or adopt the proposed taxonomy.

## Participant sequence

Use the existing workspace and calibration entry points. Home should offer
the next due task, an exact draft to resume, or an understandable waiting
state. Keep ordinary journaling separate and lightweight. The paper packet
contains reusable templates, not a sequence of web pages or a per-sample
question count.

| Task | Participant experience | Instrument groups |
| --- | --- | --- |
| Start session | Confirm code, application and conditions; supply IDs automatically and confirm actual times. | `SE-META`, `SE-CONTEXT`, `SE-CONDITIONS`, `SE-PRIOR-TERMS`, `BL-META` / `META` |
| Blotter impression | Detection, own description, liking, interest in trying on skin, optional reason and season/setting; record interruption or discomfort. | Remaining `BL-*` |
| Session comparison | After absolute judgments, rank eligible detected samples by scent liking; allow ties such as 1,1,3 and incomplete/no-rank states. | `SE-RANK`, `SE-RANK-STATUS`, `SE-DEVIATION` |
| Skin checks | Assigned trial with actual application time and a due-task timeline; record detection, description and current liking, or a missed/interrupted check. | `SK-TIME`, `SK-DETECT`, `SK-TEXT`, `SK-LIKE-NOW`, `SK-STOP` |
| Final skin judgment | Overall liking, willingness to wear again, optional reason, season/setting, discomfort and actual observation-period end. | `SK-FINAL-TIME`, `SK-WEAR`, `SK-LIKE-OVERALL`, `SK-DRIVER`, `SK-SEASON`, `SK-SETTING`, `SK-DISCOMFORT` |
| Optional scheduled late check | Separate detection task after final judgment; never replace the final endpoint. | `SE-LATE-SCHEDULED`, `SK-LATE-DETECT` |
| Information received | Available throughout; record familiarity, identity guesses, formal or accidental disclosure and vocabulary exposure with times. | `SE-RECOGNITION`, `SE-DISCLOSURE`, `SE-SESSION-TERMS` |
| Unpriced use roles | After relevant blind work closes, ask when the person would wear it, before introducing spending questions. | `FU-ROLE-LINKS`, `FU-ROLE-BASIS`, `FU-ROLE` |
| Optional profile and references | Multiple formats and unlimited size/purpose entries; reuse familiar alternatives and preserve price uncertainty/basis. | All `PR-*` and `REF-*` |
| Offer context | Record prior knowledge, then show the exact offer and ask wearer, gift, current intended use and experience. | `VAL-PRIOR-INFORMATION`, `VAL-OFFER`, `VAL-WEARER`, `VAL-GIFT`, `VAL-INTENDED-USE`, `VAL-EXPERIENCE`, `VAL-SKIN-COUNT`, `VAL-RECIPIENT-EXPERIENCE` |
| Value decision | Separate personal value, buying now and next step; optional reasons, reference comparison and cost-related own use. | All remaining `VAL-*` except organizer `VAL-PROFILE-LINK` |

Free description precedes ratings. Do not prime blind answers with house
notes, taxonomy checklists or AI suggestions. Season and setting suitability
remain optional on **both** blotter and skin forms; actual session conditions
are separate. Non-detection is not dislike, and final non-detection does not
invalidate an assessable retrospective judgment.

In digital presentation, ask prior-offer knowledge before first displaying
the offer where possible. The paper asks retrospectively on the offer card:
this ordering change needs its own presentation version. Preserve the actual
sequence if the person already saw the information. Current intended use
is asked after price and must not overwrite the earlier unpriced use role.

## Organizer ownership and disclosure

Separate organizer modes: prepare, run, release, recover and interpret.
`OP-RELEASE` supplies protocol settings; `OP-SELECTION` distinguishes
skin/holdout allocation from the value-offer subset; `OP-SEQUENCE` retains
offer order and prior disclosures; `OP-RECOGNITION-LINK` joins spontaneous
comments to exposure; `OP-CORRECTION` preserves discrepancies; `OP-CODING`
records later interpretation. `VAL-PROFILE-LINK` is optional reviewed metadata,
never a prerequisite for answering value.

Move study allocation out of the mandatory first participant step. Declare
coverage/holdout allocation before outcomes; any permitted adaptive skin
selection retains its rule, eligible set, selections and omissions. Capture
permission for a recorder does not automatically grant allocation or private
mapping authority. Keep the evaluator and recorder identities distinct.

Proposed release order: resolve relevant blind tasks/repeats and scheduled
late checks; close or explicitly skip unpriced use roles; offer optional
profiles/references; release coded price offers; separately release identity
and catalog information when permitted. A skipped profile never blocks value.

Define a release group covering the participants/presentations a disclosure
could compromise. A household-wide group is the simpler first-batch proposal;
unrelated future work need not block forever. Protect future holdouts, record
withdrawals/missing-task closure, and freeze predictions before their target
outcomes. A single enrollment's reveal flag cannot establish this policy.

Price, brand, identity, published notes and taxonomy exposure are separate
cumulative facts. Price alone can cue identity; hiding it again cannot undo
exposure. Preserve affected evidence and apply the declared eligibility rule.
Familiarity alone is neither verified recognition nor automatic exclusion.

Server-side allowed actions and allowlisted payloads govern every transition.
Keep identity, images, URLs, private mappings and repeat/holdout labels out of
blind API responses, HTML, caches, errors, logs and exports. A mapping-aware
manager switching to participant view does not regain blindness.

Use one declared real offer per sample initially. Further offers get separate
assessments, sequence and prior-information context. Store intended server
payload, delivery time and render acknowledgment separately; none proves
comprehension. Retain actually reported display mismatches and issue corrected
offers/responses as linked records. Do not show profile thresholds/reference
prices beside the initial value question; conduct explicit comparison later.

## Saving, time and records

Extend existing Program, Enrollment, Session and Presentation entities;
retain exact catalog-version links and independent repeat presentations.
Add versioned instrument/protocol releases, stage-specific trials/tasks,
drafts, submitted responses/corrections, exposure events, unpriced role links,
profile versions/size entries/references and offer/assessment snapshots.
Use typed domain models and constrained response contracts, not an unvalidated
JSON catch-all or a general-purpose survey platform.

- Autosave drafts to the server with visible Saving / Saved / Not saved state.
  A draft is not a submitted observation or training label. Restore the exact
  task after refresh; do not show success before acknowledgment.
- Submit explicitly with idempotency and optimistic concurrency. A timeout,
  second tab or assigned recorder must not duplicate or overwrite evidence.
  Retain conflicting drafts for review; recheck release state transactionally.
- Close sessions/trials separately from submitting one check. Resolve required
  tasks as observed, missed, interrupted or not administered under the protocol.
  Passing a scheduled time does not submit an answer.
- Store application, actual observation, trial end, final judgment and entry
  times separately, with timezone/precision/uncertainty. A trial can pass four
  hours while its 240-minute check is missed. Calculate elapsed time only from
  known compatible timestamps.
- Keep the final wear/overall-liking endpoint independent of repeated and
  optional eight-hour detection. A final judgment must not lock out that task.
- Append corrections with original/source links, reason, author and correction
  information state. Post-price corrections never rewrite blind originals.
- Preserve genuine legacy 0-10 responses. New nine-point liking and five-category
  wear responses need distinct scales, constructs and export/model semantics.

For the first batch, require connected submission and verified server draft
recovery. Retain in-page input during transient failures but clearly identify
unsaved work. Use paper if the service is unavailable; do not promise offline
durability until local storage, account separation and reconciliation are built
and rehearsed. Reminders are optional; due-task visibility and resume are core.

Generate paper from the same released IDs/questions. Transcribe into the same
trial/task with original source, actual observation and later recorder/entry
time. Compare existing web answers rather than silently replacing them. Verify
export/restore of raw text, statuses, scale versions, disclosure, corrections,
profiles, references and exact offers before relying on this backup route.

Later taxonomy coding preserves multiple/no family, uncertainty and unresolved
meaning, with author and vocabulary version. Retain explicit Gourmand, Chypre,
Fougère and Oud concepts without settling their kinds in this PR. House/provider
assertions, participant perceptions and ingredient claims remain distinct;
[source permissions](../fragella-api.md) also remain separate from mapping quality.

## Current gaps and delivery order

The baseline already has guided calibration/resume, append-only observations,
stage locks and delayed identity reveal. It does not implement this instrument:
`SampleObservationPanel` manually posts a form with structured scales before
description; `ResponseInput` uses 0-10 liking/wear/buy and Boolean detection;
`lock_stage()` requires one detection answer, not scheduled-task completion;
`reveal_blocker()` gates enrollment locks; controlled history and ML evaluation
label observations 0-10. Skin-plan actions currently use recorder/enrollment
authorization. A new UI alone cannot correct these storage and gate differences.

| ID | Implementation outcome | Evidence required before use |
| --- | --- | --- |
| WEB-01 | Pin instrument/presentation versions, scales/statuses, actual dose/timing, selection, missing-task rules, endpoints and release scope. | Every field group mapped; actual batch settings reviewed; affected ADR/guide amendments. |
| WEB-02 | Versioned task/response storage, drafts, idempotent submit, concurrency, times and corrections. | PostgreSQL migration/constraints and export round-trip; old scales unchanged. |
| WEB-03 | Task Home, progressive blotter/rank/skin/final UI and both-stage suitability. | Phone/keyboard flow, exact resume, non-detection, ties, early stop and missed/late checks. |
| WEB-04 | Organizer permissions, allocation and separate price/identity release groups. | Cross-participant/holdout gates, stale-tab rejection and leakage checks on all surfaces. |
| WEB-05 | Unpriced roles, optional multi-size profiles/references, exact offers and value follow-up. | Not-sure partial profile, no-profile offer, gift/shared experience and sample-first versus smaller final amount. |
| WEB-06 | Identified paper transcription, conflict/correction history and backup/restore. | Recover partly saved web/paper work without losing either source or backdating entry. |
| WEB-07 | Scale-, construct- and endpoint-aware history, exports and model manifests. | Drafts excluded; late detection cannot replace final judgment; holdouts/post-price evidence remain appropriately excluded. |
| WEB-08 | Human participant, organizer and recorder rehearsal on intended deployment/devices. | Capture, interruptions, timing, disclosure, value branches, burden and recovery demonstrated. |

Start with WEB-01/02, then participant and organizer flows, follow-up and
recovery. WEB-07's consumer protections are needed before any new responses
reach those consumers; human release rehearsal follows. All eight remain
implementation work. Baseline-only collection may precede later modules only
when its own capture/recovery/disclosure gates are operational and price stays
inaccessible. Unasked original blind judgments cannot be recovered later.

No taxonomy picker, AI annotation, inventory, retailer integration, offline
synchronization, notifications or new prediction algorithm is required for the
initial raw-capture workflow. Keep the scope tied to preserving valid evidence.
