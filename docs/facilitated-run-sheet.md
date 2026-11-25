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

This is the facilitator's operating procedure for the six-evaluator format: six people, each with their own tray of
three coded blotters, working silently and at the same time, on paper. It pairs with the
[facilitated session sheet](facilitated-session-sheet.md) (version `facilitated-session-sheet v1.0`) and the
[conditions slip](facilitated-conditions-slip.md) (version `facilitated-conditions-slip v1.0`).

Everything here is a draft for the P6.3 rehearsal. Numbers marked **provisional** are confirmed or changed by that
rehearsal, and any change is recorded in the F1 pre-exposure declaration (see the [F1 gate](planning/gates/f1.md)).

## Roles and blinding

- The facilitator is the declared mapping holder. The facilitator retrieves the blind-to-identity mapping, labels and
  sprays the vials, writes spray times, collects sheets, transcribes them through the single recorder login, verifies
  them, and controls the household reveal. The facilitator is also an evaluator, so those rows are not blind: they
  are flagged non-blind, excluded from blind-baseline training, and retained in evaluation.
- Because the facilitator knows what is on every tray, this is single-blind with observer cues. Control the cues:
  neutral face, no comment on any sample, no hint when a blotter is handed over, the same handing-over routine for
  every blotter.
- The facilitator's own tray is sprayed and handed to the facilitator by the same routine, and the facilitator fills in
  a sheet like everyone else. Do not look at the vial mapping for your own tray while you are scoring it.
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

Eighteen blotters is six people times three. Limit how many are in the room at once (see the round procedure below).

- Use a room with no competing odour: no cooking, candles, air fresheners, cleaning products, flowers or plug-ins on
  the day. Run ventilation (a window plus a fan, or an extractor) from at least 15 minutes before the first spray, and
  keep it running throughout.
- Seat evaluators apart, facing away from one another or behind simple screens, so nobody sees a face or a sheet. Allow
  roughly 1.5 m between seats. A table surface per person, a pen, the sheet on a clipboard, a clock visible to everyone.
- A lidded jar or sealed bag outside the room for finished blotters. A finished blotter leaves the room as soon as
  its column is initialed; do not leave used blotters on the table.
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
header files contain only blind codes, the evaluator reference, a random paper record ID and the sheet version. Never
commit, upload or email the mapping file or the facilitator-only output. Print the header files and put the
facilitator sheets in a folder that stays with you.

## Order of operations for one session

The ceiling from spray to first smell is **provisional 5 minutes**, confirmed in P6.3. There is no fixed elapsed
interval beyond that. Record the actual times (sprayed, first smelled, column finished) on the sheet. A breach is
flagged as a deviation, not silently dropped, and the sample is not re-sprayed to fix the time.

Because six blotters in a round are all handed out together and each evaluator moves at their own pace, spray one
round at a time (one blotter per evaluator) so the 5-minute ceiling can hold for every column. Spraying all 18
blotters at the start would make the second and third columns breach the ceiling by design; confirm the round
method, or a different one, in P6.3 before F1.

| Step | Who | What | Time note |
| --- | --- | --- | --- |
| 1 | Facilitator | Ventilate the room; print sheets (with pre-printed codes) and, for consenting evaluators, slips; lay out six trays with the three coded, unsprayed blotter cards in each evaluator's own order | Before anyone arrives |
| 2 | Evaluators | Sit, silence phones, complete the conditions slip alone if they accepted the consent, hand it back face down | Before the first spray |
| 3 | Facilitator | Read the room thermometer and hygrometer, file slips apart from sheets, start the clock | Write the date and start time |
| 4 | Facilitator | Round 1: spray the first blotter of every tray at a fixed distance and count (the same for every blotter, fixed in the declaration), write the sprayed time on each sheet, hand each blotter over by the same routine | Spray time per blotter, hh:mm:ss |
| 5 | Evaluators | Smell at once, write the first-smelled time, complete the column, initial **Column complete**, hand the blotter back | Within the 5-minute provisional ceiling |
| 6 | Facilitator | Remove used blotters to the lidded jar outside the room, then wait for clean air | At least 2 minutes after the last sniff; about 5 after a persistent or aversive sample |
| 7 | Facilitator | Rounds 2 and 3: repeat steps 4 to 6. An evaluator who is still writing keeps their sheet; do not start their next spray until their previous column is initialed | Same rules each round |
| 8 | Evaluators | Rank the samples in Part D, then hand the whole sheet to the facilitator and stay silent | Ranking after all three columns are initialed |
| 9 | Facilitator | Collect all six sheets, check each is complete enough to enter and that no column was changed after initials, then end the sitting | Note the end time |
| 10 | Facilitator | Hand over: say only that the sitting is finished and when the next one is. No discussion of any sample or score | Silence rules still apply |

At each round, an evaluator sniffs only their own blotter. Do not describe a blotter. Do not hint at a stronger or
weaker sample.

### Clean air

- Minimum 2 minutes of clean air between the last sniff of one sample and the first sniff of the next, as set by
  ADR-005. Extend it to about 5 minutes after a persistent or aversive sample (a persistent stimulus, an evaluator
  scoring Discomfort high, or one who stepped away). The facilitator spray sheet can mark a vial as persistent so the
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
  rescue a column.
- If an evaluator cannot smell a sample, they circle **No** under Detected and leave the rest of that column blank. Do
  not suggest a second sniff, a different blotter, or a different technique. A sample that was not detected is left out
  of that evaluator's ranking.
- If any evaluator needs to step away (discomfort), pause that evaluator's next spray, extend the clean-air interval
  for them, and note the time. Other evaluators wait for the next round together; do not run ahead.
- A breach of the spray-to-first-smell ceiling is recorded as a deviation. The application raises the
  `spray_to_smell_ceiling_exceeded` flag itself when you type the first-smell time; the evidence is kept and nothing
  is dropped. Also keep the breach in the deviation log.

## Transcription window

All six sheets for a session must be captured in the application, and each stage locked, before the next session
starts. The gap of at least 3 hours between same-day sessions is the transcription window. If transcription is not
finished, the next sitting waits.

1. Enter one evaluator at a time through the single recorder login: confirm the enrollment and paper record ID, then
   type the blind code printed on the paper into the "Blind code printed on the sheet" box for each column. The
   application refuses to save when it is not the code of the sample on screen, so a mismatch means the wrong sheet or
   the wrong evaluator: stop and check.
2. Type the paper's spray time, first-smell time (asked once per sample) and column-finished time. The application
   stores the first smell as the presented time and the column-finished time as the observed time, and works out
   elapsed minutes as whole minutes from spray to column finished; you never type them. The session start, session
   end and ranking times are typed from the sheet in the same way. A time in the future, before the session existed or
   more than 7 days ago is refused as a probable typing error. The exact times stay on the paper.
3. Enter an ambiguous mark as blank plus a flag. Never guess.
4. Consent is recorded once per evaluator, on their first session, with a note of where it was written (for example,
   signed on the paper sheet). Enter the conditions slip into the session-context form only for an evaluator who
   accepted it; later sessions never ask again.
5. A saved observation cannot be edited, so compare each column on screen with the paper before pressing Save, then
   complete Part E on the sheet and sign it.
6. Do not discuss what you just typed with anyone.

## Paper retention and scans

- The consent text says that answers "are kept while the evaluation runs and for 12 months after it ends. After that the
  evaluation database is deleted. When it is deleted, the manager also deletes every backup copy of it." No repository
  document sets a separate period for paper, so this run sheet applies the same period to the score sheets, the
  conditions slips and the scans, and the manager destroys them at the same time as the database and its backups
  (see [Backup and restore](deployment/backup-and-restore.md#retiring-the-evaluation-database)). Confirm this with the
  owner before F1; it is an inference, not a stated rule.
- After Part E is complete, scan each score sheet in full (both sides) and keep the original. Scans and originals are
  private evidence kept outside the repository. Keep slip scans in a different folder from sheet scans.
- Keep sheets and slips in separate folders at all times. Only the paper record ID links them.
- Never write an identity, role or mapping on a sheet, a scan or a filename.
- Keep the deviation log (ceiling breaches, talk, interruptions, room contamination) with the sheets, apart from
  the mapping.

## Household reveal

The reveal is a program-level event after every evaluator has finished baseline, repeats and holdouts. Until then,
no one is told what any sample was, even after their own session. The facilitator controls the reveal and announces it.
