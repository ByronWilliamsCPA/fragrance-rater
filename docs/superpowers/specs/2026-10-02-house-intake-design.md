---
title: "House Intake Instrument: How Fragrance Houses Describe Their Fragrances"
schema_type: common
status: draft
owner: core-maintainer
purpose: >-
  Define the form a fragrance house uses to describe one of its fragrances in its own
  words, how those submissions are stored and fenced, and how a manager reviews them
  into ADR-012 manufacturer-provided evidence.
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
2. **Staged until reviewed.** Submissions live in `house_submissions`. A house can never change catalog facts
   directly: only a manager's review (below) writes to `fragrances`, `calibration_source_snapshots`, or perfumer
   attribution. `declared_label` still waits for D1, so the house's notes travel verbatim in the snapshot payload,
   which keeps ADR-017's sequencing intact.
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
6. **Managers review, houses write.** A manager can read and review every house's submitted records, but
   cannot create or edit their content, and does not see drafts. A manager writing on a house's behalf would no
   longer be the house's own statement.

## Manager review

Each submitted record starts as `pending`. A manager either adopts it or declines it, exactly once. If the house
submits a correction while the record is still pending, the original becomes `superseded` and can no longer be
reviewed. A record that has already been adopted or declined keeps its outcome when a correction follows.

**Adopting** answers two questions:

1. *Which catalog version is this?* The screen lists live versions from the same brand or with a similar name,
   ranked by how many identity facts agree, and the manager can search the whole catalog. Alternatively, the
   manager adds a new version built from the house's own name, brand, concentration, and launch year. The manager
   supplies only what a house cannot: the version key, the Edwards family (`Unclassified` per ADR-014 when none
   fits), and a gender target if the house did not state one.
2. *Which facts does the manager accept?* Each fact is compared with the chosen version and is either `same`,
   `differs`, or `house_silent`. Facts that agree are accepted by default. If the launch year or gender target
   differs, it can be accepted only by also writing it to the catalog, because evidence must never cite a value
   the catalog does not hold. If the name, brand, or concentration differs, it cannot be accepted, because that
   usually means a different version. A catalog typo should be fixed first. A fact the house did not give is
   never cited to it, including a gender target the manager chose for a new version.

An adoption writes, in one transaction:

- one `SourceSnapshot`: `source_type=manufacturer_provided`, the house's own `permission_state` (the manager
  cannot widen it), `fields` listing exactly the accepted facts, the product page as `source_url`,
  `source_reference` naming the submission and the representative, `verification_status=verified`, and a payload
  holding the house's full declaration verbatim;
- the catalog updates the manager accepted, or the new catalog version (`data_source=manufacturer`);
- optionally, the house's perfumer credits, citing the product page (or a `urn:fragrance-rater:house-submission:`
  reference when the house gave no page). An attribution that already exists is not duplicated.

The submission is then linked to both the catalog version and the snapshot. The outcome, the links, and the
reviewer are recorded with one conditional update, so if two managers review the same record at once, exactly one
succeeds and the other's writes are rolled back with a 409. Database constraints prevent a row from being marked
adopted without those links, or declined without a reason.

**Declining** requires a reason, which the house sees and can respond to by submitting a correction. A house
sees the outcome, the date, and the manager's note. It never sees the manager's account name or internal
catalog and evidence ids.

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

- From D1, have adoption also write `declared_label` rows from the snapshot payload, and backfill earlier
  adoptions the same way.
- The catalog API does not return perfumer attributions yet (an existing gap noted in `api/fragrances.py`), so
  adopted credits are stored but not yet shown on catalog pages.
- Notify the manager when a house submits. Today the manager has to check the list.
- A house-facing view of what was adopted, and a permission-withdrawal path that feeds ADR-017's purge-by-source.
- Move house membership from configuration to a managed table if the number of houses grows beyond a handful.
