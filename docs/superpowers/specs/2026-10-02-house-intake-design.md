---
title: "House Intake Instrument: How Fragrance Houses Describe Their Fragrances"
schema_type: common
status: draft
owner: core-maintainer
purpose: >-
  Define the form a fragrance house uses to describe one of its fragrances in its own
  words, how those submissions are stored and fenced, and how they later become
  ADR-012 manufacturer-provided evidence.
tags:
  - taxonomy
---

This is the "house intake instrument" that the olfactory vocabulary spec lists as its next sub-project. A fragrance
house representative uses it to describe one of the house's fragrances. Each submission becomes ADR-012
manufacturer-provided evidence once a manager reviews it.

## What the house is asked

The form has three numbered sections. Only the items marked *required* block submission. A draft only needs a
name.

| Section | Field | Required to submit | Why |
| --- | --- | --- | --- |
| 1. The fragrance | Name | yes | Identity |
| | House | fixed from the account | Never typed by the house, never taken from the request |
| | Collection or line | | ADR-012 brand/line attribution |
| | Concentration (or a named "something else") | yes | ADR-012 confirmable fact; ADR-006 version identity |
| | Formulation or edition | | ADR-006 `version_key` (reformulations, editions) |
| | Launch year | yes, unless upcoming | ADR-012 confirmable fact |
| | Availability | yes | Explains a missing year; signals discontinuation |
| | Marketed for | | Maps to `gender_target`; "the house does not say" is a real answer |
| | Perfumers | | `VersionPerfumer` attribution, now with a manufacturer source |
| | Product page (https only) | | Citation for `SourceSnapshot.source_url` |
| | Barcodes (GS1 check digit) | | The strongest identity signal the project has |
| 2. The scent | Note structure (pyramid or single list) | | Some houses publish no pyramid |
| | Top/heart/base notes, or a single list, in order | one of notes, accords, or description | ADR-017 layer 1 `declared_label` shape |
| | Accords, family as described, official description | | Captured verbatim |
| 3. Permission | Use: recommendations and training, or record checks only | yes | ADR-012 `permission_state` |
| | Name and role of the person submitting | yes | ADR-012: a named representative is what justifies `retain_and_train` |
| | Authority confirmation | yes | |
| | Note to the reviewer | | |

## Decisions

1. **Houses answer in their own words.** Notes, accords, and family are stored exactly as entered. Outer
   whitespace is trimmed; nothing is case-folded, translated, or mapped to `fr-core`. The list order is the
   house's order. The form tells the house that we only want the notes it already publishes, not its formula.
2. **Staged, not adopted.** Submissions live in `house_submissions` and do not write to `fragrances`,
   `calibration_source_snapshots`, or `declared_label`. Turning a submission into evidence is a separate reviewed
   manager step (see follow-ups). This keeps ADR-017's sequencing intact, because `declared_label` still waits for
   D1. It also means a house can never change catalog facts directly.
3. **Submitted records are immutable.** A correction creates a new draft that points at the original
   (`supersedes_id`, unique, so a record can be corrected only once) and clears the authority confirmation.
   Drafts can be discarded; submitted records cannot.
4. **Permission is the house's explicit choice.** It is never a default. It is stored on the row at submission
   time as `permission_state`, using the same `retain_and_train` / `retain_for_qc_only` values as
   `SourceSnapshot`.
5. **House accounts are fenced on the server.** Several household routes have no per-identity checks (for
   example, `GET /reviewers` lists family members, and any identity can edit the catalog).
   `HouseContributorFenceMiddleware` therefore restricts a house account to `/api/v1/house-intake/*` and
   `/health`. It is an allowlist, so routers added later are closed to houses by default. The frontend's
   house-only shell is presentation only, not the protection.
6. **Managers read, houses write.** A manager can read every house's submissions but cannot create or edit
   them. A manager writing on a house's behalf would no longer be the house's own statement.

## Access and operations

- `HOUSE_CONTRIBUTORS` is a JSON object mapping a verified Authentik username to a house name, for example
  `{"ana.ruiz@maison-aurele": "Maison Aurele"}`. Colleagues at one house share its records. Startup fails if a
  username is also in `CALIBRATION_ADMIN_USERNAMES` or maps to a blank house name.
- Onboarding a house: create the Authentik user (ideally in a dedicated group bound to this application only),
  add the username to `HOUSE_CONTRIBUTORS`, and redeploy. Removing the mapping revokes access immediately. Their
  submitted records stay.
- Houses reach the app through the same Traefik/Authentik boundary (ADR-008). No public route or token link is
  added.

## Follow-ups (not built here)

- **Manager adoption step:** match a submission to a catalog version (or create one), then write a
  `SourceSnapshot` (`source_type=manufacturer_provided`, `permission_state` from the row, `fields` listing the
  confirmed columns, `source_reference` naming the submission and the representative). From D1, also write its
  `declared_label` rows.
- Notify the manager when a house submits. Today the manager has to check the list.
- A house-facing view of what was adopted, and a permission-withdrawal path that feeds ADR-017's purge-by-source.
- Move house membership from configuration to a managed table if the number of houses grows beyond a handful.
