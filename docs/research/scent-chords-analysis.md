---
title: "Scent chords: analysis and integration reference"
schema_type: common
status: published
owner: core-maintainer
purpose: "Record evidence and integration guidance for scent-chord exploration."
tags:
  - development
  - architecture
---

**Reviewed:** 2026-09-11. **Status:** research supporting proposed project work.

## Recommendation

Use Scent chords as a reference for source-note exploration, reproducible catalog statistics
and candidate generation. Keep our canonical version catalog, evaluator records, blind
workflow and recommendation policies authoritative. Co-occurrence describes a published
catalog; it does not measure a person's preference or a perfume's chemical composition.

The [Project Plan](../planning/PROJECT-PLAN.md#8-milestone-d1-source-and-vocabulary-foundation)
translates these findings into D1–D5 deliverables and acceptance criteria after the P1 release
and P2 measurement gates. This document records
the evidence and reasoning; it does not authorize a data import or assert that these features
have been implemented.

## Scope and reproducibility

The review inspected the [deployed site](https://scent-database.vercel.app/), its public assets
and metadata, and the [public repository at a pinned commit](https://github.com/juweek/scent-database/tree/a0671de5f9a08ca36b517d51f598c6b6a533792d).
The inspected commit is `a0671de5f9a08ca36b517d51f598c6b6a533792d` (2026-08-31).
Live metadata matched the inspected repository at review time. This was source/data inspection,
not an interactive browser usability test or a comprehensive security audit. Counts below are
snapshot-specific; they should not be treated as a continuously refreshed service contract.

| Evidence | Location in the pinned repository |
| :--- | :--- |
| Site architecture and usage | [README](https://github.com/juweek/scent-database/blob/a0671de5f9a08ca36b517d51f598c6b6a533792d/README.md) |
| Source provenance and example data | [FRAGRANCE-DATA.md](https://github.com/juweek/scent-database/blob/a0671de5f9a08ca36b517d51f598c6b6a533792d/docs/FRAGRANCE-DATA.md) |
| Parfumo integration status | [PARFUMO.md](https://github.com/juweek/scent-database/blob/a0671de5f9a08ca36b517d51f598c6b6a533792d/docs/PARFUMO.md) |
| Embedding contract | [EMBEDDING.md](https://github.com/juweek/scent-database/blob/a0671de5f9a08ca36b517d51f598c6b6a533792d/docs/EMBEDDING.md) |
| Pair rankings and filtered-population calculation | [notePairings.js](https://github.com/juweek/scent-database/blob/a0671de5f9a08ca36b517d51f598c6b6a533792d/src/data/notePairings.js) |
| Taxonomy and family mapping | [noteTaxonomy.js](https://github.com/juweek/scent-database/blob/a0671de5f9a08ca36b517d51f598c6b6a533792d/src/data/noteTaxonomy.js) |
| Individual fragrance visualization | [PerfumeChord.jsx](https://github.com/juweek/scent-database/blob/a0671de5f9a08ca36b517d51f598c6b6a533792d/src/viz/PerfumeChord.jsx) |
| Corpus and similarity pipeline | [pipeline scripts](https://github.com/juweek/scent-database/tree/a0671de5f9a08ca36b517d51f598c6b6a533792d/scripts/pipeline) |

## What the application actually provides

The title is “Scent chords: explore perfume pairings.” It is a React/Vite application using
precomputed, sharded JSON and chord visualizations. The inspected source does not provide a
documented backend API for another application's production integration.

| Capability | Lesson for fragrance-rater | Boundary |
| :--- | :--- | :--- |
| Note and family chord wheels | Explore common published combinations; offer accessible tables for precise comparisons | Ribbon size is catalog co-occurrence, not formulation percentage |
| Raw versus beyond-chance associations | Separate popular pairings from unusually associated pairings | Association is not preference, causation or information gain |
| Accord and pyramid views | Preserve source order and top/heart/base structure | Published pyramid positions are not measured skin timepoints |
| Individual fragrance profiles | Explain source metadata after reveal alongside perceived notes | Keep source and evaluator statements visibly separate |
| Similar published-note profiles | Generate a candidate pool before personalized selection | Similar notes do not guarantee similar smell or liking |
| Static preprocessing and lazy loading | Reproducible, offline-capable assets with versioned snapshots | Live external assets can change independently of frozen experiments |

The note wheel uses a custom ten-family taxonomy: citrus, fresh, herbal, floral, fruity, sweet,
spicy, amber, woody and musky. It should not silently replace the application's existing fragrance
wheel classifications. The accord wheel includes 56 accords after a support floor of 40 perfumes;
28 rarer accords are omitted. Its beyond-chance matrix uses positive observed-minus-expected
counts, which is a different statistic from lift. UI labels must identify which quantity is shown.

## Dataset provenance and population differences

The shipped metadata identifies Kaggle dataset `olgagmiufana1/fragrantica-com-fragrance-dataset`,
version 3, file `fra_cleaned.csv`, and declares **CC BY-NC-SA 4.0**. The recorded source hash is:

```text
6cfc07226db77f94528d02a9e8cce2825fd0a14fff89b918a8ecc40d933a4d6f
```

The source documentation describes a September 2024 snapshot. Recent application commits do
not establish that the fragrance data is current. The original CSV was not committed in the
inspected repository; this review relied on exported records, metadata and pipeline code.

| Population or export | Observed size or behavior |
| :--- | :--- |
| Wheel corpus | 24,059 fragrances; 140 displayed notes |
| Fragrance example export | 23,989 records used; 252 indexed notes; 27,653 pairs |
| Individual perfume index | 24,050 perfumes; 1,668 distinct notes; 106,350 distinct pairs |
| Individual index eligibility | Minimum 3 notes, maximum observed 24, median 9 |
| Export loading | 256 record shards and 27 search shards |
| Note lists / pair examples | Lists capped at 100; up to 4 examples per pair |

These differing counts can reflect different filters and export purposes; they are not by
themselves proof of an error. They do require explicit denominators. Top examples and capped
lists are not complete populations. Pair examples favor community quality using a rating/count
ranking, which must not be mistaken for random sampling or evaluator preference evidence.

The Parfumo document is a scoping proposal: **no Parfumo dataset or completed Parfumo pipeline
was present** in this inspected repository. This project is therefore not a shortcut to our
required Parfumo source preservation work.

## Statistical lessons and a concrete denominator defect

For one explicitly defined population of size `N`, with note counts `nA`, `nB` and pair count
`nAB`, use:

```text
expected_pair_count = nA * nB / N
lift = nAB * N / (nA * nB)
partner_share = nAB / nA
```

Lift above one indicates that the pair appears more often than independence would predict in
that population. It is not a probability, confidence interval or measure of personal liking.
Undefined denominators need explicit handling. Rare pairs can have large lift, so report support
and version any minimum-support or shrinkage policy.

From the whole wheel corpus (`N = 24,059`), rose occurs 6,133 times, musk 10,945 times and
carnation 828 times. Rose–musk occurs 3,467 times (lift about 1.24), while rose–carnation occurs
461 times (lift about 2.18). The first pair is more common; the second is more unusually
associated relative to the prevalence of its component notes. This is a useful distinction
for exploration and generating contrasts, not a reason to recommend carnation to everyone.

**Observed defect in the inspected snapshot:** `pairingsFor` selects the current subset's pair
matrix and population size but uses whole-corpus note totals. The calling wheel passes the
selected set, so the best-rated view mixes populations. For example, using that subset's 317
rose–carnation occurrences and `N = 11,266` with whole-corpus totals produces about 0.70.
That is not valid subset lift. This review does not provide a corrected value because the
individual-perfume export has different eligibility filters and cannot supply exact replacement
denominators for the wheel subset.

Our implementation must recompute note totals, pair counts and population size from the same
filtered, deduplicated snapshot. Add a regression fixture in which subset prevalence differs
from whole-corpus prevalence; merely testing the formula against its own inputs misses this bug.

## Identity, taxonomy and baseline suitability

No dedicated concentration field was present in the 24,050 exported individual records.
Concentration sometimes appears in display names, which is insufficient for canonical resolution.
Heuristic name stems used for grouping flankers must not become identity keys.

| Baseline reference checked | Export finding | Consequence |
| :--- | :--- | :--- |
| Molecule 01 | No matching record found | Cannot use this export as a complete diagnostic baseline |
| Tihota | No matching record found | Requires another verified source |
| Comme des Garçons Marseille | No matching record found | Requires another verified source |
| Tam Dao EDP | Tam Dao Eau De Toilette (2003) and Limited Edition (2019); no explicitly identified EDP | Do not substitute EDT for the required EDP |
| Eau Rose EDT | Generic Eau Rose (2012) and explicit Eau Rose EDP (2022) | Verify the generic record's exact version before linking |
| Acqua di Giò EDT | Multiple same-name/year/variant records, including separately named EDP | Resolve concentration and source identity explicitly |

“No matching record” refers to this export, not every upstream source or every possible spelling.
The minimum-three-note eligibility rule can omit minimalist diagnostic fragrances. Our catalog
and program eligibility must not require three published notes.

Alias fragmentation is also material: the corpus separately contains `oak moss` and `oakmoss`,
and `vanille` and `vanilla`. The first spelling combination has 62 co-occurrences and lift about
6.34; the second has 446 and lift about 0.84. These are different raw-label populations, not
interchangeable estimates of one normalized pair. Suppressing alias partners in results does not
merge counts. Normalize with a versioned mapping, retain raw labels and deduplicate each record
before recomputing statistics. Do not automatically collapse chemically or perceptually distinct
terms because their names look similar.

Family mapping sources also disagree (45 of the 140 wheel notes in the inspected mapping
comparison). The implementation resolves precedence, but a family label is still a taxonomy
choice. Preserve its origin and mapping version. Evaluator descriptions such as “pencil shavings”
must remain intact rather than being silently rewritten to a published note such as vetiver.

## Candidate generation and model integration

The inspected pipeline uses Jaccard similarity between note sets, blocks candidates using three
rare notes, requires at least two shared notes, and returns up to eight ordinary neighbors plus
five variant neighbors. This is an efficient, nonexhaustive retrieval heuristic, not a learned
preference model. Name-based variant grouping needs stronger canonical version evidence in our app.

A useful initial design is a candidate service that offers both similar published profiles and
controlled contrasts, for example vanilla with dry woods versus vanilla with sweet fruit. Pass
that pool through evaluator-specific selection, availability and experiment policies. Preserve
why each sample was selected, the retrieval algorithm, snapshot, score type and model run.
Separate predicted liking, novelty, uncertainty and cost instead of disguising all of them as one
match percentage. High association alone does not establish expected information gain.

With a small family baseline, broad learned pair-interaction models are easy to overfit. Start
with interpretable retrieval and existing affinity scoring; compare candidate strategies
prospectively. Do not use final holdout ratings to tune aliases, thresholds or selection weights
and then report performance on those same holdouts as out-of-sample validation.

## Blindness and presentation rules

The most useful profile after reveal has three clearly labeled sections: published/source
metadata, the evaluator's recorded perception, and model interpretation. Preserve initial blind
responses and append later observations. Source pyramid notes must remain separate from actual
elapsed-time skin observations; ranks must not be drawn as invented ingredient percentages.

Before reveal, participant responses must not expose version IDs, house, notes, family-derived
identity hints, repeated-version links or blind-code mappings through new APIs or caches. Apply
the same policy to history, progress, explanations and profile summaries. Public catalog browsing
is distinct from disclosing which catalog item corresponds to a blind presentation. Record known
prior exposure rather than asserting that an already revealed version is naive in a later test.

## Reuse options and licensing boundaries

| Option | Assessment |
| :--- | :--- |
| Link to the public application | Useful immediately as an external reference; keep it outside blind session prompts |
| Embed its interface | Technically documented, but adds availability, privacy and versioning dependencies; optional after reveal |
| Copy its implementation | No software LICENSE/COPYING grant was found in the inspected snapshot; obtain permission or implement the ideas independently |
| Import the exported corpus | Declared dataset license has noncommercial/share-alike conditions; review intended use and upstream permissions before import or redistribution |
| Build our own derived assets | Recommended using authorized, pinned source snapshots and explicit taxonomy/version provenance |
| Evaluate Parfica vocabulary assets | Promising for aliases/identifiers, subject to per-asset provenance and license review |

The embedding documentation describes iframe auto-height messages. Any implementation here must
validate both `event.origin` and `event.source`, use a narrow message schema and send no private
evaluator data. Prefer local assets when frozen experimental reproducibility or offline use matters.

A public repository is not by itself a general software reuse license; see
[GitHub's licensing guidance](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/licensing-a-repository).
The [CC BY-NC-SA 4.0 terms](https://creativecommons.org/licenses/by-nc-sa/4.0/) address attribution,
noncommercial use and share-alike adaptations, but do not guarantee every underlying right.
The inspected manifest's declaration is evidence of its stated terms, not independent verification
of upstream Fragrantica permissions. This is an integration gate, not a conclusion that every
possible use is prohibited.

[Parfica Open Data](https://github.com/parfica/parfica-open-data) offers selected note/taxonomy and
brand/identifier fields under CC0. Wikipedia-derived text columns retain CC BY-SA terms;
Open Beauty Facts-derived EAN/INCI fields have separate ODbL terms. It deliberately excludes commercial fragrance pyramids, ratings, descriptions and
images. Review individual assets and pin a revision before adoption; it cannot replace our
fragrance-version/source catalog. No Parfica dataset was imported as part of this analysis.

## Decision record and remaining questions

Adopt the analytical distinction between frequency and association, reproducible preprocessing,
explicit source/profile separation and a candidate-generation stage. Defer copying code, importing
the corpus, embedding, learned interactions and full wheel UI until their concrete need and relevant
rights are established. Preserve ordinary encounter history and the delayed-reveal policy.

Implementation still needs: a complete verified baseline manifest; live PostgreSQL migration and
concurrency validation for calibration; permission evidence for chosen source assets; a reviewed
alias/taxonomy version; representative parser fixtures; and a prospective candidate-evaluation
protocol. This documentation does not claim those gates are complete.
