---
title: "Facilitator run sheet for facilitated blind sessions"
schema_type: common
status: draft
owner: core-maintainer
purpose: "Give the facilitator one page of room setup, timing, silent-work and paper-handling rules for six-person sessions."
tags:
  - guide
  - evaluation
---

This is the facilitator's operating procedure for the six-evaluator format: six people working silently on paper, one
sample at a time, **each with their own blotters**. Each evaluator has their own tray of three coded blotters, sprays
their own blotter, and smells it themselves. The facilitator helps the other five keep their blotters, trays and sheets
organized and does not evaluate in those sessions. (A group blotter procedure, one blotter per sample passed round all
six, was tried physically on 2026-11-25 and abandoned: it got two evaluators through in two minutes. See
[Group blotter mode: built, not used](#group-blotter-mode-built-not-used).) It pairs with the
[facilitated session sheet](facilitated-session-sheet.md) (version `facilitated-session-sheet v3.0`) and the
[conditions slip](facilitated-conditions-slip.md) (version `facilitated-conditions-slip v1.0`).

Everything here is a draft. The P6.3 rehearsal was waived by the owner on 2026-11-27 (F1 gate sign-off 18; a waiver,
not a pass), so nothing in this run sheet has been rehearsed in the six-person format, and sheet v3.0 has never been
used in any rehearsal. Numbers marked **provisional** have not been confirmed by a rehearsal; any change is recorded in
the F1 pre-exposure declaration (see the [F1 gate](planning/gates/f1.md)).

## Sheet v3.0 in one page

Sheet v3.0 is one generic Letter sheet printed double-sided (flip on the long edge) and used for any session and any
evaluator. Nothing per session or per evaluator is pre-printed. The facilitator prints one copy per evaluator per
session from the same master (six evaluators times 17 sessions is 102 copies). What changed from v2.2, and what each
change means at the table and at transcription:

| Topic | Under v3.0 |
| :--- | :--- |
| Header | Handwritten: **Session ___ of ___** (both numbers), **Evaluator reference**, **Paper record ID**, and the three sample codes. The back repeats small boxes for the same fields. Blotter mode **Individual trays** is pre-ticked |
| Codes | The code of a sample is the label on its atomizer (for example `B32`). The evaluator writes it in the column; it is not pre-printed. See [Codes](#individual-blotters-f1) |
| Not detected | There is no Detected row. **Intensity 0 means not detected.** The evaluator circles Intensity 0, writes the times, initials the column and leaves the rest of the column blank. See [Silent work and interruptions](#silent-work-and-interruptions) |
| Skip reasons | There is no "Not answering because" box. An empty column with no Intensity circled gets a one-line facilitator margin note, and the transcriber chooses `skipped`, `unable_to_assess` or `interrupted` from it |
| Ranking opt-outs | **I would rather not rank** is entered as `skipped`; **I could not tell them apart** is entered as `unable_to_assess` |
| Consent and data classification | Not on the sheet. Consent is recorded once per evaluator in the evaluator packet (see [Evaluator packet and one-time handouts](#evaluator-packet-and-one-time-handouts)) |
| Facilitator reconciliation | There is no Part E. A compact per-evaluator tracker is proposed in its place, pending owner confirmation (see [Facilitator tracker](#facilitator-tracker-proposal)) |
| Extra paper answers | Would wear, would buy, type of event and season are asked on the sheet and are **scanned and retained, not keyed in F1** (see [Paper-only answers](#paper-only-answers-scanned-not-keyed)) |

## Two different numbers: do not conflate them

| Name | Value | From where to where | Source |
| :--- | :--- | :--- | :--- |
| **Spray-to-first-smell ceiling** | **2 minutes**, provisional (P6.3 tests it) | An evaluator's own spray of their own blotter to that evaluator's own first smell of it | Owner decision 2026-11-25 (replaces the earlier 5 minutes; kept at 2 minutes after the group attempt, now per own blotter) |
| **Clean-air interval** | **At least 2 minutes**, about 5 minutes after a persistent or aversive sample | The last sniff of one sample to the first sniff of the next | ADR-005, unchanged |

The first limits how stale a blotter may be when its own evaluator smells it. The second limits carryover between samples. They
happen to share the figure 2; they are checked separately and written down separately.

## Checkpoint rule: no holdout is sprayed or smelled before its checkpoint exists

This is the one rule that cannot be repaired afterwards, so check it before the first holdout blotter of the program.

**What the server does (individual blotters, verified in `disclosure_gate.py`).** The holdout gate is **per
enrollment**: an evaluator's holdout samples open only when that evaluator's own checkpoint exists, and the server
refuses a holdout exposure, observation, lock, session start or ranking for an evaluator who has none (409). It also
refuses (422) an explicit evidence time on a holdout that is earlier than that evaluator's own latest checkpoint. The
manager's readiness view shows `holdouts_open` on each evaluator's row; use that row value. In an individual program
`holdouts_open_program_wide` is always false and `enrollments_missing_checkpoint` only lists who has no checkpoint yet:
neither of them gates anything.

**What the facilitator does.** The six evaluators sit the same sitting together, so the server's per-evaluator gate is
not enough on its own: an evaluator without a checkpoint who smells a holdout at the table has smelled it too early,
and the server will then refuse to record it. Do not run a holdout sitting until the manager has created a checkpoint
for **every one of the six** and `holdouts_open` is true on all six rows. This is a procedure the facilitator owns, not
something the application enforces for the group. The facilitator's own evaluator enrollment is one of the six.

Why: a holdout smelled on paper before its checkpoint exists cannot be made prospective afterwards. The server cannot
know when a blotter was physically smelled, so keeping to this order is a procedure. If a holdout is smelled early by
mistake, do not transcribe it as if it were prospective: record it in the deviation log and tell the manager before
entering anything; no merged procedure covers this case.

Before the first holdout, write the **checkpoint-created time of every enrollment** in the F1 pre-exposure declaration
(see the [F1 gate](planning/gates/f1.md)). The readiness view shows which enrollments are missing a checkpoint but not
the time each was created, so note the clock time when the manager creates them. When the program's reveal policy is
`HOUSEHOLD` (the owner's plan for F1; the server allows it with individual blotters), a checkpoint is also refused
until that evaluator's baseline blotters and planned skin tests are locked, and the single program-level reveal waits
until all six have finished baseline, checkpoint and holdouts.

## Roles and blinding

- The facilitator is the declared mapping holder. The facilitator retrieves the blind-to-identity mapping, prepares the
  coded blotters for each evaluator's tray, helps the other five keep their blotters, trays and sheets organized,
  enforces silence and the clean-air interval, collects sheets, transcribes them through the single recorder login,
  verifies them, and controls the household reveal. **The facilitator does not evaluate during those sessions.**
- The facilitator's own evaluations run in **separate sessions**, with the same sheet, the same ceiling and the same
  routine. Because the facilitator knows what is on every tray, those are single-blind with observer cues: the rows are
  flagged non-blind, excluded from blind-baseline training, and retained in evaluation. Do not look at the vial mapping
  while you are scoring.
- Because the facilitator knows what is on every tray, control the cues in the five evaluators' sessions too: neutral
  face, no comment on any sample, no hint when a blotter card is handed over, the same handing-over routine for every
  blotter.
- Each evaluator sprays their own blotter and writes their own spray time and first-smelled time. The facilitator does
  not spray for them and does not write their times.
- The identity mapping and the facilitator spray sheets never enter an evaluator's sight and never enter the repository
  (see [Spray sheets](#spray-sheets)).

## Calendar limits

- At most 6 blotters per evaluator per day, which is two sessions of three.
- Same-day sessions are at least 3 hours apart. The ADR-005 amendment sets 3 hours as the minimum; longer is fine.
- Seventeen sessions at two per day need at least 9 test days; plan the calendar from that, not from the room.
- Facilitated sessions have no skin tests. A skin test is a separate optional path, one new application per evaluator
  per day, on its own day. For F1 only the facilitator does skin tests; the five other evaluators are skin-absent by
  design.

## Before the first session: novices

Three of the six evaluators are new to fragrance. Familiarise them on a day before their first pilot session, using
non-pilot samples only (never a fragrance from the pilot set, so that nothing in the pilot is spoiled or recognised
afterwards):

1. Show the paper sheet and a conditions slip, and walk through every row and scale, including that **Intensity 0 means
   not detected** (circle it and leave the rest of the column blank) and that a circled zero on any other row is a
   real answer. Hand each novice the rules card and the property guide (see
   [Evaluator packet and one-time handouts](#evaluator-packet-and-one-time-handouts)). Explain only what the rows mean;
   do not add examples or say what a typical score looks like.
2. Run one practice session of three non-pilot blotters on a practice sheet, with the same silence, timing and
   ranking rules.
3. Do not coach answers, do not say what a "good" rating looks like, and do not tell the evaluator what a sample
   was. Explain only what the rows mean.
4. Include everyone. There is no exclusion threshold for novices. Repeat consistency is reported descriptively, and
   six repeat pairs are not an individual reliability figure (ADR-005).

Record the consent in the application once, with the evaluator present, before session 1. The server stamps the time
and the choice persists until withdrawn. Do not ask for consent again at each sitting. Record the session-context
choice too; only evaluators who accepted it get a conditions slip. Also record it once on paper in the evaluator packet
(see below); the session sheet carries no consent field.

## Evaluator packet and one-time handouts

Each evaluator has a packet kept by the facilitator, apart from the sheets and the mapping. It holds:

- **The consent record, written once.** Consent version, date, who consented, and the guardian where one is required.
  This is the single paper record of consent. It is not repeated on any session sheet. The application wizard requires
  a **consent note** for each session at transcription; the facilitator copies the packet's note (for example the
  version, the date and where it is written) into it every time, and does not ask the evaluator again.
- **The rules card**, given to the evaluator **once**, at the start, before session 1. It is not handed out per session.
- **The property guide** (`facilitated-property-guide v1.0`), given **once** in the same way. It stays a reading aid and
  adds no recorded field.

The rules card and property guide are one-time handouts; sessions are run with the generic sheet alone.

## Room setup and ventilation

Each evaluator sprays one blotter at a time, so up to six sprayed blotters are in the room at once, a stronger room
than a single shared blotter would give. Ventilation and prompt removal of used blotters carry the weight here.

- Use a room with no competing odour: no cooking, candles, air fresheners, cleaning products, flowers or plug-ins on
  the day. Run ventilation (a window plus a fan, or an extractor) from at least 15 minutes before the first spray, and
  keep it running throughout.
- Seat evaluators apart, facing away from one another or behind simple screens, so nobody sees a face or a sheet. Allow
  roughly 1.5 m between seats. Each seat has a table surface, a pen, the sheet on a clipboard, the evaluator's own tray
  of three coded blotters, and a clock visible to everyone. Sprays point away from faces and from other blotters.
- A lidded jar or sealed bag outside the room for finished blotters. A blotter leaves the room as soon as its column is
  initialed. Do not leave used blotters on the table.
- Water for comfort only. No coffee beans (ADR-005 removed them) and no sniffing own skin as a reset.
- Room readings are optional and never block a sitting. If a room thermometer is at hand, read it at the start of each
  sitting and write the temperature on the conditions slips. A hygrometer is not needed: leave the humidity row blank
  when there is no reading. An empty row is a valid answer, so do not estimate or guess a value.
- Everyone, facilitator included, wears no fragrance and no scented products that day. If anyone has, note it on that
  person's slip and tell nobody which sample may be affected.

## Who may be in the room

Only the six evaluators and the facilitator are in the room: no onlookers, visitors, pets or partners. The evaluators
themselves may be children or adults. No phones; phones are left outside or switched off and put away. If anyone enters, treat it as an interruption (see below) and note it.

## Spray sheets

Generate the facilitator spray sheets with `scripts/make_spray_sheets.py` from a local mapping file. Every mapping row
needs the `atomizer` column (the label printed on the container, for example `B07` or `H03`); the tool rejects a mapping
where a vial has two atomizers or one atomizer serves two vials. Its default output directory is
`tmp_cleanup/spray-sheets/`, which is gitignored and local-only. The spray sheets contain vial numbers and are
facilitator-only. Under sheet v3.0 the evaluator's sheet is a generic form with nothing pre-printed, so the per-evaluator
pre-printed header files of sheet v2.2 are not part of the sheet; the evaluator writes the code, which is the atomizer
label, in the column. What the generator emits for the v3.0 workflow is owned by the sheet and tooling change set, so
check the script's `--help` rather than this page. Run it without `--mode`, or with `--mode individual`, for individual
trays (this is the F1 mode). The `--mode group` option is kept for the unused group blotter mode. Never commit, upload or
email the mapping file or the facilitator-only output. Put the facilitator sheets in a folder that stays with you.

## Individual blotters (F1)

Decided by the product owner on 2026-11-25, after the group blotter procedure was tried physically and abandoned (see
[Group blotter mode: built, not used](#group-blotter-mode-built-not-used)). Everyone does the procedure on their own;
the facilitator helps the other five keep their blotters, trays and sheets organized and does not evaluate in those
sessions.

What this means for the sheets and the data (verified in `shared_triples.py` and `calibration_service.py`):

- **Codes.** The program's blotter mode is `INDIVIDUAL` (the application default). Enrollment by default draws a random
  blind code per evaluator per sample, unique across the database, but for the F1 program `v3.2` the owner decided on
  2026-11-27 that all six evaluators see **one shared code per physical sample, equal to the label on the atomizer**
  (B01 to B39 and H01 to H10), with the repeats keeping their own distinct codes so a repeat stays hidden (F1 gate
  sign-off 19 and the [ADR-005 note](planning/adr/adr-005-controlled-calibration.md#2026-11-27-note-shared-blind-codes-equal-to-the-atomizer-label-in-the-f1-program)).
  So a code names a sample, not an evaluator: the six sheets for one session carry the same three codes, in
  different orders. The server's blind-code check therefore cannot catch a sheet entered under the wrong evaluator; that
  check is procedural (see [Transcription window](#transcription-window)).
- **Enrollment algorithm.** For the six to smell the same three samples in a sitting, enroll them with
  `shared-triples-latin-rotation-v1`: every evaluator receives the same sessions in the same session order, and the
  order inside each session is a Williams balanced Latin-square row chosen by that evaluator's enrollment ordinal and
  the session number, so across six evaluators each sample sits in each position twice per session of three. That
  algorithm refuses the readable `E01-S1-2` labels, because the session number in a readable label would name which
  evaluators hold the same fragrance. The default independent shuffle (`system-random-shuffle-v1`) gives each evaluator
  different sessions and is not suited to a shared sitting. The manager chooses the algorithm at enrollment; every
  enrollment of a program must use the same shared algorithm, and the blotter mode is locked once an evaluator is
  enrolled.
- **Seat positions.** The per-evaluator order differs, so which sample an evaluator smells first is not tied to a seat
  or to what the neighbour is smelling.
- **No group flag.** The `group_shared_blotter` session flag is raised only for group blotter mode, so none of these
  sessions carries it, and every ordinary eligibility rule applies unchanged.
- **Reveal.** Reveal policy `HOUSEHOLD` is allowed with individual blotters (the owner's plan): all six finish baseline,
  checkpoints and holdouts, then one program-level reveal.

### Who does what

- Each **evaluator** sprays their own blotter for the current sample, writes their own spray time (hh:mm:ss), smells it
  once, writes their own first-smelled time, completes the column and initials it. Nobody passes a blotter to anyone.
- The **facilitator** helps keep blotters, trays and sheets organized and in the right order, keeps the clock, signals
  each round, enforces silence and the clean-air interval, and removes finished blotters to the jar. The facilitator
  does not score and does not write an evaluator's times.
- **Spray method (owner decision, 2026-11-25):** one spray from about 15 cm (6 in), pointed away from faces and other
  blotters, the same for every blotter. This is an instruction to each evaluator. The values are written in the F1
  pre-exposure declaration.
- **Vial access (owner decision, 2026-11-26):** evaluators walk up to the vials as they are ready to spray their own
  blotter. The facilitator does not schedule or control turns at the vials. The facilitator still helps keep blotters
  and sheets organized and does not evaluate in these sessions. Evaluators see only the atomizer label printed on
  the container, which is also the code they write, never a vial number, brand, name or other identity; the
  facilitator-only spray sheets keep the vial and the mapping private. The evaluator reads the code on the coded blotter
  in their tray, finds the atomizer with the same label, sprays from it, and writes that code in the column.
  Because the spray time is each evaluator's own, the 2 minute rule below applies unchanged: if an evaluator misses the
  window, they spray a fresh blotter of the same sample. P6.3 observes this: how often evaluators queued or crowded at
  the vials, and how many fresh blotters were needed. If the walk-up approach had to be changed, note it in the
  rehearsal log; that would be a new owner decision.

### The 2 minute window and the fresh blotter

The ceiling is **2 minutes from an evaluator's own spray to that evaluator's own first smell**. It is provisional; P6.3
tests whether it holds for all six evaluators and how often a fresh blotter was needed.

1. The evaluator sprays their own blotter, writes the spray time, and smells it at once, writing the first-smelled
   time.
2. If an evaluator's 2 minutes pass before they have smelled that blotter, they do not smell it: they spray a **fresh
   blotter of the same sample** (the same blind code) and write the new spray time. The new blotter has its own 2
   minute window, counted from its own spray. Note each fresh blotter in the deviation log as information, not a
   failure: P6.3 needs to know how often it happened.
3. **How it is written on paper.** The row **Time sprayed** on an evaluator's sheet is the spray time of the blotter
   *that evaluator smelled*, in their own hand. The blind code is unchanged.
4. If the window is **missed anyway** (the evaluator smelled more than 2 minutes after the spray time of the blotter
   they smelled), they write the true first-smelled time and tell the facilitator. Nothing is dropped, nothing is
   adjusted, and the blotter is not re-sprayed to repair that column. The application raises the
   `spray_to_smell_ceiling_exceeded` flag when the time is entered; also note it in the deviation log.
5. In the application each evaluator's own sprayed time and first-smelled time must fall within 2 minutes of each
   other, which is why the sprayed time on the sheet must be the blotter they smelled.

## Order of operations for one session

There is no fixed elapsed interval beyond the ceiling and the clean-air interval. Record the actual times (sprayed,
first smelled, column finished) on the sheet. A breach is flagged as a deviation, not silently dropped.

| Step | Who | What | Time note |
| --- | --- | --- | --- |
| 1 | Facilitator | Ventilate the room; set out six seats, each with a blank v3.0 sheet on a clipboard (two sides, nothing pre-printed except Individual trays ticked) and the evaluator's own tray of three unsprayed coded blotters in that evaluator's session order; slips for consenting evaluators | Before anyone arrives |
| 2 | Evaluators | Sit, silence phones, complete the conditions slip alone if they accepted the consent, hand it back face down. Both sides of the sheet carry the handwritten `Session ___ of ___` (both numbers), Evaluator reference and Paper record ID, written before the first spray; the evaluator writes the three codes in the code boxes as each sample comes up | Before the first spray |
| 3 | Facilitator | Read the room thermometer if there is one (optional; humidity may stay blank), file slips apart from sheets, start the clock | Write the date and start time |
| 4 | Evaluators | On the facilitator's signal (proposed pacing, P6.3 confirms), each sprays their own blotter for sample 1 as instructed (owner decision 2026-11-25: one spray from about 15 cm, away from faces and other blotters, the same for every blotter; written in the declaration), and writes their own spray time | Spray time, hh:mm:ss, in their own hand |
| 5 | Evaluators | Smell once, write the first-smelled time, then complete the column and initial **Column complete** | Own first smell within 2 minutes of own spray; otherwise the fresh-blotter rule |
| 6 | Facilitator | Help anyone whose blotter, tray or sheet is out of order; apply the fresh-blotter rule where an evaluator's window has passed unsmelled; as each column is initialed, remove that blotter to the lidded jar outside the room | Note the time of the last sniff in the round |
| 7 | Facilitator | Clean air: signal the next round only when every evaluator has initialed the previous column and the clean-air interval has passed since the last sniff in the round | At least 2 minutes after the last sniff; about 5 after a persistent or aversive sample |
| 8 | Evaluators and facilitator | Samples 2 and 3: repeat steps 4 to 7, one sample and one blotter each at a time. Nobody sprays the next blotter while anyone is still writing | Same rules each round |
| 9 | Evaluators | Turn the sheet over, fill in the notes and the paper-only answers on the back, rank the samples (or tick one of the two ranking opt-outs), write the sitting times, then hand the whole sheet to the facilitator and stay silent | Ranking after all three columns are initialed |
| 10 | Facilitator | Collect all six sheets, check each is complete enough to enter and that no column was changed after initials, add a one-line margin note for any empty column with no Intensity circled, update the tracker, then end the sitting | Note the end time |
| 11 | Facilitator | Hand over: say only that the sitting is finished and when the next one is. No discussion of any sample or score | Silence rules still apply |

An evaluator sniffs their blotter once. Do not describe a blotter. Do not hint at a stronger or weaker sample. Do not
spray all three samples at the start: it breaks the window and the clean-air rule at once.

The facilitator's own evaluations are not part of these sittings. They run in separate sessions, one evaluator, same
sheet and rules, flagged non-blind.

### Clean air

- Minimum 2 minutes of clean air between the last sniff of one sample and the first sniff of the next, as set by
  ADR-005. This is the clean-air interval and is not the spray-to-first-smell ceiling (also 2 minutes, a different
  thing; see the table at the top). It runs from the last sniff in the round by any evaluator. Extend it to
  about 5 minutes after a persistent or aversive sample (a persistent stimulus, an evaluator scoring Discomfort high,
  or one who stepped away). The facilitator spray sheet can mark a vial as persistent so the
  longer interval is not forgotten.
- ADR-005 asks for at most one exceptionally persistent or animalic stimulus per session. This is a composition
  matter for the manager and the enrollment template, not something to decide at the table.
- Clean air means no blotters in the room and ventilation on. Evaluators stay seated and silent.

## Silent work and interruptions

- No talk about samples, scores, reactions or guesses, to anyone, until the household reveal. That includes in the
  corridor, in the kitchen, between sessions and on the way home.
- If someone talks, stop the round, note the time and what was said in the deviation log without correcting anyone,
  and flag the sheets that may be affected. Do not discard data.
- If an evaluator is interrupted before finishing a column, the column is left as it is and is not redone with the same
  blotter; the facilitator writes a one-line margin note saying so (see the next rule). Nobody replaces or re-sprays a
  blotter to rescue an interrupted or undetected column. (The fresh blotter is only for a blotter whose own 2 minute
  window passed before its evaluator smelled it.)
- **Intensity 0 means not detected.** If an evaluator cannot smell a sample, they circle **0** on the Intensity row
  ("0 not detected, 5 overpowering"), write the times, initial the column and leave the rest of that column blank. Do
  not suggest a second sniff, a different blotter, or a different technique. A sample that was not detected is left out
  of that evaluator's ranking. A circled 0 on any other row remains a real answer. There is no Detected row.
- **Empty column, no Intensity circled.** The sheet no longer has a "Not answering because" box. The facilitator writes a
  one-line margin note (why) on the sheet or in the tracker, without asking the evaluator to explain more. The
  transcriber chooses `skipped`, `unable_to_assess` or `interrupted` from that note. Do not guess: if the note does not
  decide it, ask the manager before entering.
- If any evaluator needs to step away (discomfort), pause the next round, extend the clean-air interval, and note the
  time. The other evaluators wait for the next round together; nobody runs ahead.
- A breach of the 2 minute spray-to-first-smell ceiling is recorded as a deviation. The application raises the
  `spray_to_smell_ceiling_exceeded` flag itself when you type the first-smell time; the evidence is kept and nothing
  is dropped. Also keep the breach in the deviation log.

## Transcription window

All six sheets for a session must be captured in the application, and each stage locked, before the next session
starts. The gap of at least 3 hours between same-day sessions is the transcription window. If transcription is not
finished, the next sitting waits.

1. Enter one evaluator at a time through the single recorder login: confirm the enrollment and paper record ID, then
   type the code handwritten on the paper into the "Blind code printed on the sheet" box for each column. **Key the
   columns in the app's position order** (the order of the evaluator's schedule on screen, which is the column order on
   the sheet); the typed code is only a confirmation. The application refuses to save when it is not the code of the
   sample on screen (409, no override), so a mismatch means a mis-written code, columns taken out of order, or the
   wrong sheet: stop and check. In program `v3.2` the codes are shared by all six evaluators, so the guard cannot catch
   a sheet entered under the wrong evaluator; that check is procedural: one recorder, one evaluator's stack at a time,
   and the evaluator reference and paper record ID on the sheet compared with the enrollment on screen before saving.
2. Type the paper's spray time, first-smell time (asked once per sample) and column-finished time. The application
   stores the first smell as the presented time and the column-finished time as the observed time, and works out
   elapsed minutes as whole minutes from spray to column finished; you never type them. The session start, session
   end and ranking times are typed from the sheet in the same way. A time in the future, before the session existed or
   more than 7 days ago is refused as a probable typing error. The exact times stay on the paper.
3. Enter an ambiguous mark as blank plus a flag. Never guess. Type each evaluator's own **Time sprayed** from their
   own sheet: it is that evaluator's own spray, so it differs between evaluators and after a fresh blotter.
4. **Circled Intensity 0.** Enter it as detected **No**: the application stores detected false, intensity 0, liking
   empty and response status `not_detected`, and the rest of the column stays empty. This is the existing rule, so no
   application change is involved. A circled 0 on any other row is entered as a real answer.
5. **Empty column, no Intensity circled.** Choose `skipped`, `unable_to_assess` or `interrupted` from the facilitator's
   margin note. **Ranking opt-outs:** "I would rather not rank" is entered as `skipped` and "I could not tell them
   apart" as `unable_to_assess`.
6. **Consent note.** The wizard asks for a consent note for each session. Copy it from the consent record in the
   evaluator's packet; it is not on the sheet. Enter the conditions slip into the session-context form only for an
   evaluator who accepted it; later sessions never ask again.
7. A saved observation cannot be edited, so compare each column on screen with the paper before pressing Save. Then
   update the evaluator's row in the tracker.
8. Do not discuss what you just typed with anyone.

### Paper-only answers (scanned, not keyed)

For F1 the following are asked on the sheet, **scanned and retained, and not entered in the application**:

- **Would wear** and **would buy** (0 to 10). The application already accepts both at the blotter stage, but the blotter
  form does not ask them, and F1 keys them only after F1.
- **Type of event** and **season.** The application refuses both at the blotter stage (they are skin-stage fields).
- **Time zone, recorder initials and the paper record ID.** These are scan provenance and are not stored by the
  application.

Do not key these, do not estimate them and do not discuss them. Capture changes after F1, does not gate P6 or F1, and
is planned in [PROJECT-PLAN.md section 11a](planning/PROJECT-PLAN.md#post-f1-follow-up-blotter-stage-would-wear-would-buy-and-event-type-capture-proposed-2026-11-27)
as a Proposed item. Whether the consent wording covers opinions about wearing, buying, events and seasons is an open
owner question; this run sheet does not settle it.

### Facilitator tracker (proposal)

**Proposal, pending owner confirmation.** In place of the per-session Part E reconciliation of sheet v2.2, keep one
small tracker per evaluator, apart from the sheets and the mapping, with one row per session and these columns: sheet
printed, sheet completed, scanned, transcribed, checked, margin notes. It carries no answers, no code-to-fragrance data
and no identity. Until the owner confirms it, the facilitator may keep these ticks in any equivalent private list; the
sheet v3.0 itself has no reconciliation section.

## Paper retention and scans

- The consent text says that answers "are kept while the evaluation runs and for 12 months after it ends. After that the
  evaluation database is deleted. When it is deleted, the manager also deletes every backup copy of it." No repository
  document sets a separate period for paper, so this run sheet applies the same period to the score sheets, the
  conditions slips and the scans, and the manager destroys them at the same time as the database and its backups
  (see [Backup and restore](deployment/backup-and-restore.md#retiring-the-evaluation-database)). The owner confirmed this
  period on 2026-11-25 (see the [F1 gate](planning/gates/f1.md)).
- After transcription and the check, scan both sides of each evaluator's session sheet (sheet v3.0 is one sheet printed
  double-sided, so two images per session) and keep the originals. The paper-only answers (would wear, would buy, type
  of event, season) exist only on these scans and originals, so scan the back as carefully as the front. Scans and
  originals are private evidence kept outside the repository. Keep slip scans in a different folder from sheet scans.
- Keep sheets and slips in separate folders at all times. Only the paper record ID links them.
- Never write an identity, role or mapping on a sheet, a scan or a filename.
- Keep the deviation log (ceiling breaches, talk, interruptions, room contamination) with the sheets, apart from
  the mapping.

## Household reveal

The reveal is a program-level event after every evaluator has finished baseline, repeats and holdouts. Until then,
no one is told what any sample was, even after their own session. The facilitator controls the reveal and announces it.
The application allows the `HOUSEHOLD` reveal policy with individual blotters (verified in `disclosure_gate.py` and
`api/calibration.py`); the manager's readiness view reports `household_reveal_ready` once all six enrollments have
finished baseline, a checkpoint and their holdouts.

## Group blotter mode: built, not used

A group blotter mode (program `blotter_mode` `SHARED_GROUP`, one blotter per sample passed around the six evaluators,
shared blind codes, one shared order, the `group_shared_blotter` session flag and the server-side group safeguards of
pull requests #220 and #221) is merged in the application and **not used by F1**. On 2026-11-25 the owner tried the
procedure physically and could get through only two evaluators in two minutes, so F1 returned to one blotter per
evaluator. The code is retained, unused, and individual blotters remain the application default. The spray-sheet
generator still accepts `--mode group` for the same reason. Nothing on the printed sheet refers to it other than the
**Group blotter** option of the **Blotter mode** line, shown as not used.
