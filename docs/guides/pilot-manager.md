---
title: "Pilot manager guide"
schema_type: common
status: published
owner: core-maintainer
purpose: "Explain preparation, operation, disclosure, recovery, and closeout for the family pilot."
tags:
  - guide
  - usage
  - deployment
---

The manager is responsible for exact-version identity, physical labels, recorder access, blind
disclosure, recovery, and retained evidence. Complete the
[P6 pilot-readiness runbook](../deployment/p6-pilot-readiness.md) with synthetic data before
using actual pilot perfumes.

## Prepare the release and accounts

Record the deployed commit and image digests. Confirm that traffic enters through the dedicated
Traefik and Authentik boundary, the API and database have no public host ports, and
`AUTHENTIK_REQUIRED=true`. Use separate manager, recorder, and participant accounts. Verify the
configured manager usernames before opening the program.

## Build and freeze a program

1. Open **Program setup** and create a named, versioned draft.
2. Search the catalog and select the exact name, house, concentration, and `version_key` shown on
   the physical sample.
3. Record the identity evidence and assign the intended role. Link hidden repeats to the exact
   baseline membership.
4. Compare the draft with the reviewed physical manifest. Resolve every mismatch; never guess a
   version.
5. Review the frozen-definition preview and confirm activation. Activation is irreversible for
   that program definition.

## Enroll, label, and operate

Enroll the named evaluator and grant only the recorder usernames that need access. (The
[facilitated variant](#facilitated-six-evaluator-variant) uses one recorder login for all six evaluators.) Choose the
blind label scheme at enrollment: **Standard** (for example `E01-S1-2`, the default and easiest
to label) or **Random code** (8 hex characters). Standard labels reveal which sessions are
baseline and which are holdout (holdout sessions are numbered last), so choose Random code when
that must stay hidden from evaluators and recorders. Generate the
manager-only mapping and print the blind labels. Keep the mapping away from participants and
remove discarded labels from the work area.

Use the progress overview to follow blotter completion, the finalized skin plan, planned skin
work, and reveal blockers. A holdout does not block the main reveal merely because its own
blotter is unfinished; its identity remains hidden until its own blotter is locked. Confirm any
consequential action in the application and inspect the returned state.

## Facilitated six-evaluator variant

F1 may run as a facilitated, paper-first format with six evaluators (decided 2026-11-24; see the
[F1 gate](../planning/gates/f1.md) and the ADR-005 and ADR-009 amendments of that date). This variant departs
from the ordinary workflow above in several ways. Where it is silent, the ordinary workflow applies. Which
software parts are merged is stated here and nowhere else in this guide; do not assume anything marked pending.

### What the variant is

- Six evaluators, one facilitator. The facilitator is the declared mapping holder, is also an evaluator, helps the
  other five keep their blotters, trays and sheets organized (and does not evaluate in those sessions), transcribes,
  verifies and controls the reveal. The holder's own evaluations run in separate sessions. The holder's rows are
  flagged non-blind, excluded from blind-baseline training and retained in evaluation. The observations are
  single-blind with observer cues.
- Evaluators work in silent sessions on paper: one sheet per evaluator per session, three sample columns, no logins
  and no phones. F1 uses **individual blotters** (decided
  2026-11-25 after the group procedure failed a physical attempt): each evaluator has their own blotters and sprays
  their own. See [Individual blotters](#individual-blotters-f1) below. The facilitator transcribes every sheet through **one recorder login**. This departs from
  the rule in the rest of this guide that evaluator and recorder identities stay distinct; the F1 pre-exposure
  declaration must say so.
- All six evaluators are captured in the application before the next session starts.
- Facilitated sessions have no skin tests. Skin is a separate optional path on its own day. For F1 only the holder
  does skin tests; the other five evaluators are skin-absent by design.

The printed materials are the [session sheet](../facilitated-session-sheet.md), the
[conditions slip](../facilitated-conditions-slip.md), the
[property guide handout](../facilitated-property-guide.md) (give it to each evaluator before the first session), and the
[facilitator run sheet](../facilitated-run-sheet.md). Follow the run sheet for room setup, ventilation, round
timing, silent work, interruptions, paper handling and the transcription window. The run sheet and both forms are
drafts until the P6.3 rehearsal.

### What is merged and what is pending

| Part | State |
| :--- | :--- |
| Shared-triple enrollment, Latin-square order, random codes, session-plan preview (#211); the Latin-square order is for individual mode, which F1 uses (the unused group blotter mode gives every evaluator the same order) | Merged |
| Non-blind quality flag and the `/non-blind` call (#213) | Merged |
| Holdout gate, household reveal, `reveal_policy`, manager checkpoints (#214) | Merged |
| Paper sheet, conditions slip, run sheet, spray-sheet generator (#215) | Merged |
| Facilitated guides, P6.2 and P6.3 scope, F1 declaration template (#217) | Merged |
| Session-scoped wizard (skin-plan step removed from the blotter flow, per-session ranking, holdout sequence, manager checkpoint and household reveal panel) (#216) | Merged |
| Transcription timing (paper first-smell, finished and session times, whole-minute elapsed time) and the blind-code confirmation guard (#218) | Merged |
| Group blotter mode in the application, built and not used by F1 (program `blotter_mode`, shared codes and order, `group_shared_blotter` flag, 2 minute ceiling) | Merged: #220, `6774525` (see [PROJECT-PLAN.md section 11a](../planning/PROJECT-PLAN.md#f1-facilitated-format-work-items-decided-2026-11-24)) |
| Group blotter procedure: sheet v2.0, run sheet, spray-sheet `--mode group`, guides, gates | Merged: #219, after #220; superseded for F1 by the individual-blotters revision (sheet v2.1) |
| Group safeguards in the server, retained and not used by F1 (program-wide holdout gate, evidence before checkpoint refused, group programs reveal as a household, 2 minute ceiling rule `v2`) | Merged: #221, `2bcd3cc` |

A merged item is not gate evidence: none of this has been rehearsed in P6.3. Re-read this table against the merged pull
requests before relying on it.

### Enroll with shared triples

1. Create and activate the program as usual. For a household reveal, set the reveal policy to `HOUSEHOLD` on the
   draft program (at creation, or with `PUT /api/v1/calibration/programs/{program_id}/reveal-policy` while the
   program is still a draft). The default `ENROLLMENT` reveals each evaluator separately and leaks across
   evaluators who share triples. The server allows `HOUSEHOLD` with the default `INDIVIDUAL` blotter mode, which is the F1 plan. (A
   `SHARED_GROUP` program, which F1 does not use, always reveals as a household.)
2. In **Program setup**, leave the blotter mode at `INDIVIDUAL` (the default) and choose the shared-triples
   algorithm `shared-triples-latin-rotation-v1`: standard labels are refused with it, and blind codes are random and
   specific to each evaluator, because with shared triples a label that names the session would reveal session identity
   and holdout status. Every enrollment of a program must use the same shared algorithm. Do not choose `SHARED_GROUP`
   or `shared-triples-group-blotter-v1`: group blotter mode is merged (#220) but not used by F1.
3. Name any exceptionally persistent or animalic samples. The manager supplies them; the template allows at most one
   per session and generates nothing about persistence itself.
4. Use **Preview session plan** before the first enrollment. It shows the session composition the next evaluator
   would receive (the program's recorded one, the one you supplied, or a freshly generated one, which is not stored
   until you enroll) and which rotation the next evaluator takes. The preview names fragrances, so it is
   manager-only and stays in a closed disclosure; do not show it to an evaluator. Check that holdouts sit in the last
   sessions and that each hidden repeat sits at least twice the session size in positions after its original, then
   enroll the six evaluators one by one. Enrollment fixes the order within each session for that evaluator (a Latin-square row by enrollment ordinal and
   session number); the actual order is stored.
5. Generate the manager-only mapping and print the blind labels. Build the facilitator spray sheets and each
   evaluator's pre-printed code row with `scripts/make_spray_sheets.py`; its output is facilitator-only, goes to the
   gitignored `tmp_cleanup/spray-sheets/` by default, and is never committed.

### Flag the holder as non-blind

Call `POST /api/v1/calibration/enrollments/{enrollment_id}/non-blind` for the holder's enrollment, with a written
explanation (for example "declared mapping holder; facilitates, transcribes and controls the reveal"). It raises one
`non_blind` flag per session and is idempotent. Record the holder's enrollment id and the date the call is made in the
F1 pre-exposure declaration, before the first exposure. The flag removes the holder's rows from blind-baseline
training and keeps them in evaluation.

### Create checkpoints before the holdouts

A holdout sample refuses every write until its enrollment has a checkpoint, and a checkpoint cannot be created once
any holdout observation exists. Nothing in the evaluator screens creates one. After all six evaluators have finished
baseline, hidden repeats and planned skin, and each skin plan is finalized (an intentionally empty plan for the five),
create the checkpoints as a manager:

- Check `GET /api/v1/calibration/programs/{program_id}/readiness` for each enrollment's `checkpoint_blocker`,
  `holdouts_open` and `missing_checkpoint` (the response also lists `enrollments_missing_checkpoint`, a policy-level
  `household_reveal_ready` and `household_revealed`). `holdouts_open_program_wide` is only ever true for a
  `SHARED_GROUP` program, so it is always false for F1; use the per-row `holdouts_open`.
- Create them with `POST /api/v1/calibration/programs/{program_id}/checkpoints`. By default it also freezes one
  prediction snapshot per program holdout. Skipped enrollments are listed with a reason.

This holds in every program with holdouts, including the P6 synthetic rehearsal, until a manager checkpoint button
exists in the wizard; #216 (merged) adds a checkpoint and household reveal panel in **Program setup**. The owner decided on 2026-11-25 that F1 does not require a
linked prediction per holdout; the call freezes predictions by default, and the declaration should state what was
frozen.

With individual blotters the holdout gate is per enrollment: an evaluator's holdouts open when that evaluator's own
checkpoint exists, and the server refuses a holdout evidence time earlier than that checkpoint (422). Because the six
evaluators sit together, hold the holdout sitting until all six have a checkpoint. The server cannot see when a blotter
was smelled: tell the facilitator when the readiness view shows no missing checkpoint, and write each checkpoint's
creation time in the declaration. The facilitator must not spray or smell a holdout before then (see the
[run sheet](../facilitated-run-sheet.md#checkpoint-rule-no-holdout-is-sprayed-or-smelled-before-its-checkpoint-exists)).

### Household reveal

With `HOUSEHOLD`, the per-evaluator reveal is refused. A manager reveals every evaluator together with
`POST /api/v1/calibration/programs/{program_id}/reveal`, once every enrollment has its baseline, repeats and planned
skin locked, a finalized skin plan, a checkpoint, and all holdouts locked. Readiness shows `HOUSEHOLD_WAIT` for an
evaluator who is done while another is not. Reveal only after all six have finished, and announce it yourself.

**Withdrawn-evaluator caveat.** An evaluator who withdraws stays enrolled in the program, so the household reveal
keeps waiting for them: an enrollment that cannot finish blocks everyone's reveal (verified in code; the `HOUSEHOLD` policy
the owner plans for F1 cannot reveal any other way). No merged procedure covers this
(neither dropping an enrollment from the program nor revealing without them). The owner decided on 2026-11-25 that
there is no code change: the household reveal waits and the owner decides what to do at that time. Write whatever is
decided into the declaration. A withdrawn `session_context` consent also withholds that
evaluator's conditions answers from reads and the evidence export, so decide how their rows are handled before the reveal.

### Transcribe, verify and retain

Enter one evaluator at a time through the single recorder login and compare each column on screen with the paper
before saving, because a saved observation cannot be edited. Enter an ambiguous mark as blank plus a flag. A column
first smelled after the provisional 2-minute ceiling (counted from that evaluator's own spray of the blotter they smelled)
is entered with a `spray_to_smell_ceiling_exceeded` flag. Enter each evaluator's own spray time: it is their own and
differs between evaluators, and after a fresh blotter. Type the blind code from the paper column for each column: with
individual blotters the codes are per evaluator, so a sheet entered under the wrong evaluator is refused (409). Keep
the original sheets and slips, scan them, and store the scans outside the repository; the retention period is 12 months after
the evaluation ends, decided by the owner on 2026-11-25 (see below). Record each sheet's version id and the conditions slip's version id in the declaration.

### Individual blotters (F1)

Decided by the product owner on 2026-11-25; follow the [run sheet](../facilitated-run-sheet.md#individual-blotters-f1)
for the procedure. In short:

- **One blotter per evaluator per sample.** Each evaluator has their own tray of three coded blotters and sprays their
  own; you do not spray for them and do not write their times. You help the five keep their blotters, trays and sheets
  organized, enforce silence and clean air, and you do not evaluate during those sessions; your own evaluations run in
  separate sessions. Print the sheets with `scripts/make_spray_sheets.py` (individual mode is the default).
- **Ceiling.** The spray-to-first-smell ceiling is **2 minutes** from an evaluator's own spray to that evaluator's own
  first smell. It is provisional; P6.3 tests it. If an evaluator's window passes unsmelled, they spray a fresh blotter
  of the same sample (same blind code) and write the new spray time on their sheet.
- **Not the clean-air interval.** The 2 minute clean-air interval between samples (about 5 minutes after a persistent
  sample, ADR-005) is a different number and is unchanged.
- **No group flag.** No session carries `group_shared_blotter`, and pooled reliability has only the holder split.
- **Spray method.** One spray from about 15 cm (6 in), pointed away from faces and other blotters, the same for every
  blotter (owner decision, 2026-11-25); write the values in the declaration.
- **Group blotter mode is unused.** It was built and merged (#220, #221) and abandoned for F1 after the owner's
  physical attempt on 2026-11-25 got two evaluators through in two minutes. Do not enable it.

### Owner decisions for this variant (2026-11-25)

The owner decided on 2026-11-25: the scale wording is accepted, `would_buy` stays on the blind skin form, paper is kept
12 months after the evaluation ends and destroyed with the database and its backups, spray is one spray from about 15 cm,
no linked prediction is required per holdout, a withdrawn evaluator needs no code change (the household reveal waits
and the owner decides then), and no guardian clause is added to the consent text (the application is for the owner's
household only). The full record is in the [F1 gate](../planning/gates/f1.md). How each evaluator reaches the vial for
their own spray is not part of those decisions; confirm it in the P6.3 rehearsal and never show an evaluator a vial
number or any identity.

## Measure and close the workflow

Use the recommendation report with an explicit evaluator and UTC time window. Review population,
exclusions, denominators, algorithm versions, strategies, filters, and source snapshots before
export. Store exported evidence in the private P6 evidence directory after redaction review.

Record connectivity failures and manual recoveries in **Pilot operations**. Operational entries
must describe the user impact and recovery action without hostnames, credentials, tokens, blind
mappings, or private observations.

## Outage procedure

1. Confirm the outage from a second authorized device without bypassing Authentik.
2. Tell participants to stop submitting and switch to the
   [printed evaluation and outage form](../printable-evaluation-form.md).
3. Preserve blind codes, stages, elapsed minutes, and local times without adding identities.
4. Follow the owned alert and recovery procedure. Do not expose the API or database as a shortcut.
5. After recovery, verify readiness, enter each paper response once, and compare it with the
   signed paper record.
6. Record the failure and recovery events, then store the drill evidence privately.

## Before approving real testing

Review every P6 record, all known limitations, the participant instructions, backup and restore
results, and the target-device matrix. Only a signed `go` in the readiness record permits F1.
Any failed or missing item keeps the decision at `no-go` and returns the issue to its owning P
sprint. For the facilitated variant, the rehearsal must have run the paper plus transcription flow in the six-person
format (see the [P6 gate](../planning/gates/p6.md)).
