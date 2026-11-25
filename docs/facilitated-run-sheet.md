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
sample at a time. In **group blotter mode** (the F1 mode, decided 2026-11-25) the facilitator passes one physical
blotter per sample around the six evaluators; in **individual mode** each evaluator has their own tray of three coded
blotters. It pairs with the
[facilitated session sheet](facilitated-session-sheet.md) (version `facilitated-session-sheet v2.0`) and the
[conditions slip](facilitated-conditions-slip.md) (version `facilitated-conditions-slip v1.0`).

Everything here is a draft for the P6.3 rehearsal. Numbers marked **provisional** are confirmed or changed by that
rehearsal, and any change is recorded in the F1 pre-exposure declaration (see the [F1 gate](planning/gates/f1.md)).

## Two different numbers: do not conflate them

| Name | Value | From where to where | Source |
| :--- | :--- | :--- | :--- |
| **Spray-to-first-smell ceiling** | **2 minutes**, provisional (P6.3 tests it) | One blotter's spray to each evaluator's first smell of that blotter | Owner decision 2026-11-25 (replaces the earlier 5 minutes) |
| **Clean-air interval** | **At least 2 minutes**, about 5 minutes after a persistent or aversive sample | The last sniff of one sample to the first sniff of the next | ADR-005, unchanged |

The first limits how stale a blotter may be when someone smells it. The second limits carryover between samples. They
happen to share the figure 2; they are checked separately and written down separately.

## Checkpoint rule: no holdout is sprayed or smelled before its checkpoint exists

This is the one rule that cannot be repaired afterwards, so check it before the first holdout blotter of the program.

- **Group mode (`SHARED_GROUP`, the F1 mode).** Do not spray or smell any holdout blotter until the manager has created
  a checkpoint for **every enrollment in the program** (all six) and the manager's readiness view shows
  `holdouts_open_program_wide` true with `enrollments_missing_checkpoint` empty. One physical holdout blotter reaches
  all six evaluators, so a single missing checkpoint holds the holdouts back for everyone.
- **Individual mode.** Do not spray or smell an evaluator's holdout blotters until that evaluator's own checkpoint
  exists (`holdouts_open` true on that evaluator's readiness row).

Why: a holdout smelled on paper before its checkpoint exists cannot be made prospective afterwards. The server now
refuses holdout evidence whose times are earlier than the checkpoint that opened the holdouts, but it cannot know when
a blotter was physically smelled, so keeping to this order is a procedure the facilitator owns, not something the
application enforces. If a holdout is smelled early by mistake, do not transcribe it as if it were prospective: record
it in the deviation log and tell the manager before entering anything; no merged procedure covers this case.

Before the first holdout, write the **checkpoint-created time of every enrollment** in the F1 pre-exposure declaration
(see the [F1 gate](planning/gates/f1.md)). The readiness view shows which enrollments are missing a checkpoint but not
the time each was created, so note the clock time when the manager creates them.

## Roles and blinding

- The facilitator is the declared mapping holder. The facilitator retrieves the blind-to-identity mapping, labels and
  sprays the vials, writes spray times, collects sheets, transcribes them through the single recorder login, verifies
  them, and controls the household reveal. The facilitator is also an evaluator, so those rows are not blind: they
  are flagged non-blind, excluded from blind-baseline training, and retained in evaluation.
- Because the facilitator knows what is on every tray, this is single-blind with observer cues. Control the cues:
  neutral face, no comment on any sample, no hint when a blotter is handed over, the same handing-over routine for
  every blotter.
- The facilitator takes a seat in the fixed seat order and smells the same blotter by the same routine as everyone
  else, and fills in a sheet like everyone else. Do not look at the vial mapping while you are scoring. In individual
  mode the facilitator's own tray is sprayed and handed over by the same routine.
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

1. Show the paper sheet and a conditions slip, and walk through every row and scale, including that a circled zero is a
   real answer and that blank means "not answering".
2. Run one practice session of three non-pilot blotters on a practice sheet, with the same silence, timing and
   ranking rules.
3. Do not coach answers, do not say what a "good" rating looks like, and do not tell the evaluator what a sample
   was. Explain only what the rows mean.
4. Include everyone. There is no exclusion threshold for novices. Repeat consistency is reported descriptively, and
   six repeat pairs are not an individual reliability figure (ADR-005).

Record the consent in the application once, with the evaluator present, before session 1. The server stamps the time
and the choice persists until withdrawn. Do not ask for consent again at each sitting. Record the session-context
choice too; only evaluators who accepted it get a conditions slip.

## Room setup and ventilation

Eighteen blotters is six people times three, which is too strong a smell to have in the room at once. Group blotter
mode keeps one sprayed blotter in the room at a time (see the procedure below).

- Use a room with no competing odour: no cooking, candles, air fresheners, cleaning products, flowers or plug-ins on
  the day. Run ventilation (a window plus a fan, or an extractor) from at least 15 minutes before the first spray, and
  keep it running throughout.
- Seat evaluators apart, facing away from one another or behind simple screens, so nobody sees a face or a sheet. Allow
  roughly 1.5 m between seats. The blotter moves seat to seat in the fixed order: evaluators pass it on silently, or
  the facilitator carries it if the seats are too far apart (P6.3 decides which works inside 2 minutes). A table surface per person, a pen, the sheet on a clipboard, a clock visible to everyone.
- A lidded jar or sealed bag outside the room for finished blotters. In group blotter mode a blotter leaves the room as
  soon as the last evaluator has smelled it; in individual mode as soon as its column is initialed. Do not leave used
  blotters on the table.
- Water for comfort only. No coffee beans (ADR-005 removed them) and no sniffing own skin as a reset.
- Read the room thermometer and hygrometer at the start of each sitting; the readings go on the conditions slips.
- Everyone, facilitator included, wears no fragrance and no scented products that day. If anyone has, note it on that
  person's slip and tell nobody which sample may be affected.

## Who may be in the room

Only the six evaluators and the facilitator. No children, pets, visitors, observers or partners. No phones; phones
are left outside or switched off and put away. If anyone enters, treat it as an interruption (see below) and note it.

## Spray sheets

Generate the facilitator spray sheets and each evaluator's pre-printed header row of blind codes with
`scripts/make_spray_sheets.py` from a local mapping file. Its default output directory is `tmp_cleanup/spray-sheets/`,
which is gitignored and local-only. The spray sheets contain vial numbers and are facilitator-only. The per-evaluator
header files contain only blind codes, the blotter mode, the evaluator reference, a random paper record ID and the
sheet version. Run it with `--mode group` for group blotter mode (every evaluator may then hold the same code and
order for a sample; the spray sheet becomes one blotter per sample with the seat order and the 2 minute window) and
without it, or with `--mode individual`, for individual trays. Never
commit, upload or email the mapping file or the facilitator-only output. Print the header files and put the
facilitator sheets in a folder that stays with you.

## Group blotter mode (F1)

Decided by the product owner on 2026-11-25. Eighteen blotters smelling at once is too strong, so the facilitator
passes **one physical blotter per sample** around the six evaluators, **one blotter at a time**.

What this means for the sheets and the data:

- **Shared code.** Every evaluator holds the same blind code for a given sample, printed on every evaluator's header
  (the generator prints the same three codes in the same order on all six).
- **Same order for everyone.** Within a session all six evaluators smell the three samples in the same order. The
  per-session Latin-square rotation of the earlier plan is not used in this mode.
- **Accepted limitation.** Because the code and the order are shared, one evaluator can in principle see or infer
  that another is smelling the same sample, and the order and the seat position are confounded with the score.
  The owner accepts this. The scores are marked as **group-blotter scores** by the session flag `group_shared_blotter`
  (raised automatically at enrollment of a `SHARED_GROUP` program, so nothing is set at transcription). The flag is
  informational only: these scores **remain eligible for training**, and pooled reliability is reported both ways
  (with and without them). The flag lets that choice be reversed later.
- **Application support.** The application behaviour above (program `blotter_mode`, the
  `shared-triples-group-blotter-v1` enrollment algorithm, the flag and the 2 minute check) is implemented by merged
  code pull request #220, and by #221, which adds the server-side holdout and reveal safeguards described under
  [Checkpoint rule](#checkpoint-rule-no-holdout-is-sprayed-or-smelled-before-its-checkpoint-exists); see the
  [project plan](planning/PROJECT-PLAN.md#f1-facilitated-format-work-items-decided-2026-11-24) for its state.

### Seat order and who does what

- Fix one **seat order** (seat 1 to seat 6, the facilitator's own seat included) before the first session and use it
  for every sample in a session. Name it in the F1 pre-exposure declaration. Seat order is a private facilitator
  record; it is not printed on a sheet. (Whether to rotate it between sessions is an open owner decision, because the
  first seat always gets the freshest blotter.)
- The **facilitator sprays and times**. The facilitator writes the spray time (hh:mm:ss) and watches a clock visible
  to the facilitator.
- Evaluators write only their own first-smelled time and column details, and pass the blotter on in silence.

### The 2 minute window and the replacement blotter

The ceiling is **2 minutes from a blotter's spray to each evaluator's first smell** of that blotter. It is provisional;
P6.3 tests whether six people can rotate within it. Judge it at every hand-over:

1. Spray the blotter and write its spray time. Hand it to seat 1; each evaluator smells it once, writes the
   first-smelled time at once, and passes it to the next seat.
2. Before handing the blotter to the next evaluator, look at the clock. If that evaluator could not be expected to
   smell it within 2 minutes of its spray time, do not hand it over. Spray a **new blotter of the same sample** (the
   same blind code) and write the new spray time. That evaluator and every remaining evaluator smell the new blotter.
3. The new blotter has its own 2 minute window, counted from its own spray time. If it is again too slow, repeat.
4. **How it is written on paper.** The row **Time sprayed** on an evaluator's sheet is the spray time of the blotter
   *that evaluator smelled*. Evaluators who smelled the original have the original's spray time; evaluators who
   smelled a replacement have the replacement's later spray time. The blind code is the same on every sheet. Write
   each spray time on the sheets of the evaluators it applies to, and note the replacement in the deviation log
   (log it as information, not a failure: P6.3 needs to know how often it happened).
5. If the window is **missed anyway** (an evaluator first smells more than 2 minutes after the spray time of the
   blotter they smelled), the evaluator writes the true first-smelled time. Nothing is dropped, nothing is
   adjusted, and the blotter is not re-sprayed to repair that evaluator's column. The application raises the
   `spray_to_smell_ceiling_exceeded` flag when the time is entered; also note it in the deviation log. Then use the
   replacement rule for any evaluators who have not yet smelled.
6. In the application each evaluator's own sprayed time and first-smelled time must fall within 2 minutes of each
   other (that evaluator's own pair), which is why the sprayed time on the sheet must be the blotter they smelled.

## Order of operations for one session

There is no fixed elapsed interval beyond the ceiling and the clean-air interval. Record the actual times (sprayed,
first smelled, column finished) on the sheet. A breach is flagged as a deviation, not silently dropped.

| Step | Who | What | Time note |
| --- | --- | --- | --- |
| 1 | Facilitator | Ventilate the room; print sheets (with pre-printed shared codes and the blotter mode) and, for consenting evaluators, slips; set out six seats in the fixed seat order and the unsprayed blotter cards for the three samples, in the session's order, out of the room | Before anyone arrives |
| 2 | Evaluators | Sit in seat order, silence phones, complete the conditions slip alone if they accepted the consent, hand it back face down | Before the first spray |
| 3 | Facilitator | Read the room thermometer and hygrometer, file slips apart from sheets, start the clock | Write the date and start time |
| 4 | Facilitator | Sample 1: spray one blotter at the declared distance and count (the same for every blotter, fixed in the declaration), write the spray time, hand it to seat 1 by the same routine every time | Spray time, hh:mm:ss |
| 5 | Evaluators | Smell once, write the first-smelled time, pass the blotter to the next seat in silence, then complete the column and initial **Column complete** | Each first smell within 2 minutes of the spray time of the blotter smelled; otherwise the replacement rule |
| 6 | Facilitator | Apply the replacement rule at each hand-over; when the last evaluator has smelled, remove the blotter to the lidded jar outside the room | Note the time of the last sniff |
| 7 | Facilitator | Clean air: spray the next blotter only when every evaluator has initialed the previous column and the clean-air interval has passed since the last sniff | At least 2 minutes after the last sniff; about 5 after a persistent or aversive sample |
| 8 | Facilitator | Samples 2 and 3: repeat steps 4 to 7, one sample and one blotter at a time. Do not start the next spray while any evaluator is still writing | Same rules each round |
| 9 | Evaluators | Rank the samples in Part D, then hand the whole sheet to the facilitator and stay silent | Ranking after all three columns are initialed |
| 10 | Facilitator | Collect all six sheets, check each is complete enough to enter and that no column was changed after initials, then end the sitting | Note the end time |
| 11 | Facilitator | Hand over: say only that the sitting is finished and when the next one is. No discussion of any sample or score | Silence rules still apply |

An evaluator sniffs the blotter once, in their turn. Do not describe a blotter. Do not hint at a stronger or weaker
sample. Do not spray all three samples at the start: it breaks the window and the clean-air rule at once.

### Individual mode (not the F1 mode)

In individual mode each evaluator has their own tray of three coded blotters with their own codes and order, and the
facilitator sprays in rounds of one blotter per evaluator so the ceiling can hold for every column. The same 2 minute
ceiling applies from each blotter's spray to its evaluator's first smell, and the clean-air interval is unchanged.
Individual mode is the default in the application (`blotter_mode` `INDIVIDUAL`) and is kept for rehearsal and any
future program; F1 uses group blotter mode.

### Clean air

- Minimum 2 minutes of clean air between the last sniff of one sample and the first sniff of the next, as set by
  ADR-005. This is the clean-air interval and is not the spray-to-first-smell ceiling (also 2 minutes, a different
  thing; see the table at the top). In group blotter mode it runs from the last evaluator's sniff. Extend it to
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
- If an evaluator is interrupted before finishing a column, they tick **Interrupted**, the facilitator writes the time on
  the sheet, and the column is not redone with the same blotter. The facilitator never replaces or re-sprays a blotter to
  rescue an interrupted or undetected column. (The replacement blotter in group blotter mode is only for a blotter whose
  2 minute window would otherwise be missed for evaluators who have not yet smelled it.)
- If an evaluator cannot smell a sample, they circle **No** under Detected and leave the rest of that column blank. Do
  not suggest a second sniff, a different blotter, or a different technique. A sample that was not detected is left out
  of that evaluator's ranking.
- If any evaluator needs to step away (discomfort), pause the next spray, extend the clean-air interval, and note the
  time. In group blotter mode the whole room waits, because there is one blotter at a time; do not run ahead. In
  individual mode the other evaluators wait for the next round together.
- A breach of the 2 minute spray-to-first-smell ceiling is recorded as a deviation. The application raises the
  `spray_to_smell_ceiling_exceeded` flag itself when you type the first-smell time; the evidence is kept and nothing
  is dropped. Also keep the breach in the deviation log.

## Transcription window

All six sheets for a session must be captured in the application, and each stage locked, before the next session
starts. The gap of at least 3 hours between same-day sessions is the transcription window. If transcription is not
finished, the next sitting waits.

1. Enter one evaluator at a time through the single recorder login: confirm the enrollment and paper record ID, then
   type the blind code printed on the paper into the "Blind code printed on the sheet" box for each column. The
   application refuses to save when it is not the code of the sample on screen, so a mismatch means the wrong sheet or
   the wrong evaluator: stop and check. In group blotter mode the six sheets of a session carry the same codes, so the
   code alone no longer tells the evaluators apart: confirm the enrollment and the paper record ID first. The
   application cannot catch a sheet entered under the wrong evaluator in this mode, because every enrollment shares the
   blind code, so this check is yours.
2. Type the paper's spray time, first-smell time (asked once per sample) and column-finished time. The application
   stores the first smell as the presented time and the column-finished time as the observed time, and works out
   elapsed minutes as whole minutes from spray to column finished; you never type them. The session start, session
   end and ranking times are typed from the sheet in the same way. A time in the future, before the session existed or
   more than 7 days ago is refused as a probable typing error. The exact times stay on the paper.
3. Enter an ambiguous mark as blank plus a flag. Never guess. Type each evaluator's own **Time sprayed** from their
   own sheet: after a replacement blotter it differs between evaluators of the same session.
4. Consent is recorded once per evaluator, on their first session, with a note of where it was written (for example,
   signed on the paper sheet). Enter the conditions slip into the session-context form only for an evaluator who
   accepted it; later sessions never ask again.
5. A saved observation cannot be edited, so compare each column on screen with the paper before pressing Save, then
   complete Part E on sheet 2 (the facilitator sheet) and sign it.
6. Do not discuss what you just typed with anyone.

## Paper retention and scans

- The consent text says that answers "are kept while the evaluation runs and for 12 months after it ends. After that the
  evaluation database is deleted. When it is deleted, the manager also deletes every backup copy of it." No repository
  document sets a separate period for paper, so this run sheet applies the same period to the score sheets, the
  conditions slips and the scans, and the manager destroys them at the same time as the database and its backups
  (see [Backup and restore](deployment/backup-and-restore.md#retiring-the-evaluation-database)). Confirm this with the
  owner before F1; it is an inference, not a stated rule.
- After Part E is complete, scan every page of each evaluator's session sheet, all four pages (the session sheet is two
  duplex sheets: sheet 1 is the evaluator's Parts A to D, sheet 2 is the facilitator's Part E plus the instructions),
  and keep the originals. Clip sheet 2 behind that evaluator's sheet 1 (the paper record ID is in Part A on sheet 1) so
  the two stay together. Scans and originals are
  private evidence kept outside the repository. Keep slip scans in a different folder from sheet scans.
- Keep sheets and slips in separate folders at all times. Only the paper record ID links them.
- Never write an identity, role or mapping on a sheet, a scan or a filename.
- Keep the deviation log (ceiling breaches, talk, interruptions, room contamination) with the sheets, apart from
  the mapping.

## Household reveal

The reveal is a program-level event after every evaluator has finished baseline, repeats and holdouts. Until then,
no one is told what any sample was, even after their own session. The facilitator controls the reveal and announces it.
