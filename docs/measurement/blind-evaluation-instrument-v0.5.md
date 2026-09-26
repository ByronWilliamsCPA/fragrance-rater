---
title: "Blind evaluation instrument draft 0.5"
schema_type: common
status: draft
owner: core-maintainer
purpose: "Preserve the proposed blind and later value questionnaire as an implementation handoff."
tags:
  - development
  - planning
---

Prepared September 25, 2026. This is the project-authored questionnaire text
from the current review packet: 35 blind field groups, 37 follow-up groups and
six organizer groups. It contains no participant answers, physical-sample
mapping, vendor records or provider taxonomy tables. Groups may contain
several subfields; the count is not questions per sample.

Status: **proposal for review, not a released protocol or implemented API**.
The web UI is the intended primary capture route; paper is a version-matched
backup. The [web workflow plan](../planning/blind-evaluation-web-workflow.md)
defines the digital sequence, storage gaps and release work. Existing
[calibration V1](../calibration-v1.md) remains the description of implemented
behavior. This draft does not amend accepted ADRs, adopt a taxonomy or
convert historical response scales.

Retain the instrument identifier `FR-PANEL draft 0.5` with captured evidence.
Freeze individual question, scale and presentation versions before release;
wording, response options and stage identity must survive exports and
corrections. The proposed digital pre-offer knowledge screen changes prompt
order and therefore needs its own presentation version.

## Response conventions

- One answer per circle group. Rectangular checkboxes indicate multi-select questions, subject to the exclusivity instruction printed with the question.
- A numbered liking response is ordinal raw evidence on `hedonic-9-v1`; it is not a renamed legacy 0–10 response.
- `cannot_assess`, `missed`, `not_asked`, `skipped` and `interrupted` remain separate from answered values. A blank on an administered question is unanswered unless explicit evidence supports another status. Do not guess whether the person could not assess or preferred to skip. Not asked requires instrument/administration evidence; it cannot be inferred just from a blank. A paper question being present is not proof it was administered.
- A negative current detection result leaves current-timepoint liking unanswered with reason `not_detected`. It does not invalidate earlier responses or an assessable retrospective final judgment.
- Keep observed time, elapsed time, paper completion time and later transcription time distinct. If a clock time crosses midnight, record the actual date during transcription rather than guessing.
- Unselected suitability options mean not selected in a prompted multi-select, not an explicit dislike or avoidance judgment.
- In season suitability, choose individual seasons OR year-round OR none OR cannot judge. In setting suitability, choose settings (including Other) OR none OR cannot judge.
- For session conditions, None noticed and Prefer not to answer are alternatives to selecting conditions.
- Internal product identity, experimental role, repeat link, randomization and physical-sample mapping stay in an operator record. The record must identify who can access the mapping and when each relevant disclosure occurred. The random blind code on the worksheet must resolve to that record without showing it to the participant.

## Scale definitions

`wear-intent-5-v1`: definitely would not; probably would not; unsure; probably would; definitely would. Cannot assess is a response status, outside the ordered scale. The skin and blotter questions share option labels, but they are distinct outcomes.

`hedonic-9-v1`:

| Code | Meaning |
| --- | --- |
| 1 | Dislike extremely |
| 2 | Dislike very much |
| 3 | Dislike moderately |
| 4 | Dislike slightly |
| 5 | Neither like nor dislike |
| 6 | Like slightly |
| 7 | Like moderately |
| 8 | Like very much |
| 9 | Like extremely |

`detection-v1`: clearly detectable; faintly detectable; not detectable. Cannot assess and Missed are separately coded response statuses even though displayed next to the detection choices for convenience. This is self-reported detection, not an objective concentration measure.

`recognition-v1`: unfamiliar; vaguely familiar; think I know the identity. Identity guess is separate raw text; a guess is not verified identity. Prior ownership/wear is yes/no/unknown about the fragrance the participant believes it is. Formal disclosure and recognition are separate fields.

## Skin worksheet

| ID | Question / field | Timing and semantics |
| --- | --- | --- |
| META | Evaluator, session, blind sample, date, application time, timezone, site, method and dose count | Application/exposure metadata. Physical item and operator preparation details remain in a linked record. |
| SK-TIME | Observed time and elapsed minutes | Repeated at nominal 15, 60 and 240 minutes. Actual elapsed time governs the observation. |
| SK-DETECT | Is the fragrance detectable? | Repeated current observation; `detection-v1`. |
| SK-TEXT | What do you notice? What changed? Your own words. | Optional raw text per checkpoint, before liking. Preserve literal uncertainty/negation and all linked continuation text. Do not normalize in place or infer prominence from word order. |
| SK-LIKE-NOW | Liking now (circle one) | Repeated current observation; `hedonic-9-v1`. Never substitute for final overall liking. |
| SK-FINAL-TIME | Judged date/time/elapsed; observation period and actual end date/time | Observation period: Ended before 4 h / Reached 4 h or later / Not sure. This concerns the period actually experienced, not whether the nominal four-hour check was taken. Check status and actual check times remain on the development page. Judgment time, trial end and later transcription are separate. Do not automatically map historical reached/early/late categories to these new options. |
| SK-WEAR | Would you personally choose to wear this fragrance again? | Proposed primary experienced-wear intent; `wear-intent-5-v1`. No assumption of purchase or actual future wear. |
| SK-LIKE-OVERALL | Overall, how much did you like it during this trial? | Separate summary question; `hedonic-9-v1`. May be answered even if no longer detectable at final check. |
| SK-DRIVER | What increased or reduced your willingness to wear it? | Optional raw preference-driver explanation. Later concept mapping must preserve this text and attribution. |
| SK-SEASON | Which seasons would suit it? | Optional hypothetical suitability: spring/summer/fall/winter OR year-round/none/cannot judge. |
| SK-SETTING | Where would you wear it? | Optional hypothetical work-school/home/social outing/formal event/outdoor activity/other, OR none/cannot judge. |
| SK-DISCOMFORT | Discomfort during the trial? What happened / when? | No/yes/cannot assess plus raw detail. Separate from disliking the odor. |
| SK-STOP | Washed or scrubbed off? When? Why stop, wash or miss a check? | No/yes plus event time and raw reason. Keep assessable partial responses. |
| SK-LATE-DETECT | Optional detection around eight hours | Only if scheduled: about eight hours. Record actual date/time/elapsed and detection/status. Keep the earlier final judgment. Additional samples need their own identified sheet. Unscheduled checks are not missed scheduled checks; preserve any unsolicited observation separately. |

Do not label a four-hour cutoff as exact longevity. Detected at 240 minutes and no longer observed gives a lower bound; detected at 240 and absent at 480 gives an interval. A wash event has a separate reason. Formal censoring derivation/version is an implementation todo.

## Blotter worksheet

| ID | Question / field | Semantics |
| --- | --- | --- |
| BL-META | Evaluator/session/date/code/application/observation time and elapsed minutes | Screening exposure. The draft leaves a fixed blotter observation interval undecided; the organizer must select and record it before release. Application and observation have separate date/time fields. |
| BL-DETECT | Is the sample detectable? | `detection-v1`; non-detection is not dislike. |
| BL-TEXT | Describe the smell in your own words. Uncertainty is welcome. | Optional raw description, before liking. Retain all continuation pages with the original question/presentation context. |
| BL-LIKE | How much do you like the scent right now? | `hedonic-9-v1`, current blotter liking. |
| BL-TRY | Based on this blotter, would you want to try wearing this fragrance? | `wear-intent-5-v1` labels, but the construct is interest in a skin trial, not demonstrated skin preference. |
| BL-DRIVER | What most influenced that answer? | Optional raw explanation. |
| BL-SEASON | Which seasons would suit it, based on the blotter impression? | Optional hypothetical spring/summer/fall/winter OR year-round/none/cannot judge. Same option codes as SK-SEASON; distinct stage/question identity. |
| BL-SETTING | Where would you wear it, based on the blotter impression? | Optional hypothetical work-school/home/social outing/formal event/outdoor activity/other OR none/cannot judge. Same option codes as SK-SETTING; distinct stage/question identity. |
| BL-DISCOMFORT | Discomfort during this check? | No/yes/cannot assess; detail preserved. |
| BL-STATUS | Interrupted or unable to complete, time and reason | Separate from a low score or non-detection. |

## Session companion

| ID | Field / question | Semantics |
| --- | --- | --- |
| SE-META | Evaluator/session/date/start/end/timezone | Shared session metadata. |
| SE-CONTEXT | Indoor/outdoor/mixed; alone/with others | Actual conditions, not hypothetical suitability. |
| SE-CONDITIONS | Congestion/illness, allergy symptoms, personal scent, ambient odors, none noticed, prefer not to answer; optional detail and temperature/humidity | Self-reported optional context. Do not infer diagnoses or fill blanks from assumption. |
| SE-RANK | Actual presentation order, blind codes, eligibility, preference rank | One event per planned session group of up to three blotters, after individual ratings. Rank only detected samples whose scent liking can be compared. Wear intent alone does not establish liking comparability. Equal preferences share ranks (for example 1, 1, 3); retain raw tie groups. A larger event needs a deliberately revised contract, not silently split ranks. |
| SE-RANK-STATUS | Complete, insufficient eligible samples, unable, skin-only | Fewer than two eligible means Not enough samples and no rank event. Unable to rank is distinct. Skin trial only means no blotter task was administered; an all-nondetected blotter group is not skin-only. |
| SE-DEVIATION | Changed order, missed sample, assistance or other deviation | Raw reason retained; intended order and randomization remain operator metadata. |
| SE-RECOGNITION | Familiarity/recognition, time noticed, identity guess, prior ownership/wear | One block per sample; observations remain time-specific rather than globally labeling a fragrance known. |
| SE-DISCLOSURE | Identity disclosed yes/no/unknown, information and time | Remains sample-specific and independent of recognition. The organizer also records mapping-holder knowledge and any source of product information in operator metadata. |
| SE-PRIOR-TERMS | Have you already seen scent words or family lists for this panel? No/yes/not sure; what/when | Participant self-report at session start, not proof that no priming occurred. Earlier-session list exposure may affect later sessions. Absent in v0.2: not asked, not no. |
| SE-SESSION-TERMS | Scent words / family lists received during this session? No/yes/not sure | Separate from identity disclosure. Shared detail line/continuation records affected code(s), exact information/list reference and date/time. If timing is unknown, keep it unknown. |
| SE-LATE-SCHEDULED | Scheduled / Not scheduled | Organizer marks whether the optional late check is assigned for the linked sample. If not assigned, not_asked requires that administration evidence; an unmarked schedule is unknown, not proof of not_asked. |

## Deliberate omissions and remaining protocol decisions

The blind pages do not ask confidence, projection, perceived intensity, density/weight, the full seven exploratory descriptors, separate season avoidance, family selection, or descriptor prominence. Detection is not projection or an intensity scale. Price/value/purchase intent now have their own later module. A maximum-willingness-to-pay question is deliberately not included in this first integrated version; profile thresholds and exact-offer responses supply the initial value evidence. Full inventory counts/volumes, actual acquisitions and actual wear events are also not elicited here. These omissions are not neutral answers.

The primary target/stage, original scales, skin/holdout scope, timing windows and final eligibility rules remain release decisions; this packet explicitly uses groups of up to three blotters and retains equal ranks. The packet preserves the current draft's 15/60/240-minute skin checks and optional 480-minute detection. The organizer page provides explicit blanks for the study-specific blotter wait interval and other release settings; no scientific timing optimum or approval is implied. Do not use unfilled settings as an operational protocol.

The implemented packet revisions do not adopt the proposed taxonomy hierarchy. Preserve original blind answers, exact question versions and the later information context. Final non-detection must not discard an assessable final wear/overall-liking answer.

## Organizer annotation contract

The organizer pages are used after original answers are preserved. They are not participant data and must not be distributed as a rater checklist.

- Preserve the original paper/scan, page/response reference, participant, presentation, stage/time and instrument version. A copied phrase is linked to its original answer, not treated as another observation.
- Record coder identity, annotation date, review state and the vocabulary/mapping version actually used. Record the exact vocabulary release and artifact hash; proposed definitions must not be labeled as an unchanged approved release.
- Family candidates allow zero, one or several; a primary family is optional and belongs to this annotation, not an inferred participant selection. Add explicit supporting evidence for the family assignments.
- For each exact phrase record candidate concept(s), relation/status, evidence and uncertainty. The v0.5 worksheet explicitly requests target-broader/target-narrower, close, exact, related or composite direction/type; no precise relation is implied by convenience of display. `Unresolved` is a resolution status, not an odor code.
- `Draft/reviewed/rejected` describes annotation review. It does not establish source permissions, study eligibility or truth of an ingredient claim. `Reviewed` must have a traceable reviewer/date in the annotation history; attach a review record if different from the coder/date in the header.
- Four printed rows are writing space, not a storage cap. Append pages with the same source IDs. No descriptor rank is elicited or imposed; later coding cannot recover unasked prominence.
- Keep source notes/accords, evaluator perceptions and material assertions separate. Do not infer families by copying browse-tree ancestry, or treat a material-named descriptor as a formula claim.
- For an independent coding rehearsal, give coders the relevant odor text and context before preference or value outcomes. No printed guidance is a participant observation.
- No transcript, annotation or new vocabulary version silently changes the inputs of an already frozen forecast. Retrospective reanalysis is a separate derived artifact.

## Integrated follow-up: distribution and capture rules

Complete the planned blind sheets first and preserve them. After the relevant blind block and repeats are closed, release A, then B, then C. Prefer releasing after the entire panel if further exposures could be influenced. Check holdouts and other participants before showing prices. A copy of the combined owner-review packet must not circulate during blind sessions.

A records retrospective intended-use roles before money/profile prompts. It is not a new real-time blind checkpoint, even if price/identity remain unknown. Link its source experiences and preserve any prior knowledge. B records individual size/format thresholds and references. C records one particular offer, intended wearer and information state; use another assessment ID for a different offer or purpose.

Every follow-up page carries evaluator, date/time/zone and profile or assessment IDs; sample-specific pages link the original trial/sheet. Repeated printed cards require entry/reference IDs. Their count is not a response cap. Preserve paper, raw answers, actual occurrence time, later entry time and corrections with authorship. Format labels may overlap: a travel decant can be one nominal-size entry with multiple source labels, not two independent budget observations. Unspecified sizes/ranges/currency stay unspecified.

For profile amounts, enough experience means enough to consider purchasing **that size**. It does not require an own-skin trial; an unfamiliar sample can itself be the purchase being considered. The routine total is comfortable spending, exceptional total is considered only for an exceptional purchase, and ceiling is a stated maximum or explicit no-fixed-ceiling answer. Do not infer the thresholds from quantities owned, from each other or from a single rejected offer. Inventory counts, nominal/remaining mL and actual transactions remain distinct and are not requested in these forms.

For all questions, an untouched blank is unanswered unless administration evidence supports not asked/skipped. Explicit cannot judge, unknown/not sure and prefer-not responses retain their actual meaning. Use `not_applicable` for a skipped comparison with no reference or a non-wearer's personal-use effect; preserve the reason. No fixed ceiling is an answered categorical statement, not an infinite numeric value. A completed multi-select with no marks is not automatically a chosen None. Preserve ambiguous paper responses for review rather than silently repairing them.

A person's reference may be shared across size rows while its stated price/size basis remains fixed. A 100 mL price cannot imply a purchasable 10 mL offer. If reference price is uncertain, show its actual remembered/unknown status; a supplied choice remains context-limited rather than a verified current-price comparison. Do not compute liking divided by price, exact cost per wear, calibrated purchase probability, demand curves or causal price effects from these responses.

The offer page captures prior price/brand/identity/notes knowledge. The operator record separately logs exact information actually disclosed with times and links to the private physical/version identity. Keep source/seller information off the participant card if it reveals concealed identity. Lock shown prices as snapshots; later catalog changes do not alter an earlier response. Known tax/shipping treatment and availability remain explicit; unknown amounts must not be filled by assumption. A planned sample purchase is not an acquisition, and “smelled on another person” is not an own-skin trial.

A gift response belongs to the buyer under a gift context. Another wearer's reported exposure is attributed to that buyer and may be unknown; it is not the recipient's liking/wear/value response. A self-use assessment and a gift assessment need distinct assessment IDs if both are collected. Profile selection does not imply purchase behavior, and declined full-bottle intent does not erase sampling interest.

## Link, routing and correction rules

**Profile participation:** selecting formats and selecting an alternative remain exclusive. None/Prefer not to answer skip entries. Not sure permits any entries the person can judge; it does not require them. An optional entry is not evidence that an uncertain format selection was actually definite. Unknown markers apply independently to size, price and currency; blank and explicit unknown are different.

**Linkage and purchase context:** Profile/Entry IDs on offer page 1 are organizer-managed. Matched means the actual compatible entry is recorded; no match, profile not collected, unresolved and not checked remain distinct. Profile participation is not a prerequisite for a value answer. Record review time/author/basis for a later link. The independently optional use-role pointer resolves to a follow-up record + role entry ID and that entry's actual source trial(s). Both requires the relevant blotter and skin source instances. Avoid joining by fragrance name alone. No post-price intended use overwrites the pre-price role.

**Offer preparation:** organizer pre-fills candidate fields on both offer and comparison pages from the same card, including its exact format/mL/price/currency/basis, then verifies both before showing them. Log any discrepancy with both source records and actual seen-time. A corrected disclosure and any new answer are separately timed and linked; neither replaces an earlier response. An intended private offer does not establish what was actually seen.

**Sequence and selection:** keep a per-respondent sequence group/position with prior assessment and disclosure IDs. Record distinct skin/holdout and value-subset rules, eligible lists, selected/omitted IDs and reasons before their affected use. Do not label repeated priced choices independent first-price observations or generalize a preference-selected value subset to the entire panel. Selecting skin holdouts from observed favorite blotters does not support the intended general prediction claim without a suitable evaluation design.

**Recognition and coding:** join the existing timed recognition/disclosure to observations through evaluator/session/presentation and actual time. Preserve spontaneous comparisons without telling participants to look for repeats. Vague familiarity is not verified identity; eligibility requires the declared rule. Permit supported overlapping/no families and leading descriptors. Rehearsal can discover unresolved coding boundaries; only approved versioned definitions may support affected normalized reports/features.

## Follow-up questions and exact response sets

### A - Unpriced use roles

| ID | Printed question / field | Response / interpretation |
| --- | --- | --- |
| FU-ROLE-LINKS | Role entry ID: / Sample code: / Source sheet / trial ID(s): / Trial date(s): | source links; repeat: per role entry; semantics: Exact source instances, not just fragrance identity. Reference the composite follow-up record + role entry ID from later assessment links; preserve unknown or unresolved source links without guessing.; recorded by organizer_with_participant_confirmation |
| FU-ROLE-BASIS | Experience considered: | Blotter; Skin; Both; repeat: per role entry; semantics: Retrospective before money/profile prompts. Link every source sheet/trial ID and date used, including both blotter and skin when Both is selected. Role entry ID is unique within its follow-up record across continuation sheets. No replacement of original blind judgments. |
| FU-ROLE | Setting purchase cost aside, when would you choose to wear this? | Ordinary days; A deliberate treat; Particular occasions; Other; Would not wear; Cannot judge; repeat: per sample/source experience |

### B - Repeated size/format profile

| ID | Printed question / field | Response / interpretation |
| --- | --- | --- |
| PR-FORMATS | Which formats would you consider buying? Select formats OR one alternative. | Sample; Decant; Travel size; Bottle; Other; None; Not sure; Prefer not to answer; semantics: Select one or more formats OR one alternative. Do not silently resolve contradictory marks. Optional entries under Not sure do not retroactively turn it into a format selection.; skip: None or Prefer not to answer skips size entries. Not sure permits any judgeable size entries; leaving them empty is also allowed. Reference cards remain optional. |
| PR-VOLUME | Format label(s): / Size: | Exact size; Range; Size unknown; repeat: each format + nominal volume + declared purpose entry; semantics: One entry per format + nominal size/range/status + purchase context. A travel decant can use both raw labels in one entry. Extra copies are unlimited. Total prices/ranges refer to that size, not per mL. Enough experience means enough to consider buying that size; an own-skin trial is not required. |
| PR-CURRENCY | Currency: | Currency unknown; repeat: each entry; semantics: A currency text value OR explicit Currency unknown; preserve ambiguous conflicting marks. A blank without evidence is unanswered, not a chosen unknown. Amounts are total money for this size, not price per mL. |
| PR-PURPOSE | Thinking of a purchase for: | Myself; A gift; Other; repeat: each entry; semantics: A gift threshold does not automatically apply to self use, or vice versa. |
| PR-COMFORT | Comfortable routine total: | Not sure; Prefer not to answer; repeat: each entry; semantics: Optional soft spending threshold under the stated enough-experience assumption for this size; no exposure is inferred. |
| PR-STRETCH | Exceptional-purchase total: | Not sure; Prefer not to answer; repeat: each entry; semantics: Amount considered only for a purchase exceptional for this purpose; not a promise to spend. |
| PR-CEILING | Amount I would not exceed: | No fixed ceiling; Not sure; Prefer not to answer; repeat: each entry; semantics: One amount/range OR one option. No fixed ceiling is a stated answer, not a numeric infinity. Do not derive ceilings from rejected offers. |
| PR-REFERENCES | Reference IDs (optional): | reference links; repeat: each entry; semantics: Reuse one reference across entries while preserving its actual offer size/basis; no invented equivalent purchase format. |
| PR-CONDITIONS | Would purchase context or familiarity change these answers? | free text; repeat: each entry |

### B - Personal references

| ID | Printed question / field | Response / interpretation |
| --- | --- | --- |
| REF-STATUS | Name fragrances a new purchase would compete with. | References supplied; No reference yet; Prefer not to answer |
| REF-IDENTITY | Fragrance / version, if known: | text plus links; repeat: reference card; semantics: Profile/reference/linked entry IDs plus fragrance/version and For whom / intended use. Purchase context, intended wearer and intended use remain distinct; keep raw text. |
| REF-FAMILIARITY | Own it / Worn it / Smelled it / Other | Own it; Worn it; Smelled it; Other; repeat: reference card; semantics: Ownership does not itself establish purchasing or wearing. |
| REF-OFFER | Format: / Size: / Price / range: / Currency: | Size unknown; Price unknown; Currency unknown; repeat: reference card; semantics: Unknown markers apply independently to size, price and currency. For each component use a value OR its unknown marker. Blank is not zero or a selected unknown. Preserve source/date/uncertainty and reviewed conflicting marks. |
| REF-PRICE-BASIS | This price is (choose one): | Remembered paid price; Current replacement price; Other / unsure; repeat: reference card |

### C - Offer and current purchase context

| ID | Printed question / field | Response / interpretation |
| --- | --- | --- |
| VAL-OFFER | OFFER CARD / Prepared by the organizer | immutable offer fields; semantics: Organizer-prepared exact offer snapshot: ID, format/mL, total/currency/per-mL basis, circle-one tax/shipping/availability, checked time and actual shown time/zone. Prefill THIS OFFER on the comparison page from the same shown card and verify before distribution. Private source/product links remain in the organizer record. Unknown stays unknown. Differences between intended/private and actually displayed values require a preserved discrepancy record, not overwrite. |
| VAL-PROFILE-LINK | Optional organizer links: Profile / Entry / Use-role entry; Entry link (circle): | Matched; No match; Profile not collected; Unresolved; Not checked; semantics: Matched requires actual Profile and Entry IDs for a compatible format/size/purchase context. No match means reviewed and no compatible entry; Profile not collected differs from unresolved ambiguity and Not checked. Multiple candidate links remain unresolved until reviewed. Assessment ID carries links across pages. Use-role link is independently optional and may be unresolved even with a matched price profile. No profile or exact match is required to answer value. Preserve later link review author/time/basis.; recorded by organizer |
| VAL-WEARER | Who would use this purchase? Choose one. | Myself; Someone else; Shared; Undecided |
| VAL-GIFT | Would it be a gift? | No; Yes; Undecided |
| VAL-INTENDED-USE | Intended use of this purchase (optional): | free text; semantics: Current intended use after the offer reveal, separate from wearer and gift status. Do not copy or overwrite the earlier unpriced FU-ROLE response; a linked earlier role may differ. |
| VAL-EXPERIENCE | How have you experienced this fragrance so far? Select all OR None. | On someone else; On a blotter; On my skin; Other; None; semantics: Respondent actual experience before current decision; no gift-recipient preference inferred. |
| VAL-SKIN-COUNT | Own-skin trials: | None; Once; Several; Not sure; semantics: Self report, not inferred from owning a sample. Inconsistencies with the experience checklist are reviewed, never silently resolved. |
| VAL-RECIPIENT-EXPERIENCE | If another person would use it: what have they tried, to your knowledge? | Not tried; Smelled only; Worn it; Unknown; Not applicable; semantics: Buyer-reported most applicable experience category. Worn does not imply liking. For self-only purchase mark not applicable; shared use may refer to the other wearer. |
| VAL-PRIOR-INFORMATION | Before this offer card, did you already know any of the following? | No; Yes; Not sure; repeat: Price; Brand; Product identity; Published scent notes; semantics: Retain known-at time/uncertainty and source/detail. Do not code missing as No. The operator logs actual shown information separately. |

### C - Value, intent and next action

| ID | Printed question / field | Response / interpretation |
| --- | --- | --- |
| VAL-VALUE | For the person and use recorded on this offer card, how good a value is this exact size and price to you? | Very poor; Poor; Fair; Good; Excellent; Cannot judge; semantics: Decision-maker value for the recorded wearer/gift context and optional current intended use. Answerable without a personal profile or reference. A blank optional use line does not block value answers and does not imply an ordinary-day use. No recipient preference is inferred. |
| VAL-BUY | Would you choose to buy this offer now for that person and use, given your experience so far and current circumstances? | Definitely not; Probably not; Unsure; Probably yes; Definitely yes; Cannot assess; semantics: Current stated purchase intent, not actual order or calibrated probability. It can be low while sampling interest is positive. |
| VAL-NEXT | What would you choose to do next? Choose one main step. | Buy this offer now; Obtain a sample first; Try my existing sample again; Seek a smaller amount to keep; Have the intended wearer try it; Compare alternatives; Wait; Pass on this offer; Not sure; Other; semantics: One primary intended step; conditions may be free text. Sample-first is not an order, and a smaller final amount is not necessarily a trial for a bottle. |
| VAL-REASON | What most influenced your decision? Select any; optional. | Enjoyment; Expected use; Good price for the benefit; Not worth the price to me; Outside my spending limit; Suitable quantity / convenience; Own enough / a similar fragrance; Need more experience myself; Need recipient feedback; Other; semantics: Unselected options are not independently elicited negative answers. |
| VAL-CONDITIONS | Anything else, including conditions before you would buy? (Optional) | free text |

### C - Reference comparison and own use

| ID | Printed question / field | Response / interpretation |
| --- | --- | --- |
| VAL-COMPARE-ELIGIBLE | Can you compare a familiar alternative for the same intended wearer and use? | Yes; No reference; Not comparable; Cannot judge; skip: Only Yes continues reference comparison; other answers skip to VAL-USE, with comparison not applicable or cannot-assess reason retained. |
| VAL-REFERENCE-OFFERS | THIS OFFER / REFERENCE OFFER | two offer snapshots; semantics: Organizer pre-fills THIS OFFER from the shown offer card for this assessment; participant/reference evidence supplies the reference snapshot. Compare a fresh purchase for the same intended wearer and use. Preserve actual format/mL, price/currency/basis and reference source/date/uncertainty. Flag mismatches and keep both originals; any corrected disclosure and new answer have separate times and links. |
| VAL-COMPARE-BASIS | Comparison draws on (select any): | Memory; Extra smelling / wearing after prices; Other; semantics: Retain sample/reference and time for extra experience; mixed/unknown context is explicit. Post-price experiences do not become blind responses. |
| VAL-REFERENCE | For that wearer and use, which would you choose to buy? | This offer; Reference; Either equally; Neither; Cannot compare; semantics: Fresh-purchase choice at shown/recalled offers, distinct from cost-free use of an already-owned bottle. Not an ordinal scent ranking or recipient report. |
| VAL-COMPARE-DETAIL | Why / any limitation of the comparison? (Optional) | free text |
| VAL-USE | Would this price change how often or when you would use it? | No; Yes; Cannot judge; I would not be the wearer; printed_instruction: For shared use, answer about your own use.; semantics: Self-use intention; not wearer is not applicable rather than No. For shared use answer own-use component only. If Yes preserve how in free text. |

## Organizer field groups

| ID | Record | Semantics |
| --- | --- | --- |
| OP-RELEASE | Release ID / date; timing/dose; late check; selection/eligibility/offer-order plan; capture/recovery | Batch values must be chosen before use; document generation does not fill these facts. |
| OP-SELECTION | Eligible list; skin/holdout allocation rule; value-offer subset rule; selected/omitted IDs and reasons | Distinct skin and value selection frames. Predeclared preference-selected value data remain scoped; holdout design must support the claimed general prediction evaluation. |
| OP-SEQUENCE | Evaluator; Assessment; Sequence group / position; Prior assessment / disclosure IDs | Order and previous price/identity information are preserved. Later offers are not independent first-price impressions. |
| OP-RECOGNITION-LINK | Spontaneous comments and recognition links | Timed join to existing recognition evidence. Preserve spontaneous comments; do not ask about repeats or infer identity from familiarity. Eligibility is applied with recorded policy, not blanket exclusion. |
| OP-CORRECTION | Display mismatch or other correction | Original values and times remain immutable. A corrected answer is new and linked; a planned private snapshot cannot erase an actually shown price. |
| OP-CODING | Interpretation worksheet and vocabulary/mapping version | Overlaps are permitted with evidence lineage; no ingredient assertion or prominence from word order. Unapproved meanings remain unresolved. Rehearsal is separate from approved normalized use. |

## Release requirements

Before exposure, approve the intended endpoints/scales, actual blotter interval,
dose, skin windows, optional late-check assignment, selection/holdout policy,
missing-task closure and disclosure scope. Demonstrate capture, export,
recovery and human comprehension with the intended devices and people.
The nominal times in this document are draft choices, not established optima.

Print only the relevant participant modules from the released instrument;
keep organizer identity and allocation records separate. Paper transcription
must retain the original source, observed time, later entry time and any
conflict with an existing digital response.

Later taxonomy annotations retain raw wording and independent source rights.
A material-like description is not proof of an ingredient. Proposed hierarchy,
provider crosswalks and restricted comparison data are outside this handoff.
See the [vendor-use boundary](../fragella-api.md) before adding external data.
