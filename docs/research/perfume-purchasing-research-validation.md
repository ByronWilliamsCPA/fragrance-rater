---
title: "Perfume-Purchasing Research Validation"
schema_type: common
status: published
owner: core-maintainer
purpose: "Claim-level validation of the two LLM-generated purchasing research reports and the bounded changes they support in the data-capture assessment."
tags:
  - research
  - evaluation
---

> **Status**: Evidence review for product-owner and data-science planning
> **Version**: 1.0
> **Updated**: 2026-09-21
> **Reviewed inputs**: [deep-research-report (13)](deep-research-report%20%2813%29.md) and
> [Perfume Purchasing Literature Review](Perfume%20Purchasing%20Literature%20Review.md)
> **Companion analysis**:
> [Preference-Prediction Data Capture Assessment](../planning/preference-prediction-data-capture-assessment.md)
> **Authority**: Advisory. This document validates research leads; it does not change an ADR,
> `PROJECT-PLAN.md`, the calibration protocol, or an approved milestone.

## 1. Executive verdict

Neither reviewed report is reliable enough to use as a requirements source without claim-level
verification.

`deep-research-report (13).md` is a useful topic map, but it combines genuine research, a restricted
bachelor dissertation, unauditable vendor statistics, weak consumer surveys, and uncited market
claims. It also turns correlational or adjacent-domain results into causal recommender advice.

`Perfume Purchasing Literature Review.md` is not a defensible literature review in its present
form. Its references include peer-reviewed papers, but also blogs, retailers, vendors, Wikipedia,
Reddit, Medium, ResearchGate landing pages, marketing services, and search-result summaries. It
frequently treats citations as interchangeable evidence and uses conclusions such as
“conclusively,” “ultimate ground truth,” and “eliminate blind-buy risk” that the underlying studies
do not support.

The validated evidence causes **small refinements, not a change of ML strategy**:

- preserve familiarity, detection/non-detection, perceived intensity, associations, and desired
  emotional effect as separate observations;
- retain physical application method, skin versus blotter stage, dose, elapsed time, and
  time-varying performance;
- model liking, wear, and purchase as different targets and keep offer/retail context out of the
  intrinsic-smell target;
- treat sampling as a prospective workflow to measure, not a proven causal feature boost;
- do not add genetics, MHC type, personality inventories, gender stereotypes, skin microbiome,
  skin type, influencer trends, packaging image features, GC-MS, or molecular embeddings to the
  first baseline.

## 2. Validation method

The reports were treated as untrusted lead lists. A claim was allowed to affect the recommendations
only when the cited work could be located in a primary publisher, journal, repository, or full
paper and its design and conclusion actually matched the claim. Reviews were used to test broad
claims only when they synthesized the relevant primary literature. Vendor and commercial material
could identify a product hypothesis, but not establish a prevalence, effect size, causal
relationship, or model feature weight.

Verdicts mean:

- **Supported**: the source and study support the bounded statement shown here;
- **Narrower than claimed**: a real result exists, but the report extrapolates beyond its population,
  stimulus, outcome, or design;
- **Contradicted**: stronger evidence does not support the report's statement;
- **Unverified**: the source is inaccessible, lacks auditable methods/data, or is not an adequate
  source for the claim;
- **Not decision-relevant**: the result may be real but does not answer this application's question.

## 3. Claim audit and effect on the current analysis

| Report claim | Independent validation | Verdict | Effect on Fragrance Rater |
| :--- | :--- | :--- | :--- |
| Familiarity, perceived intensity, and pleasantness are related across cultures | Distel et al. studied 123 women in three countries rating 18 everyday odors and reported positive correlations among these measures. Correlation does not show that increasing intensity or familiarity increases perfume liking. The report also gives the wrong journal issue/pages. [Primary record](https://pubmed.ncbi.nlm.nih.gov/10321820/) | Narrower than claimed | Keep separate response-level familiarity, intensity, detection, and liking fields. Explore interactions; do not hard-code an intensity/familiarity boost or call the relationship causal. |
| Odor-evoked memories can be especially emotional | Herz and Schooler found odor-cued autobiographical memories were more emotional than visual- or verbal-cued memories in a within-person study. It did not test perfume purchase or prove that specific notes cause specific moods. [Primary record](https://pubmed.ncbi.nlm.nih.gov/11868193/) | Supported, bounded | Retain optional `reminds_me_of`/association and desired-effect fields. Do not infer mood from published notes. |
| Sampling causes about 86% less regret and 3.2 times more repurchase | The exact figures occur on a Scento marketing page whose detailed methodology and row-level data are not publicly auditable. Independent evidence supports the **directional utility** of samples, but not those numbers: two consumer-product field experiments found incremental sales effects lasting up to 12 months; a 55,000-sample e-commerce quasi-experiment found a 64% relative spending increase during the campaign month and purchase/spending effects for at least three months; and a vendor-reported YSL fragrance campaign attributed full-size purchases within 30 days to 8.33% of sample recipients. [Scento claim](https://www.scento.com/pl/blog/perfume-consumer-behavior-statistics-2026-how-people-buy-fragrance), [field experiments](https://doi.org/10.1287/mksc.1030.0052), [e-commerce experiment](https://doi.org/10.1287/mnsc.2020.00902), [YSL case](https://www.odore.com/case-studies/ysl-product-sampling) | Exact figures unverified; general utility supported | Do not use 86% or 3.2×. It is supportable to say sampling can increase sales and may have durable effects, while disclosing that the fragrance-specific YSL result is vendor-reported, selected high-intent users, and has no published control. Record sample access, acquisition, and comparison-group outcomes so the application can measure incremental lift. |
| Brand personality predicts perfume purchasing | The cited University of Malta work exists, but it is a 2009 bachelor dissertation with a 120-person questionnaire. Its repository abstract says brand personality increased preference while consumer-brand personality congruence did not. [University record](https://www.um.edu.mt/library/oar/handle/123456789/79153) | Narrower than claimed | Brand can remain a catalog feature and later observed affinity. Do not add a personality inventory or treat brand personality as a validated causal driver. |
| Gender-incongruent scent can improve product value | Doucé et al. conducted an 182-customer field experiment involving **ambient store scent** in gender-specific clothing stores. It did not study whether a person likes or wears a gender-incongruent perfume. The report's volume/pages are incorrect. [Primary paper](https://doi.org/10.1002/cb.1567) | Not decision-relevant | Do not derive gender-based fragrance rules or novelty recommendations. If retail environment is ever studied, keep it separate from perfume response. |
| A 2026 mixed-method study of about 300 people establishes leading perfume purchase factors | The located paper describes surveys/interviews but does not report the claimed sample size. Its regression predicts an average from the same component variables, producing the expected equal coefficients and an apparent perfect fit; that is circular and cannot rank real purchase drivers. [Full paper](https://www.rjwave.org/jaafr/papers/JAAFR2601478.pdf) | Unsupported for inference | It may supply brainstorming categories only. Do not use its factor ordering, demographic conclusions, or sustainability claims to set baseline fields or weights. |
| MHC-related genetics are among the most robust perfume-choice mechanisms | A 2020 meta-analysis found no significant overall MHC-dissimilarity effects on actual mate choice, relationship satisfaction, or odor preference and identified publication bias. It explicitly describes MHC-driven fragrance selection as conjectural. [Meta-analysis](https://doi.org/10.1098/rspb.2020.0300) | Contradicted | Do not collect HLA/MHC, reproductive, or other genetic data. Do not present genetics as an explanation for recommendations. |
| Olfactory-receptor genetics explain 10–20% of smell perception | Trimmer et al. tested 332 people, 68 individual odorants at two concentrations, and 276 phenotypes. Genotype plus ancestry, age, and gender explained 10–20% for 15 selected single-odorant phenotypes. This is not evidence that those variables explain complex-perfume liking, wearing, or buying. [Primary record](https://pubmed.ncbi.nlm.nih.gov/31040214/) | Narrower than claimed | Capture response-specific non-detection and perceived intensity. Do not add genotyping, ancestry, age, or gender merely to reproduce this narrow result. |
| Perfume interacts idiosyncratically with body odor | Three small experiments found donor-by-perfume interactions; in the third, 21 rated donors' body odor combined with their self-selected perfume more favorably than with an assigned perfume. The work does not identify MHC, microbiome, or skin type as a usable predictor. [Primary paper](https://doi.org/10.1371/journal.pone.0033810) | Supported, bounded | Preserve skin-stage evidence and application details, and do not substitute blotter response for skin response. It does not justify biological profiling. |
| Oily/dry skin determines perfume longevity and should be a recommender input | Laboratory and modeling work supports that formulation, ingredient properties, temperature, airflow, and skin interaction affect evaporation/permeation. The cited evidence does not validate the report's consumer “oily skin lasts longer” rule or establish a useful self-reported skin-type feature. [Engineering review](https://pmc.ncbi.nlm.nih.gov/articles/PMC8196857/), [primary model](https://pubmed.ncbi.nlm.nih.gov/18503438/) | Narrower than claimed | Capture dose, application site/method, elapsed time, temperature/context, and repeated performance observations. Defer skin type; do not collect microbiome data. |
| The Principal Odor Map is a ready foundation for personalized perfume recommendation | The POM predicts perceptual labels and related properties from molecular structure and was prospectively tested on 400 previously uncharacterized **individual odorants**. It does not model proprietary multi-ingredient perfume formulations, user preference, context, wear, or purchase. [Primary paper](https://pubmed.ncbi.nlm.nih.gov/37651511/) | Narrower than claimed | Do not make molecular embeddings a baseline dependency. Reconsider only if lawful, versioned ingredient-level inputs and a validated mixture-to-product representation become available. |
| GC-MS is the “ultimate ground truth” for scent | GC-MS can identify or quantify volatile components under a declared analytical method; it does not by itself provide human perception, mixture effects, skin evolution, liking, wear intent, or purchase behavior. | Category error | Keep chemical composition, published notes, perceived notes, and outcomes as different evidence layers. No GC-MS requirement belongs in the initial roadmap. |
| Demographics, personality, gender coding, social trends, packaging, and influencers should be model inputs | The reviewed reports rely chiefly on weak surveys, adjacent-domain results, commercial pages, or uncited generalizations for these recommendations. No robust, decision-matched evidence was validated. | Unverified | Do not widen the baseline questionnaire or introduce stereotype-prone features. Add only under a prespecified hypothesis, ethical review, adequate sample, and demonstrated incremental value. |

## 4. Corrections to the generated reports

These are material source-integrity problems, not cosmetic bibliography issues:

- Distel et al. is *Chemical Senses* 24(2), 191–199, not the issue/pages shown in report 13.
- The Doucé ambient-scent article is *Journal of Consumer Behaviour* 15(3), 271–280 (2016),
  not 14(1), 35–44; more importantly, its treatment is store ambience rather than worn perfume.
- The claimed `N≈300` is not reported in the located Ganti paper.
- Scento's precise percentages and multipliers are company claims whose underlying methodology and
  data were not available for independent reproduction.
- Several consumer and market assertions are attributed only to retailer blogs, commercial survey
  summaries, or sources that themselves provide no primary data.
- The second report often cites a source for a nearby topic rather than for the numerical or causal
  claim in the sentence.
- A citation existing is not proof that the generated summary accurately represents it. The MHC,
  POM, skin, ambient-scent, and olfactory-genetics passages are examples of real research being
  stretched into unsupported application requirements.

## 5. Changes to the existing data-capture recommendations

### 5.1 Strengthened recommendations

The evidence strengthens, not originates, the following existing requirements:

1. Record detection/non-detection, familiarity, perceived intensity, and liking separately.
2. Preserve memory/association text and optional desired emotional effect without turning either
   into a predetermined note-to-mood mapping.
3. Treat blotter and skin observations as different evidence; record application method, dose,
   site, timepoint, and actual elapsed time.
4. Collect performance as a trajectory or declared timepoint, not one context-free “longevity”
   value.
5. Separate intrinsic smell liking from would-wear and offer-conditioned would-buy outcomes.
6. Record sample access and acquisition before interpreting absent wear or purchase as a negative.

### 5.2 Recommendations explicitly not added

Do not add the following before the first baseline:

- genotype, MHC/HLA type, ancestry, hormonal/reproductive data, or skin microbiome;
- a Big Five or fragrance-personality questionnaire;
- gender-derived preference rules or age-cohort stereotypes;
- self-reported oily/dry skin as a required model feature;
- social-media popularity, influencer mentions, packaging image embeddings, or trend scores;
- GC-MS profiles, POM embeddings, or inferred ingredient formulas;
- a built-in boost for intensity, familiarity, brand prestige, luxury price, or sample availability;
- vendor-reported percentages as targets, priors, benchmarks, or acceptance thresholds.

This is not a judgment that every deferred factor is irrelevant. It means the reviewed research
does not show that collecting it now would add reliable predictive value proportional to burden,
bias, privacy, cost, and missingness.

## 6. Prospective tests suggested by the research

The reports are most useful as a source of hypotheses the application can test with its own data:

| Hypothesis | Minimum design | Do not infer from |
| :--- | :--- | :--- |
| Familiarity changes the intensity-liking relationship | Pre-reveal familiarity, intensity, liking, repeated exposures, evaluator-level grouping | Cross-sectional correlation alone |
| Skin response adds signal beyond blotter response | Same fragrance/evaluator with standardized blotter and skin observations, application/time metadata | Self-selected favorites alone |
| Sampling access changes downstream purchase behavior | Frozen recommendation, sample availability and acquisition, offer details, mature follow-up, censoring, and an eligible comparison group | A post-sample conversion rate without its counterfactual |
| Emotional association improves contextual wear prediction | Optional association/desired effect plus scenario-specific wear outcome and actual wear follow-up | Note names or marketing copy |
| Brand or price affects purchase but not smell liking | Blind pre-reveal rating followed by post-reveal offer-conditioned decision | A single revealed-brand survey |

These tests should be preregistered in the application's experiment/decision records, evaluated
with user-grouped prospective splits, and reported with uncertainty and missingness. None should
delay the minimum baseline unless its required field cannot be reconstructed later.

## 7. Evidence-use rule going forward

Future research summaries should maintain a claim ledger with the exact claim, primary source,
population, stimulus, outcome, design, effect/uncertainty, limitations, and product decision it is
allowed to influence. Commercial or secondary sources should be labeled as hypothesis-generating.
Any recommendation involving sensitive data, new user burden, or a durable model feature should
require either replicated decision-matched evidence or a prespecified internal experiment.

This rule prevents a large bibliography from being mistaken for a validated evidence base and
keeps the first baseline focused on data that can actually answer the three product questions.
