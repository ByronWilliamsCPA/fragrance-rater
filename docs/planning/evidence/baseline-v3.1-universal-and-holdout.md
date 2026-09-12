---
title: "Universal Baseline and Validation Holdout V3.1"
schema_type: common
status: published
owner: core-maintainer
purpose: "Authoritative source content for the 43-fragrance/49-presentation calibration baseline and holdout panel referenced by P1.1 and ADR-009."
tags:
  - planning
  - calibration
  - evidence
---

**Received:** 2026-09-12, from the product owner, as the "AUTHORITATIVE UNIVERSAL BASELINE — V3.1"
and "AUTHORITATIVE VALIDATION HOLDOUT SET — V3.1" documents. This page reproduces that content
verbatim (reformatted as tables) so it is versioned in the repository rather than living only in
chat history, per
[Controlled Calibration V1](../../calibration-v1.md#configuration-and-workflow): *"The current
43-fragrance/49-presentation baseline is not seeded: its complete version-resolved manifest was
not present in the repository. Add the verified list through program setup/API; no catalog
identities were guessed from fragrance names."* This document is that verified list's source
text; it is not itself the P1.1 manifest (see **What this document is not**, below).

## Structural validation

Checked against the physical-structure and protocol rules in the source document:

- 33 unique `BaselineNumber` entries (#01-#33), 6 of which carry a `HIDDEN_REPEAT` presentation,
  giving 39 presentation slots (`S01A`-`S13C`) across 13 sessions of 3. Every one of the 39
  slots is assigned exactly once; there are no gaps or duplicate assignments.
- 10 unique `HoldoutNumber` entries (H01-H10), disjoint from the 33 baseline
  `BaselineNumber` identities. 33 + 10 = 43 fragrances; 39 + 10 = 49 presentations, matching the
  "43-fragrance/49-presentation baseline" already referenced in
  [Controlled Calibration V1](../../calibration-v1.md).
- Under the 5-day accelerated protocol (Day 1: S01-S03; Day 2: S04-S06; Day 3: S07-S09; Day 4:
  S10-S11; Day 5: S12-S13), every hidden repeat's initial and repeat presentation fall on
  different days:

  | Baseline # | Fragrance | Initial | Day | Repeat | Day |
  | :--- | :--- | :--- | :--- | :--- | :--- |
  | #03 | Giorgio Armani Acqua di Giò EDT | S01A | 1 | S07A | 3 |
  | #14 | Escentric Molecules Molecule 01 EDT | S02A | 1 | S08A | 3 |
  | #08 | Diptyque Eau Rose EDT | S03A | 1 | S09A | 3 |
  | #20 | Diptyque Tam Dao EDP | S04A | 2 | S10A | 4 |
  | #17 | Comme des Garçons Marseille EDT | S05A | 2 | S11A | 4 |
  | #27 | Indult Tihota EDP | S01C | 1 | S12A | 5 |

## What this document is not

Per `scripts/validate_calibration_manifest.py` (the P1.1 manifest validator), a calibration
manifest entry additionally requires a `fragrance_id` resolved to a canonical catalog
`FragranceVersion`, an absolute HTTPS `source_url`, non-empty `verification_evidence`, and
`physical_sample_confirmed: true`. None of that is established here:

- No entry below has been resolved to a catalog `FragranceVersion` id yet.
- Most entries have no recorded `source_url`/`verification_evidence` beyond the version notes
  transcribed from the source document.
- Only two entries are marked as already-owned inventory (#16 Dior Sauvage, #33 Imaginary
  Authors A City on Fire); every other physical sample is still on order, so
  `physical_sample_confirmed` cannot honestly be `true` for it yet.

P1.1 (`docs/planning/gates/p1.md`) therefore remains **blocked on inventory** even with this
document in place. It is the verified *design* input P1.1 needs once physical samples and source
verification are complete - see the [P1 gate](../gates/p1.md) for current status.

## Universal baseline (33 fragrances / 39 presentations)

| # | Fragrance | Concentration | Diagnostic role | Session | Hidden repeat | Version note |
| :-- | :--- | :--- | :--- | :--- | :--- | :--- |
| 01 | Acqua di Parma Colonia | Eau de Cologne | Citrus / aromatic freshness | S13B | - | |
| 02 | KAYALI Eden Juicy Apple \| 01 | Eau de Parfum | Juicy non-citrus fruit | S04B | - | |
| 03 | Giorgio Armani Acqua di Giò | Eau de Toilette | Mainstream aquatic / marine | S01A | S07A | |
| 04 | Diptyque Philosykos | Eau de Toilette | Leafy / milky green fig | S06A | - | |
| 05 | Frédéric Malle Synthetic Nature / Synthetic Jungle | Eau de Parfum | Intense green / floral / fresh / synthetic | S05C | - | Renamed from Synthetic Jungle to Synthetic Nature; preserve source/version metadata appropriately |
| 06 | Houbigant Fougère Royale | Eau de Parfum | Classical fougère | S10B | - | Current EDP formulation |
| 07 | Chanel N°5 | Eau de Parfum | Aldehydic floral | S12B | - | EDP version, not the original 1921 parfum formulation |
| 08 | Diptyque Eau Rose | Eau de Toilette | Bright / transparent rose | S03A | S09A | |
| 09 | Frédéric Malle Portrait of a Lady | Eau de Parfum | Dense rose / patchouli | S01B | - | |
| 10 | Frédéric Malle Carnal Flower | Eau de Parfum | White floral / tuberose | S02B | - | |
| 11 | Escentric Molecules Molecule 01 + Iris | Eau de Toilette | Iris / powder with Iso E Super | S13A | - | |
| 12 | Narciso Rodriguez for her PURE MUSC | Eau de Parfum | Clean musk | S03C | - | |
| 13 | Papillon Artisan Perfumes Salome | Eau de Parfum | Animalic / bodily boundary | S06B | - | |
| 14 | Escentric Molecules Molecule 01 | Eau de Toilette | Iso E Super / transparent wood | S02A | S08A | |
| 15 | Escentric Molecules Molecule 02 | Eau de Toilette | Ambroxan / mineral / radiance | S10C | - | |
| 16 | Dior Sauvage | Eau de Toilette | Modern fresh amberwood | S09B | - | Already owned |
| 17 | Comme des Garçons Marseille | Eau de Toilette | Soap / clean / fresh / synthetic | S05A | S11A | |
| 18 | Maison Francis Kurkdjian Baccarat Rouge 540 | Eau de Parfum | Sweet / radiant amberwood | S11B | - | |
| 19 | Lalique Encre Noire | Eau de Toilette | Dark / rooty vetiver | S02C | - | |
| 20 | Diptyque Tam Dao | Eau de Parfum | Creamy sandalwood | S04A | S10A | |
| 21 | Guerlain Mitsouko | Eau de Parfum | Classical chypre | S08B | - | |
| 22 | Guerlain Shalimar | Eau de Parfum | Classical amber | S05B | - | |
| 23 | Tom Ford Ombré Leather | Eau de Parfum | Leather | S12C | - | 2018 EDP/original-current EDP; NOT EDT, Parfum, or Ombré Leather 16 |
| 24 | Montale Black Aoud | Eau de Parfum | Dark/assertive oud + rose | S07C | - | |
| 25 | Comme des Garçons Avignon | Eau de Toilette | Focused incense | S04C | - | |
| 26 | Tauer L'Air du Désert Marocain | Eau de Toilette Intense | Dry / mineral / spiced amber | S03B | - | Original L'Air du Désert Marocain; NOT L'Air du Désert Marocain Noir |
| 27 | Indult Tihota | Eau de Parfum | Vanilla / sweetness | S01C | S12A | |
| 28 | Mugler Angel | Eau de Parfum | Patchouli gourmand | S09C | - | |
| 29 | Akro Bake | Eau de Parfum | Literal bakery gourmand | S11C | - | |
| 30 | Zoologist Bee | Extrait de Parfum | Honey / wax | S08C | - | |
| 31 | Tom Ford Tobacco Vanille | Eau de Parfum | Sweet / spiced tobacco | S06C | - | |
| 32 | Escentric Molecules Molecule 01 + Black Tea | Eau de Toilette | Tea / woody | S07B | - | |
| 33 | Imaginary Authors A City on Fire | Eau de Parfum | Smoke / combustion | S13C | - | Already owned |

## Validation holdout (10 fragrances / 10 presentations)

| # | Fragrance | Concentration | Diagnostic role | Related baseline probes | Note |
| :-- | :--- | :--- | :--- | :--- | :--- |
| H01 | Dior Homme Intense | Eau de Parfum | Iris / powder generalization | #11, #07 | 2011 EDP/current lineage |
| H02 | Tom Ford Oud Wood | Eau de Parfum | Polished oud / wood generalization | #24, #20 | Prior exposure must be checked per evaluator before treating as a valid blind holdout |
| H03 | Frédéric Malle Vetiver Extraordinaire | Eau de Parfum | Vetiver generalization | #19, #06 | |
| H04 | Unum LAVS | - | Incense generalization | #25, #33 | |
| H05 | Xerjoff Naxos | - | Honey / tobacco interaction and generalization | #30, #31, #27 | |
| H06 | Tom Ford Black Orchid | Eau de Parfum | Dense / dark floral generalization | #09, #10, #28 | |
| H07 | Caron Aimez-Moi | - | Violet / floral-powder generalization | - | Tests a deliberately underrepresented baseline dimension |
| H08 | Hermès Osmanthe Yunnan | - | Independent tea / transparent floral generalization | #32 | Perfumer: Jean-Claude Ellena |
| H09 | Serge Lutens Borneo 1834 | - | Patchouli / cacao generalization | #28, #29 | |
| H10 | Kenzo Jungle L'Éléphant | Eau de Parfum | Spice / maximalism | #26, #22 | |

## Data/model rules restated from the source document

These restate rules the source document specified for using this content; they do not relax any
existing calibration or measurement policy in
[Controlled Calibration V1](../../calibration-v1.md), P1, P2, or ADR-009.

1. `BaselineNumber` (#01-#33) and `HoldoutNumber` (H01-H10) are permanent canonical identities,
   stored separately from `FragranceVersion`, `SessionLabel`, and experimental role.
2. A hidden repeat or a holdout must reference the same canonical `FragranceVersion` as its
   original/related entry; neither creates a duplicate fragrance record.
3. Holdout eligibility is evaluator-specific: an evaluator is eligible for a given holdout only
   if they have no prior exposure that would compromise blind prediction testing (H02 is flagged
   explicitly for this check).
4. Before an evaluator's holdout is revealed, a frozen `ModelRun` (evaluator, model/version,
   training-data cutoff, timestamp, `FragranceVersion`, predicted liking, prediction
   confidence/uncertainty, information value if applicable) is persisted and the later evaluation
   links back to it; holdout results do not retroactively enter the training data for the run
   being validated, though they may become ordinary training data for later model versions once
   validation scoring is complete.
5. `SessionLabel` (`S01A`-`S13C`) identifies a physical/presentation slot, not smelling order;
   presentation order is randomized/counterbalanced per evaluator, and hidden-repeat status is
   never exposed to evaluators.
