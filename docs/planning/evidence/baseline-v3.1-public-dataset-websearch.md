---
title: "Baseline/Holdout V3.1 Public Dataset (WebSearch Pass, One-Time)"
schema_type: common
status: published
owner: core-maintainer
purpose: "Records notes/accords/family/perfumer/description facts gathered for the 33 baseline + 10 holdout fragrances via WebSearch only, with a source citation for every fact, as a one-time research pass rather than a repeatable import."
tags:
  - planning
  - calibration
  - evidence
---

**Date:** 2026-09-15

**Prompted by:** "Make sure to document what you get from where. This is a one time exercise
we don't need to build repeatable processes" - a follow-up to
[Dataset-Building Source Compliance](baseline-v3.1-dataset-source-compliance.md), which found
that parfumo.com, fragrantica.com, and basenotes.net each exclude `ClaudeBot` site-wide in
`robots.txt`. This document is the resulting one-time research pass: four parallel research
passes (one per block of the 43 entries below) used **only the `WebSearch` tool** - a licensed
indexed-snippet search API, not a crawl of the excluded sites - to gather descriptive content
(note pyramids, accords, family, perfumer, a consensus description), citing every source
actually used. `WebFetch` was used directly only against sites *not* excluded (Wikipedia was
fetched directly for three entries, noted inline below); nothing was fetched directly from
parfumo.com, fragrantica.com, or basenotes.net - citations to those domains below are WebSearch
snippet citations, not page fetches.

**No code or tooling was added or changed for this.** This is a manual, one-time documentation
exercise, not a new import path, scraper, or pipeline - consistent with the request not to build
a repeatable process. Nothing below has been written into the application's `Fragrance` catalog
or any database; it exists only as this document.

## What this is and is not

- This is **public-source consensus content** - what Fragrantica, Parfumo, Basenotes, brand
  official sites, retailers, and independent review blogs (Kafkaesque, Now Smell This, Bois de
  Jasmin, Cafleurebon, and others) publicly say about each fragrance - gathered secondhand via
  search snippets, not verified against a physical bottle.
- It is **not** P1.1 evidence: it does not resolve a `fragrance_id`, does not add
  `verification_evidence` in the manifest-validator sense, and does not change
  `physical_sample_confirmed` status for any entry (still true only for #16 and #33, per
  [Parfumo Source Resolution](baseline-v3.1-parfumo-source-resolution.md)). P1.1 remains
  **blocked on inventory** exactly as before.
- Where sources disagreed, gave no clear answer, or an attribution seemed thin, each research
  pass was told to say so rather than guess - consistent with this project's "unknown stays
  unknown" invariant. Those flags are collected in **Cross-cutting flags**, below, in addition to
  being noted inline.

## Baseline (33 fragrances)

### 01. Acqua di Parma — Colonia

- **Notes**: Top: Sicilian lemon, sweet orange, bergamot. Heart: lavender, rose, verbena, rosemary. Base: vetiver, sandalwood, patchouli.
- **Main accords**: Citrus and aromatic/herbal, with a floral-woody drydown (bergamot/lemon lead, lavender-rosemary heart, woody base).
- **Fragrance family**: Citrus Aromatic (with floral facets); often simply called a classic "eau de cologne" style.
- **Perfumer**: Not publicly/consistently attributed for the original 1916 formula - **unknown/uncertain**. (François Demachy is credited for a *different* flanker, Colonia Oud, not the original.)
- **Description**: A timeless, sunny Italian classic - bright Calabrian citrus opens, an aromatic lavender-rosemary-rose heart follows, and warm woody vetiver/sandalwood/patchouli settles it. Considered the archetypal "elegant Mediterranean cologne."
- **Sources**: [Fragrantica: Acqua di Parma Colonia](https://www.fragrantica.com/perfume/Acqua-di-Parma/Acqua-di-Parma-Colonia-1681.html), [Parfumo: Colonia (Eau de Cologne)](https://www.parfumo.com/Perfumes/Acqua_di_Parma/Colonia_Eau_de_Cologne), [Basenotes: Acqua di Parma Colonia](https://basenotes.com/fragrances/acqua-di-parma-colonia-by-acqua-di-parma.26120042), [Cult Beauty: The Ultimate Guide to Acqua di Parma](https://www.cultbeauty.com/blog/101-guide-to-acqua-di-parma/)

### 02. Kayali — Eden Juicy Apple | 01

- **Notes**: Top: red apple, lychee, black currant, pink grapefruit. Middle: wild berries, raspberry bloom/blossom, jasmine, May rose. Base: sugar, musk, vanilla flower, amber, moss.
- **Main accords**: Fruity, sweet, vanilla.
- **Fragrance family**: Floral Fruity Gourmand.
- **Perfumer(s)**: Clement Gavarry and Gabriela Chelariu.
- **Description**: A juicy, candy-like fruity gourmand built on a crisp red apple accord layered with berries and a soft jasmine/rose heart, finished with sweet vanilla-musk-amber - widely described as addictive and mainstream-appealing.
- **Sources**: [Fragrantica: Eden Juicy Apple | 01 EDP](https://www.fragrantica.com/perfume/Kayali-Fragrances/Eden-Juicy-Apple-01-Eau-De-Parfum-70875.html), [Fragrantica News: Kayali Eden Juicy Apple 01](https://www.fragrantica.com/news/Kayali-Eden-Juicy-Apple-01-Eau-De-Parfum-15875.html), [Sephora: Kayali Eden Juicy Apple 01](https://www.sephora.com/product/kayali-eden-juicy-apple-01-P479717), [KAYALI official site](https://us.kayali.com/products/eden-juicy-apple-01)

### 03. Giorgio Armani — Acqua di Giò pour Homme

- **Notes**: Top: Calabrian bergamot, lemon, neroli, green tangerine. Middle: sources disagree - either rosemary/persimmon/jasmine/cyclamen/freesia/coriander/marine notes, or sweet lime/mandarin as an alternate top variant; both are given by different aggregator sites. Base: Indonesian patchouli, cedar, oakmoss, white musk.
- **Main accords**: Aquatic/marine leads, then citrus and aromatic (rosemary), with a woody-musky base.
- **Fragrance family**: Aquatic (Fresh Aquatic) - generally credited with popularizing the men's aquatic family.
- **Perfumer**: Alberto Morillas (lead nose; Annick Menardo also credited in some fuller histories).
- **Description**: A fresh, Mediterranean-inspired marine scent - bright citrus, an aromatic rosemary/sea-breeze heart, and a warm woody-musky base. One of the most influential and best-selling men's fragrances ever released.
- **Sources**: [Fragrantica: Acqua di Gio (1996)](https://www.fragrantica.com/perfume/Giorgio-Armani/Acqua-di-Gio-410.html), [Parfumo: Acqua di Giò pour Homme](https://www.parfumo.com/Perfumes/Giorgio_Armani/Acqua_di_Gio_pour_Homme_Eau_de_Toilette), [Basenotes: Acqua di Giò pour Homme](https://basenotes.com/fragrances/acqua-di-gio-pour-homme-by-giorgio-armani.26120041), [Armani Beauty official site](https://www.giorgioarmanibeauty-usa.com/fragrances/mens-cologne/acqua-di-gio/acqua-di-gio-eau-de-toilette/A005.html)

### 04. Diptyque — Philosykos

- **Notes**: Two disagreeing framings: Diptyque's own simplified version (Top: fig; Middle: fig leaf; Base: fig tree) vs. a fuller aggregator pyramid (Top: fig leaf, fig; Middle: green notes, coconut; Base: fig tree, woody notes, cedar). Best characterized as a fig-note-family composition rather than a strict classic pyramid.
- **Main accords**: Green, woody, milky/lactonic, sweet-fresh.
- **Fragrance family**: Aromatic Green ("green fig").
- **Perfumer**: Olivia Giacobetti.
- **Description**: Widely regarded as the definitive "fig" fragrance - tart green leaves up front, a not-too-sweet milky fig fruit in the heart, dry woody-fig-tree base. Praised for clarity and naturalistic realism.
- **Sources**: [Fragrantica: Philosykos EDT](https://www.fragrantica.com/perfume/Diptyque/Philosykos-Eau-de-Toilette-72040.html), [Fragrantica: Philosykos EDP (2012)](https://www.fragrantica.com/perfume/Diptyque/Philosykos-Eau-de-Parfum-2012-56405.html), [Basenotes: Philosykos EDT](https://basenotes.com/fragrances/philosykos-eau-de-toilette-by-diptyque.26122099), [Luckyscent: Philosykos EDT](https://www.luckyscent.com/products/philosykos-eau-de-toilette-by-diptyque), [Diptyque official site](https://www.diptyqueparis.com/en_us/p/philosykos-eau-de-toilette-100ml-1.html)

### 05. Editions de Parfums Frédéric Malle — Synthetic Nature (f.k.a. Synthetic Jungle)

- **Notes**: Top: galbanum, basil, black currant. Middle: lily-of-the-valley, hyacinth, jasmine, ylang-ylang, almond. Base: oakmoss, patchouli.
- **Main accords**: Green, mossy/earthy, intensely floral (dewy lily-of-the-valley/hyacinth), amplified with a "glossy synthetic" black-currant brightness.
- **Fragrance family**: Green Chypre (a modernized take on the classic green chypre).
- **Perfumer**: Anne Flipo, with Frédéric Malle.
- **Description**: A deliberately "synthetic-forward" reinterpretation of the classic green chypre accord (explicitly a nod to Chanel No. 19 and Estée Lauder Private Collection) - sharp galbanum-basil greenness, dewy white florals, mossy patchouli base.
- **Sources**: [Fragrantica: Synthetic Jungle](https://www.fragrantica.com/perfume/Frederic-Malle/Synthetic-Jungle-68794.html), [Fragrantica: Synthetic Nature](https://www.fragrantica.com/perfume/Frederic-Malle/Synthetic-Nature-89055.html), [Cafleurebon review](https://cafleurebon.com/frederic-malle-synthetic-jungle-review-anne-flipo-2021-the-vertsatile-draw/), [The Candy Perfume Boy review](https://thecandyperfumeboy.com/2021/10/20/perfume-review-synthetic-jungle-by-editions-de-parfums-frederic-malle/), [Perfume Society: Malle/Flipo conversation](https://perfumesociety.org/synthetic-jungle-frederic-malle-in-conversation-with-anne-flipo/)

### 06. Houbigant — Fougère Royale (2010)

- **Notes**: Top: lavender, green notes, chamomile, bergamot. Middle: geranium, carnation, cinnamon, rose, lilac. Base: oakmoss, clary sage, patchouli, tonka bean, amber.
- **Main accords**: Aromatic-lavender lead, spicy-floral heart, earthy mossy-woody base - a classic fougère structure with extra floral/spice richness.
- **Fragrance family**: Aromatic Fougère.
- **Perfumer**: Rodrigo Flores-Roux (working with creative director Roja Dove on the reinterpretation of Paul Parquet's 1882 original).
- **Description**: A modernized, more floral and spice-laced reworking of the historic 1882 fougère archetype.
- **Sources**: [Fragrantica: Fougère Royale (2010)](https://www.fragrantica.com/perfume/Houbigant/Fougere-Royale-2010-10891.html), [Parfumo: Fougère Royale 2010 EDP](https://www.parfumo.com/Perfumes/Houbigant/Fougere_Royale_2010), [Now Smell This review](https://nstperfume.com/2010/12/02/houbigant-fougere-royale-fragrance-review/), [Cafleurebon review](https://cafleurebon.com/houbigant-fougere-royale-review-rodrigo-flores-roux-2010-10th-year-anniversary-draw/), [Luckyscent](https://www.luckyscent.com/products/fougere-royale-by-houbigant)

### 07. Chanel — N°5 Eau de Parfum (1986)

- **Notes**: Top: aldehydes, ylang-ylang, neroli, bergamot, peach. Middle: iris, jasmine, rose, lily-of-the-valley. Base: sandalwood, oakmoss, vanilla, patchouli, vetiver.
- **Main accords**: Aldehydic-floral lead, rich floral heart, warm woody-powdery-vanillic base.
- **Fragrance family**: Floral Aldehyde.
- **Perfumer**: Jacques Polge (this 1986 EDP is his fuller reinterpretation of Ernest Beaux's 1921 original parfum).
- **Description**: A richer, more voluminous rendition of the 1921 original, retaining the aldehydic sparkle and abstract floral bouquet but built up with a warmer, ambery-vanillic, powdery woody base.
- **Sources**: [Fragrantica: Chanel No 5 EDP (1986)](https://www.fragrantica.com/perfume/Chanel/Chanel-No-5-Eau-de-Parfum-40069.html), [Basenotes: No. 5 EDP (1986)](https://basenotes.com/fragrances/no-5-eau-de-parfum-by-chanel.26156223), [Bois de Jasmin review](https://boisdejasmin.com/2011/02/chanel-no-5-perfume-edt-edp-review-and-fragrance-poll.html), [Wikipedia: Chanel No. 5](https://en.wikipedia.org/wiki/Chanel_No._5)

### 08. Diptyque — Eau Rose

- **Notes**: Two framings again disagree - an aggregator pyramid (Top: litchi, black currant, bergamot; Middle: rose, geranium, jasmine; Base: musk, white honey, Virginia cedar) vs. Diptyque's own simpler framing (Top: Damask rose; Middle: Centifolia rose; Base: litchi). Both agree the fragrance is built on Damascena + Centifolia rose with a lychee/fruity brightness.
- **Main accords**: Floral (rose-centered) with fruity brightness and a soft honeyed-musky finish.
- **Fragrance family**: Floral Fruity.
- **Perfumer**: Not clearly attributed for the original 2012 EDT - **unknown/uncertain**. (Fabrice Pellegrin is confirmed only for the later, distinct 2022 EDP reformulation.)
- **Description**: A bright, playful rose - juicy lychee/black currant top, Damascena/Centifolia rose heart, soft honey-musk drydown - closer to a fresh tea rose than a deep or spicy one.
- **Sources**: [Fragrantica: Eau Rose (2012)](https://www.fragrantica.com/perfume/Diptyque/Eau-Rose-14214.html), [Basenotes: Eau Rose EDT (2012)](https://basenotes.com/fragrances/eau-rose-by-diptyque.26133691), [Now Smell This review](https://nstperfume.com/2012/01/20/diptyque-eau-rose-fragrance-review/), [Diptyque official site](https://www.diptyqueparis.com/en_us/l/fragrances/eau-rose-collection.html), [Cafleurebon (2022 EDP, perfumer context)](https://cafleurebon.com/diptyque-eau-rose-eau-de-parfum-review-fabrice-pellegrin-2022-unleash-the-rose-with-maurice-harris-draw/)

### 09. Editions de Parfums Frédéric Malle — Portrait of a Lady

- **Notes**: Top: rose, clove, raspberry, black currant, cinnamon, red berries. Middle: Turkish rose, patchouli, incense, sandalwood, ylang-ylang. Base: incense, sandalwood, musk, benzoin, amber, cedar, ambergris, vanilla.
- **Main accords**: Rose leads overwhelmingly, then patchouli and incense/spice, with a warm ambery-woody-musky base.
- **Fragrance family**: Oriental Floral (a "baroque" rose chypre-oriental hybrid).
- **Perfumer**: Dominique Ropion.
- **Description**: A deliberately maximalist "baroque" rose fragrance pairing an unprecedented dose of Turkish rose with an equally intense patchouli heart, spice, incense, and an ambery-woody-musky base. Inducted into the Fragrance Foundation Hall of Fame.
- **Sources**: [Fragrantica: Portrait of a Lady](https://www.fragrantica.com/perfume/Frederic-Malle-Editions-de-Parfums/Portrait-of-a-Lady-10464.html), [Frédéric Malle official site](https://www.fredericmalle.com/product/19566/50241/parfums/portrait-of-a-lady/by-dominique-ropion), [Now Smell This review](https://nstperfume.com/2010/12/15/frederic-malle-portrait-of-a-lady-perfume-review/), [Parfumo: Portrait of a Lady](https://www.parfumo.com/Perfumes/Editions_de_Parfum_Frederic_Malle/portrait-of-a-lady-eau-de-parfum)

### 10. Editions de Parfums Frédéric Malle — Carnal Flower

- **Notes**: Top: eucalyptus, melon, bergamot, galbanum. Middle: coconut, tuberose, jasmine, ylang-ylang, orange blossom. Base: white musk, animal notes, amber.
- **Main accords**: Tuberose-white floral dominant, green-camphoraceous top, creamy coconut-musk facet.
- **Fragrance family**: White Floral (tuberose-centric).
- **Perfumer**: Dominique Ropion (formula development reportedly took over two years).
- **Description**: Regarded as one of the definitive modern tuberose fragrances - green galbanum/eucalyptus brightness up top, heady tuberose heart, creamy coconut-milky, musky warmth beneath.
- **Sources**: [Fragrantica: Carnal Flower](https://www.fragrantica.com/perfume/Frederic-Malle/Carnal-Flower-1024.html), [Frédéric Malle official site](https://www.fredericmalle.com/product/19566/50210/parfums/carnal-flower/by-dominique-ropion), [Kafkaesque review](https://kafkaesqueblog.com/2014/01/20/frederic-malle-carnal-flower/), [The Scented Devil review](https://varanisridari.home.blog/2025/04/16/carnal-flower-by-editions-de-parfums-frederic-malle-2005/)

### 11. Escentric Molecules — Molecule 01 + Iris

- **Notes**: No traditional pyramid - a minimalist, near-linear composition. Flat list: Iso E Super, iris pallida absolute (orris root), Hedione.
- **Main accords**: Woody (from Iso E Super) and floral-powdery/creamy (from iris) - sources split between "Woody" and "Soft Floral" as the primary family.
- **Fragrance family**: Woody / Soft Floral - no single consensus label.
- **Perfumer**: Geza Schoen.
- **Description**: Pairs a large dose of Iso E Super (velvety, cedar-like, "second skin") with iris pallida absolute for a sweet, creamy, powdery floral lift rather than earthy/dry iris.
- **Sources**: [Fragrantica: Molecule 01 + Iris](https://www.fragrantica.com/perfume/Escentric-Molecules/Molecule-01-Iris-66048.html), [Basenotes: Molecule 01 + Iris](https://basenotes.com/fragrances/molecule-01-iris-by-escentric-molecules.26163098), [Cafleurebon review](https://cafleurebon.com/molecule-01-iris-by-escentric-molecules-review-geza-schoen-2021-plus-inspired-iris-giveaway/), [Escentric Molecules official site](https://www.escentric.com/en-us/products/molecule-01-plus-iris-100ml), [Scent Grail](https://scentgrail.com/holy-grail-scents/molecule-01-review/)

### 12. Narciso Rodriguez — for her Pure Musc

- **Notes**: Top: Musk. Middle: Jasmine, Ylang-Ylang, Orange Blossom. Base: Cashmeran.
- **Main accords**: Musky (lighter/darker nuances), white floral, warm/powdery woody (cashmeran).
- **Fragrance family**: Floral Woody Musk.
- **Perfumer**: Sonia Constant.
- **Description**: An intimate, skin-close musk built as a "duality" of lighter/darker musk facets wrapped in a creamy white-floral bouquet, softened by warm, slightly powdery cashmeran woods - designed to work alone or as a layering base.
- **Sources**: [Fragrantica: Pure Musc For Her (2019)](https://www.fragrantica.com/perfume/Narciso-Rodriguez/Pure-Musc-For-Her-53441.html), [Parfumo: For Her Pure Musc EDP](https://www.parfumo.com/Perfumes/Narciso_Rodriguez/for-her-pure-musc-eau-de-parfum), [Narciso Rodriguez official site](https://www.narcisorodriguezparfums.com/en/narciso-rodriguez-for-her-pure-musc/for-her-PURE-MUSC.html)

### 13. Papillon Artisan Perfumes — Salome

- **Notes**: Top: bitter red orange, bergamot. Middle: hyraceum, jasmine, carnation, tobacco, Turkish rose, orange blossom. Base: castoreum, cumin, oakmoss, hay, patchouli, styrax, birch tar, vanilla. Sources vary on exact tier placement of hyraceum/cumin/castoreum, though the note list itself is consistent.
- **Main accords**: Animalic, chypre, floral (jasmine/rose/orange blossom), smoky/leathery, musky.
- **Fragrance family**: Chypre Floral - commonly described as an "animalic chypre."
- **Perfumer**: Liz Moores (Papillon's founder).
- **Description**: A bold, unapologetically animalic chypre inspired by a 1920s photograph of an erotic dancer - hyraceum/castoreum/cumin evoking warm skin, balanced against a lush indolic floral bouquet, finishing smoky and mossy. A 2016 Art and Olfaction Award nominee.
- **Sources**: [Fragrantica: Salome (2015)](https://www.fragrantica.com/perfume/Papillon-Artisan-Perfumes/Salome-32210.html), [Parfumo: Salome](https://www.parfumo.com/Perfumes/Papillon_Artisan_Perfumes/Salome), [vivir.com review](https://vivir.com/article/papillon-artisan-perfumes-salome), [Luckyscent](https://www.luckyscent.com/products/salome-by-papillon-artisan-perfumes)

### 14. Escentric Molecules — Molecule 01

- **Notes**: No conventional pyramid - a single-material composition of Iso E Super alone.
- **Main accords**: Woody, musky; described as skin-scent-like with "marked intermittence" (fades in and out to the wearer's own nose).
- **Fragrance family**: Fragrantica classifies it "Woody Floral Musk," though given the single-material composition this label should be treated with caution; most descriptive copy simply says "woody/musky."
- **Perfumer**: Geza Schoen.
- **Description**: A conceptual, minimalist fragrance built entirely around Iso E Super, credited with popularizing "skin scent" and single-molecule perfumery.
- **Sources**: [Fragrantica: Molecule 01 (2006)](https://www.fragrantica.com/perfume/Escentric-Molecules/Molecule-01-845.html), [Escentric Molecules official site](https://www.escentric.com/en-us/pages/molecule-01), [Parfumo: Molecule 01](https://www.parfumo.com/Perfumes/Escentric_Molecules/Molecule_01)

### 15. Escentric Molecules — Molecule 02

- **Notes**: Also a single-material composition - Ambroxan alone.
- **Main accords**: Amber/ambery, musky, with a soft citrus/marine-adjacent freshness some reviewers note ("fountain pen ink").
- **Fragrance family**: Amber/musk - described plainly rather than assigned a formal pyramid family.
- **Perfumer**: Geza Schoen.
- **Description**: The sister composition to Molecule 01, built entirely around Ambroxan - warm, sweet, velvety, highly persistent, a "skin scent" whose expression varies by wearer chemistry.
- **Sources**: [Fragrantica: Molecule 02 (2008)](https://www.fragrantica.com/perfume/Escentric-Molecules/Molecule-02-3606.html), [Parfumo: Molecule 02](https://www.parfumo.com/Perfumes/Escentric_Molecules/Molecule_02), [ZGO Perfumery](https://zgoperfumery.com/products/escentric-molecules-molecule-02-eau-de-toilette)

### 16. Dior — Sauvage (2015)

- **Notes**: Top: Calabrian bergamot, pepper. Middle: Sichuan pepper, lavender, pink pepper, vetiver, patchouli, geranium, elemi. Base: Ambroxan, cedar, labdanum.
- **Main accords**: Fresh spicy, amber, citrus/aromatic.
- **Fragrance family**: Aromatic Fougère / Woody Aromatic ("fresh spicy amber").
- **Perfumer**: François Demachy.
- **Description**: A clean, blue-sky citrus-pepper opening over a dry, diffusive ambroxan-and-cedar base - a huge commercial phenomenon that came to define the mainstream 2010s "fresh ambroxan" men's style.
- **Sources**: [Fragrantica: Sauvage (2015)](https://www.fragrantica.com/perfume/Dior/Sauvage-31861.html), [Parfumo: Sauvage EDT](https://www.parfumo.com/Perfumes/Dior/Sauvage_Eau_de_Toilette), [Persolaise review](https://persolaise.com/2015/09/persolaise-review-sauvage-from.html)

### 17. Comme des Garçons — Marseille (2021)

- **Notes**: Accord-based rather than a classic pyramid - savon de Marseille accord, neroli, orange crystal, orange blossom, Petalia, Cosmone, an "overdose" of Ambrofix, general woody/amber notes. No source clearly separated these into tiers.
- **Main accords**: Soapy/clean (defining trait), musky, aromatic, floral, woody-amber.
- **Fragrance family**: Floral Woody Musk (per Fragrantica).
- **Perfumer**: Quentin Bisch.
- **Description**: A conceptual "soap" fragrance evoking traditional Savon de Marseille bar soap - clean without reading sterile, thanks to a natural, slightly aromatic earthiness underneath.
- **Sources**: [Fragrantica: Marseille (2021)](https://www.fragrantica.com/perfume/Comme-des-Garcons/Marseille-70223.html), [Parfumo: Marseille](https://www.parfumo.com/Perfumes/Comme_des_Garons/marseille), [Now Smell This](https://nstperfume.com/2021/09/13/comme-des-garcons-marseille-new-fragrance/), [ZGO Perfumery](https://www.zgoperfumery.com/comme-des-garcons-marseille-eau-de-toilette/)

### 18. Maison Francis Kurkdjian — Baccarat Rouge 540 (2016)

- **Notes**: Top: saffron, jasmine. Middle: amberwood, ambergris, Hedione. Base: fir resin, cedar, sugar (ethyl maltol), Ambroxan, oakmoss.
- **Main accords**: Woody, amber, warm/spicy, white floral, sweet/gourmand, fresh, animalic, faintly mineral. MFK itself describes three "auras": air (jasmine/saffron), mineral (dry ambergris-woods), fire (ethyl maltol sweetness).
- **Fragrance family**: Oriental Floral / Amber Woody.
- **Perfumer**: Francis Kurkdjian.
- **Description**: Originally commissioned by Baccarat for its 250th anniversary (created 2013-2014, EDP launch 2016). Became one of the best-selling niche fragrances worldwide, its popularity heavily amplified by fragrance-review social media, spawning an unusually large "dupe" market.
- **Sources**: [Fragrantica: Baccarat Rouge 540](https://www.fragrantica.com/perfume/Maison-Francis-Kurkdjian/Baccarat-Rouge-540-33519.html), [Wikipedia: Baccarat Rouge 540](https://en.wikipedia.org/wiki/Baccarat_Rouge_540) (fetched directly - not an excluded site), [Bois de Jasmin review](https://boisdejasmin.com/2025/08/maison-francis-kurkdjian-baccarat-rouge-540-perfume-review.html)

### 19. Lalique — Encre Noire (2006)

- **Notes**: Top: cypress. Middle: vetiver. Base: cashmere wood, musk.
- **Main accords**: Woody, green, earthy, with a subtle spicy/smoky-rubbery-leather facet from the Haitian vetiver component.
- **Fragrance family**: Woody Aromatic.
- **Perfumer**: Nathalie Lorson.
- **Description**: A dark, minimalist, vetiver-forward masculine on a very high vetiver dose (reportedly ~14%, Bourbon + Haitian vetiver) - foresty cypress over a smoky, earthy, ink-like vetiver heart. A modern "cult classic."
- **Sources**: [Fragrantica: Encre Noire (2006)](https://www.fragrantica.com/perfume/Lalique/Encre-Noire-1834.html), [Parfumo: Encre Noire EDT](https://www.parfumo.com/Perfumes/Lalique/Encre_Noire_Eau_de_Toilette), [Bois de Jasmin: Cult Classic](https://boisdejasmin.com/2024/08/cult-classic-lalique-encre-noire.html)

### 20. Diptyque — Tam Dao (EDP, 2012/2013)

- **Notes**: Top-note detail is inconsistent across sources for the EDP specifically (one pyramid gives Italian cypress/myrtle/rose, associated with the original EDT; other retailer copy for the EDP instead lists sandalwood/cedar/amberwood/coriander/musk/lime/vanilla/ginger with no clear tiering) - treat top notes as uncertain. Middle: sandalwood, cedar. Base: Brazilian rosewood, spices, amber, white musk (consistent across sources).
- **Main accords**: Woody (dominant), balsamic, warm spicy, powdery, aromatic.
- **Fragrance family**: Floral Woody Musk per Fragrantica, though most descriptive copy just calls it a "woody sandalwood/cedar" fragrance.
- **Perfumer**: Daniel Moliere (attributed by sources; not always explicitly credited in Diptyque's own retail copy - light caution).
- **Description**: Diptyque's signature woody fragrance - creamy sandalwood contrasted with dry, pencil-shaving cedar, rounded with amber and spice. The EDP is described as a richer, more cedar/sandalwood-forward version of the original 2003 EDT.
- **Sources**: [Fragrantica: Tam Dao EDP (2013)](https://www.fragrantica.com/perfume/Diptyque/Tam-Dao-Eau-de-Parfum-49104.html), [Parfumo: Tam Dao EDP](https://www.parfumo.com/Perfumes/Diptyque/Tam_Dao_Eau_de_Parfum), [Diptyque official site](https://www.diptyqueparis.com/en_us/l/fragrances/collections/tam-dao.html)

### 21. Guerlain — Mitsouko

- **Notes**: Sources disagree - Wikipedia's summary: Top: bergamot; Middle: peach, rose, iris, clove, jasmine; Base: vetiver, oakmoss, labdanum. Fragrantica's current EDP listing simplifies to: Top: spices/peach; Middle: rose/jasmine; Base: patchouli/vetiver. The peach, oakmoss, vetiver, and rose/jasmine notes are the consistent through-line.
- **Main accords**: Fruity, chypre (mossy/woody-earthy), floral, spicy, powdery (via the "Guerlinade" base of tonka/vanilla/iris/rose).
- **Fragrance family**: Chypre Fruity - widely credited as the original/founding "fruity chypre."
- **Perfumer**: Jacques Guerlain (1919).
- **Description**: Considered one of the most important perfumes in history, refining Coty's Chypre - a "peach skin" note over a dry oakmoss-vetiver chypre base, bittersweet and autumnal. Preserved in its original 1919 form in the Osmothèque archive; acknowledged reformulations since, especially post-IFRA oakmoss restrictions.
- **Sources**: [Fragrantica: Mitsouko EDP (1919 formulation page)](https://www.fragrantica.com/perfume/Guerlain/Mitsouko-Eau-de-Parfum-25316.html), [Fragrantica: Mitsouko EDP (2021 reissue)](https://www.fragrantica.com/perfume/Guerlain/Mitsouko-Eau-de-Parfum-113910.html), [Wikipedia: Mitsouko](https://en.wikipedia.org/wiki/Mitsouko) (fetched directly), [Guerlain official site](https://www.guerlain.com/us/en-us/p/les-legendaires-mitsouko---eau-de-parfum-P024104.html)

### 22. Guerlain — Shalimar (1986 formulation)

- **Notes**: General/classic Shalimar structure across all history: Top: bergamot, lemon, florals. Middle: iris, jasmine, rose. Base: vanilla, tonka bean, opoponax/incense-resins, patchouli, vetiver, sandalwood, musk, ethylvanillin. **No source documents a pyramid specific to the exact 1986 batch** - Guerlain did not use the "Eau de Parfum" designation until 1990, so the 1980s-era concentrated version (1986-~1989/90) was marketed as "Parfum de Toilette." Reported here as the general historical composition, not a confirmed 1986-specific pyramid - genuinely uncertain.
- **Main accords**: Oriental, vanilla, powdery, amber/balsamic, floral, citrus top.
- **Fragrance family**: Oriental (Ambery) - credited with establishing the "oriental" family as a genre.
- **Perfumer**: Jacques Guerlain (created 1921, launched 1925 after a naming dispute forced a temporary rename to "No. 90").
- **Description**: Considered the first true "oriental" perfume, pairing ethylvanillin with the base of Jicky (1889). Vintage/1980s-era Shalimar is generally described by enthusiasts as richer, more animalic, and more resinous than modern post-IFRA formulations.
- **Sources**: [Fragrantica: Shalimar Parfum (1925 listing)](https://www.fragrantica.com/perfume/Guerlain/Shalimar-Parfum-33557.html), [Fragrantica: Shalimar EDP (1990-era listing)](https://www.fragrantica.com/perfume/Guerlain/Shalimar-Eau-de-Parfum-53.html), [Wikipedia: Shalimar (perfume)](https://en.wikipedia.org/wiki/Shalimar_(perfume)) (fetched directly), [Kafkaesque: Guide to Vintage Shalimar Part II](https://kafkaesqueblog.com/2016/10/14/guide-vintage-shalimar-part-ii-edt-pdt-edp-1970s-1990s/), [Fragrantica Club board thread](https://www.fragrantica.com/board/viewtopic.php?id=115376)

### 23. Tom Ford — Ombré Leather (2018)

- **Notes**: Top: cardamom. Middle: leather, jasmine sambac. Base: amber, moss, patchouli.
- **Main accords**: Leathery, spicy (cardamom-forward opening), oriental amber-patchouli base - "leathery-spicy" overall, evoking new leather car seats.
- **Fragrance family**: No single consensus family name found (informally a leather/oriental-spicy composition) - **treat as uncertain**.
- **Perfumer**: Sonia Constant.
- **Description**: A dark, smooth black-leather fragrance - warm cardamom-spice opening, creamy jasmine sambac heart, ambery/mossy/patchouli base. Widely characterized as more wearable/subtle than earlier Tom Ford leather entries.
- **Sources**: [Fragrantica News: New Ombré Leather (2018)](https://www.fragrantica.com/news/New-Tom-Ford-Ombre-Leather-2018-10994.html), [Fragrantica: Ombré Leather (2018)](https://www.fragrantica.com/perfume/Tom-Ford/Ombre-Leather-2018-50239.html), [Parfumo: Ombré Leather 2018 EDP](https://www.parfumo.com/Perfumes/Tom_Ford/ombre-leather-2018-eau-de-parfum)

### 24. Montale — Black Aoud (2006)

- **Notes** (flat list): rose, agarwood (oud), patchouli, musk, French labdanum, mandarin orange.
- **Main accords** (ranked): rose, oud, patchouli, musky, woody, floral, warm spicy, amber, citrus.
- **Fragrance family**: Woody Floral Musk (also commonly described informally as an "amber/oriental" oud fragrance).
- **Perfumer**: Pierre Montale.
- **Description**: Montale's flagship oud composition - Cambodian-style agarwood and Indonesian patchouli, softened by musk, rosy florals, and mandarin citrus. Credited with introducing Western niche audiences to modern "oud."
- **Sources**: [Fragrantica: Black Aoud (2006)](https://www.fragrantica.com/perfume/Montale/Black-Aoud-1142.html), [Parfumo: Black Aoud](https://www.parfumo.com/Perfumes/Montale/Black_Aoud), [Montale official site](https://www.montaleparfums.com/en/oriental/30-black-aoud-noir.html)

### 25. Comme des Garçons — Series 3: Incense - Avignon (2002)

- **Notes**: A shorter and a longer list disagree - shorter: Roman chamomile, cistus/labdanum oil, elemi, incense, vanilla, patchouli, palisander; longer: top chamomile/elemi/aldehydes, middle labdanum/spices/ambrette, base incense/myrrh/cedar/rosewood/patchouli/oakmoss/vanilla/musk. Both reported since they disagree.
- **Main accords**: A dominant, smoky ash-laden frankincense/myrrh "church incense" accord balanced by resinous/balsamic notes - dry, smoky, resinous, mildly spicy overall.
- **Fragrance family**: Sources disagree - both "Oriental Woody" and a more specific "woody incense" (a dry, vertical smoke-resin-air structure rather than a classic warm oriental) were found. Treat as approximate.
- **Perfumer**: Bertrand Duchaufour.
- **Description**: Widely regarded as one of the most accurate "church incense" fragrances made - dry, smoky, resinous frankincense/myrrh (part of the Series 3: Incense set, Avignon representing Catholicism).
- **Sources**: [Fragrantica: CDG Series 3 Incense Avignon](https://www.fragrantica.com/perfume/Comme-des-Garcons/Comme-des-Garcons-Series-3-Incense-Avignon-1230.html), [Parfumo: Series 3 Incense Avignon](https://www.parfumo.com/Perfumes/Comme_des_Garons/Series_3_Incense_Avignon), [Basenotes reviews](https://basenotes.com/fragrances/parfums-parfums-series-3-incense-avignon-by-comme-des-garcons.26122019/reviews/), [ZGO Perfumery](https://zgoperfumery.com/products/comme-des-garcons-incense-series-3-avignon-eau-de-toilette)

### 26. Tauer Perfumes — No. 02 L'Air du Désert Marocain (EDT Intense, 2005)

- **Notes**: Top: coriander, cumin, petitgrain, lavender. Middle: labdanum, birch, jasmine, geranium. Base: amber (ambergris accord), cedar, vetiver, patchouli, oakmoss.
- **Main accords**: Radiant amber-spice - coriander, cumin, cistus/labdanum, cedarwood, vetiver, plus a "cold, dusty, incense-laden" ambergris-style amber accord.
- **Fragrance family**: Sources diverge - Fragrantica-style "Oriental Spicy" vs. Tauer's own site describing it as "dry amber / woody spicy / resinous." Both reported since they disagree.
- **Perfumer**: Andy Tauer.
- **Description**: A "Saharan desert at night" composition - spicy-oriental over a dry, dusty amber and woody-resinous base. Considered one of the most celebrated independent/artisanal niche fragrances, conceived as a lighter counterpart to Tauer's Le Maroc Pour Elle.
- **Sources**: [Fragrantica: L'Air du Desert Marocain (2005)](https://www.fragrantica.com/perfume/Tauer-Perfumes/02-L-Air-du-Desert-Marocain-4573.html), [Parfumo: L'Air du Désert Marocain EDT Intense](https://www.parfumo.com/Perfumes/Tauer/no-02-l-air-du-desert-marocain-eau-de-toilette-intense), [Tauer official site](https://tauerperfumes.com/products/no-02-lair-du-desert-marocain-50-ml), [Kafkaesque review](https://kafkaesqueblog.com/2013/01/10/perfume-review-tauer-perfumes-lair-du-desert-marocain/)

### 27. Indult — Tihota (2006)

- **Notes** (flat list): Tahitian vanilla, sugar cane, white musk, tonka bean, amber, almond milk.
- **Main accords**: Vanilla (dominant), sweet, musky, powdery.
- **Fragrance family**: Spicy Amber Vanilla (sometimes just described as a pure/gourmand vanilla).
- **Perfumer**: Francis Kurkdjian.
- **Description**: A famously vanilla-forward, near-monolithic fragrance - Tahitian vanilla in sugar-cane-like sweetness, softened by white musk and creamy almond-milk, a long powdery-sweet drydown. Cited as one of the definitive "gourmand vanilla" niche fragrances.
- **Sources**: [Fragrantica: Tihota (2006)](https://www.fragrantica.com/perfume/Indult/Tihota-4346.html), [Parfumo: Tihota](https://www.parfumo.com/Perfumes/Indult/Tihota), [So Avant Garde](https://so-avant-garde.com/products/tihota-eau-de-parfum)

### 28. Mugler — Angel (1992)

- **Notes**: Key notes: Calabrian bergamot, praline, patchouli leaf; a fuller description adds red berries and vanilla in the heart/base.
- **Main accords** (ranked): sweet, patchouli, warm spicy, caramel, fruity, vanilla, woody, honey, powdery, chocolate.
- **Fragrance family**: Amber Vanilla (also described historically as the fragrance that founded the modern "gourmand" category).
- **Perfumer(s)**: Olivier Cresp and Yves de Chirin.
- **Description**: A landmark, category-defining "gourmand" fragrance - bergamot citrus opening, an intense sugary praline/cotton-candy heart, earthy patchouli and creamy vanilla base. Credited with launching the modern gourmand genre.
- **Sources**: [Fragrantica: Angel (1992)](https://www.fragrantica.com/perfume/Mugler/Angel-704.html), [Parfumo: Angel EDP](https://www.parfumo.com/Perfumes/mugler/Angel), [Wikipedia: Angel (perfume)](https://en.wikipedia.org/wiki/Angel_(perfume)), [MUGLER official site](https://inter.mugler.com/default/fragrance/women-s-fragrances/angel/angel-eau-de-parfum/M010101003.html)

### 29. Akro — Bake (2023)

- **Notes**: Top: lemon zest, rum. Middle: whipped cream, praline. Base: bourbon vanilla, brown sugar.
- **Main accords**: Sweet, gourmand, citrus.
- **Fragrance family**: Oriental Vanilla.
- **Perfumer**: Olivier Cresp.
- **Description**: A dessert-like gourmand built to evoke a bakery - lemony-boozy top notes, whipped cream and praline, a warm bourbon vanilla/brown-sugar base. Publicly stated to be inspired by lemon cupcakes from a London bakery (Crumbs & Dollies).
- **Sources**: [Fragrantica: Bake (2023)](https://www.fragrantica.com/perfume/Akro/Bake-81614.html), [Parfumo: Bake](https://www.parfumo.com/Perfumes/Akro/bake), [Fragrantica News: AKRO Bake by Olivier Cresp](https://www.fragrantica.com/news/AKRO-Bake-by-Olivier-Cresp-18334.html), [Aedes.com](https://www.aedes.com/products/bake-eau-de-parfum)

### 30. Zoologist — Bee (Extrait de Parfum, 2019)

- **Notes**: Top: orange, ginger (syrup), royal jelly accord. Middle: broom, heliotrope, mimosa, orange blossom. Base: benzoin, labdanum, musks, sandalwood, tonka bean, vanilla.
- **Main accords**: vanilla, beeswax, honey, powdery, amber, yellow floral, sweet, warm spicy, animalic, woody.
- **Fragrance family**: No explicit single named family found in sources - best described, per its own accord profile, as a honey/beeswax gourmand-floral-amber. **Treat family classification as uncertain.**
- **Perfumer**: Cristiano Canali.
- **Description**: Built around a royal-jelly accord and rare beeswax absolute, balancing warm honeyed-gourmand sweetness with floral lift and a subtle animalic musk/wax undertone - reviewed as a distinctive "honey/beeswax" niche fragrance rather than a literal insect-scent novelty.
- **Sources**: [Fragrantica: Bee (2019)](https://www.fragrantica.com/perfume/Zoologist-Perfumes/Bee-58140.html), [Now Smell This review](https://nstperfume.com/2020/01/29/zoologist-bee-fragrance-review/), [Venba](https://www.venbafragrance.com/products/zoologist-bee-extrait-1)

### 31. Tom Ford — Tobacco Vanille (2007)

- **Notes**: Top: tobacco leaf, spicy notes. Middle: vanilla, cocoa/cacao, tonka bean, tobacco blossom. Base: dried fruit accord, sweet wood sap.
- **Main accords**: tobacco, sweet, vanilla/ambery-vanilla, gourmand, earthy - a "dry, realistic tobacco" accord balanced against a "very sweet sugary vanilla" accord per community description.
- **Fragrance family**: Oriental Spicy (also loosely "Warm & Spicy").
- **Perfumer**: Olivier Gillotin.
- **Description**: One of Tom Ford's most iconic Private Blend fragrances - rich pipe-tobacco-leaf and spice opening, a creamy vanilla-cocoa-tonka heart, warm sweet dried-fruit/woody-sap drydown. Archetypal "cozy" rich oriental, best suited to cold weather/evening wear.
- **Sources**: [Fragrantica: Tobacco Vanille (2007)](https://www.fragrantica.com/perfume/Tom-Ford/Tobacco-Vanille-1825.html), [Parfumo: Tobacco Vanille EDP](https://www.parfumo.com/Perfumes/Tom_Ford/Tobacco_Vanille_Eau_de_Parfum), [Basenotes](https://basenotes.com/fragrances/tobacco-vanille-by-tom-ford.26125943), [TOM FORD BEAUTY official site](https://www.tomfordbeauty.com/products/tobacco-vanille-eau-de-parfum)

### 32. Escentric Molecules — Molecule 01 + Black Tea (2023)

- **Notes** (flat list - a "molecule + accord" composition, not a classic pyramid): Iso E Super, black tea (camellia sinensis infusion), maté tea absolute, with bitter-fresh and subtle floral facets.
- **Main accords**: Woody/cedar (from Iso E Super), black tea, maté, bitter-fresh, faintly floral - described as smoky, earthy, fresh, spicy, "Earl Grey-like."
- **Fragrance family**: Woody Aromatic.
- **Perfumer**: Geza Schoen.
- **Description**: Part of the "Molecule +" line, pairing Molecule 01's skin-like Iso E Super base with a black-tea/maté heart accord - a minimalist, "second-skin" scent prized for its skin-chemistry-dependent, understated woody-tea character.
- **Sources**: [Fragrantica: Molecule 01 + Black Tea (2023)](https://www.fragrantica.com/perfume/Escentric-Molecules/Molecule-01-Black-Tea-79414.html), [Parfumo: Molecule 01 + Black Tea](https://www.parfumo.com/Perfumes/Escentric_Molecules/molecule-01-black-tea), [ÇaFleureBon](https://cafleurebon.com/escentric-molecules-molecule-01-m-ginger-black-tea-and-guaiac-wood-geza-schoen-2023-plus-pick-your-pheromone-giveaway/), [Escentric Molecules official site](https://www.escentric.com/en-us/products/molecule-01-black-tea)

### 33. Imaginary Authors — A City on Fire (2014)

- **Notes** (flat list - not clearly split into a pyramid by sources): cade oil, spikenard, cardamom, Clearwood™, dark berries, labdanum, burnt match.
- **Main accords**: Burnt match/smoke (opening, very prominent), smoky cade/juniper, dark berries, cardamom, spikenard (heart), labdanum and Clearwood™ (woody-resinous base).
- **Fragrance family**: Woody Aromatic.
- **Perfumer**: Josh Meyer.
- **Description**: An austere, smoke-forward niche fragrance opening with an intense "burnt match" accord and smoky cade/juniper, tempered by dark-berry sweetness, settling into a spicy cardamom-spikenard heart and resinous woody base. Originally developed exclusively for Machus, a Portland menswear retailer.
- **Sources**: [Fragrantica: A City On Fire (2014)](https://www.fragrantica.com/perfume/Imaginary-Authors/A-City-On-Fire-29211.html), [Fragrantica News](https://www.fragrantica.com/news/Imaginary-Authors-Newest-A-City-On-Fire-6192.html), [Imaginary Authors official site](https://imaginaryauthors.com/products/a-city-on-fire), [Basenotes](https://basenotes.com/fragrances/a-city-on-fire-by-imaginary-authors.26145097)

## Validation holdout (10 fragrances)

### H01. Dior — Homme Intense (2011)

- **Notes**: Top: lavender. Heart: iris, ambrette, pear (liqueur). Base: Virginia cedar, vetiver.
- **Main accords** (ranked): iris, woody, powdery, musky, floral, aromatic.
- **Fragrance family**: Woody Floral Musk (also described in retailer copy as "powdery iris/amber woods" - same idea, different emphasis).
- **Perfumer**: François Demachy.
- **Description**: A dry, powdery reinterpretation of the original Dior Homme, built around an unusually prominent iris note fused with ambrette musk and pear, on cedar and vetiver. Regarded as elegant, austere, and "cold" in a refined way.
- **Sources**: [Fragrantica: Dior Homme Intense 2011](https://www.fragrantica.com/perfume/Dior/Dior-Homme-Intense-2011-13016.html), [Parfumo: Dior Homme Intense 2011](https://www.parfumo.com/Perfumes/Dior/Dior_Homme_Intense_2011), [FragIndex](https://www.fragindex.com/fragrance/dior-homme-intense-2011), [Perfume Finder](https://perfumefinder.app/encyclopedia/dior/dior-homme-intense-2011)

### H02. Tom Ford — Oud Wood (2007)

- **Notes** (flat list; sources did not consistently split top/heart/base for the *original 2007 EDP* - the split pyramid found belongs to the newer 2024 "Oud Wood Parfum" flanker, reported separately below): rare oud (agarwood), sandalwood, Brazilian rosewood, cardamom, Sichuan/pink pepper, vetiver, tonka bean, vanilla, amber.
- **Main accords**: woody, warm spicy, smoky/oud-woody, sweet amber-vanilla drydown.
- **Fragrance family**: Oriental Woody (unisex).
- **Perfumer**: Richard Herpin (Givaudan) - multiple sources agree, though the original's Fragrantica "nose" credit isn't always prominent, so treat with light caution.
- **Description**: An abstracted, "clean" take on oud - smoky/warm-spicy top, smooth creamy oud/sandalwood/vetiver heart, soft vanilla-tonka-amber base. Frequently cited as an accessible oud entry point since it avoids raw agarwood's harsher barnyard/medicinal facets.
- **Sources**: [Fragrantica: Oud Wood](https://www.fragrantica.com/perfume/Tom-Ford/Oud-Wood-1826.html), [Fragrantica: nose Richard Herpin](https://www.fragrantica.com/noses/Richard_Herpin.html), [Parfumo: Oud Wood EDP](https://www.parfumo.com/Perfumes/Tom_Ford/Oud_Wood_Eau_de_Parfum), [Silloria](https://www.silloria.com/en/perfumers/richard-herpin)

### H03. Editions de Parfums Frédéric Malle — Vétiver Extraordinaire (2002)

- **Notes**: Top: bitter orange, bergamot, pepper, caraway, cardamom. Heart: vetiver, pink pepper, cloves, incense, licorice. Base: cedar, oakmoss, sandalwood, myrrh, musk, ambrette.
- **Main accords**: green-woody vetiver, cedar/wood, sweet spice, musk.
- **Fragrance family**: Woody / Oriental Woody (wording varies, but sources agree it's vetiver-woody at its core).
- **Perfumer**: Dominique Ropion.
- **Description**: A vetiver "overdose" (reportedly ~25% concentration) built on a stripped-down Haitian vetiver essence paired with five other woody notes to show off the material's many facets - smoky, green, earthy, dry. Regarded as a modern benchmark vetiver fragrance.
- **Sources**: [Fragrantica: Vetiver Extraordinaire](https://www.fragrantica.com/perfume/Frederic-Malle/Vetiver-Extraordinaire-4774.html), [Parfumo: Vétiver Extraordinaire](https://www.parfumo.com/Perfumes/Editions_de_Parfum_Frederic_Malle/Vetiver_Extraordinaire), [ZGO Perfumery](https://zgoperfumery.com/products/editions-de-parfums-frederic-malle-vetiver-extraordinaire-eau-de-parfum)

### H04. Unum / Filippo Sorcinelli — LAVS (Extrait de Parfum)

- **Brand-name ambiguity (already flagged in [Parfumo Source Resolution](baseline-v3.1-parfumo-source-resolution.md); reconfirmed here)**: Marketed as "Unum - LAVS," but Fragrantica and Parfumo both list it under the designer page "Filippo Sorcinelli." Both names are legitimately used - reported together, not resolved here.
- **Year discrepancy (new finding)**: The source document/prior evidence records 2013; Fragrantica's own page lists **2014**. Inconsistent across sources; not resolved - flagging for the product owner rather than picking one.
- **Notes**: Top: black pepper, cardamom, jasmine. Heart: elemi, labdanum, cloves, coriander. Base: opoponax, oakmoss, rosewood (also called palisander/Brazilian rosewood by different sources), amber, tonka bean.
- **Main accords**: incense, spices, amber, resinous/balsamic, aromatic woods.
- **Fragrance family**: Oriental / Oriental-Spicy (unisex).
- **Perfumer**: Not clearly attributed to a named professional perfumer in sources found - presented as designed/conceived by Filippo Sorcinelli himself (a couture vestment designer and cathedral organist by background). **Treat as uncertain.**
- **Description**: A powerful, "gothic," church-incense-driven fragrance evoking a Catholic High Mass - incense, labdanum, and spices dominate, resinous and liturgical. Widely cited as Unum's best-selling scent.
- **Sources**: [Parfumo: LAVS by Filippo Sorcinelli](https://www.parfumo.com/Perfumes/Filippo_Sorcinelli/lavs), [Fragrantica: Lavs (2014)](https://www.fragrantica.com/perfume/Filippo-Sorcinelli/Lavs-29991.html), [Cafleurebon review](https://cafleurebon.com/new-perfume-review-unum-lavs-da-vincis-demons-draw/), [Kafkaesque: interview with Filippo Sorcinelli](https://kafkaesqueblog.com/2015/09/15/interview-filippo-sorcinelli-of-unum-lavs/)

### H05. Xerjoff — Naxos (2015)

- **Notes**: Top: bergamot, lemon, lavender, jasmine sambac, spice accents. Heart: cinnamon, jasmine, honey, cashmeran. Base: vanilla, tonka bean, tobacco leaf.
- **Main accords**: honey-tobacco (defining accord), sweet/gourmand, tobacco, vanilla, citrus opening, lavender.
- **Fragrance family**: Inconsistent across sources - found described as "Oriental Fougère," "Citrus Gourmand," and simply "Woody" in three different places. **No clear consensus - flagged rather than picked.**
- **Perfumer**: Chris Maurice.
- **Description**: Praised for its rich honey-tobacco-vanilla accord - bright Sicilian lemon/bergamot/lavender opening into a warm honey-cinnamon-jasmine heart, then a smooth pipe-tobacco-tonka drydown. Commonly described as a cold-weather, golden, autumn/winter scent.
- **Sources**: [Fragrantica: XJ 1861 Naxos](https://www.fragrantica.com/perfume/Xerjoff/XJ-1861-Naxos-30529.html), [Fragrantica: nose Chris Maurice](https://www.fragrantica.com/noses/Chris_Maurice.html), [Kafkaesque review](https://kafkaesqueblog.com/2016/08/12/xerjoff-xj-1861-naxos/), [Parfumo: Naxos](https://www.parfumo.com/Perfumes/Xerjoff/naxos)

### H06. Tom Ford — Black Orchid (2006)

- **Notes**: Top: black truffle, gardenia/ylang-ylang, black currant, bergamot/mandarin/Amalfi lemon, French jasmine. Heart: the fictional "black orchid" accord, tuberose, spices, fruity notes, lotus wood, gardenia, jasmine, black violet. Base: patchouli, sandalwood, dark chocolate, incense, amber, vetiver, vanilla, balsam, white musk.
- **Main accords**: floral, spicy, sweet/gourmand, woody, in combination - sources agree it's a rich, multi-layered blend rather than one dominant accord.
- **Fragrance family**: Oriental Floral / "oriental chypre" (both terms found - different eras of Fragrantica's own classification schema, not a real contradiction).
- **Perfumer(s)**: David Apel and Pierre Negrin (Givaudan).
- **Description**: A dark, opulent, "fantasy" floral-oriental built around the invented "black orchid" note - luxurious black truffle/citrus top, spicy/fruity floral heart, rich almost-gourmand chocolate/patchouli/incense/vanilla base. One of the defining Tom Ford signature scents.
- **Sources**: [Fragrantica: Black Orchid (2006)](https://www.fragrantica.com/perfume/Tom-Ford/Black-Orchid-1018.html), [Fragrance Foundation](https://fragrance.org/award/tom-ford-black-orchid/), [Agoratopia: David Apel](https://www.agoratopia.com/perfumers/david-apel), [Basenotes: Black Orchid EDP](https://basenotes.com/fragrances/black-orchid-eau-de-parfum-by-tom-ford.26125725)

### H07. Caron — Aimez-Moi (1996 Eau de Toilette)

- **Disambiguation (confirms prior [Parfumo Source Resolution](baseline-v3.1-parfumo-source-resolution.md) finding)**: This is the **1996 EDT "Aimez-Moi"** by Dominique Ropion (Fragrantica page dated 1996) - distinct from "Aimez-Moi Comme Je Suis" (a separate, later men's fragrance), from "N'Aimez Que Moi" (a much older 1916 Caron parfum that inspired this one), and from a separate 2013 "La Selection Aimez-Moi" re-edition. Everything below is specifically about the 1996 EDT.
- **Notes**: Top: violet, star anise, mint, cardamom, bergamot. Heart: iris, peach, magnolia, rose tincture, jasmine. Base: woodsy notes, musk, vanilla, sandalwood, amber.
- **Main accords**: oriental, floral, powdery, violet.
- **Fragrance family**: Oriental Floral.
- **Perfumer**: Dominique Ropion.
- **Description**: A spicy-powdery oriental floral - anise/cardamom/mint spiced opening over a soft violet-iris-peach floral heart, warm musk-vanilla-sandalwood base. Now discontinued in its original form.
- **Sources**: [Fragrantica: Aimez-Moi (1996)](https://www.fragrantica.com/perfume/Caron/Aimez-Moi-2816.html), [Parfumo: Aimez-Moi 1996 EDT](https://www.parfumo.com/Perfumes/Caron/Aimez_Moi_Eau_de_Toilette); cited only to confirm the distinct, non-matching listings: [Fragrantica: N'Aimez Que Moi (1916)](https://www.fragrantica.com/perfume/Caron/N-Aimez-Que-Moi-7428.html), [Fragrantica: La Selection Aimez Moi (2013)](https://www.fragrantica.com/perfume/Caron/La-Selection-Aimez-Moi-17795.html)

### H08. Hermès — Osmanthe Yunnan (2005)

- **Notes**: Top: tea, orange. Heart: osmanthus, freesia. Base: apricot, leather (suede).
- **Main accords**: floral-fruity, tea, osmanthus/apricot-peach-tea (signature lactonic accord), light leather/suede drydown.
- **Fragrance family**: Floral Fruity (per Fragrantica).
- **Perfumer**: Jean-Claude Ellena (confirmed).
- **Description**: A minimalist "haiku" fragrance built around a single exotic flower (osmanthus), foregrounding its natural tea/apricot/peach facets rather than masking them. Sheer and elusive, with a soft suede undertone - among the most pared-down of the Hermessence line.
- **Sources**: [Fragrantica: Hermessence Osmanthe Yunnan](https://www.fragrantica.com/perfume/Hermes/Hermessence-Osmanthe-Yunnan-2674.html), [Now Smell This review](https://nstperfume.com/2005/11/21/perfume-review-hermes-osmanthe-yunnan/), [Parfumo: Osmanthe Yunnan](https://www.parfumo.com/Perfumes/Hermes/osmanthe-yunnan), [Fragrantica: nose Jean-Claude Ellena](https://www.fragrantica.com/noses/Jean-Claude_Ellena.html)

### H09. Serge Lutens — Borneo 1834 (2005)

- **Notes** (flat list - described more as accord-driven than a strict pyramid): patchouli, cacao, French labdanum, galbanum, cardamom, white flowers; some sources add camphor and cannabis-resin-like facets.
- **Main accords**: patchouli, cacao/gourmand, woody, balsamic, earthy amber, warm spicy.
- **Fragrance family**: Serge Lutens' own house category "A Touch of Wood" - commonly cross-classified externally as Woody / Oriental Woody.
- **Perfumer**: Christopher Sheldrake.
- **Description**: A dense, "dank" patchouli fragrance with dark cacao, resinous labdanum, and green galbanum bitterness - deliberately combines "ugly" earthy/moldy facets with rich, boozy, tobacco-like warmth. Regarded as one of the more avant-garde patchouli-centric releases in the Lutens catalog.
- **Sources**: [Fragrantica: Borneo 1834](https://www.fragrantica.com/perfume/Serge-Lutens/Borneo-1834-5201.html), [Parfumo: Bornéo 1834](https://www.parfumo.com/Perfumes/Serge_Lutens/Borneo_1834), [Australian Perfume Junkies](https://australianperfumejunkies.com/2012/08/17/borneo-1834-by-christopher-sheldrake-for-serge-lutens-2005/), [Kafkaesque review](https://kafkaesqueblog.com/2013/01/12/perfume-review-serge-lutens-borneo-1834/)

### H10. Kenzo — Jungle L'Éléphant (Kenzo Jungle, 1996)

- **Notes**: Top: cloves, cumin, mandarin orange. Heart: cardamom, caraway, licorice, mango, ylang-ylang, heliotrope, gardenia. Base: vanilla, amber, patchouli.
- **Main accords**: spicy-oriental, spices (cumin/cardamom/clove/caraway), vanilla-amber gourmand warmth.
- **Fragrance family**: Spicy Oriental.
- **Perfumer(s)**: Jean-Louis Sieuzac and Dominique Ropion (co-credited).
- **Description**: A bold, spice-forward oriental built on an unusual cumin-cardamom-clove-caraway spice accord (often likened to chai/dessert spices) over a sweet, syrupy vanilla-amber-patchouli base. A distinctive, "love it or hate it" 1990s release, praised in enthusiast circles as a modern spicy-oriental masterpiece.
- **Sources**: [Fragrantica: Kenzo Jungle L'Elephant](https://www.fragrantica.com/perfume/Kenzo/Kenzo-Jungle-L-Elephant-70.html), [Cafleurebon: Modern Masterpieces](https://cafleurebon.com/cafleurebon-modern-masterpieces-kenzo-jungle-l-elephant-dominique-ropion-jean-louis-sieuzac-1996/), [Parfumo: Kenzo Jungle / Jungle L'Éléphant](https://www.parfumo.com/Perfumes/Kenzo/Kenzo_Jungle_Jungle_L_Elephant)

## Cross-cutting flags for the product owner

Beyond the per-entry flags inline above, these are worth a second look before treating anything
here as more than a research starting point:

- **H04 LAVS year discrepancy is new**: the source document (and the prior
  [Parfumo Source Resolution](baseline-v3.1-parfumo-source-resolution.md)) gives 2013;
  Fragrantica's own listing gives 2014. This was not previously flagged and should be checked
  against the physical bottle alongside the already-open brand-string question (Unum vs. Filippo
  Sorcinelli).
- **Several fragrance-family labels have no real consensus** and were reported as split or
  uncertain rather than picked: #11 (Woody vs. Soft Floral), #14/#15 (single-material
  compositions, family label questionable), #23, #25, #26, #30, H05. Do not treat the single
  family value shown for these as authoritative without independent confirmation.
- **Several note pyramids disagree between sources** for the same fragrance/concentration: #03,
  #04, #08, #20, #21, #22 (see each entry's notes for the specific disagreement). #22 in
  particular could not be pinned to the specific 1986 batch at all - only the general historical
  Shalimar composition is reported.
- **Several perfumer attributions are unconfirmed or carry light caution**: #01 (unknown for the
  1916 original), #08 (unknown for the 2012 EDT specifically), #20 (Daniel Moliere, not
  consistently credited by Diptyque itself), H02 (Richard Herpin, credited but not prominently),
  H04 (no named perfumer found; presented as the designer's own work).
- **H02 Oud Wood**: the only split top/heart/base pyramid found in search results belongs to a
  *different*, newer product (the 2024 "Oud Wood Parfum" flanker) - the original 2007 EDP this
  program uses is more accurately described with the flat note list given above, not that pyramid.

None of the above changes P1.1's status; it remains **blocked on inventory** as recorded in the
[P1 gate](../gates/p1.md).
