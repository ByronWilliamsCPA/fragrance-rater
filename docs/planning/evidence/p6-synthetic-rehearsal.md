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

**Status:** Pending target deployment

**Private evidence location:** Pending

**Release commit and image digests:** Pending

**R7b participant-instrument build exercised (commit SHA and image digests):** Pending

Use unmistakably synthetic evaluator names, catalog versions, observations, and outcomes. Record
the UTC start/end time, operator, role account, expected result, observed result, pass/fail, and
private artifact reference for each step.

| Step | Required result | Result | Evidence reference |
| :--- | :--- | :--- | :--- |
| Create versioned program | Draft has a unique name and version | Pending | Pending |
| Select exact catalog versions | Name, house, concentration, and `version_key` match manifest | Pending | Pending |
| Assign baseline, repeat, holdout, and another role | Frozen preview preserves roles and repeat link | Pending | Pending |
| Activate definition | Confirmation is required; later mutation is rejected | Pending | Pending |
| Enroll evaluator and recorder | Named assignment and randomized sessions appear | Pending | Pending |
| Print mapping and labels | Manager sees correct mapping; participant cannot retrieve it | Pending | Pending |
| Record and lock blind blotter work | Zero, null, text, and normal values persist correctly | Pending | Pending |
| Finalize skin plan and record skin work | Empty or selected plan and elapsed observations persist | Pending | Pending |
| Reveal and add post-reveal response | Blockers enforce policy; holdout remains concealed as required | Pending | Pending |
| Record repeated ordinary encounters | History retains both encounters and correct dates | Pending | Pending |
| Create and reopen recommendations | Reopen is idempotent and creates no duplicate impressions | Pending | Pending |
| View explanation | Deterministic fallback remains usable without the LLM provider | Pending | Pending |
| Append feedback revisions | Interest and sampling revisions remain ordered and immutable | Pending | Pending |
| Link a later synthetic outcome | Pre-impression outcome is rejected; later outcome links once | Pending | Pending |
| Filter and export metrics | Window, population, exclusions, denominators, versions, strategy, and snapshot persist | Pending | Pending |
| Record failure and recovery | Status identifies and then clears the affected evaluator | Pending | Pending |
| Interrupt and retry | Saved state resumes without duplicate data or transition | Pending | Pending |

These rows are required when F1 runs in the facilitated format (see the [P6 gate](../gates/p6.md)). All rows are pending; none is
evidence yet.

| Step | Required result | Result | Evidence reference |
| :--- | :--- | :--- | :--- |
| Sheet and slip versions rehearsed | Version id of the paper sheet and of the conditions slip recorded; equals the ids F1 will name | Pending | Pending |
| Shared-triple enrollment of six synthetic evaluators | `INDIVIDUAL` blotter mode; same session composition, per-session Latin-square rotation, random per-evaluator codes, preview matches stored plan | Pending | Pending |
| Paper session for six evaluators | Silent parallel sheets completed for at least one full session on paper, then one evaluator at a time transcribed through one recorder login | Pending | Pending |
| Blind-code confirmation and ambiguous marks | A mismatched code is not saved, including one sheet deliberately entered under the wrong evaluator (expected 409 with per-evaluator codes; record honestly if it is not caught); an ambiguous mark enters as blank plus a flag | Pending | Pending |
| Individual blotter flow and ceiling | One blotter per evaluator per sample, each evaluator spraying their own; the facilitator organizes and does not evaluate; actual sprayed, first-smelled and column-finished times recorded; provisional 2-minute ceiling counted from each evaluator's own spray confirmed or replaced; breaches flagged | Pending | Pending |
| Fresh blotter | At least one rehearsed fresh blotter (same sample, same blind code, sprayed when that evaluator's own window passed unsmelled); each sheet's Time sprayed is the spray time of the blotter that evaluator smelled; transcription enters each evaluator's own spray time; count of fresh blotters recorded | Pending | Pending |
| No group flag | No session carries `group_shared_blotter` (group blotter mode is built and unused); pooled reliability has the holder split only | Pending | Pending |
| Non-blind holder | Holder's enrollment flagged non-blind; training eligibility excludes it and evaluation keeps it | Pending | Pending |
| Checkpoints before holdouts | A holdout write is refused before that evaluator's own checkpoint (409) and accepted after; an explicit evidence time before the checkpoint is refused (422); checkpoints created by a manager | Pending | Pending |
| Household reveal | Refused until every enrollment is ready; one atomic reveal after the holdouts | Pending | Pending |
| Skin-absent by design | Five evaluators finalize an empty plan; completeness denominators count skin only for evaluators with a plan | Pending | Pending |
| Paper retention | Scans stored privately; retention period fixed by the owner is recorded | Pending | Pending |

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

**Rehearsal result:** Pending

**Reviewer and UTC date:** Pending
