---
title: "P6 synthetic rehearsal log"
schema_type: common
status: draft
owner: core-maintainer
purpose: "Retain the complete synthetic setup-to-report rehearsal result for P6."
tags:
  - planning
  - testing
  - evaluation
---

**Status:** Not completed; the P6.3 rehearsal was waived by the owner on 2026-11-27 (F1 gate sign-off 18). A waiver, not a pass

**Private evidence location:** Pending

**Release commit and image digests:** Pending

**R7b participant-instrument build exercised (commit SHA and image digests):** Not recorded; the R7b acceptance export from a synthetic run is still owed

Use unmistakably synthetic evaluator names, catalog versions, observations, and outcomes. Record
the UTC start/end time, operator, role account, expected result, observed result, pass/fail, and
private artifact reference for each step.

| Step | Required result | Result | Evidence reference |
| :--- | :--- | :--- | :--- |
| Create versioned program | Draft has a unique name and version | Waived 2026-11-27 (sign-off 18) | None |
| Select exact catalog versions | Name, house, concentration, and `version_key` match manifest | Waived 2026-11-27 (sign-off 18) | None |
| Assign baseline, repeat, holdout, and another role | Frozen preview preserves roles and repeat link | Waived 2026-11-27 (sign-off 18) | None |
| Activate definition | Confirmation is required; later mutation is rejected | Waived 2026-11-27 (sign-off 18) | None |
| Enroll evaluator and recorder | Named assignment and randomized sessions appear | Waived 2026-11-27 (sign-off 18) | None |
| Print mapping and labels | Manager sees correct mapping; participant cannot retrieve it | Waived 2026-11-27 (sign-off 18) | None |
| Record and lock blind blotter work | Zero, null, text, and normal values persist correctly | Waived 2026-11-27 (sign-off 18) | None |
| Finalize skin plan and record skin work | Empty or selected plan and elapsed observations persist | Waived 2026-11-27 (sign-off 18) | None |
| Reveal and add post-reveal response | Blockers enforce policy; holdout remains concealed as required | Waived 2026-11-27 (sign-off 18) | None |
| Record repeated ordinary encounters | History retains both encounters and correct dates | Waived 2026-11-27 (sign-off 18) | None |
| Create and reopen recommendations | Reopen is idempotent and creates no duplicate impressions | Waived 2026-11-27 (sign-off 18) | None |
| View explanation | Deterministic fallback remains usable without the LLM provider | Waived 2026-11-27 (sign-off 18) | None |
| Append feedback revisions | Interest and sampling revisions remain ordered and immutable | Waived 2026-11-27 (sign-off 18) | None |
| Link a later synthetic outcome | Pre-impression outcome is rejected; later outcome links once | Waived 2026-11-27 (sign-off 18) | None |
| Filter and export metrics | Window, population, exclusions, denominators, versions, strategy, and snapshot persist | Waived 2026-11-27 (sign-off 18) | None |
| Record failure and recovery | Status identifies and then clears the affected evaluator | Waived 2026-11-27 (sign-off 18) | None |
| Interrupt and retry | Saved state resumes without duplicate data or transition | Waived 2026-11-27 (sign-off 18) | None |

These rows are required when F1 runs in the facilitated format (see the [P6 gate](../gates/p6.md)). All rows are waived (2026-11-27, sign-off 18); none is
evidence.

| Step | Required result | Result | Evidence reference |
| :--- | :--- | :--- | :--- |
| Sheet and slip versions rehearsed | Version id of the paper sheet and of the conditions slip recorded; equals the ids F1 will name | Waived 2026-11-27 (sign-off 18) | None |
| Shared-triple enrollment of six synthetic evaluators | `INDIVIDUAL` blotter mode; same session composition, per-session Latin-square rotation, random per-evaluator codes, preview matches stored plan | Waived 2026-11-27 (sign-off 18) | None |
| Paper session for six evaluators | Silent parallel sheets completed for at least one full session on paper, then one evaluator at a time transcribed through one recorder login | Waived 2026-11-27 (sign-off 18) | None |
| Blind-code confirmation and ambiguous marks | A mismatched code is not saved, including one sheet deliberately entered under the wrong evaluator (expected 409 with per-evaluator codes; record honestly if it is not caught); an ambiguous mark enters as blank plus a flag | Waived 2026-11-27 (sign-off 18) | None |
| Individual blotter flow and ceiling | One blotter per evaluator per sample, each evaluator spraying their own; the facilitator organizes and does not evaluate; actual sprayed, first-smelled and column-finished times recorded; provisional 2-minute ceiling counted from each evaluator's own spray confirmed or replaced; breaches flagged | Waived 2026-11-27 (sign-off 18) | None |
| Fresh blotter | At least one rehearsed fresh blotter (same sample, same blind code, sprayed when that evaluator's own window passed unsmelled); each sheet's Time sprayed is the spray time of the blotter that evaluator smelled; transcription enters each evaluator's own spray time; count of fresh blotters recorded | Waived 2026-11-27 (sign-off 18) | None |
| No group flag | No session carries `group_shared_blotter` (group blotter mode is built and unused); pooled reliability has the holder split only | Waived 2026-11-27 (sign-off 18) | None |
| Non-blind holder | Holder's enrollment flagged non-blind; training eligibility excludes it and evaluation keeps it | Waived 2026-11-27 (sign-off 18) | None |
| Checkpoints before holdouts | A holdout write is refused before that evaluator's own checkpoint (409) and accepted after; an explicit evidence time before the checkpoint is refused (422); checkpoints created by a manager | Waived 2026-11-27 (sign-off 18) | None |
| Household reveal | Refused until every enrollment is ready; one atomic reveal after the holdouts | Waived 2026-11-27 (sign-off 18) | None |
| Skin-absent by design | Five evaluators finalize an empty plan; completeness denominators count skin only for evaluators with a plan | Waived 2026-11-27 (sign-off 18) | None |
| Paper retention | Scans stored privately; retention period fixed by the owner is recorded | Waived 2026-11-27 (sign-off 18) | None |

Attach a redacted metrics export manifest containing its filename, SHA-256 hash, byte count,
redaction reviewer, and private location. Do not commit the export itself.

## Observations during the dry run

Recorded as they happened. They are notes, not evidence: no row above is marked complete by them.

- Program `rehearsal-1` was a setup mistake (one stimulus used twice, another missing) that was activated and so
  locked; program definitions cannot be edited or deleted after activation. It was abandoned with 0 enrollments and
  `rehearsal-2` was created and activated instead.
- Six synthetic evaluators were enrolled in order E1 to E6 through the API (shared-triple template, random
  per-enrollment blind codes). E1 was flagged non-blind before any exposure (2026-11-26 23:06 UTC).
- Consent was recorded for E2 to E6 between 03:20 and 03:22 UTC on 2026-11-27 ("signed on paper"). E1's consent was
  granted and then withdrawn on purpose by the owner five seconds later (03:11 UTC) to see the effect. Both events are
  kept in the log, no evaluation was affected, and E1 continues as an evaluator who declined the conditions questions.
- **Finding 1.** Pressing Continue on the consent screen starts the session. All six first sessions were started at
  the consent minute (03:11 to 03:22 UTC), not at a sitting time, and the app refuses a second start. The owner
  accepted this for the rehearsal. For F1, record consent together with the start time written on the paper sheet at
  transcription, and do not press Continue at the sitting.
- **Finding 2.** Consent cannot be granted again or changed in the app once its session has started, because the
  intro screen shows only for an unstarted session. A mistaken withdrawal then needs an operator API call.
- **Finding 3.** A mistake in a program setup cannot be fixed in the app, and the session-plan error "needs more
  baseline stimuli" is generic: `generate_template` collapses every template error into one message, so it hides
  which rule failed. Worth a clearer message after F1.
- **Finding 4.** The manager screens have no way to add an evaluator; a person is created with `POST /reviewers`.
  A manager-only "Add an evaluator" screen is built in a separate change, and the owner decided when it goes live
  (see the F1 gate, sign-off 15).

**Rehearsal result:** Not completed. The owner waived the remainder on 2026-11-27 after step 3.1 (see F1 gate sign-off 18). No row above beyond steps 1.x to 3.1 is evidenced.

**Reviewer and UTC date:** Pending
