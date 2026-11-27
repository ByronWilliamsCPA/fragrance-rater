---
title: "Facilitated blind session sheet (blotter)"
schema_type: common
status: draft
owner: core-maintainer
purpose: "Define the generic two-sided blotter session sheet, its one-time handouts, and the facilitator rules for scoring, transcription and tracking."
tags:
  - guide
  - evaluation
---

Sheet version: `facilitated-session-sheet v3.0`

This document defines the paper form an evaluator completes for one blotter session, and the facilitator-side material
that goes with it. The form itself is not typeset from this file: `scripts/render_session_sheet.py` builds it, and
`scripts/print_forms.sh` prints it. This file lists every field so the form can be reviewed in text, and a unit test
checks that the printed form carries every field named here.

## The form {.facilitator}

**One generic master form.** There is one master, printed double-sided on one US Letter sheet (flip on the long
edge), used for any session and any evaluator. Nothing that is specific to a session or an evaluator is pre-printed.
Print it once for each evaluator and session from the same master (six evaluators and 17 sessions is 102 copies).
Build the print files with `scripts/print_forms.sh`.

**Written in by hand.**

- **Session** and **of**: both numbers of `Session ___ of ___` are written.
- **Evaluator reference**: the opaque reference, never a name.
- **Paper record ID**: the same ID goes on the conditions slip, if the evaluator completes one.
- **Sample 1, Sample 2 and Sample 3 code**: the code written on the atomizer (for example `B32`). The back side repeats
  small write-in boxes for the session numbers, evaluator reference, record ID and the three codes ("same codes as
  the front").

**Pre-ticked.** Blotter mode **Individual trays**. **Group blotter** is shown as not used.

### Front: scores, one column per sample

| Section | Field | Entry |
| --- | --- | --- |
| Sitting strip | Blotter mode | Individual trays (pre-ticked); Group (not used) |
| Sitting strip | Local date | written |
| Sitting strip | Time zone | written |
| Sitting strip | Recorder initials | written |
| Rule line | Intensity rule | "Intensity 0 = you cannot smell it. Circle 0, write the times, initial the column, and leave the rest of that column blank." |
| Sample answers | Sample code (per column) | written from the atomizer |
| Sample answers | Time sprayed | hh:mm:ss, the blotter you smelled |
| Sample answers | Time first smelled | hh:mm:ss |
| Sample answers | Time this column finished | hh:mm:ss |
| Sample answers | Do you recognize this? | No / Vaguely / Exactly |
| Sample answers | Have you owned or worn it? | Yes / No / Not sure |
| What you perceived | Intensity | 0 not detected, 5 overpowering |
| What you perceived | Sweetness | 0 not sweet, 5 very sweet |
| What you perceived | Freshness | 0 not fresh, 5 very fresh |
| What you perceived | Density | 0 thin and airy, 5 thick and heavy |
| What you perceived | Dryness | 0 not dry, 5 very dry |
| What you perceived | Clean or soapy | 0 not at all, 5 strongly |
| What you perceived | Earthy or rooty | 0 not at all, 5 strongly |
| What you perceived | Bodily or animalic | 0 not at all, 5 strongly |
| How you responded | Liking | 0 strongly dislike, 10 love it |
| How you responded | Discomfort | 0 comfortable, 5 had to step away |
| How you responded | Would wear | 0 never, 10 definitely |
| How you responded | Would buy | 0 never, 10 definitely |
| How sure you are | Confidence | 0 just guessing, 5 completely sure |
| How sure you are | Familiarity | 0 completely new to me, 5 I know this well |
| Column complete | Evaluator initials | written, per column |

The front page headings are "What you perceived" (properties of the fragrance itself, whether or not you liked them),
"How you responded" (your own reaction; a fragrance can be strongly perceived and still disliked) and "How sure you
are" (how much weight this record should carry).

### Back: setting, notes, ranking and sitting times

| Section | Field | Entry |
| --- | --- | --- |
| Where and when would you wear it | Type of event | Tick all that fit: Work or school, At home, Social outing, Formal event, Outdoor activity, Something else. Tick only this: None of these; Cannot judge |
| Where and when would you wear it | Season | Tick all that fit: Spring, Summer, Fall, Winter, Year-round (Year-round may be combined, for example with Spring). Tick only this: None of these; Cannot judge |
| Notes | Perceived notes | words, separate with commas |
| Notes | What you liked | words |
| Notes | What you disliked | words |
| Notes | Reminds you of | words |
| Notes | Anything else | words |
| Ranking | Place | one place per sample; samples can share a place |
| Ranking | I would rather not rank | tick |
| Ranking | I could not tell them apart | tick |
| Times for the whole sitting | Session start time | hh:mm:ss |
| Times for the whole sitting | Session end time | hh:mm:ss |
| Times for the whole sitting | Ranking time | hh:mm:ss |

The notes carry the line "Use your own words. Do not copy a note list. Do not record passwords, medical details, or
unrelated personal information." The ranking instruction reads "Complete after all three columns are initialed. Rank
only samples you could smell, 1 for the one you liked most. Samples can share a place: give two samples 1, and the
next sample is 3."

**Footer.** Every page carries `Session ___ of ___, evaluator ___ | side N of 2` (both session numbers handwritten)
and the version marker `facilitated-session-sheet v3.0`.

## Handling and privacy {.facilitator}

Do not write the fragrance identity, experimental role, repeat relationship, holdout status, or any mapping anywhere on
the sheet. The only thing on the sheet that points at a sample is the code the evaluator copies from the atomizer. The
facilitator keeps completed sheets as private evidence and enters them through the authenticated application. Nobody
discusses a sample or a score with anyone until the household reveal.

This sheet covers blotter observations only. A skin test uses its own sheet, one per skin day. The conditions
questions (feeling unwell, congestion, hunger and the rest) are not on the sheet: they go on the separate
[conditions slip](facilitated-conditions-slip.md), filed apart from this sheet. The paper record ID is the only link
between the two, so the facilitator writes the same ID on both. The facilitator runs the session by the
[facilitator run sheet](facilitated-run-sheet.md).

At hand-in, check that the session numbers, evaluator reference, paper record ID and the three codes are legible and
that each initialed column has its three times.

## Scoring rules for the transcriber {.facilitator}

**Intensity 0 means not detected.** An evaluator who cannot smell a sample circles Intensity 0, writes the three
times, initials the column and leaves the rest of the column blank. There is no separate detection row. When keying,
enter a circled Intensity 0 as detected **No** (in the application: detected false, intensity 0, liking null,
response status `not_detected`). A circled 0 on any other row remains a real answer.

**Do you recognize this?** The transcriber maps the paper wording to the application value: **No** to `new`,
**Vaguely** to `vaguely_familiar`, **Exactly** to `recognized_exact`.

**An empty column with no Intensity circled.** The sheet has no skip reasons any more. The facilitator writes a
one-line margin note saying why, on the sheet or in the tracker below. The transcriber chooses between `skipped`,
`unable_to_assess` and `interrupted` from that note.

**Ranking opt-outs.** "I would rather not rank" is `skipped`. "I could not tell them apart" is `unable_to_assess`.

**Keying order.** Key the columns in the application's position order. The code the transcriber types is only a
confirmation: a code that differs from the application's is refused, with no override, so check the written code
against the enrollment before saving.

**Ambiguous marks** are entered as blank plus a flag. A saved observation cannot be edited, so compare each column on
screen with the paper before pressing Save.

## Fields that stay on paper for F1 {.facilitator}

These fields are scanned and retained with the sheet, and are **not keyed into the application** for F1.

| Field | Why it stays on paper |
| --- | --- |
| Would wear and Would buy | The application accepts both at the blotter stage but the entry form does not offer them. F1 keys them after F1 only. |
| Type of event and Season | The application refuses event and season fit at the blotter stage. |
| Time zone, Recorder initials, Paper record ID | Scan provenance only. The application does not store them. |

Capture of these fields changes after F1 and must not gate P6 or F1. The plan is the post-F1 blotter-stage capture item
in [the project plan](planning/PROJECT-PLAN.md). That item names would wear, would buy and event fit; it does not yet
name Season, and neither do the Proposed ADR-005 and ADR-009 amendments. Adding Season there is open (see the open
questions below).

## Rules card (one-time handout) {.rules-card}

Give each evaluator this card once, at the start. It is not reprinted for each session.
`facilitated-session-sheet v3.0`

1. Work silently. Do not discuss samples, scores, or reactions with anyone, including other evaluators, until the
   household reveal. Until then, talk only about logistics (a window, a pen, a break).
2. You spray your own blotters, one at a time, as you are shown. Write the code from the atomizer, then write the time
   you sprayed. Smell the blotter right away and write the time you first smell it. Your own spray to your own first
   smell is provisionally 2 minutes: do not wait and do not hold the blotter. If the 2 minutes pass before you have
   smelled it, do not smell it: spray a fresh blotter of the same sample and write the new spray time. If you smelled
   it late, write the true time anyway and tell the facilitator.
3. Complete one sample column at a time, left to right. Write the finish time and initial **Column complete**.
4. After initialing, never change that column, even if a later sample changes your mind.
5. Leave an answer blank when you are not answering it. A circled zero is a real answer. If you cannot smell a sample,
   circle **0** for Intensity, write the times, initial the column, and leave the rest of it blank.
6. When all three columns are initialed, turn the sheet over. Tick where and when you would wear each sample, write
   your notes, then rank the samples. Write the three times for the whole sitting.
7. Hand the whole sheet to the facilitator and stay silent until everyone has finished. You will not see this sheet
   again, and you will not hear what any sample was until the household reveal.

## Consent line (one-time handout) {.consent-line}

Complete this once for each evaluator and keep it in the evaluator packet. Consent is not recorded on the session sheet.
`facilitated-session-sheet v3.0`

| Field | Entry |
| --- | --- |
| Evaluator reference | _______________________________________________ |
| Consent text version | _______________________________________________ |
| Date consent given | _______________________________________________ |
| Who consented | _______________________________________________ |
| Guardian who consented (where required) | _______________________________________________ |
| Facilitator initials | _______________________________________________ |

At transcription the application wizard requires a consent note for each session. The facilitator copies it from this
line.

## Facilitator tracker (proposal) {.facilitator}

**Proposal, for owner confirmation.** One small tracker per evaluator replaces the per-session reconciliation part of
the old sheet. It is a facilitator working page, not part of what an evaluator sees.

Evaluator reference: ______________________________

| Session | Printed | Completed | Scanned | Transcribed | Checked | Margin notes (why a column is empty) |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | ☐ | ☐ | ☐ | ☐ | ☐ | |
| 2 | ☐ | ☐ | ☐ | ☐ | ☐ | |
| 3 | ☐ | ☐ | ☐ | ☐ | ☐ | |
| 4 | ☐ | ☐ | ☐ | ☐ | ☐ | |
| 5 | ☐ | ☐ | ☐ | ☐ | ☐ | |
| 6 | ☐ | ☐ | ☐ | ☐ | ☐ | |
| 7 | ☐ | ☐ | ☐ | ☐ | ☐ | |
| 8 | ☐ | ☐ | ☐ | ☐ | ☐ | |
| 9 | ☐ | ☐ | ☐ | ☐ | ☐ | |
| 10 | ☐ | ☐ | ☐ | ☐ | ☐ | |
| 11 | ☐ | ☐ | ☐ | ☐ | ☐ | |
| 12 | ☐ | ☐ | ☐ | ☐ | ☐ | |
| 13 | ☐ | ☐ | ☐ | ☐ | ☐ | |
| 14 | ☐ | ☐ | ☐ | ☐ | ☐ | |
| 15 | ☐ | ☐ | ☐ | ☐ | ☐ | |
| 16 | ☐ | ☐ | ☐ | ☐ | ☐ | |
| 17 | ☐ | ☐ | ☐ | ☐ | ☐ | |

**Checked** means the on-screen column was compared with the paper before saving and the paper-to-application
comparison was exact, or corrected with an explanation. Keep the original sheets under the retention rule in the
[run sheet](facilitated-run-sheet.md#paper-retention-and-scans).

## Sheet version and open questions {.facilitator}

The sheet version id is printed in the footer of both pages. It is the only record of which paper wording an evaluator
used, because the application pins only the frontend build, not the paper form. The facilitator names the sheet version
(and the conditions slip version) in the F1 pre-exposure declaration (see the [F1 gate](planning/gates/f1.md)) before
the first exposure, and that declaration must name sheet v3.0. Any change to a row, a scale, an anchor, the ceiling
wording, or a rule is a new version id: a minor number such as v3.1 for a wording-only fix that changes no data field,
a major number such as v4.0 for any change to what is recorded. Sheets of two versions are never mixed inside one
program without recording both in the declaration. A sheet that does not show a version id is not used.

**Open questions for the owner.** None of these is settled by this document.

1. **Consent coverage.** The approved consent text (`family-consent-v1`) lists strength, liking and familiarity. It
   does not name would wear, would buy, or event and season opinions. Whether the wording covers them is open. The
   consent text is not changed here.
2. **F1 gate item 4.** The gate asks that the sheet and slip ids equal the ids used in the P6.3 rehearsal. P6.3 was
   waived, and v3.0 is a new sheet. How the gate reads against a v3.0 sheet is open. This document does not claim the
   item is satisfied.
3. **Tracker.** The facilitator tracker above is a proposal and needs owner confirmation.
4. **Season in the plan.** Season is not yet named in the post-F1 plan item or in the Proposed ADR-005 and ADR-009
   amendments.

**Version history.** `v1.0` was the first draft (one tray of three blotters per evaluator, a provisional 5 minute
spray-to-first-smell ceiling). The next draft (2026-11-25) added the Blotter mode row, changed the ceiling to 2
minutes, and drafted a group blotter procedure, abandoned the same day after the owner tried it physically. `v2.1`
(2026-11-25) returned to one blotter per evaluator per sample and kept the 2 minute ceiling, now counted from an
evaluator's own spray to their own first smell. The 2 minute spray-to-first-smell ceiling is not the 2 minute clean-air
interval between samples; they are different numbers. `v2.2` (2026-11-27) added the pre-printed atomizer row. No new
recorded field.

`v3.0` (2026-11-27, **major**: what is recorded changes) replaces the per-evaluator, per-session pre-printed sheet
with one generic two-sided master with handwritten identity. Recorded fields **added**: Would wear and Would buy (0 to
10), Type of event and Season (all four are paper-only for F1), time zone and recorder initials as scan provenance,
and the three times for the whole sitting. Fields **changed**: Intensity now reads "0 not detected" and a
circled 0 means not detected; the Recognize row reads No / Vaguely / Exactly; the Familiarity anchor reads "0 completely
new to me". Fields **removed**: the per-evaluator header, the yes/no detection row (replaced by Intensity 0), the
skip-reason tick boxes (replaced by a facilitator margin note), the consent tick box (consent is recorded once on the
evaluator packet line), the data-classification tick boxes, the printed version row (the footer carries the version),
and the per-session reconciliation part (replaced by the tracker proposal). The rules card and the property guide are
now one-time handouts.
