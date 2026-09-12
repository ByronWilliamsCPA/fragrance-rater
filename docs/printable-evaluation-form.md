---
title: "Printable evaluation and outage form"
schema_type: common
status: published
owner: core-maintainer
purpose: "Provide a disclosure-safe paper record for ordinary and blind fragrance observations during an approved outage."
tags:
  - guide
  - evaluation
  - deployment
---

Print one copy for each sample and stage. Use this form only when the manager has declared an
application outage during an approved synthetic rehearsal or pilot. Stop electronic submissions
until the manager announces recovery.

For a blind session, write only the physical blind code. Do not write the fragrance identity,
experimental role, repeat relationship, holdout status, or mapping anywhere on this form. Keep
completed forms with the assigned recorder and store them as private evidence.

## Session and record

| Field | Entry |
| --- | --- |
| Paper record ID | _______________________________________________ |
| Data classification | ☐ Synthetic rehearsal ☐ Approved family pilot |
| Workflow | ☐ Ordinary rating ☐ Blind controlled session |
| Program or session private reference | _______________________________________________ |
| Assigned evaluator reference | _______________________________________________ |
| Recorder initials | __________________ |
| Local date and time | __________________ |
| Time zone | __________________ |

## Sample and stage

Complete the row that applies to the selected workflow.

| Field | Entry |
| --- | --- |
| Ordinary rating: exact fragrance version | _______________________________________________ |
| Blind session: physical blind code | _______________________________________________ |
| Blind stage | ☐ Blotter ☐ Skin ☐ Post-reveal |
| Elapsed minutes from application | __________________ |
| Observation local date and time | __________________ |

For a pre-reveal blind stage, leave the ordinary fragrance-version row blank. For an ordinary
rating, leave the blind code, blind stage, and elapsed-minutes rows blank unless the application
workflow requires an elapsed observation.

## Core observation

For an ordinary rating, circle **Ordinary rating** and leave the remaining rows blank. For a blind
controlled session, complete the fields shown for the selected stage in the application. A zero
is a real response. If **Detected** is **No**, record intensity as `0` and leave liking blank.

| Measure | Response |
| --- | --- |
| Ordinary rating | 1 2 3 4 5 |
| Detected | Yes / No |
| Intensity | 0 1 2 3 4 5 |
| Liking | 0 1 2 3 4 5 6 7 8 9 10 / N/A |
| Confidence | 0 1 2 3 4 5 / N/A |
| Projection | 0 1 2 3 4 5 / N/A |
| Longevity in minutes | __________________ / N/A |

## Perceived attributes

Circle one value or mark `N/A`. Record only what the evaluator perceives.

| Attribute | Response |
| --- | --- |
| Sweetness | 0 1 2 3 4 5 / N/A |
| Freshness | 0 1 2 3 4 5 / N/A |
| Density | 0 1 2 3 4 5 / N/A |
| Familiarity | 0 1 2 3 4 5 / N/A |
| Dryness | 0 1 2 3 4 5 / N/A |
| Clean or soapy | 0 1 2 3 4 5 / N/A |
| Earthy or rooty | 0 1 2 3 4 5 / N/A |
| Bodily or animalic | 0 1 2 3 4 5 / N/A |
| Discomfort | 0 1 2 3 4 5 / N/A |

## Optional outcome ratings

Complete only fields shown for this workflow and stage in the application.

| Measure | Response |
| --- | --- |
| Opening liking | 0 1 2 3 4 5 6 7 8 9 10 / N/A |
| Drydown liking | 0 1 2 3 4 5 6 7 8 9 10 / N/A |
| Would wear | 0 1 2 3 4 5 6 7 8 9 10 / N/A |
| Would buy | 0 1 2 3 4 5 6 7 8 9 10 / N/A |
| Artistic appreciation | 0 1 2 3 4 5 6 7 8 9 10 / N/A |

## Perceived notes and comments

Do not copy a note list or concealed identity. Do not record passwords, medical details,
hostnames, tokens, or unrelated personal information.

```text
Perceived notes: _____________________________________________________________
Likes: ______________________________________________________________________
Dislikes: ___________________________________________________________________
Reminds me of: ______________________________________________________________
Comments or ordinary-rating observations:
______________________________________________________________________________
______________________________________________________________________________
```

## Reconciliation after recovery

The recorder enters this observation through the authenticated application after service
recovery. Before entry, verify that no saved electronic response already represents this paper
record. Never use a direct API, database, or unauthenticated route as an outage shortcut.

| Check | Entry |
| --- | --- |
| Evaluator or participant initials | __________________ |
| Recorder initials | __________________ |
| Duplicate check completed | ☐ Yes |
| Entered by | _______________________________________________ |
| Entry UTC date and time | _______________________________________________ |
| Application response private reference | _______________________________________________ |
| Paper-to-application comparison | ☐ Exact ☐ Corrected with explanation below |
| Verified by and UTC date/time | _______________________________________________ |

Correction or recovery explanation:

```text
______________________________________________________________________________
______________________________________________________________________________
______________________________________________________________________________
```

The recorder signs the paper record after reconciliation and stores it under the pilot evidence
retention rules. Record the outage and recovery in **Pilot operations** without copying private
observations or blind mappings into operational notes.
