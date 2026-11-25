---
title: "P1.1 baseline manifest verification record"
schema_type: common
status: draft
owner: core-maintainer
purpose: "Retain the validation result, content hash, and known limits of the P1.1 exact-version baseline manifest without committing the manifest itself."
tags:
  - planning
  - calibration
  - evidence
---

**Status:** Validated on 2026-11-24; closed on a single-checker pass by owner decision (second label check open)

## Result

| Item | Value |
| :--- | :--- |
| Program | Family calibration baseline, `v3.1-draft` |
| Entries | 49: 33 universal baseline, 10 holdout, 6 hidden repeats (43 distinct fragrances) |
| Validator | `scripts/validate_calibration_manifest.py` with `--expect-shape baseline=33,hidden_repeat=6,holdout=10,total=49`: `valid calibration manifest: 49 entries` |
| Manifest SHA-256 | `3bc3edc98d164a9e594f344338ae385d9d18e9a831d7652fad0949e62d6e4b76` |
| Verified by | B. Williams (core maintainer, product owner) |
| Label check performed | 2026-11-22, about 18:00 Pacific (recorded as `2026-11-23T02:00:00Z`) |
| Physical sample confirmed | `true` for all 49 entries (the 43 fragrances are labelled decants in hand; two are retail bottles) |
| Catalog rows | 43 rows created in production on 2026-11-24 in one transaction, family `Unclassified`; every entry carries its catalog `fragrance_id` |

The manifest is private. It stays outside the repository (the working copy sits in the gitignored `tmp_cleanup/`
directory), and only this record and the hash are committed. Anyone holding the file can re-check it against the hash
above and the validator command.

## Single-checker deviation

The 2026-11-01 owner decision accepted "the decant source's parent-product record plus a two-person label check" as
P1.1 proof for decants. This pass has one checker. The owner has no second person available, so on 2026-11-24 the owner
chose to close P1.1 on a single-checker pass for now.

- The manifest omits `label_checked_by` on every entry. The validator accepts the field absent but rejects a single
  name, so omission is the accurate encoding. It was therefore run without `--require-label-check`; with that flag it
  reports `label_checked_by is required (two people)` on all 49 entries, as expected.
- Closing on one checker is a recorded owner deviation from the two-person wording. It is not a two-person pass.
- A later second check is added by regenerating the manifest with `--checker`, which changes the hash. That record
  replaces this one.

## Known limits carried by the manifest

- **H01:** `version_key` `edp-current-2026` attests a 2026 decant, not the 2011 lineage the V3.1 design names, so the
  holdout's lineage assumption is unmet.
- **Concentrations confirmed from product pages by the owner:** H02, H05, H06 (Eau de Parfum).
- **Concentrations derived, not confirmed:** H04 (Extrait de Parfum), H07 (Eau de Parfum), H08 (Eau de Toilette),
  H09 (Eau de Parfum). Decant labels carry no concentration, and the owner's recheck of the product pages did not
  settle them. They rest on the decant source and retailer product pages recorded in each entry's
  `verification_evidence`. For H04, no brand page lists the product any more.
- **B05:** recorded as "Synthetic Nature" by owner decision (2026-11-22). The brand renamed it recently and the
  direction is unconfirmed, so "Synthetic Jungle" is carried as an R6 alias.
- **B25, H10:** no usable `source_url`; each carries a `source_reference`.
- **Immutability:** `version_key` cannot be patched after row creation, and concentration is part of the unique
  identity index. A wrong value is corrected by a new row plus a soft-delete of the old one, which changes the
  manifest and its hash.

## Catalog row creation

The rows were created through the application's own service layer from inside the production application container
over SSH (`FragranceService.create`), so no Authentik session cookie, API key, or token was used. The run was a single
transaction that commits only when no row is blocked. A read-only query afterwards found 43 live rows with 43 distinct
identities.

The per-row audit events (actor `operator-cli:p1.1-catalog`) were written to the exec session's output rather than the
container's main log, and the helper discarded that output, so there is no retained audit log for these 43 creates.
The rows and their timestamps, the manifest ids, and this record are the evidence.

## What this unblocks

R6 alias decisions for the 43 versions can now be authored against the verified identities, including the
"Synthetic Jungle" alias for B05.
