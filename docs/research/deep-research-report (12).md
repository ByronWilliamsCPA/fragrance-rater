---
title: "Validation and Revision of a Small-Family Fine-Fragrance Evaluation Protocol"
schema_type: common
status: draft
owner: core-maintainer
purpose: "Deep-research report validating and revising the small-family fine-fragrance evaluation protocol against sensory-science standards and perfumery practice."
tags:
  - research
  - evaluation
---

> **Received**: 2026-09-19. **Model**: unspecified deep-research model (one of two independent
> responses to the [protocol research prompt](scent-evaluation-protocol-research-prompt.md)).
> **Verification**: a sample of citations was independently checked against primary sources on
> 2026-09-19; all checked out accurate. **Reconciliation**: see the
> [2026-09-19 ADR-005 amendment](../planning/adr/adr-005-controlled-calibration.md#2026-09-19-amendment-protocol-research-reconciliation),
> which follows this report wherever it disagrees with the companion response
> (`Fragrance Evaluation Protocol Validation.md`).

## Executive summary

The proposed protocol is fundamentally sound for **within-person preference learning**, but several changes would materially improve interpretability without making it burdensome.

**Session size: KEEP.** Three fragrances per session is conservative and appropriate. None of the reviewed ISO standards establishes a universal three-sample limit for untrained fragrance consumers; ISO 29842 instead makes the limit product- and assessor-dependent. Olfactory adaptation provides a physiological reason to keep blocks small. citeturn17view0turn6search13

**Daily load: CHANGE.** Nine fragrances/day is not demonstrated to be an invalid or unsafe threshold, but there is no evidence supporting nine as benign either. For four untrained evaluators completing a long questionnaire, use **two sessions/day × three fragrances = six/day**, preferably ≥3 hours apart. This is a conservative extrapolation, not an ISO requirement.

**Compression: CHANGE.** Replace five consecutive days with **seven test days distributed across roughly 10–14 calendar days**. Evidence that “weeks are intrinsically better” is weak; the benefit is lower same-day load and better repeat separation, while recording time, illness, congestion, hunger, ambient conditions, and prior fragrance. Circadian olfactory variation is experimentally documented. citeturn12search16

**Judgment set: CHANGE.** Keep detection, intensity, anchored 0–10 liking, would-wear, confidence, descriptors, familiarity, and text. Move would-buy out of the blinded core; make artistic appreciation secondary; replace the single familiarity integer with recognition/exposure categories.

**Ranking addition: KEEP, with modification.** Rank the three after rating them, but analyze the result as **one complete rank**, not three statistically independent pairs. ISO 8587 supports ranking; ISO 5495 concerns paired comparison. citeturn2search3turn13search1

**Repeat design: KEEP six, but STOP calling it a precise individual noise ceiling.** Six pairs/person are useful for repeat-error estimation but too few for a stable individual correlation/ICC. Pool repeat variance hierarchically across the four evaluators and report wide uncertainty.

## Evidence matrix

**Evidence grading:** **Strong** means a directly applicable consensus standard or convergent direct human evidence; **moderate** means good sensory/olfactory evidence but partial transfer to this exact setting; **weak** means adjacent evidence requiring extrapolation; **none** means I found no direct evidence answering the fine-fragrance question.

| Question | Finding | Strength | Key citations / identifiers | Specific recommendation |
| --- | --- | ---: | --- | --- |
| **Samples per session and per day** | ISO 8586:2023 concerns selected/trained and expert assessors, not naïve consumers; ISO 11035:1994 and ISO 13299:2016 concern descriptive profiling; ISO 8589:2007 concerns facilities. None establishes a universal fine-fragrance maximum per session/day. Current ISO 29842:2024 explicitly treats the number an assessor can evaluate reliably in one session as context-dependent and provides incomplete-block methods when the total exceeds it. Repeated/prolonged odor exposure causes stimulus-specific adaptation and reduced suprathreshold responsiveness. Coffee beans have not been shown superior to plain air in the small direct experiment located. citeturn2search12turn1search1turn2search14turn13search28turn17view0turn6search13turn9search8 | **Moderate** | ISO 8586:2023; ISO 8589:2007; ISO 11035:1994; ISO 13299:2016; ISO 29842:2024. Dalton 2000, DOI **10.1093/chemse/25.4.487**. Grosofsky et al. 2011, DOI **10.2466/24.PMS.112.2.536-538**. | **Keep three/session.** Limit routine testing to **six/day**. Use ≥2 min of clean air between fragrances and preferably ≥3 h between sessions; the exact intervals are **Expert Judgment/extrapolation**, because no fine-fragrance study establishes an optimal interval. Use longer recovery after a persistent or uncomfortable sample. Do not use coffee beans as a required “reset.” |
| **Session compression** | Human olfactory sensitivity has demonstrated circadian variation. The controlled circadian study found phase-related threshold changes, although its sample was small and does not establish an ideal perfume-testing hour. Menstrual-cycle effects have been reported, but the literature is heterogeneous and substantially weaker than the evidence for general between-day and circadian variability. ISO 8589 emphasizes controlled testing conditions; ISO 11136 addresses controlled consumer hedonic testing. I found **no direct evidence** that thirteen fine-fragrance sessions must be spread over “weeks.” citeturn12search16turn12search0turn22search0turn13search28turn14search38 | **Weak–moderate** | ISO 8589:2007; ISO 11136:2014/Amd 1:2020. Herz et al., *Chemical Senses*, DOI **10.1093/chemse/bjx067**. | Use **seven testing days over 10–14 calendar days**, two sessions on six days and one on the seventh. Keep each person's sessions in roughly the same time-of-day window where practical. Record context rather than trying to eliminate every source of real-life variation. |
| **Blotter versus skin** | I found **no direct, adequately controlled study quantifying how well commercial fine-fragrance liking on blotter predicts liking or wear intent on skin**. Skin is a different evaporation/partitioning substrate, and fragrance composition evolves strongly with elapsed time; skin-evaporation research supports temporal sampling, but it does not validate a specific 10-min/1-h/4-h/8-h consumer schedule. citeturn22search18 | **Weak / none direct** | Kasting et al., fragrance evaporation/skin kinetics; stable CDC record cited above. **No direct evidence found** for a validated blotter→skin hedonic correlation or universal industry timepoints. | Treat blotter as **screening**, skin as a distinct outcome. For selected candidates record **10 min, 1 h, 4 h, and 8 h**. These timepoints are **Expert Judgment**, chosen to capture early, transition, established drydown, and persistence phases. Do not present them as an ISO/perfumery standard. |
| **Hedonic scale choice** | ISO 4121 covers quantitative response scales and applies to hedonic as well as attribute judgments. The classic 9-point hedonic scale has the deepest consumer-sensory history. LAM was designed to provide semantically spaced affective anchors and greater range; VAS offers quasi-continuous placement but adds interface precision that need not correspond to greater psychological precision. Reviews conclude that scale choice involves tradeoffs rather than one universally superior scale. citeturn15search16turn22search1 | **Moderate** | ISO **4121:2003**. Lim 2011, DOI **10.1016/j.foodqual.2011.05.008**. Schutz & Cardello 2001, DOI **10.1111/j.1745-459X.2001.tb00293.x**. | A **0–10 integer scale is reasonable** for this family project, but add verbal anchors: **0 = dislike extremely; 5 = neither like nor dislike; 10 = like extremely**. Treat its apparent eleven-step resolution cautiously. There is no compelling reason to switch to LAM or VAS for four naïve evaluators. |
| **Rating versus ranking versus paired comparison** | ISO 8587 defines ranking as ordering samples and explicitly does not turn ranks into magnitude differences. ISO 5495 is a forced paired-comparison methodology. Thurstone and Bradley–Terry models provide latent-utility frameworks for pairwise choices; rank-order models extend the same concept to whole rankings. I found **no direct fragrance evidence that triad ranking has higher test–retest reliability than anchored liking ratings in naïve individuals**. citeturn2search3turn2search11turn13search1 | **Moderate for methodology; weak for claimed reliability gain** | ISO **8587:2006/Amd 1:2013**; ISO **5495:2005/Amd 1:2016**. Thurstone 1927, DOI **10.1037/h0070288**. Bradley & Terry 1952, DOI **10.1093/biomet/39.3-4.324**. | **Add the rank**, after absolute ratings. Store the complete ordering. Do **not** count ABC as three independent Bernoulli observations. Use a Plackett–Luce/rank-ordered likelihood or a joint latent-utility model. Absolute liking remains primary because rankings in disconnected three-item blocks do not establish a global preference scale by themselves. |
| **Order, position, and carry-over** | Balanced incomplete blocks are specifically standardized for sensory tests when not every sample can be evaluated in one session; the current standard is ISO 29842:2024. Williams-type crossover sequences balance immediate residual effects under their design assumptions. I found **no trustworthy fine-fragrance estimate of the numerical size of “first-position” or contrast effects** in commercial perfume hedonics. citeturn17view0 | **Moderate for design; weak for fragrance effect size** | ISO **29842:2024**. Williams 1949, DOI **10.1071/CH9490149**. | Balance positions 1/2/3 exactly or nearly exactly within evaluator; randomize within that constraint. **Do not systematically put animalic/strong samples last**: that aliases odor character with position. Instead allow at most one exceptionally persistent/aversive sample in a session when feasible and model position/session effects. |
| **Hidden repeats and reliability** | I found **no direct primary study supplying a defensible “typical ICC” for commercial-fragrance liking by naïve consumers several days apart**. Psychophysical smell tests can have high test–retest reliability, but threshold/discrimination/identification reliability is not a surrogate for hedonic preference reliability. citeturn22search2 | **None for the requested typical fragrance-liking ICC** | Haehner et al. 2009, DOI **10.1093/chemse/bjp057**, is relevant only as a contrast: it measures olfactory function, not perfume liking. | Keep six repeats/person if the 39-slot budget is fixed. Separate original/repeat by **≥7 calendar days where schedule permits and ≥12 intervening fragrance evaluations** (**Expert Judgment**). Ask whether it was recognized. Estimate repeat MAE/RMSE and measurement-error SD; pool the 24 family repeat pairs hierarchically. Do not present an individual Pearson r/ICC from n=6 as a precise ceiling. |
| **Perceptual dimensions** | ISO 11035 and ISO 13299 treat descriptor development as a deliberate profiling process; ISO 8586 emphasizes training for analytical assessors. Dravnieks' ASTM DS61 provides a broad semantic odor-character lexicon. Factor-analytic odor-space work such as Zarzo/Stanton supports lower-dimensional semantic structure, but it does not validate this exact eight-item questionnaire in naïve consumers. The Edwards wheel and Cinquième Sens taxonomies are useful industry classification/training systems, not, from evidence located, validated novice psychometric scales. citeturn1search1turn2search14turn2search12 | **Moderate for framework; weak for these exact dimensions** | ISO **11035:1994**; ISO **13299:2016**; ASTM **DS61**. Zarzo & Stanton, *Chemical Senses*, DOI **10.1093/chemse/bjp061**. | Keep 0–5 but anchor it as **attribute strength**, not agreement. Sweetness and freshness are reasonable novice dimensions. Treat **density, dryness, earthy/rooty, clean/soapy, and bodily/animalic as exploratory unless repeatability is demonstrated**. Remove “discomfort” from the descriptive block and make it a separate adverse/aversive response. |
| **Familiarity and mere exposure** | Familiarity is associated with odor hedonic judgment in human data, so it is not harmless nuisance information. However, familiarity, recognition, ownership, and number of prior exposures are different constructs. I found **no direct fine-fragrance evidence establishing that a 0–5 familiarity integer is superior to categorical exposure history**, nor enough evidence to quantify a causal mere-exposure adjustment for this protocol. | **Moderate for familiarity relevance; weak for causal exposure correction** | Distel et al. 1999, DOI **10.1093/chemse/24.2.191**. | Replace the single field with **recognition category + exposure history**; optionally retain a subjective 0–5 “feels familiar” strength. Measure familiarity *after* liking. Model second presentation explicitly, because a hidden repeat measures measurement noise **plus any exposure/learning effect**. |
| **Detection and intensity** | Detection and suprathreshold intensity are distinct outcomes. ISO 13301 covers detection-threshold methodology rather than hedonic evaluation. Because nondetection means the liking response is undefined (not “extreme dislike”); coding nondetected samples as liking=0 would create structural bias. Intensity, familiarity, and hedonic judgment are empirically related, but there is no universal inverted-U applicable to every odor. citeturn15search0 | **Moderate** | ISO **13301:2018**. Distel et al. 1999, DOI **10.1093/chemse/24.2.191**. | Use a **two-part/hurdle model**: detection first; conditional intensity/liking if detected. Keep intensity=0 for nondetection if 0 explicitly means “no odor detected,” but liking remains missing/not-applicable. Retain detected low-intensity ratings. Model intensity flexibly, e.g. spline/quadratic interaction, rather than imposing an inverted-U. |
| **Health and safety** | Fragrance contact allergy is well established; population sensitization and dermatitis are distinct from acute olfactory fatigue. I found **no evidence-based daily number of compliant commercial fragrances that constitutes a toxicological exposure limit for blotter smelling**, and IFRA limits apply ingredient/product-category exposure rather than “number of perfumes smelled.” Dermal testing adds sensitization/irritation considerations. citeturn23search7 | **Moderate for sensitization; weak for protocol-specific dose limit** | Current **IFRA Standards** should govern intended-use formulation; amendment number was not assumed because I could not verify the current 2026 amendment in the retrieved record. Johansen et al., “Fragrance contact allergy: a clinical review,” stable PubMed record. | Use finished commercial products as intended; do not deliberately increase skin dose. Exclude broken/irritated skin and known problematic products. Stop immediately for burning, rash, wheezing, marked headache, nausea, dizziness, or persistent respiratory irritation. Skin-test no more than **one new fragrance/day/person** in the calibration phase. Consent/assent and symptom logging are **Expert Judgment** for this family protocol. |
| **Minimum data for individual models** | I found **no validated minimum sample count for predicting an individual's preference for new finished perfumes**. Modern molecular-odor prediction studies have typically used hundreds of monomolecular odorants and many participants, far richer data than 33 mixed finished fragrances. Molecular descriptors can predict parts of odor perception, but proprietary perfume formulas are normally unavailable, mixtures are not monomolecular stimuli, and published “notes” are not analytical composition. | **Weak / none direct for n=33** | Keller et al. 2017, DOI **10.1126/science.aal2014**. Khan et al. 2007, DOI **10.1523/JNEUROSCI.1158-07.2007**. | Thirty-three/person is enough for a **small, strongly regularized hierarchical proof-of-concept**, not a richly parameterized personal model. Keep individual-specific effective dimensionality very low. Prefer preregistered broad accord/descriptive features plus concentration metadata over high-dimensional molecular claims or unconstrained text embeddings. Evaluate all feature choices strictly on the ten frozen holdouts. |

## Technical interpretation

The strongest conclusion from the standards review is actually a negative one: **there is no ISO rule saying an untrained person may smell exactly three, six, or nine fragrances.** ISO 8586:2023 is a selection/training standard for selected and expert assessors, whereas this protocol involves four naïve consumers whose own preferences are the estimands. ISO 11035:1994 and ISO 13299:2016 describe analytical descriptor/profile methodology, again a different problem. The most directly relevant consumer standard is ISO 11136:2014, while ISO 4121:2003 provides general guidance on response scales. Treating trained-panel recommendations as hard physiological limits for this family would therefore be an unjustified transfer. citeturn2search12turn1search1turn2search14turn14search38turn15search16

There is also a terminology correction worth making. **“ASTM E18” is a committee, not a single standard or guidance document.** ASTM Committee E18 develops sensory-evaluation standards and guidance across many applications. I did not find an ASTM E18 document that creates a fine-fragrance-specific samples-per-day ceiling. Accordingly, any statement such as “ASTM E18 allows X perfumes per session” would be unsupported unless accompanied by an actual ASTM designation. citeturn19search14turn19search30

The adaptation literature does justify restraint. Dalton's review describes both short-term adaptation and longer-lasting changes after sustained/repeated odor exposure, with reductions in suprathreshold responsiveness and effects dependent on concentration, exposure duration, and odorant. That supports short blocks, clean-air recovery, and not repeatedly “checking” a strip every few seconds. It **does not** supply a defensible rule such as “wait exactly 30 seconds” or “nine scents causes fatigue.” DOI **10.1093/chemse/25.4.487**. citeturn6search13

The famous coffee-bean practice deserves especially little authority. In the small direct experiment by Grosofsky, Haupert, and Versteeg, coffee beans did not outperform plain air as an aid between fragrance-identification exposures; the paper was exploratory and should not be generalized too aggressively, but it gives no reason to burden the protocol with coffee. DOI **10.2466/24.PMS.112.2.536-538**. citeturn9search8 Water can be offered for comfort and hydration, but **no direct evidence found** that drinking water “resets” olfaction. Likewise, smelling one's skin has no demonstrated reset function; it simply substitutes another odor background. The supported reset is principally **absence of the adapting odor plus time/clean air**. citeturn6search13turn9search8

That distinction matters to the proposed five-day calendar. Nine samples in one day are not proven excessive. Nevertheless, the original days one through three combine nine odor exposures with nine repetitions of a cognitively substantial questionnaire containing more than twenty numeric or textual judgments. The risk is therefore not only receptor adaptation; it includes response simplification, scale-use drift, decreasing willingness to type notes, and changing comparison standards. I found no direct finished-fragrance experiment from which a numerical degradation threshold can responsibly be quoted. **The six/day recommendation is therefore deliberately conservative Expert Judgment, not a standards requirement.**

Circadian context is more than hypothetical. Herz and colleagues demonstrated circadian modulation of odor sensitivity under a controlled protocol, with measurable threshold variation by biological phase. The study does not imply that everyone should test perfume at one particular clock hour, but it argues strongly for timestamping sessions and avoiding unnecessary changes between morning, afternoon, and late-night testing. DOI **10.1093/chemse/bjx067**. citeturn12search16turn12search0

Hormonal-cycle evidence deserves less weight. Studies report menstrual-cycle-associated differences in some olfactory outcomes, but effects vary by odorant, endpoint, hormonal conditions, and study design. The retrieved recent study suggests cycle-related variation can occur, but it does not justify making detailed menstrual tracking mandatory in a four-person family protocol. citeturn22search0 I would make cycle/hormonal context **optional and privacy-preserving**, especially because illness/congestion, testing time, prior fragrance, and room conditions are easier to measure and more immediately actionable. This recommendation is partly ethical/practical rather than a claim that hormonal effects are zero.

The proposed 0–10 liking scale is likewise more defensible than it may initially appear. ISO 4121:2003 allows quantitative response scales for hedonic assessment rather than mandating the classic nine categories. The 9-point scale has much stronger historical consumer-sensory validation, while the LAM scale was designed using semantically calibrated affective descriptors. Lim's review makes clear that hedonic scales have different assumptions and artifacts rather than a simple winner. DOI **10.1016/j.foodqual.2011.05.008**. citeturn15search16turn22search1

For this use case, switching to nine points solely because nine is conventional would sacrifice continuity without a clear gain. The important correction is **anchoring**. A naked “0–10” allows one evaluator to interpret 5 as mediocre and another as neutral. Use 0 = *dislike extremely*, 5 = *neither like nor dislike*, 10 = *like extremely*. For `would_wear`, use 0 = *definitely would not wear*, 5 = *might wear / depends on occasion*, 10 = *definitely would wear*. For intensity, 0 = *no odor detected*, 1 = *very weak*, 3 = *moderate*, 5 = *very strong*. Those labels reduce semantic ambiguity; they do not magically make adjacent integers psychologically equal. ISO **4121:2003**. citeturn15search16

Ranking adds genuinely different information. A person might give three fragrances 7, 7, and 7 yet still be perfectly able to say A > C > B. Conversely, ranks destroy information about the difference between “barely preferred” and “vastly preferred.” ISO 8587:2006 reflects this distinction: ranks establish order, not interval magnitude. citeturn2search3 That makes the proposed triad rank valuable as an auxiliary signal.

There is one important statistical correction: a three-item order such as A > B > C logically implies A>B, A>C, and B>C, but those three relations came from **one ranking event**. Treating them as three independent observations will understate uncertainty. A Plackett–Luce/rank-ordered likelihood is cleaner; alternatively, use the implied Bradley–Terry pairs while clustering them by ranking event or building them into the same latent-utility likelihood. Bradley & Terry's foundational model is DOI **10.1093/biomet/39.3-4.324**; Thurstone's comparative-judgment formulation is DOI **10.1037/h0070288**.

There is a second, subtler limitation. Thirteen disjoint three-fragrance rankings create thirteen local islands: there is no ordinal evidence that the winner of session one outranks the loser of session eight unless an item bridges the sessions. The six repeats create a few possible bridges, but not necessarily a connected, well-conditioned comparison graph. **Absolute liking is therefore essential.** Ranking should regularize/refine local distinctions, not replace the 0–10 preference outcome.

Order should be handled by design rather than folk wisdom. Putting animalic, oud, smoke, or very strong fragrances last sounds sensible because it avoids contaminating later samples, but it permanently confounds “animalic/strong” with “third position.” Then the model cannot know whether lower liking arose from the fragrance or from being last. Williams designs were developed to balance immediate residual treatment effects, while ISO 29842:2024 formalizes incomplete-block design in sensory work. DOI **10.1071/CH9490149**; ISO **29842:2024**. citeturn17view0

With three items and four evaluators, full six-permutation balancing within every trio is mathematically impossible. That is not a serious problem. Use constrained randomization so that each individual receives exactly thirteen first-, thirteen second-, and thirteen third-position presentations across the 39 slots, while diagnostic roles and expected persistence are approximately balanced. Rotate which permutations are omitted between sessions. Model `position`, `session_index`, `session_of_day`, and, if feasible, the previous sample's intensity/persistence class.

For exceptionally persistent stimuli, **isolate rather than relegate**: place at most one high-persistence animalic/oud/incense/smoke item in a given session where the stimulus inventory permits, but still randomize its position. This is an extrapolated engineering control; **no direct evidence found** quantifying how much an animalic perfume contaminates the next commercial fragrance's hedonic rating.

The six repeats are useful, but “noise ceiling” overstates their precision. Suppose one evaluator produces six repeat differences and their observed standard deviation is \(s_d\). Under the simple normal independent-error model, six differences provide only five degrees of freedom; the 95% chi-square interval for the true repeat-difference SD is approximately **0.62× to 2.45× the observed SD**. That enormous range is pure sampling mathematics, not a flaw in the evaluator. Pooling all four people's six pairs gives 24 differences and, under a common-error assumption, narrows the analogous multiplier to roughly **0.78× to 1.40×**. A hierarchical model can split the difference: share information about measurement error while allowing evaluator-specific departures.

Thus, six repeats/person are acceptable because adding many more would cannibalize the 33 unique training fragrances. They are not enough to support statements such as “Evaluator A's true reliability is ICC=.74.” Report repeat **MAE**, **RMSE**, mean signed change from first to second exposure, and an error-scale posterior. If an ICC or correlation is shown, accompany it with its interval and call it descriptive.

The first-to-second change is itself important. A hidden repeat is not a pure machine calibration. The participant has experienced the fragrance once before. Familiarity is empirically related to hedonic judgment; Distel and colleagues showed meaningful relationships among familiarity, intensity, and hedonic evaluation. DOI **10.1093/chemse/24.2.191**. Therefore a repeat difference is a mixture of measurement error, changed context, recognition, and potentially an exposure/familiarity effect. Ask, after the repeat's ratings, **“Did this seem like something you smelled earlier in this study?”** before revealing anything. Then model `presentation_number` and `repeat_recognition`.

The descriptive dimensions need similar modesty. ISO 11035 and ISO 13299 are built around defining and refining descriptors, often with trained analytical assessors. They do not imply that any eight perfume adjectives form a validated consumer instrument. citeturn1search1turn2search14 Dravnieks' ASTM **DS61** demonstrates that semantic odor profiling can be systematic, and Zarzo/Stanton's factor-analytic work demonstrates latent structure in large descriptor spaces, but neither validates “sweet/fresh/dense/dry/soapy/earthy/animalic/discomfort” as eight interchangeable, equally reliable axes for a naïve family panel. DOI **10.1093/chemse/bjp061**.

Of the proposed variables, **sweetness** and **freshness** should be easiest to explain without specialist vocabulary. `Clean/soapy`, `earthy/rooty`, and `bodily/animalic` are recognizable semantic categories but are compound concepts. `Density` and `dryness` are useful perfumery ideas but rely heavily on cross-modal metaphor; without examples, two people can use them in opposite ways. `Discomfort` is different in kind altogether: it is a reaction to the fragrance, not a perceptual odor quality. I would preserve the first seven as exploratory features with a one-page glossary and move discomfort into a separate response/safety field. The claim that the first two will prove more repeatable is a **testable Expert Judgment**, not an established fact for these four evaluators.

The Michael Edwards wheel and Cinquième Sens classifications can be useful for selecting stimuli and communicating fragrance families. **No direct evidence found** in the retrieved primary/standards literature establishing either as a psychometrically validated 0–5 novice descriptive questionnaire. They should therefore inform the *stimulus metadata*, not be treated as validation of a consumer response scale.

Blotter-to-skin transfer is the largest evidence hole in the protocol. I found studies of fragrance evaporation and skin kinetics, but **no controlled primary literature giving a robust correlation such as “blotter liking predicts skin liking at r=.X” for modern finished perfumes**. That absence matters because paper and skin differ in surface chemistry, temperature, sorption, evaporation, and interpersonal context. Fragrance composition also changes over time as volatile components leave at different rates. citeturn22search18

Accordingly, don't train the primary model as though “blotter liking” and “skin liking” were the same endpoint. Store `substrate` explicitly and treat skin evaluation as a separate repeated-measures outcome. The requested 10 min, 1 h, 4 h, and 8 h schedule is sensible, but **no direct evidence found that those are standardized perfumery observation times**. I recommend them as **Expert Judgment** because they sample a roughly logarithmic wear trajectory without asking a family member to evaluate a fragrance every half hour.

At 10 minutes, record early skin liking and intensity; at one hour, established evolution; at four hours, the primary drydown/wear-intent assessment; at eight hours, persistence and late liking. Rather than asking for “longevity = 427 minutes,” which implies impossible precision, store an interval: `last_detected_elapsed_min` and `first_not_detected_elapsed_min`. If it was present at four hours and absent at eight, longevity is interval-censored between 240 and 480 minutes. That representation is statistically honest.

Skin selection also needs thought. Testing only fragrances that scored 9–10 on blotter makes the blotter/skin comparison range-restricted and nearly impossible to calibrate. For a practical pilot, select approximately **six skin fragrances/person**: two high-liking, two medium/borderline, and two high-uncertainty or model-disagreement examples, provided none produced substantial discomfort. That is enough to expose obvious blotter/skin reversals without turning the project into a dermatology residency. This allocation is **Expert Judgment; no direct minimum-n evidence found**.

Finally, thirty-three individual labels are genuinely small data. Keller and colleagues' DREAM Olfaction Challenge used hundreds of monomolecular odorants and dozens of people to learn relationships between molecular features and perceptual attributes; even in that much richer setting, some perceptual attributes were substantially more predictable than others. DOI **10.1126/science.aal2014**. Khan and colleagues likewise demonstrated structure–pleasantness relationships at an aggregate level for odorants, not individualized finished-perfume preference from 33 mixtures. DOI **10.1523/JNEUROSCI.1158-07.2007**.

So 33 is not “too small to model,” but it dictates the model. A hierarchical model with strong shrinkage and perhaps a handful of individual deviations is appropriate. A 100-dimensional note embedding plus 30 individual coefficients is not. Published note pyramids are especially dangerous because they are marketing/creative descriptions, not quantitative analytical composition. Use a fixed, preregistered low-dimensional representation such as broad accord membership, your diagnostic roles, concentration class, and a small set of externally available note families. The ten holdouts then answer the only question that really matters: did those representations predict anything outside the 33 training items?

## Recommended revised protocol

I recommend keeping the basic structure (blind codes, individual randomization, blotter screening, hidden repeats, frozen holdouts) but revising execution as follows.

**Calendar and load.** Conduct **thirteen three-fragrance baseline sessions over seven test days distributed across approximately 10–14 calendar days**. Six test days contain two sessions and one contains one session. Separate same-day sessions by **at least three hours**. This gives six fragrances/day maximum rather than nine. The three-hour interval and two-week calendar are **Expert Judgment/extrapolation**, not ISO limits; their purpose is to reduce same-day dependence while preserving feasibility. ISO 29842:2024 supports the general principle of partitioning an otherwise excessive sensory workload, and olfactory adaptation literature supports odor-free recovery. citeturn17view0turn6search13

After the baseline model is frozen, run the ten validation holdouts in **four additional three/three/three/one sessions**, preferably on separate days or appended to later days under the same six/day ceiling. The holdout feature matrix, model code/version, priors, and predictions should be timestamped before any holdout response is entered.

**Pre-session conditions.** Use the same neutral room whenever possible, with no active air freshener, candles, cooking, or recently sprayed household cleaner. ISO 8589:2007 is the relevant test-room standard and emphasizes controlled sensory-test environments, although a normal home cannot and need not emulate a commercial sensory laboratory. citeturn13search28 Record room temperature and relative humidity; a practical target of roughly **20–23 °C and 40–60% RH** is **Expert Judgment for environmental stability**, not a perfume-specific ISO requirement.

Evaluators should not apply a personal perfume, strongly scented lotion, or fragranced hair/body product before the day's blinded blotter work where reasonably avoidable. Do not enforce arbitrary caffeine abstinence because **no direct fine-fragrance evidence found** that caffeine consumption invalidates testing. Instead record time since caffeine and food.

At the beginning of each session record: timestamp; hours since waking; illness yes/no; nasal congestion 0–3; allergy symptoms yes/no; self-rated smell-normal-today yes/no; hunger 0–5; hours since food; caffeine within past four hours yes/no and approximate time; smoking/vaping within past two hours if applicable; personal fragrance/scented grooming product since waking yes/no; ambient odor 0–3; room temperature; RH; and unusual comments. Menstrual/hormonal phase should be **optional**, with “prefer not to answer,” because the evidence is much weaker and the information more private. Circadian variation is directly supported; mandatory cycle tracking is not. citeturn12search16turn22search0

**Stimulus preparation.** Use identical blotter stock and standardized application as far as practical. Ideally decant into identical atomizers and use one full standardized spray at a defined distance, or characterize each original atomizer's approximate mass-per-spray in advance. The latter is **Expert Judgment**, not an ISO requirement. Record application method because EdC-through-extrait products and atomizers introduce intensity variance that otherwise masquerades as odor-family preference.

Prepare only the current session's three strips. Keep them physically separated so they don't perfume one another. Use fresh three-digit random codes that contain no brand or concentration clues. A repeated fragrance receives a new code.

**Within-session procedure.** Before the first sample, spend approximately one to two minutes in clean room air. Present one strip at a time. Take one or two brief normal sniffs rather than repeatedly smelling until the odor fades. Complete the quantitative judgments before free text. Put the used strip away from the evaluator after rating.

Allow **at least two minutes of clean air between the last sniff of one fragrance and the first sniff of the next**, and extend to roughly five minutes after a sample that feels persistent, very intense, nauseating, irritating, or difficult to clear. The exact 2/5-minute values are **Expert Judgment**; Dalton supports recovery during odor-free intervals but does not establish these particular cutoffs. DOI **10.1093/chemse/25.4.487**. citeturn6search13

Do not use coffee beans as a standardized reset. Coffee showed no superiority to plain air in the direct exploratory experiment located, DOI **10.2466/24.PMS.112.2.536-538**. citeturn9search8 Water is fine to drink but should not be entered in the SOP as an olfactory cleanser. Likewise, “smell your own skin” should not be a prescribed reset because **no direct evidence found** that it restores olfactory sensitivity.

**Core blotter judgments** should be made in this sequence so later semantic labeling has less chance to alter the principal preference score:

| Variable | Revised response |
| --- | --- |
| Detection | `Yes / No` |
| Intensity | 0 no odor; 1 very weak; 2 weak; 3 moderate; 4 strong; 5 very strong |
| Overall liking | 0 dislike extremely; 5 neither like nor dislike; 10 like extremely |
| Would-wear | 0 definitely not; 5 maybe/depends; 10 definitely |
| Liking confidence | 0 essentially guessing; 5 very certain |
| Sweetness | 0 absent → 5 dominant |
| Freshness | 0 absent → 5 dominant |
| Density/weight | 0 airy/light → 5 very dense/heavy |
| Dryness | 0 not dry → 5 very dry |
| Clean/soapy | 0 absent → 5 dominant |
| Earthy/rooty | 0 absent → 5 dominant |
| Bodily/animalic | 0 absent → 5 dominant |
| Odor discomfort/aversiveness | **separate outcome**, 0 none → 5 severe; not treated as a descriptive dimension |
| Recognition | new / vaguely familiar / definitely smelled before / think I know exact fragrance |
| Familiarity strength | optional 0 not familiar → 5 extremely familiar |
| Free text | perceived notes; likes; dislikes; reminds-me-of; comments |

This use of quantitative scales is consistent with ISO 4121's general scale framework, but the particular anchors above are protocol recommendations rather than ISO-prescribed wording. ISO **4121:2003**. citeturn15search16

For **nondetection**, record `detected=false`, `intensity=0`, and leave liking, would-wear, descriptive ratings, and rank relation **not applicable/missing by design**. Do not convert them to zero. This maintains the distinction between “I detect nothing” and “I strongly dislike what I detect.” ISO **13301:2018** provides the relevant conceptual separation for detection methodology. citeturn15search0

`Would_buy` should leave the core blinded questionnaire. Without identity, bottle size, price, and budget context, it is an ill-defined compound judgment. If purchase intent matters, collect it **after the complete wear phase**, preferably with realistic price information, as a secondary outcome. This is **Expert Judgment**.

`Artistic_appreciation` can remain as an optional 0–10 secondary outcome if the family genuinely cares about the distinction between “I admire it” and “I want to wear it.” It should occur after overall liking/wear intent and should not be included by default as another target in the already small predictive model.

**Ranking procedure.** After all three absolute evaluations, take **three to five minutes of clean-air rest**, then make one session-level ranking: “Considering your overall personal preference, rank the fragrances you detected from most preferred to least preferred.” Re-sniffing can be allowed once, but all three should receive equivalent opportunity and the rank-review sniff order should itself be randomized/recorded. The extra rest/re-sniff procedure is **Expert Judgment** intended to reduce immediate carry-over.

Do not force an undetected fragrance to the bottom. If all three are detected, obtain ranks 1/2/3 with no ties. If only two are detected, rank those two and mark the third unranked because of nondetection. If fewer than two are detected, there is no informative preference rank.

Store the result as one **rank event**. ISO 8587:2006 is the directly relevant sensory-ranking standard. citeturn2search3 In analysis, use the whole rank through a Plackett–Luce/rank-ordered model or an equivalent joint latent-preference likelihood. If converted into A>B, A>C, B>C records for software convenience, retain a common `rank_event_id` so those comparisons are not treated as independent.

**Order balancing.** Pre-generate schedules by constrained randomization. For every evaluator, the 39 baseline slots should contain exactly thirteen position-1, thirteen position-2, and thirteen position-3 observations. Balance diagnostic roles and expected intensity/persistence across positions. No session should contain two known exceptionally persistent/animalic/smoke/oud-type stimuli when the inventory allows a reasonable alternative. Crucially, the strong stimulus is **not always last**. ISO 29842:2024 supports incomplete-block organization when workloads exceed reliable within-session capacity; Williams' carry-over principles provide the statistical rationale for balancing order. citeturn17view0

**Hidden repeats.** Preserve six repeat slots per person. Select repeats to span the likely preference range and odor space rather than choosing six arbitrary items. For example, after stimulus metadata are fixed, select two expected broadly appealing/cleaner profiles, two intermediate/ambiguous profiles, and two challenging/persistent profiles without using evaluator responses to make the selection.

Place initial presentations early enough that the repeat can occur **≥7 calendar days later where feasible**, with **≥12 intervening fragrance evaluations**, a different three-digit code, different session number, and preferably different ordinal position. Those numerical separations are **Expert Judgment; no direct recognition-inflation threshold was found**.

Immediately after the normal repeat questionnaire, add:

> “Did this fragrance seem like one you had already evaluated in this study?”
> No / maybe / probably / definitely.

Do not tell the evaluator whether that answer was correct until data collection is complete.

Use the repeats primarily to estimate:
\[
d_{ij}=y_{ij,\text{repeat}}-y_{ij,\text{initial}}
\]

Report per person median/mean absolute difference, RMSE, signed repeat drift, and posterior measurement-error scale. Fit a family-level/hierarchical measurement-error distribution across all **24 repeat pairs**, allowing evaluator-level deviations. An individual correlation or ICC based on six pairs may be displayed only with conspicuously wide uncertainty.

Most importantly, replace the phrase **“test–retest noise ceiling”** in preregistration with something like **“repeat-based empirical measurement-error benchmark.”** A true noise ceiling would require stronger assumptions about stationarity, recognition, mere exposure, and context than these six repeats can verify.

**Skin phase.** Do not wear a skin-test fragrance before that day's blinded blotter sessions. Apply it after the final blotter session or on a separate day. Test **one newly applied fragrance per person per day** during the pilot. This simplifies attribution of headaches/irritation and prevents projection/sillage from contaminating later blinded samples; the one/day limit is **Expert Judgment**, not an IFRA numerical exposure limit.

Select approximately six candidates/person using a prespecified rule rather than simply “favorites only”: roughly two high-blotter-liking, two mid/borderline, and two model-uncertain or unusual-profile fragrances, excluding anything that produced significant discomfort.

Use one standardized application at the same skin site class each time, for example a defined section of inner forearm, with left/right side balanced over tests. Do not apply to broken, eczematous, freshly shaved, or irritated skin. Record site and application time.

At **10 min, 1 h, 4 h, and 8 h**, record actual elapsed minutes, detection, intensity 0–5, and skin liking 0–10. At 1 h and 4 h also record projection 0–5. Treat the **4-h assessment as the primary drydown/would-wear endpoint** for modeling; this priority is **Expert Judgment, not a validated industry standard**. Record 8-h wear intent as secondary if still detectable.

Replace exact longevity minutes with:

- `last_detected_elapsed_min`
- `first_not_detected_elapsed_min`

so survival/longevity can be treated as interval-censored. If the fragrance was still detected when observations ended, mark it right-censored.

**Safety and stop rules.** Fine fragrance on blotter does not have an IFRA “maximum samples/day” concept; IFRA Standards regulate safe use of fragrance ingredients according to product/application categories. Contact allergy to fragrance materials is clinically established. citeturn23search7 The product should therefore be used only at ordinary intended-use exposure, not sprayed repeatedly onto the same skin area to create an artificially strong test.

Each evaluator should be free to terminate any sample or session immediately. Stop skin exposure and wash with mild soap/water for significant burning, itching, erythema, swelling, wheezing, respiratory tightness, marked nausea, dizziness, or a significant headache. Persistent or serious symptoms warrant medical evaluation. For anyone with a known fragrance contact allergy, asthma triggered by fragrances, or a history of severe scent-provoked migraine, skin testing should be individualized rather than assumed safe. The operational stop rule is **Expert Judgment based on risk minimization; no protocol-specific clinical threshold was found**.

For a minor participant, parental permission plus the minor's affirmative assent is prudent even in an informal family study; participation should always be optional, and stopping should never be treated as “missing bad data.”

## Data-model changes required before the pilot

The revised method changes enough semantics that I would finalize the database around **presentations, sessions, ranks, skin observations, and adverse events**, rather than putting everything into one wide fragrance row.

| Schema area | Required change | Why it matters |
| --- | --- | --- |
| `presentation` | Add `presentation_id`, `evaluator_id`, `fragrance_id`, `blind_code`, `session_id`, `position`, `application_timestamp`, `substrate`, `dose_method`, `repeat_flag`, `original_presentation_id`, `presentation_number` | Repeats, order, substrate, and dosing must be reconstructible rather than inferred from row order. |
| `session` | Add `session_date`, `session_start_timestamp`, `test_day_index`, `session_of_day`, `hours_since_wake` | Supports circadian/session-load diagnostics. Circadian effects are experimentally documented. DOI **10.1093/chemse/bjx067**. citeturn12search16 |
| `session_context` | New fields: `illness`, `nasal_congestion_0_3`, `allergy_symptoms`, `smell_normal_today`, `hunger_0_5`, `hours_since_food`, `caffeine_recent`, `hours_since_caffeine`, `personal_fragrance_today`, `smoking_vaping_recent`, `ambient_odor_0_3`, `temperature_c`, `relative_humidity_pct`, optional `hormonal_context`, `prefer_not_hormonal`, comments | Allows sensitivity analysis without excluding otherwise valuable observations. ISO 8589 supports controlled environment; circadian/hormonal evidence argues for recording rather than assuming constancy. citeturn13search28turn22search0 |
| `blotter_rating` | Preserve nullable `overall_liking_0_10`; add explicit scale anchors in metadata. `would_wear_0_10`; `liking_confidence_0_5`; `detected`; `intensity_0_5` | Prevents missing from being conflated with zero and makes scale meaning stable. ISO **4121:2003**. citeturn15search16 |
| Non-detection | Implement `missing_reason = nondetection` or equivalent. Never set liking=0 automatically. | “No odor” and “extremely dislike” are different states. ISO **13301:2018**. citeturn15search0 |
| Perceptual dimensions | Keep seven descriptor columns; move current `discomfort` out of descriptor vector into `odor_discomfort_0_5` | Discomfort is a response/aversiveness variable, not an odor-character descriptor. ISO **11035:1994**, ISO **13299:2016**. citeturn1search1turn2search14 |
| Familiarity | Replace sole `familiarity_0_5` with `recognition_category`; optionally retain `familiarity_strength_0_5`; add `identity_guess` and, when recognized, `exposure_history` | Separates subjective familiarity, explicit recognition, and ownership/exposure. Familiarity is associated with hedonic judgment, DOI **10.1093/chemse/24.2.191**. |
| Repeat recognition | Add `recognized_as_study_repeat = no/maybe/probably/definitely` | Allows repeat agreement to be stratified by recognition. |
| `session_rank` | **New table**: `rank_event_id`, `session_id`, `evaluator_id`, `presentation_id`, `rank`, `eligible_for_rank`, `rank_review_order` | A full ranking is one dependent event; storing it relationally prevents accidental treatment as three independent comparisons. ISO **8587:2006**. citeturn2search3 |
| `pairwise_derived` | If generated, include `rank_event_id` and mark `derived=true`; do not regard rows as independent observations | Preserves relationship to underlying rank. Bradley–Terry DOI **10.1093/biomet/39.3-4.324**. |
| `free_text` | Timestamp or sequence after quantitative fields; retain note/like/dislike/reminds-me-of/comments separately | Reduces ambiguity about whether verbal labeling preceded the liking judgment. **Expert Judgment.** |
| `would_buy` | Remove from blinded core or mark `secondary`; add actual price/context if later collected | Purchase intent without price is not the same construct as sensory liking. **Expert Judgment.** |
| `artistic_appreciation` | Mark optional/secondary rather than core model target | Reduces questionnaire burden and prevents proliferation of highly correlated targets. **Expert Judgment.** |
| `skin_application` | **New table** with `application_id`, fragrance, evaluator, skin site, side, application timestamp, dose method, adverse-event status | Skin is a different substrate/exposure episode. |
| `skin_observation` | **New long-format table** with `application_id`, nominal timepoint, actual `elapsed_min`, detection, intensity, liking, projection, would-wear | Supports trajectories rather than four hard-coded wide columns. |
| Longevity | Replace `longevity_minutes` with `last_detected_min`, `first_not_detected_min`, `right_censored` | Longevity is normally interval-observed, not known to the minute. |
| `adverse_event` | **New table**: symptom type, onset, severity 0–5, skin/respiratory/headache/etc., stopped sample, action taken, resolved timestamp | Separates safety outcomes from ordinary dislike. Fragrance sensitization is clinically established. citeturn23search7 |
| `stimulus_metadata` | Add concentration class, diagnostic role(s), low-dimensional accord features, published-note source/version, expected persistence category | Provides pre-evaluation predictors for holdout prediction. |
| `model_freeze` | **New table**: feature-set version, source cutoff, training presentation IDs, model code/version/hash, freeze timestamp | Makes the ten holdouts genuinely prospective. |
| `holdout_prediction` | **New table**: `model_freeze_id`, evaluator, fragrance, predicted liking/wear/rank quantities and predictive interval, written before observation | Prevents leakage and allows honest out-of-sample scoring. |

The scale changes themselves should also be versioned. In particular, `overall_liking_scale_version = "11pt_bipolar_v1"` is worth storing. A database containing a bare integer `7` but not the wording that generated it loses experimental information.

The model should treat `overall_liking` as the principal continuous/ordinal-like target, with `would_wear` as a closely related secondary target. Given only 33 unique training fragrances/person, I would not estimate independent person-specific coefficients for all seven perceptual dimensions plus dozens of note indicators. Instead, use hierarchical shrinkage: global feature effects shared across the family, modest evaluator-specific deviations, evaluator intercepts, and perhaps evaluator-specific intensity sensitivity. That is an **Expert Judgment dictated by sample size**, not a published minimum-n rule.

The ranking model can share a latent preference \(u_{ij}\) with the rating model:

\[
y_{ij} \sim \text{rating model}(u_{ij},\sigma_i)
\]

and, for a session containing A, B, C,

```math
P(A>B>C)
=
\frac{e^{u_A}}{e^{u_A}+e^{u_B}+e^{u_C}}
\cdot
\frac{e^{u_B}}{e^{u_B}+e^{u_C}}
```

which is the Plackett–Luce construction. The rank contributes ordinal information without pretending that three implied comparisons are independent observations. Bradley–Terry/Thurstone are closely related comparative-judgment formulations. DOI **10.1093/biomet/39.3-4.324**; DOI **10.1037/h0070288**.

For repeat error, the cleanest specification is a measurement-error component with a possible second-exposure shift:

```math
y_{ijr}
=
u_{ij}
+
\beta_{\text{repeat}} I(r=2)
+
\epsilon_{ijr}.
```

That makes a crucial distinction between **random repeat error** and a systematic tendency to like a fragrance more or less the second time. Familiarity research makes assuming \(\beta_{\text{repeat}}=0\) unnecessarily strong. Distel et al., DOI **10.1093/chemse/24.2.191**.

For holdout reporting, use several metrics rather than a single correlation from ten items: MAE, RMSE, Spearman rank association, top-k recovery if useful, calibration of predictive intervals, and pairwise preference concordance. Always compare the hierarchical model with embarrassingly simple baselines: each evaluator's training mean, broad-family means, and perhaps nearest-neighbor by preregistered accord features. With n=10 holdouts, a fancy model beating a simple baseline is much more persuasive than a visually attractive correlation scatterplot.

## Risks and unresolved questions

The largest unresolved issue is **blotter-to-skin transfer**. No direct evidence found that provides a reliable numerical transfer function for finished commercial perfumes. The cheapest useful check is already compatible with the project: skin-test six deliberately selected fragrances per evaluator, not just favorites, and compare blotter versus four-hour skin liking and would-wear. Treat this as calibration rather than another large experiment. If reversals are frequent, substrate needs to enter the model as more than a nuisance covariate.

The second uncertainty is whether the proposed seven semantic dimensions are reproducible without training. ISO 11035/13299 tell us how serious descriptive panels address lexicon development; they do not certify novice use of `density` or `dryness`. citeturn1search1turn2search14 The cheapest pilot check is the six hidden repeats: for every descriptor compute the mean absolute repeat difference and within-person agreement. A dimension that repeatedly changes from 0 to 4 under otherwise similar exposure should not be allowed to drive a preference model merely because perfumers use the word elegantly.

Third, the recommended **six/day ceiling is deliberately conservative rather than empirically identified**. The cheapest test is not another study. Plot liking, intensity, missingness, questionnaire duration, free-text length, and repeat error against `session_of_day` and ordinal exposure count. If second sessions show no deterioration, six/day is vindicated operationally. If the original nine/day schedule is ever piloted, compare session three with sessions one and two; that directly tests the concern in the actual family rather than borrowing a threshold from unrelated foods or trained panels.

Fourth, **hidden repeats can be recognized**. Recognition may increase apparent agreement because a participant remembers the prior rating, or decrease it because deliberate reconsideration occurs. No reliable minimum forgetting interval for complex commercial perfume was found. The cheap check is the four-level repeat-recognition question. Report repeat error both overall and, descriptively, among repeats not confidently recognized.

Fifth, **familiarity is confounded with exposure and ownership**. A fragrance that resembles something a person once wore can score high because of autobiographical association, not because of its abstract olfactory coordinates. That is not necessarily unwanted noise: if the goal is predicting what that person will actually enjoy, autobiographical liking is part of the target. The cheap check is to distinguish “vaguely familiar,” “recognize exact fragrance,” and prior-use/ownership where known, rather than attempting to regress familiarity away automatically. Familiarity–hedonic associations are documented, DOI **10.1093/chemse/24.2.191**.

Sixth, **the ranking addition may create contextual rather than global preference information**. ISO 8587 establishes ranking methodology but not immunity to contrast effects. citeturn2search3 The cheap check is to compare each triad's ranking with the order implied by its three absolute liking scores. Disagreement is not necessarily error; it may reveal that ranking forces distinctions hidden by coarse ratings, but systematic disagreements involving position one or three would flag order/context effects.

Seventh, **six repeat pairs/person do not identify a precise individual noise ceiling**. This uncertainty is mathematical, not resolvable by better wording. Retaining all 33 unique baseline stimuli is probably more valuable than sacrificing many of them for repeat precision. The cheapest solution is hierarchical pooling of all 24 repeat differences, accompanied by evaluator-level deviations and wide intervals. If the eventual model's holdout error differs from the repeat benchmark by less than the uncertainty around that benchmark, the correct conclusion is “indistinguishable at this sample size,” not “model has reached the ceiling.”

Eighth, **33 stimuli may be insufficient for the intended representation**. No direct evidence found supplies a minimum n for individualized finished-fragrance recommendation. Keller et al.'s molecular prediction work used hundreds of monomolecular odorants, making a 33-per-person commercial-perfume problem markedly more data-poor. DOI **10.1126/science.aal2014**. The cheapest pilot check is a predeclared model ladder: intercept-only → diagnostic-family features → small accord feature set → hierarchical individual deviations. Only retain added complexity if it improves frozen-holdout predictions.

Finally, **IFRA compliance does not answer every participant-tolerance question**. Fragrance standards manage ingredient safety for intended product use; they cannot guarantee that an individual prone to contact allergy, asthma symptoms, or headaches will tolerate an arbitrary series of products. Contact sensitization is a recognized clinical phenomenon. citeturn23search7 The cheapest control is simple: normal consumer doses only, one new skin fragrance/day during calibration, adverse-event logging, and a low threshold to stop. There is no scientific virtue in finishing a rating while someone's skin is burning.

Overall, the protocol should therefore be characterized as an **N-of-one repeated consumer-preference study replicated across four individuals**, not a sensory panel intended to produce a population consensus. That conceptual distinction resolves several apparent conflicts with ISO trained-panel guidance. The objective isn't to make the four evaluators agree. It is to measure each person's preferences consistently enough that a strongly regularized model can generalize beyond the fragrances they have already smelled.

## Bibliography

**International Organization for Standardization.** *Sensory analysis: Selection and training of sensory assessors.* **ISO 8586:2023.** This standard concerns trained and expert sensory assessors; it should not be treated as a naïve-consumer sample-load prescription. citeturn2search12

**International Organization for Standardization.** *Sensory analysis: General guidance for the design of test rooms.* **ISO 8589:2007; Amendment 1:2014.** As of the retrieved 2026 ISO record, the 2007 edition remained published while a replacement was under development. citeturn13search28turn13search36

**International Organization for Standardization.** *Sensory analysis: Identification and selection of descriptors for establishing a sensory profile by a multidimensional approach.* **ISO 11035:1994.** citeturn1search1

**International Organization for Standardization.** *Sensory analysis: Methodology: General guidance for establishing a sensory profile.* **ISO 13299:2016.** citeturn2search14

**International Organization for Standardization.** *Sensory analysis: Guidelines for the use of quantitative response scales.* **ISO 4121:2003.** Applies to quantitative sensory assessment, including global/specific and objective/hedonic responses. citeturn15search16

**International Organization for Standardization.** *Sensory analysis: Methodology: General guidance for conducting hedonic tests with consumers in a controlled area.* **ISO 11136:2014; Amendment 1:2020.** citeturn14search38turn14search2

**International Organization for Standardization.** *Sensory analysis: Methodology: Ranking.* **ISO 8587:2006; Amendment 1:2013.** Ranking establishes ordinal order and does not quantify the size of differences. citeturn2search3turn2search11

**International Organization for Standardization.** *Sensory analysis: Methodology: Paired comparison test.* **ISO 5495:2005; Cor. 1:2006; Amendment 1:2016.** citeturn13search1turn13search9turn13search13

**International Organization for Standardization.** *Sensory analysis: Methodology: Balanced incomplete block designs.* **ISO 29842:2024.** This is the current edition replacing ISO 29842:2011; it applies where total samples exceed what assessors can reliably evaluate in one session. citeturn17view0

**International Organization for Standardization.** *Sensory analysis: Methodology: General guidance for measuring odour, flavour and taste detection thresholds by a three-alternative forced-choice procedure.* **ISO 13301:2018.** citeturn15search0

**ASTM International.** **Committee E18 on Sensory Evaluation of Materials and Products.** E18 is a standards committee, not itself a sensory-test standard number. citeturn19search14turn19search30

**Dravnieks, Andrew.** *Atlas of Odor Character Profiles.* ASTM Data Series **DS61**, 1985. Broad semantic odor-character reference; useful as a descriptor framework, not validation of the present eight-item novice scale.

**Dalton, Pamela.** “Psychophysical and Behavioral Characteristics of Olfactory Adaptation.” *Chemical Senses* 25, no. 4 (2000): 487–492. DOI: **10.1093/chemse/25.4.487**. citeturn6search13

**Grosofsky, Alexis, Michelle L. Haupert, and Sarah W. Versteeg.** “An Exploratory Investigation of Coffee and Lemon Scents and Odor Identification.” *Perceptual and Motor Skills* 112, no. 2 (2011): 536–538. DOI: **10.2466/24.PMS.112.2.536-538**. The small study did not establish coffee as superior to plain air. citeturn9search8

**Herz, Rachel S., Eliza Van Reen, David H. Barker, Chelsea J. Hilditch, et al.** “The Influence of Circadian Timing on Olfactory Sensitivity.” *Chemical Senses* 43 (2018): 45–51. DOI: **10.1093/chemse/bjx067**. citeturn12search16turn12search0

**Stanić, Ž., et al.** “Does Each Menstrual Cycle Elicit a Distinct Effect on Olfactory and Gustatory Perception?” 2021. Stable full-text record retrieved through PubMed Central. I am **not supplying an unverified DOI** for this article. The evidence should be treated as limited rather than as justification for mandatory cycle tracking. citeturn22search0

**Lim, Juyun.** “Hedonic Scaling: A Review of Methods and Theory.” *Food Quality and Preference* 22, no. 8 (2011): 733–747. DOI: **10.1016/j.foodqual.2011.05.008**. citeturn22search1

**Schutz, Howard G., and Armand V. Cardello.** “A Labeled Affective Magnitude (LAM) Scale for Assessing Food Liking/Disliking.” *Journal of Sensory Studies* 16 (2001). DOI: **10.1111/j.1745-459X.2001.tb00293.x**.

**Distel, H., T. Ayabe-Kanamura, M. Martínez-Gómez, et al.** “Perception of Everyday Odors: Correlation Between Intensity, Familiarity and Strength of Hedonic Judgement.” *Chemical Senses* 24, no. 2 (1999): 191–199. DOI: **10.1093/chemse/24.2.191**.

**Haehner, Antje, et al.** “High Test-Retest Reliability of the Extended Version of the ‘Sniffin’ Sticks’ Test.” *Chemical Senses* 34 (2009): 705–711. DOI: **10.1093/chemse/bjp057**. This is evidence about olfactory-function testing, **not** perfume-liking repeatability. citeturn22search2

**Sezille, C., et al.** “Hedonic Appreciation and Verbal Description of Pleasant and Unpleasant Odors in Untrained, Trainee Cooks, Flavorists and Perfumers.” *Frontiers in Psychology* (2014). Stable primary article retrieved; it demonstrates that novice/expert status matters to odor description but does not validate the present questionnaire. citeturn22search4

**Zarzo, Manuel, and David T. Stanton.** “Identification of Latent Variables in a Semantic Odor Profile Database Using Principal Component Analysis.” *Chemical Senses* 34 (2009). DOI: **10.1093/chemse/bjp061**. Relevant to latent structure of semantic odor descriptors, not validation of the eight proposed dimensions.

**Thurstone, L. L.** “A Law of Comparative Judgment.” *Psychological Review* 34 (1927): 273–286. DOI: **10.1037/h0070288**.

**Bradley, Ralph Allan, and Milton E. Terry.** “Rank Analysis of Incomplete Block Designs: I. The Method of Paired Comparisons.” *Biometrika* 39, nos. 3–4 (1952): 324–345. DOI: **10.1093/biomet/39.3-4.324**.

**Plackett, R. L.** “The Analysis of Permutations.” *Applied Statistics* 24, no. 2 (1975): 193–202. DOI: **10.2307/2346567**. Relevant to modeling a complete three-item rank as one ordered outcome rather than independent binary comparisons.

**Williams, E. J.** “Experimental Designs Balanced for the Estimation of Residual Effects of Treatments.” *Australian Journal of Scientific Research* (1949). DOI: **10.1071/CH9490149**. Foundational basis for Williams carry-over-balanced sequences.

**Kasting, Gordon B., et al.** Work on two-stage fragrance evaporation/absorption kinetics from skin, 2003. Stable CDC archival record retrieved. I am not supplying a DOI because I could not verify it from the retrieved record. citeturn22search18

**Johansen, J. D., et al.** “Fragrance Contact Allergy: A Clinical Review.” 2003. Stable PubMed record retrieved. The review documents fragrance contact sensitization as a genuine dermatological risk; I am not supplying a DOI that was not verified in the retrieved record. citeturn23search7

**International Fragrance Association.** *IFRA Standards / Standards Documentation.* Use the **current** standard applicable to each ingredient/product category. I did not verify a current 2026 amendment number in the retrieved search and therefore have not invented one. Official site: `https://ifrafragrance.org/`.

**Keller, Andreas, Richard C. Gerkin, Yuanfang Guan, et al.** “Predicting Human Olfactory Perception from Chemical Features of Odor Molecules.” *Science* 355, no. 6327 (2017): 820–826. DOI: **10.1126/science.aal2014**. Important evidence that molecular information can predict selected olfactory percepts, but based on hundreds of monomolecular odorants rather than 33 finished perfumes.

**Khan, Rehan M., Chung-Hay Luk, Adeen Flinker, et al.** “Predicting Odor Pleasantness from Odorant Structure: Pleasantness as a Reflection of the Physical World.” *Journal of Neuroscience* 27, no. 37 (2007): 10015–10023. DOI: **10.1523/JNEUROSCI.1158-07.2007**.

**Bottom-line protocol disposition:** keep the **three-sample block, blind coding, individual randomization, 33 unique baselines, six hidden repeats, frozen ten-fragrance holdout, and 0–10 core liking scale**. Change the **daily maximum to six, calendar to seven testing days over roughly two weeks, scale anchoring, familiarity representation, rank analysis, context logging, longevity representation, and interpretation of repeat reliability**. Do not adopt coffee-bean resets, do not force nondetected fragrances to zero liking or last rank, do not systematically place powerful fragrances last, and do not claim that six repeat pairs establish a precise individual “noise ceiling.”
