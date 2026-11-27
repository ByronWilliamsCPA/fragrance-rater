---
title: "P6 readiness decision"
schema_type: common
status: published
owner: core-maintainer
purpose: "Record the reviewed go or no-go decision that controls entry into F1."
tags:
  - planning
  - validation
  - releases
---

**Decision:** `go`, recorded at the owner's explicit instruction on 2026-11-27 with waivers and open evidence stated
below. This is an owner decision that departs from the decision rule at the end of this record; it is **not** a finding
that every gate row passed.

**Release commit:** `94f6cf22452c45a3144ed74bc2fefcbe8283a4df`

**Application and frontend image digests:**
`ghcr.io/byronwilliamscpa/fragrance_rater@sha256:83878ed0caf77d236954565e9584c35ca30f9edcef2044f273e34e58eda53f7b`
and
`ghcr.io/byronwilliamscpa/fragrance_rater-frontend@sha256:8910ae82b2c13853daa70e69caf9758cb7a83c4aac80337bc2e742fa7602c16c`.
Read from the running containers on 2026-11-27 and matched to the tag `sha-94f6cf2`. `INSTRUMENT_VERSION` in the
running application container equals the release commit. Image signatures were not verified locally; the CI signing job
verified them.

**Deployment identifier:** Portainer stack 131 on the private docker host (private reference, not recorded here).

**Decision maker and UTC date:** The owner (product owner and sole F1 operator), 2026-11-27 (UTC).

| Gate | Required reviewed record | Result | Reviewer | Evidence reference |
| :--- | :--- | :--- | :--- | :--- |
| P6.1 | Completed P1.1-P1.10 gate against this candidate and topology | Family-scope items done: forged-header 401, target-host smoke, one timed restore (0.47 s, row counts matched, Alembic no-op), alert recipient named. Not all P1 external evidence is recorded; P1.4 concurrency and the P1.1 second check are waived (F1 gate sign-off 11) | Owner | Private evidence folder on the operator's machine (not in the repository) |
| P6.2 | Authenticated device matrix for every supported family device | Not recorded. The [device matrix](p6-device-matrix.md) is still all Pending. The facilitator's laptop has been used through the real login during setup, which is not a recorded matrix | Owner | None |
| P6.3 | Complete synthetic setup-to-report rehearsal and redacted export manifest | **Waived** by the owner on 2026-11-27 (F1 gate sign-off 18). Only step 3.1 (consent) ran, with findings. Not evidenced: a six-person run, observed queuing and replacement-blotter counts, the four deliberate failure cases, and the R7b acceptance export | Owner | [Rehearsal log](p6-synthetic-rehearsal.md), section "Observations during the dry run" |
| P6.4 | Accessibility, keyboard, responsive, performance, disclosure, and recovery report | Not recorded. The [quality report](p6-quality-report.md) is still all Pending | Owner | None |
| P6.5 | Backup/restore, alerts, logs, ownership, optional-service, and outage drill | Partly done: the timed restore and the alert recipient (shared with P6.1). The [operations drill](p6-operations-drill.md) is still Pending. The outage procedure is the retained paper sheets | Owner | Private evidence folder on the operator's machine |
| P6.6 | Participant and manager guides plus limitations reviewed | This record. The guides were revised for sheet v2.2 and individual blotters; the limitations are listed below | Owner | This record |

## Known limitations

| Limitation | Impact | Workaround | Owner | Blocking? | Resolution or accepted rationale |
| :--- | :--- | :--- | :--- | :--- | :--- |
| The P6.3 rehearsal did not run | No end-to-end evidence that the deployed build, printed v2.2 sheets and one recorder login work for six evaluators; queuing at the atomizers is unobserved | The first F1 sittings are the first real run; the facilitator transcribes each sheet promptly and checks the first one against the paper | Owner | Accepted | Owner waiver, F1 gate sign-off 18; not a pass |
| The R7b acceptance export from a synthetic run does not exist | The export has not been exercised on the deployed build | None chosen yet | Owner | Accepted for starting F1; owed | The owner has not chosen a substitute; the plan mirrors need a follow-up once one is chosen |
| Pressing Continue on the consent screen starts the session, and consent cannot be re-granted once started | A consent recorded early starts the session clock early; a mistaken withdrawal needs an operator API call | Record consent with the paper start time at transcription; do not press Continue at the sitting | Owner | No | Rehearsal log findings 1 and 2 |
| No withdraw route for an evaluator's participation, and the household reveal waits on the disclosure gate | A withdrawal during F1 holds the household reveal | Handle by the operator path and record it | Owner | No | Family MVP profile, deliberate failure 2 |
| Setup mistakes in a program cannot be fixed in the app, and the session-plan error "needs more baseline stimuli" is generic | A wrong program definition can only be replaced, not edited | The real program (v3.2) was checked against the manifest before activation | Owner | No | Rehearsal log finding 3; clearer message after F1 |
| The v3.1 program was activated by mistake with reveal policy ENROLLMENT | Inert (one enrollment, no evaluations); the F1 program is v3.2 | Do not use v3.1 | Owner | No | F1 gate sign-off 17 |
| Evaluators are created through the operator path until the manager add-evaluator screen is deployed | Setup depends on one operator call per evaluator | The six real reviewers already exist | Owner | No | F1 gate sign-off 15; the screen is merged and not deployed |
| P6.2 and P6.4 evidence is not recorded | Device and quality results exist only as informal use | The facilitator uses one laptop through the real login | Owner | Accepted | Owner decision to proceed; the records stay Pending |
| Blind codes in program v3.2 are shared by all six evaluators and equal the atomizer label (decided and applied 2026-11-27, after the `go` above, by a reviewed data update with no code change, build or deploy) | The server's blind-code check no longer catches a sheet entered under the wrong evaluator; the H codes disclose the holdout partition and the repeats' positions are inferable (the v2.2 header already showed the atomizer label); one evaluator's reveal would unblind the others; a later add-evaluator enrollment gets random codes again; headers with the earlier random codes are obsolete | One recorder, one evaluator's sheets at a time, name and record ID checked against the enrollment on screen before saving; household reveal already in force; do not use the earlier headers; a later enrollment needs the same reviewed update or a post-F1 code change (not made, needs a new build and a pin decision) | Owner | Accepted | Owner decision, F1 gate sign-off 19; pre-change rows retained privately outside git |
| Three of six evaluators are novices and most are minors, with no guardian clause | Consent and disclosure rest on the family setting | Household-only reveal; paper retained 12 months | Owner | No | Family MVP profile (F1 gate sign-offs) |

## Decision rule

Record exactly `go` or `no-go`. `Go` is valid only when every gate row passes, every private
artifact was reviewed, no release-blocking limitation remains, and the recorded commit and image
digests match the deployed candidate. Any later candidate change requires an impact review and
rerun of affected evidence.

`No-go` must name the failed criteria, owning P sprint, corrective action, and required rerun.
F1 remains blocked until a later signed record says `go`.

**Departure from the decision rule.** Not every gate row passes: P6.3 is waived and P6.2 and P6.4 are unrecorded. The
owner chose to record `go` anyway and to proceed to F1, accepting the limitations above. The recorded commit and image
digests do match the deployed candidate (checked 2026-11-27). Any later candidate change requires an impact review. The
build freeze stands: no participant-facing build, sheet or slip change after this record without a new impact review.

**Signed decision statement:** On 2026-11-27 the owner instructed, in writing in the working session, that the P6.6
readiness decision be recorded as `go` for release commit `94f6cf22452c45a3144ed74bc2fefcbe8283a4df`, with the P6.3
waiver and the known limitations above. This record was drafted from that instruction. No separate handwritten signature
exists; the owner's instruction and the owner's review of this record are the signature, and the owner may amend or
retract it before the first sitting.
