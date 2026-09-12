---
title: "Baseline/Holdout V3.1 Parfumo Source Resolution"
schema_type: common
status: published
owner: core-maintainer
purpose: "Per-entry Parfumo source_url/brand/concentration resolution for the V3.1 baseline and holdout panel, as a precursor to the P1.1 calibration manifest."
tags:
  - planning
  - calibration
  - evidence
---

**Date:** 2026-09-12

This resolves each entry in
[Baseline/Holdout V3.1](baseline-v3.1-universal-and-holdout.md) to a specific Parfumo page by
fetching Parfumo directly (its real live-search endpoint, then the candidate detail page) and
checking the returned brand/name/concentration/release year against the source document's stated
version. It is the identity-resolution research the product owner asked for ahead of physical
sample arrival; it is **not** the P1.1 manifest itself - see **What remains before P1.1 closes**.

## Method and a scraper defect found along the way

`ParfumoScraper.search()` (`GET /s_perfumes.php?keywords=...`) turned out to return a generic
"trending perfumes" page against the live site rather than query-specific results - the same two
unrelated links came back for every query tried. Reading `main322.js`/`_js_main322.js` (Parfumo's
own bundled JS) showed the visible search box actually posts to
`/action/livesearch/livesearch.php` with `{q, o, iwear}` and gets back an HTML fragment of
`.ls-perfume-item` cards (name, concentration, brand, release year, url). That endpoint was used
here instead, followed by fetching each chosen candidate's own page and reading its `h1.p_name_h1`
/ `span.p_brand_name` / `span.p_con` / `[itemprop='description']`, the same structural elements
`ParfumoScraper` already parses.

This is a real defect in `ParfumoScraper.search()`/`search_and_import()` against the live site,
separate from this baseline-resolution task; it is noted here for a follow-up fix rather than
addressed in this pass.

## Resolved entries

Concentration is marked **(not published)** where Parfumo's own page carries no `.p_con` element
and no concentration text anywhere on the page - this happens for fragrances with only one
release Parfumo tracks (no sibling concentration to disambiguate). In every such case the name
below is otherwise an exact, unambiguous match, and the concentration is the source document's
own stated value, still to be confirmed against the physical bottle per P1.1 (`physical_sample_confirmed`).

| # | Parfumo title | Brand (catalog) | Concentration | Year | Source URL |
| :-- | :--- | :--- | :--- | :--- | :--- |
| B01 | Colonia | Acqua di Parma | Eau de Cologne (confirmed) | 1916 | <https://www.parfumo.com/Perfumes/Acqua_di_Parma/Colonia_Eau_de_Cologne> |
| B02 | Eden Juicy Apple \| 01 | Kayali | Eau de Parfum (not published; single release) | 2021 | <https://www.parfumo.com/Perfumes/Kayali/eden-juicy-apple-01> |
| B03 | Acqua di Giò pour Homme | Giorgio Armani | Eau de Toilette (confirmed) | 1996 | <https://www.parfumo.com/Perfumes/Giorgio_Armani/Acqua_di_Gio_pour_Homme_Eau_de_Toilette> |
| B04 | Philosykos | Diptyque | Eau de Toilette (confirmed) | 1996 | <https://www.parfumo.com/Perfumes/Diptyque/Philosykos> |
| B05 | Synthetic Nature | Editions de Parfums Frédéric Malle | Eau de Parfum (not published; single release) | 2021 | <https://www.parfumo.com/Perfumes/Editions_de_Parfum_Frederic_Malle/synthetic-nature-synthetic-jungle> |
| B06 | Fougère Royale (2010) | Houbigant | Eau de Parfum (confirmed) | 2010 | <https://www.parfumo.com/Perfumes/Houbigant/Fougere_Royale_2010> |
| B07 | N°5 | Chanel | Eau de Parfum (confirmed) | 1986 | <https://www.parfumo.com/Perfumes/Chanel/N5_Eau_de_Parfum> |
| B08 | Eau Rose | Diptyque | Eau de Toilette (confirmed) | 2012 | <https://www.parfumo.com/Perfumes/Diptyque/Eau_Rose> |
| B09 | Portrait of a Lady | Editions de Parfums Frédéric Malle | Eau de Parfum (confirmed) | 2010 | <https://www.parfumo.com/Perfumes/Editions_de_Parfum_Frederic_Malle/portrait-of-a-lady-eau-de-parfum> |
| B10 | Carnal Flower | Editions de Parfums Frédéric Malle | Eau de Parfum (confirmed) | 2005 | <https://www.parfumo.com/Perfumes/Editions_de_Parfum_Frederic_Malle/carnal-flower-eau-de-parfum> |
| B11 | Molecule 01 + Iris | Escentric Molecules | Eau de Toilette (not published; single release) | 2021 | <https://www.parfumo.com/Perfumes/Escentric_Molecules/molecule-01-iris> |
| B12 | For Her Pure Musc | Narciso Rodriguez | Eau de Parfum (confirmed) | 2019 | <https://www.parfumo.com/Perfumes/Narciso_Rodriguez/for-her-pure-musc-eau-de-parfum> |
| B13 | Salome | Papillon Artisan Perfumes | Eau de Parfum (not published; single release) | 2015 | <https://www.parfumo.com/Perfumes/Papillon_Artisan_Perfumes/Salome> |
| B14 | Molecule 01 | Escentric Molecules | Eau de Toilette (not published; single release) | 2006 | <https://www.parfumo.com/Perfumes/Escentric_Molecules/Molecule_01> |
| B15 | Molecule 02 | Escentric Molecules | Eau de Toilette (not published; single release) | 2008 | <https://www.parfumo.com/Perfumes/Escentric_Molecules/Molecule_02> |
| B16 | Sauvage | Dior | Eau de Toilette (confirmed) | 2015 | <https://www.parfumo.com/Perfumes/Dior/Sauvage_Eau_de_Toilette> |
| B17 | Marseille | Comme des Garçons | Eau de Toilette (not published; single release) | 2021 | <https://www.parfumo.com/Perfumes/Comme_des_Garons/marseille> |
| B18 | Baccarat Rouge 540 | Maison Francis Kurkdjian | Eau de Parfum (confirmed) | 2016 | <https://www.parfumo.com/Perfumes/Maison_Francis_Kurkdjian/Baccarat_Rouge_540_Eau_de_Parfum> |
| B19 | Encre Noire | Lalique | Eau de Toilette (confirmed) | 2006 | <https://www.parfumo.com/Perfumes/Lalique/Encre_Noire_Eau_de_Toilette> |
| B20 | Tam Dao | Diptyque | Eau de Parfum (confirmed) | 2012 | <https://www.parfumo.com/Perfumes/Diptyque/Tam_Dao_Eau_de_Parfum> |
| B21 | Mitsouko | Guerlain | Eau de Parfum (confirmed) | (not shown on page) | <https://www.parfumo.com/Perfumes/Guerlain/Mitsouko> |
| B22 | Shalimar | Guerlain | Eau de Parfum (confirmed) | 1986 | <https://www.parfumo.com/Perfumes/Guerlain/Shalimar> |
| B23 | Ombré Leather (2018) | Tom Ford | Eau de Parfum (confirmed) | 2018 | <https://www.parfumo.com/Perfumes/Tom_Ford/ombre-leather-2018-eau-de-parfum> |
| B24 | Black Aoud | Montale | Eau de Parfum (not published; single release) | 2006 | <https://www.parfumo.com/Perfumes/Montale/Black_Aoud> |
| B25 | Series 3: Incense - Avignon | Comme des Garçons | Eau de Toilette (not published; single release) | 2002 | <https://www.parfumo.com/Perfumes/Comme_des_Garons/Series_3_Incense_Avignon> |
| B26 | № 02 - L'Air du Désert Marocain | Tauer Perfumes | Eau de Toilette Intense (confirmed) | 2005 | <https://www.parfumo.com/Perfumes/Tauer/no-02-l-air-du-desert-marocain-eau-de-toilette-intense> |
| B27 | Tihota | Indult | Eau de Parfum (not published; single release) | 2006 | <https://www.parfumo.com/Perfumes/Indult/Tihota> |
| B28 | Angel | Mugler | Eau de Parfum (confirmed) | 1992 | <https://www.parfumo.com/Perfumes/mugler/Angel> |
| B29 | Bake | Akro | Eau de Parfum (not published; single release) | 2023 | <https://www.parfumo.com/Perfumes/Akro/bake> |
| B30 | Bee | Zoologist | Extrait de Parfum (not published; single release) | 2019 | <https://www.parfumo.com/Perfumes/Zoologist/bee> |
| B31 | Tobacco Vanille | Tom Ford | Eau de Parfum (confirmed) | 2007 | <https://www.parfumo.com/Perfumes/Tom_Ford/Tobacco_Vanille_Eau_de_Parfum> |
| B32 | Molecule 01 + Black Tea | Escentric Molecules | Eau de Toilette (not published; single release) | 2023 | <https://www.parfumo.com/Perfumes/Escentric_Molecules/molecule-01-black-tea> |
| B33 | A City on Fire | Imaginary Authors | Eau de Parfum (not published; single release) | 2014 | <https://www.parfumo.com/Perfumes/Imaginary_Authors/a-city-on-fire> |
| H01 | Dior Homme Intense (2011) | Dior | Eau de Parfum (not published; single release for this year) | 2011 | <https://www.parfumo.com/Perfumes/Dior/Dior_Homme_Intense_2011> |
| H02 | Oud Wood | Tom Ford | Eau de Parfum (confirmed) | 2007 | <https://www.parfumo.com/Perfumes/Tom_Ford/Oud_Wood_Eau_de_Parfum> |
| H03 | Vétiver Extraordinaire | Editions de Parfums Frédéric Malle | Eau de Parfum (not published; single release) | 2002 | <https://www.parfumo.com/Perfumes/Editions_de_Parfum_Frederic_Malle/Vetiver_Extraordinaire> |
| H04 | LAVS | Filippo Sorcinelli (see note) | Not published anywhere on the page | 2013 | <https://www.parfumo.com/Perfumes/Filippo_Sorcinelli/lavs> |
| H05 | Naxos | Xerjoff | Eau de Parfum (not published; single release) | 2015 | <https://www.parfumo.com/Perfumes/Xerjoff/naxos> |
| H06 | Black Orchid | Tom Ford | Eau de Parfum (confirmed) | 2006 | <https://www.parfumo.com/Perfumes/Tom_Ford/Black_Orchid_Eau_de_Parfum> |
| H07 | **Unresolved** - see note | Caron | - | - | - |
| H08 | Osmanthe Yunnan | Hermès | Not published anywhere on the page | 2005 | <https://www.parfumo.com/Perfumes/Hermes/osmanthe-yunnan> |
| H09 | Bornéo 1834 | Serge Lutens | Not published anywhere on the page | 2005 | <https://www.parfumo.com/Perfumes/Serge_Lutens/Borneo_1834> |
| H10 | Kenzo Jungle / Jungle L'Éléphant | Kenzo | Eau de Parfum (not published; confirmed by name/image filename match) | 1996 | <https://www.parfumo.com/Perfumes/Kenzo/Kenzo_Jungle_Jungle_L_Elephant> |

## Open items for the product owner

- **H07 Caron Aimez-Moi is unresolved - do not guess.** Parfumo lists several distinct,
  similarly-named Caron releases: "Aimez-Moi (1996)" (Eau de Toilette), "Aimez-Moi (2013)",
  and "Aimez-Moi Comme Je Suis" (2020) are plausible matches for "Aimez-Moi"; separately,
  "N'Aimez que Moi" (1916 Parfum, a 2021 reissue, and an Eau de Parfum) is a *different*,
  similarly-spelled vintage Caron fragrance, not this one. Please confirm which release the
  physical/ordered bottle is (year and concentration) before this entry is added to any manifest.
- **H04 Unum LAVS brand housing.** Parfumo catalogs this fragrance under the perfumer's personal
  name, "Filippo Sorcinelli," with "Unum" recorded as the collection/line name, not as a
  top-level brand. The source document calls it "Unum LAVS." Please confirm whether the catalog
  entry should record the brand as "Unum" (matching the source document and the bottle) or
  "Filippo Sorcinelli" (matching Parfumo's brand taxonomy) - this project's catalog has no
  separate brand/line hierarchy today (see `docs/calibration-v1.md`), so one string must be
  chosen.
- **Concentration not independently confirmable from Parfumo for the "(not published)" rows
  above.** These are all single-release fragrances with no Parfumo concentration field to cross-
  check against; the source document's stated concentration is carried forward as-is and remains
  subject to physical-bottle confirmation like every other entry, per P1.1's
  `physical_sample_confirmed` requirement.
- **`ParfumoScraper.search()`/`search_and_import()` do not work against the live site today**
  (see **Method**, above) - a separate defect from this resolution pass, noted here for
  prioritization rather than fixed in it.

## What remains before P1.1 closes

This resolution gives each entry a specific, checked Parfumo `source_url` and confirms brand/
name/concentration/year against the source document wherever Parfumo publishes them. It does not
yet give any entry:

- a `fragrance_id` (created only once each entry is imported into a running deployment's catalog,
  e.g. via `fragrance-rater import-data parfumo-url`);
- `verification_evidence` in the manifest-validator sense (a reviewed statement of how identity
  was confirmed, to be written once physical samples arrive); or
- `physical_sample_confirmed: true` for anything beyond the two already-owned items (#16, #33),
  and even those still need that confirmation recorded formally.

P1.1 (`docs/planning/gates/p1.md`) stays **blocked on inventory** until those three exist for
every entry, `scripts/validate_calibration_manifest.py` passes, and the resulting manifest is
loaded through Program setup per `docs/calibration-v1.md`.
