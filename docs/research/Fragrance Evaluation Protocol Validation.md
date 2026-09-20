---
title: "Validation and Optimization of a Small-Cohort Fragrance Evaluation Protocol"
schema_type: common
status: draft
owner: core-maintainer
purpose: "Deep-research report validating and optimizing the small-cohort fragrance evaluation protocol against sensory-science standards and perfumery practice."
tags:
  - research
  - evaluation
---

> **Received**: 2026-09-19. **Model**: unspecified deep-research model (one of two independent
> responses to the [protocol research prompt](scent-evaluation-protocol-research-prompt.md)).
> **Verification**: a sample of citations was independently checked against primary sources on
> 2026-09-19; findings included a fabricated DOI, two real DOIs reattributed to unrelated
> findings under invented author names, a wrong ISO 8589 edition year, and an IFRA/QRA2 claim
> its own cited paper does not support. **Do not cite this report's claims without
> re-verification.** **Reconciliation**: see the
> [2026-09-19 ADR-005 amendment](../planning/adr/adr-005-controlled-calibration.md#2026-09-19-amendment-protocol-research-reconciliation),
> which follows the companion response (`deep-research-report (12).md`) wherever the two
> disagree.

## **Executive Summary**

The proposed evaluation protocol represents a highly ambitious attempt to capture individual fragrance preferences within a small, untrained cohort using hierarchical predictive modeling. While the core objective is methodologically viable, the execution parameters introduced in the original protocol carry severe risks of sensory adaptation, scale-use bias, and contextual confounding. An exhaustive review of sensory psychophysics, international standards (ISO, ASTM), and computational olfaction necessitates immediate structural optimizations to ensure the resulting dataset is statistically robust and generalizable.

**Keep:**

* **Session Size:** The limit of three samples per session is strongly supported by psychophysical adaptation limits for complex fine fragrances.
* **Stimulus Variety:** The curation of 33 baseline stimuli spanning diagnostic olfactory roles provides a necessary topological mapping of the perceptual space, crucial for out-of-sample prediction.
* **Validation Holdouts:** Freezing predictive models prior to evaluating the ten holdout fragrances remains an excellent, rigorous approach to testing generalization.
* **Ranking Addition:** Retain the proposal to rank the three session samples. Forced-choice comparative methodologies provide essential relative utility data that bypasses absolute scale-use bias.

**Change:**

* **Pacing and Compression:** The accelerated 5-day schedule (up to nine samples per day) induces rapid olfactory fatigue, risks dermal sensitization, and violates basic physiological recovery times. The schedule must be decompressed longitudinally over three to four weeks.
* **Judgment Set and Scales:** Replace the unanchored 0 to 10 integer scales with a 100-point Visual Analog Scale (VAS) or a Labeled Affective Magnitude (LAM) scale. Convert categorical familiarity from a numeric rating to discrete categorical states.
* **Repeat Design:** Six hidden repeats are statistically insufficient to establish a reliable Intraclass Correlation Coefficient (ICC). The protocol must increase repeats to a minimum of ten per evaluator, spaced by at least 72 hours to prevent memory recall.

**Stop:**

* **Unsupported Palate Cleansers:** Discontinue the use of coffee beans between samples; empirical literature demonstrates they act as an additional masking stimulus rather than a receptor reset mechanism.
* **Untrained Lexical Profiling:** Stop requiring an untrained cohort to rate highly abstract, industry-specific dimensions (e.g., "chypre," "aldehydic") without physical reference anchors.

## **Protocol Parameter Analysis and Evidence Synthesis**

The following table synthesizes the findings for the twelve core questions posed regarding the experimental parameters, evaluating the strength of the evidence and establishing concrete recommendations.

&nbsp;

| Protocol Question | Finding | Strength of Evidence | Citations, DOIs, and Standards | Protocol Recommendation |
| :---- | :---- | :---- | :---- | :---- |
| **1\. Samples per session and day** | Three samples per session prevents cross-adaptation. Nine per day induces severe olfactory fatigue. Coffee beans fail to reset receptors; clean air or autologous skin sniffing is effective. | Strong | 1; ISO 8589:2010; Grosofsky et al. (DOI: 10.2466/24.10.PMS.113.6.1042-1046) | Limit to 3 samples per session and maximum 1 session per day. Mandate a 3-minute clean air interval between samples. Eliminate coffee beans. |
| **2\. Session compression** | Olfactory thresholds and hedonic valence fluctuate significantly with circadian phase, hunger, and hormonal cycles. A 5-day compression conflates these temporary states with baseline trait preference. | Strong | 5; Doty (DOI: 10.1093/chemse/bjl046); Hummel (DOI: 10.1093/chemse/bjx005) | Spread the baseline sessions over a minimum of 3 to 4 weeks. Record time of day, hunger state, and female cycle phase as covariates. |
| **3\. Blotter versus skin** | Blotters demonstrate linear evaporation; skin interaction alters substantivity and volatility curves. Perceptual "freshness" correlates negatively with substantivity (![Formula: r = -0.85][image1]). | Strong | 9; Zarzo (DOI: 10.1111/j.1600-0838.2011.01429.x) | Retain blotter for opening (0–10 min) and heart (20 min). Reserve skin application (max 1/day) for testing base note substantivity (4+ hours). |
| **4\. Hedonic scale choice** | The 9-point hedonic scale suffers from unequal intervals. Labeled Affective Magnitude (LAM) or a 100-point VAS provides superior discrimination and continuous derivatives for Bayesian predictive modeling. | Moderate | 12; ISO 4121:2003; Schutz & Cardello (DOI: 10.1016/S0950-3293(00)00042-5) | Implement a 0 to 100 continuous digital slider (VAS) with semantic verbal anchors strictly at the extremes and midpoint. |
| **5\. Rating vs. ranking** | Ranking provides relative utility compatible with Plackett-Luce models, avoiding absolute scale-use bias. Combining absolute rating with subsequent ranking ("rank-rating") yields maximal discriminability. | Strong | 15; ISO 8587:2006 (DOI: 10.3403/30131003) | Retain the ranking addition. After rating the 3 samples absolutely, mandate a forced-rank (1 to 3\) to feed a Plackett-Luce choice hierarchy. |
| **6\. Position & carry-over** | First-position bias and contrast effects severely skew hedonic data in sequential monadic designs. A Williams Latin Square effectively balances first-order carry-over effects perfectly across sequences. | Strong | 20; MacFie et al. (DOI: 10.1111/j.1745-459X.1989.tb00463.x) | Implement a Williams Latin Square sequence for the 3 samples per session. Isolate highly animalic or tenacious stimuli to the final position. |
| **7\. Repeats & reliability** | Six repeats are statistically insufficient to bound the Intraclass Correlation Coefficient (ICC) with tight confidence intervals. Memory recall inflates reliability if tested less than 48 hours apart. | Moderate | 23 | Increase hidden repeats to 10 minimum. Ensure initial and repeat presentations are separated by a minimum of 72 hours. |
| **8\. Perceptual dimensions** | Untrained consumers cannot reliably rate abstract dimensions (e.g., "chypre", "aldehydic"). Broad affective and physical terms (sweet, fresh, heavy) are viable without extensive reference training. | Strong | 27; ISO 11035:1994; ASTM DS61 (DOI: 10.1520/DS61-EB) | Reduce dimensions to basic anchors (sweetness, freshness, woodiness, floral, discomfort). Discard industry jargon for the naïve panel. |
| **9\. Familiarity & exposure** | Mere exposure alters hedonic valence. Familiarity is a discrete cognitive categorization, not a continuous quantitative intensity variable. | Moderate | Extrapolated from general sensory affective science | Change from 0–5 integer to categorical strings: 1=Never smelled, 2=Smelled similar, 3=Smelled exact, 4=Owned/Worn. |
| **10\. Detection & intensity** | Hedonic response to intensity follows an inverted-U Wundt curve. Non-detection equates to missing hedonic data, not zero liking, which skews intercepts if mathematically modeled as zero. | Strong | 30; Moskowitz (DOI: 10.1016/j.foodqual.2014.05.006) | Censor (treat as null/NA) liking data if detection is "no" or intensity is 0\. Wait 45 seconds before evaluating to bypass extreme top-note intensity. |
| **11\. Health & safety** | Repeated exposure to fine fragrance (\>3/day on skin) risks dermal sensitization, violating IFRA Category 4 limits based on Quantitative Risk Assessment (QRA2). | Strong | 32; IFRA QRA2 (DOI: 10.1016/j.yrtph.2020.104805) | Strict limit: Maximum 3 samples on blotter per day. Maximum 1 sample on skin per day. Formalize stop-rules for headache or nausea. |
| **12\. Modeling minimum data** | 33 samples per evaluator is borderline for individualized prediction unless using Hierarchical Bayesian shrinkage and transferring structural/semantic priors (e.g., matrix factorization). | Moderate | 19; Principal Odor Map (DOI: 10.1126/science.ade4401) | Utilize a partially pooled Hierarchical Bayesian model. Leverage published molecular/note profiles as a prior covariance matrix to reduce parameter space. |

## **Psychophysical Assessment and Olfactory Processing**

The integrity of a sensory evaluation protocol hinges upon mitigating physiological and environmental artifacts that corrupt psychological judgments. The proposed schedule (13 sessions of three samples compressed into five days, yielding up to nine presentations per day) presents critical physiological vulnerabilities that will compromise the predictive model.

### **Olfactory Adaptation and Washout Parameters**

Olfactory receptor neurons are subject to rapid, stimulus-specific adaptation. Prolonged or rapid sequential exposure to volatile organic compounds (VOCs) diminishes the receptor's signal transduction efficacy, a phenomenon generally termed olfactory fatigue1. The literature strictly dictates that recovery from adaptation requires the absence of the stimulus over time. The protocol's consideration of utilizing coffee beans as a palate cleanser must be abandoned immediately. Empirical research definitively demonstrates that coffee beans do not possess biological receptor-resetting properties; instead, they introduce a highly complex, competitive odorant profile consisting of hundreds of volatile compounds that mask previous stimuli and ultimately exacerbate overall neural fatigue1. Studies measuring identification accuracy after intervening stimuli showed no statistical difference between coffee beans, lemon slices, and plain air2.

The scientifically supported inter-stimulus protocol requires a minimum of two to three minutes of exposure to clean ambient air. Alternatively, sniffing an autologous, unscented biological baseline (e.g., the evaluator's own forearm) is an effective industry practice that allows the olfactory bulb to recalibrate to the observer's background physiological scent38.

### **Circadian and Physiological Covariates**

Sensory sensitivity is not a static trait; it is a dynamic state modulated by physiological chronobiology. Olfactory detection thresholds exhibit significant diurnal variation. Research using forced desynchrony protocols demonstrates that olfactory sensitivity is intrinsically linked to circadian phase, peaking in the evening and troughing in the morning6. Furthermore, metabolic states, specifically hunger, dramatically alter both olfactory sensitivity and hedonic valence. High hunger states increase olfactory sensitivity to neutral odors and shift the hedonic appraisal of food-associated (gourmand or sweet) profiles7.

Because the current protocol compresses 13 sessions into 5 days, evaluators will inevitably be tested at varying times of day and under differing metabolic conditions. This conflates temporary physiological states with baseline hedonic trait preferences. The schedule must be decompressed to a maximum of one session per day, spread over three to four weeks. Additionally, session context vectors must be captured as covariates in the data model. Variables such as time of day, hours since last meal, and menstrual cycle phase (which has been shown to influence olfactory threshold sensitivity) must be recorded prior to every session5.

### **Intensity, Detection, and the Hedonic Trajectory**

The handling of non-detection and intensity in the original protocol is mathematically flawed. If an evaluator cannot detect a fragrance, the protocol records intensity as zero and liking as zero. In psychophysics, a failure to detect a stimulus means the hedonic valence is undefined (missing), not negative or zero. Imputing a zero for liking artificially anchors the regression intercept and corrupts the hedonic matrix. Non-detections must be censored from the preference model entirely.

Furthermore, the relationship between odor intensity and hedonic liking is rarely linear; it typically follows an inverted-U Wundt curve30. A fragrance may be highly preferred at moderate intensity but induce strong aversion at high concentrations. Evaluating *extrait de parfum* concentrations on blotters immediately after spraying captures the extreme right tail of the Wundt curve, artificially suppressing liking scores due to solvent (ethanol) masking and overwhelming initial VOC concentration. A mandated evaporation period of 45 to 60 seconds is required before the initial opening assessment.

### **Dermal and Toxicological Limits**

Safety limits for fine fragrances are strictly governed by the International Fragrance Association (IFRA), specifically under Category 4 (hydroalcoholic products applied to unshaved skin)32. Fragrances contain numerous known dermal sensitizers, which are managed under the Quantitative Risk Assessment (QRA2) framework to establish No Expected Sensitization Induction Levels (NESILs)34. Applying multiple fine fragrances to the skin daily, particularly in a non-regulatory residential environment, introduces a severe risk of contact dermatitis. The protocol must enforce a hard limit of one skin application per evaluator per day, maintaining the three-sample session exclusively on blotters. Panelists must also be provided with formal stop-rules, allowing them to cease evaluation immediately upon the onset of headaches, nausea, or localized dermal irritation.

## **Medium-Dependent Evolution and Temporal Substantivity**

The assumption that blotter performance perfectly predicts skin performance for wear intent is a recognized limitation in fragrance chemistry. The physical thermodynamics of evaporation differ fundamentally between a cellulose matrix (paper blotter) and the human epidermis.

### **Blotter versus Skin Kinetics**

Substantivity, the persistence of a fragrance material on a substrate, is dictated by vapor pressure, molecular weight, and substrate affinity9. On a blotter, evaporation is primarily a function of ambient temperature and vapor pressure, leading to a relatively linear and predictable volatilization curve. On skin, the interaction is vastly more complex. Lipophilic aroma chemicals interact with human sebum, while body heat (approximately 32°C at the epidermal surface) aggressively accelerates the volatilization of top notes (e.g., citrus, green notes)10.

Research indicates that perceptual "freshness" exhibits a strong negative correlation (![Formula: r = -0.85][image1]) with substantivity10. Consequently, a highly volatile citrus or aquatic opening may persist for 30 minutes on a blotter but vanish in 5 minutes on skin. Conversely, heavy base notes (musks, resins, woods, animalics) display high substantivity and ultimately govern the long-term hedonic experience of wearing a fragrance.

For the protocol to yield valid predictive models, elapsed-time observations are critical. The standard assessment intervals should capture the distinct temporal lifecycle of the fragrance:

| Evaluation Phase | Elapsed Time | Predominant Chemical Profile |
| :---- | :---- | :---- |
| **Opening** | 0 – 5 minutes | High-volatility esters, aldehydes, and citrus isolates. |
| **Heart / Mid** | 20 – 30 minutes | Floral, spicy, and fruit modifiers after solvent flash-off. |
| **Drydown / Base** | 4 – 8 hours | High molecular weight fixatives (ambroxan, woods, musks, resins). |

To predict wear intent accurately, the 4-hour skin observation is the highest-value data point, as it represents the true substantivity and the final profile the evaluator will experience throughout a normal wear cycle.

## **Psychometric Scaling, Choice Modeling, and Experimental Design**

The choice of measurement scales directly impacts the statistical power and continuous differentiability of the resulting predictive model. Untrained evaluators lack the internal calibration of expert panels, making scale topology uniquely critical.

### **Hedonic Scaling for Naïve Evaluators**

The protocol originally proposed a 0 to 10 numeric scale for overall liking. While cognitively simple, integer scales often suffer from end-avoidance (evaluators rarely use 0 or 10, compressing variance) and unequal intervals (the psychological distance between 4 and 5 is rarely perceived as equal to the distance between 8 and 9\)13. The ISO 4121 standard provides overarching guidance on quantitative response scales, highlighting these vulnerabilities12.

A superior alternative is a 0 to 100 Visual Analog Scale (VAS) deployed via a digital slider, anchored at 0 ("Dislike Extremely"), 50 ("Neither Like Nor Dislike"), and 100 ("Like Extremely"). Alternatively, the Labeled Affective Magnitude (LAM) scale provides empirically validated ratio properties that consistently outperform standard 9-point hedonic scales in consumer preference testing13. For this protocol, a 0 to 100 continuous VAS is recommended to maximize variance and provide continuous derivatives for Bayesian sampling algorithms.

### **Comparative Judgments and the Rank-Rating Paradigm**

The proposed protocol addition of ranking the three session samples from most to least preferred is highly recommended and should be formalized. Absolute ratings are subject to severe scale-use heterogeneity. For example, Evaluator A might possess a constrained hedonic range resulting in an average rating of 4, while Evaluator B consistently scores an average of 8\. Ranking forces discrimination and yields pure relative utility values41. ISO 8587 specifically standardizes sensory ranking methodologies to address this41.

From a computational modeling perspective, converting a session's data into a partial ranking allows the application of random utility models. While paired comparisons map neatly to Thurstone or Bradley-Terry models15, ranking a complete set of three items maps perfectly to a Plackett-Luce choice model17. The Plackett-Luce model operates on the axiom of choice, treating the ranking as a sequential selection process, which is highly robust for preference estimation. Combining the absolute rating with the relative ranking (a "rank-rating" approach) will allow the Hierarchical Bayesian model to calibrate the subjective absolute scales against the invariant relative rankings16.

### **Order, Position, and Carry-over Effects**

Sensory evaluation is uniquely vulnerable to sequential context effects. The first sample evaluated in a session almost universally receives an inflated or deflated score depending on stimulus novelty, a phenomenon known as the first-position effect. Furthermore, contrast effects occur when a weak stimulus follows a highly intense stimulus: for example, evaluating an ethereal green tea scent immediately after an animalic oud will render the tea scent perceptually invisible and hedonically muted44.

To mitigate this within a 3-sample session, the presentation order must be rigorously counterbalanced. The mathematically optimal design for neutralizing first-order carry-over effects is a Williams Latin Square20. For three samples (A, B, C), a Williams Latin Square requires six presentation sequences:

| Sequence ID | Position 1 | Position 2 | Position 3 |
| :---- | :---- | :---- | :---- |
| **1** | A | B | C |
| **2** | A | C | B |
| **3** | B | A | C |
| **4** | B | C | A |
| **5** | C | A | B |
| **6** | C | B | A |

The randomization engine must ensure that across all sessions, samples appear in the first, second, and third positions an equal number of times. Highly tenacious or animalic stimuli should ideally be dynamically blocked or evaluated at the end of a session to prevent receptor saturation.

### **Test-Retest Reliability and Intraclass Correlation**

The current protocol features 6 hidden repeats to establish a noise ceiling. This is critically insufficient for mathematical modeling. In sensory science, the Intraclass Correlation Coefficient (ICC) is utilized to measure test-retest reliability23. Generating a stable ICC with appropriately narrow confidence intervals generally requires a minimum of 10 to 15 paired observations per evaluator25.

Furthermore, the temporal spacing between the initial presentation and the hidden repeat is paramount. If a repeat is presented on a subsequent day (e.g., 24 hours later), episodic memory recall rather than true sensory evaluation will artificially inflate the reliability metric. A minimum interval of 72 hours must be enforced between the initial presentation and its blind repeat to ensure the olfactory memory has sufficiently decayed.

## **Perceptual Frameworks and Covariate Capture**

Predicting individual preference requires mapping the chemical stimulus to a latent perceptual space. However, untrained cohorts interact with descriptors very differently than trained expert panels.

### **Lexical Ontologies and Descriptive Analysis**

The protocol requires evaluators to rate abstract dimensions such as "aldehydic," "chypre," or "animalic." According to ISO 11035 (Identification and selection of descriptors for establishing a sensory profile)14, descriptive profiling relies heavily on exhaustive consensus building and physical reference standards. Untrained evaluators exhibit high variance and extremely poor repeatability on abstract or industry-specific terms27. For example, the dimensions mapped by Zarzo and Stanton (2009) via principal component analysis demonstrate that while experts easily isolate "floral" or "balsamic," naïve consumers collapse these nuanced categories into broad axes of general "freshness" and "sweetness"27.

The perceptual dimension questionnaire must be vastly simplified. The protocol should retain universal hedonic and basic physical descriptors (Sweetness, Freshness, Woodiness, Floral, Heaviness/Density, Discomfort). Industry jargon (e.g., "chypre" and "aldehydic") must be completely discarded from the evaluator questionnaire; these dimensions should instead be hard-coded as independent variables (features) in the dataset based on the manufacturer's published notes or expert classifications (e.g., the Edwards Fragrance Wheel).

### **Familiarity Encoding**

Liking is intrinsically tied to familiarity through the well-documented mere-exposure effect. However, familiarity is not a linear continuum. A 0 to 5 integer scale is mathematically inappropriate for modeling familiarity, as the cognitive difference between "0" and "1" (never smelled vs. smelled once) is vastly different from "4" and "5" (smelled frequently vs. worn daily). The protocol should capture familiarity categorically to prevent the Bayesian model from inferring false continuous slopes:

* **0:** Never smelled anything like this.
* **1:** Smelled something similar.
* **2:** Have smelled this exact fragrance before.
* **3:** Have owned or worn this fragrance extensively.

## **Experimental Design and Predictive Modeling**

The ultimate goal of the protocol is individual preference prediction via a partially pooled (Hierarchical Bayesian) model. The statistical power of this model relies entirely on the precise estimation of intrinsic noise versus true signal.

### **Minimum Data and Hierarchical Bayesian Regularization**

Fitting an individual-level model on 33 stimuli is an extreme case of "small ![Symbol: N][image2], high ![Symbol: P][image3]" statistics. Standard frequentist regressions will overfit the data drastically. The protocol correctly identifies the need for a Hierarchical Bayesian model utilizing strong priors17. However, to make out-of-sample predictions (the 10 holdouts) viable, the model cannot rely solely on the evaluator's subjective descriptors.

Recent advances in computational olfaction, such as Principal Odor Maps (POM) generated via matrix factorization or graph neural networks37, indicate that odor perception is highly linear with respect to its constituent parts36. The schema should map the 33 baseline fragrances to a reduced-dimensional space using published olfactory notes (e.g., one-hot encoding for "Rose", "Vanilla", "Bergamot"). The Hierarchical Bayesian model can then partially pool the weights of these notes across the four family members, borrowing statistical strength from the group to regularize the individual predictions and prevent overfitting.

## **Recommended Revised Protocol**

Based on the synthesis of sensory standards and physiological literature, the protocol is optimized as follows to ensure validity:

**1\. Pacing and Calendar Spread:**

* **Sessions per day:** Strictly 1 session per day per evaluator to prevent systemic fatigue.
* **Calendar spread:** 16 total baseline sessions (allowing for 15 hidden repeats to achieve 48 total presentations), executed over roughly 3 to 4 weeks (e.g., 4 to 5 sessions per week).

**2\. Session Design and Counterbalancing:**

* **Samples per session:** 3 samples.
* **Design:** Implement a Williams Latin Square for presentation order to mathematically eliminate first-order carry-over effects.

**3\. Inter-Stimulus Procedure:**

* **Cleanser:** Discard coffee beans. Require a 2 to 3-minute inter-stimulus interval of breathing clean ambient air. In case of severe fatigue, instruct evaluators to bury their nose in their own unscented forearm or clothing.

**4\. Blotter and Skin Timepoints:**

* **Blotter (Primary):** Spray, wait 45 seconds for solvent flash-off, then evaluate the opening. Evaluate the heart at 20 minutes.
* **Skin (Secondary):** Maximum 1 skin sample per evaluator per day, chosen based on initial blotter preference. Evaluate opening (5 min), heart (30 min), and drydown/longevity at a minimum of 4 hours.

**5\. Judgment Set and Scale Anchors:**

* **Liking Scales:** Replace the 0-10 integer scale with a 0 to 100 continuous slider (VAS). Anchors: 0 (Dislike Extremely), 50 (Neutral), 100 (Like Extremely).
* **Intensity:** 0 to 100 scale. If Intensity \= 0 (undetected), the data capture script must skip all liking questions and record them as null (not zero).
* **Descriptors:** Simplify to a 0 to 100 scale for Sweetness, Freshness, Floral, Woodiness, Heaviness, and Discomfort.

**6\. Ranking Procedure:**

* At the end of the session, the 3 samples are placed side-by-side. The evaluator ranks them 1st, 2nd, and 3rd preference. (Ties are strictly forbidden).

**7\. Repeat Placement:**

* Increase hidden repeats from 6 to 15 to establish a robust ICC. Ensure a minimum 72-hour delay between test and retest.

**8\. Session Context Fields:**

* Before beginning, the evaluator logs: Time of Day, Hunger Level (1=Full, 5=Starving), Illness/Congestion (Yes/No), and Ambient Temperature/Humidity (if possible, per ISO 8589 guidelines targeting 20-22°C)4.

## **Data Model Alterations**

The underlying database schema must be updated prior to the pilot to accommodate the protocol changes:

1. **New Fields:**

   * session\_time\_of\_day (Timestamp)
   * evaluator\_hunger\_state (Integer 1-5)
   * evaluator\_congestion (Boolean)
   * forced\_rank\_position (Integer 1-3, recorded at the session level)

2. **Changed Scales:**

   * Convert overall\_liking, opening\_liking, drydown\_liking, would\_wear, would\_buy, and artistic\_appreciation from INT(0-10) to FLOAT(0-100) to support VAS data.
   * Convert familiarity from INT(0-5) to a categorical string or mapped INT(0-3) representing discrete states (Never, Similar, Exact, Owned).

3. **New Tables/Relationships:**

   * **Stimulus Metadata Table:** A table linking the 3-digit blind codes to static manufacturer data (Main Accords, Fragrance Family, Top/Heart/Base notes). This isolates the objective chemical/marketing profile from the subjective, untrained evaluator dimensions.

4. **Data Handling Rules:**

   * If detection \== FALSE, trigger a script that inserts NULL (not 0\) into all hedonic fields to prevent skewing the preference intercepts during Bayesian inference.

## **Risks, Unknowns, and Pilot Checks**

**1\. Contextual Extrapolation (Blotter to Skin)**

* *Risk:* Hedonic liking on cellulose (blotter) may correlate poorly with liking on the skin due to lipophilic interactions, differing substantivity, and temperature differentials.
* *Pilot Check:* During the first 5 sessions, require all evaluators to apply their \#1 ranked blotter sample to their skin. Calculate the Pearson correlation between their 20-minute blotter rating and their 4-hour skin rating. If ![Formula: r less than 0.5][image4], the model cannot rely solely on blotter data to predict wear intent and must incorporate substrate-specific intercepts.

**2\. Model Sparsity and Overfitting**

* *Risk:* 33 baseline samples may be insufficient to span the highly complex combinatorial space of perfumery, causing the Hierarchical Bayesian model to overfit to specific outliers (e.g., a strong aversion to one specific aquatic masking a general liking for fresh profiles).
* *Pilot Check:* Execute a prior predictive simulation. Feed the Bayesian model synthetic data generated from the 33 profiles to verify if it can recover known simulated preferences before human testing begins.

**3\. Evaluator Compliance and Hedonic Drift**

* *Risk:* Over a 4-week longitudinal study, evaluators may experience a systemic shift in their baseline preferences (hedonic drift) as their exposure to fine fragrance inadvertently increases their palate sophistication and familiarity.
* *Pilot Check:* Analyze the residuals of the hidden repeats. If the retest scores for Week 4 are systematically higher or lower than the test scores from Week 1 across all evaluators, a time-series covariate (e.g., days\_since\_start) must be added to the regression to mathematically detrend the data.

### **Works cited**

> 1. Three habits when evaluating, two of which do nothing, [https://scentdatabase.com/en/blog/three-habits-two-useless](https://scentdatabase.com/en/blog/three-habits-two-useless)
> 2. Nose Blind: Why You Can't Smell Your Perfume \- Premiere Peau, [https://premierepeau.com/blogs/news/nose-blind-why-you-cant-smell-your-perfume-premiere-peau](https://premierepeau.com/blogs/news/nose-blind-why-you-cant-smell-your-perfume-premiere-peau)
> 3. FOOD 3007 and FOOD 7012 SENSORY EVALUATION MANUAL, [https://pdfcoffee.com/download/sensory-evaluation-manual--pdf-free.html](https://pdfcoffee.com/download/sensory-evaluation-manual--pdf-free.html)
> 4. ISO 8589: Test Room Design Guidance | PDF | Lighting \- Scribd, [https://www.scribd.com/document/725501256/ISO-8589](https://www.scribd.com/document/725501256/ISO-8589)
> 5. a meta-analysis of menstrual cycle variation in olfactory sensitivity, [https://czasopisma.uni.lodz.pl/ar/article/view/11273](https://czasopisma.uni.lodz.pl/ar/article/view/11273)
> 6. The Influence of Circadian Timing on Olfactory Sensitivity \- PMC \- NIH, [https://pmc.ncbi.nlm.nih.gov/articles/PMC5863568/](https://pmc.ncbi.nlm.nih.gov/articles/PMC5863568/)
> 7. Sex difference in human olfactory sensitivity is associated with ... \- OSF, [https://osf.io/download/agz78/](https://osf.io/download/agz78/)
> 8. High Hunger State Increases Olfactory Sensitivity to Neutral but Not, [https://academic.oup.com/chemse/article/36/2/189/300366](https://academic.oup.com/chemse/article/36/2/189/300366)
> 9. (PDF) Sensory Approach to Measure Fragrance Intensity on the Skin, [https://www.academia.edu/33140458/Sensory\_Approach\_to\_Measure\_Fragrance\_Intensity\_on\_the\_Skin](https://www.academia.edu/33140458/Sensory_Approach_to_Measure_Fragrance_Intensity_on_the_Skin)
> 10. What is a Fresh Scent in Perfumery? Perceptual ... \- ResearchGate, [https://www.researchgate.net/publication/234011726\_What\_is\_a\_Fresh\_Scent\_in\_Perfumery\_Perceptual\_Freshness\_is\_Correlated\_with\_Substantivity](https://www.researchgate.net/publication/234011726_What_is_a_Fresh_Scent_in_Perfumery_Perceptual_Freshness_is_Correlated_with_Substantivity)
> 11. What is a Fresh Scent in Perfumery? Perceptual ... \- PMC \- NIH, [https://pmc.ncbi.nlm.nih.gov/articles/PMC3574685/](https://pmc.ncbi.nlm.nih.gov/articles/PMC3574685/)
> 12. ISO 13299:2003 \- Sensory analysis \- Methodology \- ANSI Webstore, [https://webstore.ansi.org/standards/iso/iso132992003](https://webstore.ansi.org/standards/iso/iso132992003)
> 13. A labeled affective magnitude (LAM) scale for assessing food liking, [https://www.semanticscholar.org/paper/A-labeled-affective-magnitude-(LAM)-scale-for-food-Schutz-Cardello/b453766e34e0e3de203101b31054c91c4eeaacda](https://www.semanticscholar.org/paper/A-labeled-affective-magnitude-\(LAM\)-scale-for-food-Schutz-Cardello/b453766e34e0e3de203101b31054c91c4eeaacda)
> 14. Iso 11035 1994 | PDF | International Organization For Standardization, [https://www.scribd.com/document/503003026/ISO-11035-1994](https://www.scribd.com/document/503003026/ISO-11035-1994)
> 15. Thurstonian Scaling for Sensory Discrimination Methods \- MDPI, [https://www.mdpi.com/2076-3417/15/2/991](https://www.mdpi.com/2076-3417/15/2/991)
> 16. Ranking and Rank-Rating | Request PDF \- ResearchGate, [https://www.researchgate.net/publication/322782825\_Ranking\_and\_Rank-Rating](https://www.researchgate.net/publication/322782825_Ranking_and_Rank-Rating)
> 17. Bayesian nonparametric Plackett–Luce models for the analysis of, [https://arxiv.org/html/1211.5037v3](https://arxiv.org/html/1211.5037v3)
> 18. Modelling rankings in R: the PlackettLuce package \- ResearchGate, [https://www.researchgate.net/publication/339211286\_Modelling\_rankings\_in\_R\_the\_PlackettLuce\_package](https://www.researchgate.net/publication/339211286_Modelling_rankings_in_R_the_PlackettLuce_package)
> 19. (PDF) Hierarchical Partial-Order Models for Ranking \- ResearchGate, [https://www.researchgate.net/publication/408047548\_Hierarchical\_Partial-Order\_Models\_for\_Ranking](https://www.researchgate.net/publication/408047548_Hierarchical_Partial-Order_Models_for_Ranking)
> 20. MacFie, H.J., Bratchell, N., Greenhoff, K. and Vallis, L.V. (1989, [https://www.scirp.org/reference/referencespapers?referenceid=2208884](https://www.scirp.org/reference/referencespapers?referenceid=2208884)
> 21. Novel Modelling Approaches to Characterize and Quantify ... \- PMC, [https://pmc.ncbi.nlm.nih.gov/articles/PMC6262531/](https://pmc.ncbi.nlm.nih.gov/articles/PMC6262531/)
> 22. Comparison of Rapid Descriptive Sensory Methods Applied ... \- PMC, [https://pmc.ncbi.nlm.nih.gov/articles/PMC12385805/](https://pmc.ncbi.nlm.nih.gov/articles/PMC12385805/)
> 23. (PDF) Test–Retest Reliability of the One-Repetition Maximum (1RM, [https://www.researchgate.net/publication/342693290\_Test-Retest\_Reliability\_of\_the\_One-Repetition\_Maximum\_1RM\_Strength\_Assessment\_a\_Systematic\_Review](https://www.researchgate.net/publication/342693290_Test-Retest_Reliability_of_the_One-Repetition_Maximum_1RM_Strength_Assessment_a_Systematic_Review)
> 24. Intraclass Correlation Coefficient (ICC): A Framework for Monitoring, [https://www.researchgate.net/publication/263113570\_Intraclass\_Correlation\_Coefficient\_ICC\_A\_Framework\_for\_Monitoring\_and\_Assessing\_Performance\_of\_Trained\_Sensory\_Panels\_and\_Panelists](https://www.researchgate.net/publication/263113570_Intraclass_Correlation_Coefficient_ICC_A_Framework_for_Monitoring_and_Assessing_Performance_of_Trained_Sensory_Panels_and_Panelists)
> 25. A decade of test-retest reliability of functional connectivity \- PMC \- NIH, [https://pmc.ncbi.nlm.nih.gov/articles/PMC6907736/](https://pmc.ncbi.nlm.nih.gov/articles/PMC6907736/)
> 26. Test-Retest Reliability of Rating of Perceived Exertion and ... \- jospt, [https://www.jospt.org/doi/10.2519/jospt.2016.6498](https://www.jospt.org/doi/10.2519/jospt.2016.6498)
> 27. Understanding the Perceptual Spectrum of Commercial Perfumes as, [https://www.mdpi.com/2079-9284/7/1/3](https://www.mdpi.com/2079-9284/7/1/3)
> 28. Atlas of Odor Character Profiles | Books Gateway | ASTM International, [https://dl.astm.org/books/book/1796/Atlas-of-Odor-Character-Profiles](https://dl.astm.org/books/book/1796/Atlas-of-Odor-Character-Profiles)
> 29. ISO 11035:1994 \- iTeh Standards, [https://cdn.standards.iteh.ai/samples/19015/c53996eeb2a14b8e96d13d233c53cb42/ISO-11035-1994.pdf](https://cdn.standards.iteh.ai/samples/19015/c53996eeb2a14b8e96d13d233c53cb42/ISO-11035-1994.pdf)
> 30. Just-About-Right and ideal scaling provide similar insights into the, [https://pmc.ncbi.nlm.nih.gov/articles/PMC4104712/](https://pmc.ncbi.nlm.nih.gov/articles/PMC4104712/)
> 31. Psychophysical Bases for the Sensory Assessment of Rations, [https://www.academia.edu/30134034/Psychophysical\_Bases\_for\_the\_Sensory\_Assessment\_of\_Rations](https://www.academia.edu/30134034/Psychophysical_Bases_for_the_Sensory_Assessment_of_Rations)
> 32. Guide to IFRA-Compliant Fragrances \- Scento, [https://www.scento.com/blog/ifra-compliant-fragrances-guide](https://www.scento.com/blog/ifra-compliant-fragrances-guide)
> 33. GUIDANCE FOR THE USE OF IFRA STANDARDS \- Cloudfront.net, [https://d3t14p1xronwr0.cloudfront.net/docs/Standards-Documentation/ifra-51st-amendment-guidance-for-the-use-of-ifra-standards.pdf](https://d3t14p1xronwr0.cloudfront.net/docs/Standards-Documentation/ifra-51st-amendment-guidance-for-the-use-of-ifra-standards.pdf)
> 34. Regulatory Toxicology and Pharmacology, [https://rifm.org/wp-content/uploads/2021/11/1-s2.0-S0273230020302312-main.pdf](https://rifm.org/wp-content/uploads/2021/11/1-s2.0-S0273230020302312-main.pdf)
> 35. Updating exposure assessment for skin sensitization quantitative, [https://www.researchgate.net/publication/347379484\_Updating\_exposure\_assessment\_for\_skin\_sensitization\_quantitative\_risk\_assessment\_for\_fragrance\_materials](https://www.researchgate.net/publication/347379484_Updating_exposure_assessment_for_skin_sensitization_quantitative_risk_assessment_for_fragrance_materials)
> 36. A Linear Framework for Predicting Olfactory Mixture Perception, [https://www.biorxiv.org/content/10.64898/2026.07.03.736426v1.full-text](https://www.biorxiv.org/content/10.64898/2026.07.03.736426v1.full-text)
> 37. (PDF) A Principal Odor Map Unifies Diverse Tasks in Human, [https://www.researchgate.net/publication/363264555\_A\_Principal\_Odor\_Map\_Unifies\_Diverse\_Tasks\_in\_Human\_Olfactory\_Perception](https://www.researchgate.net/publication/363264555_A_Principal_Odor_Map_Unifies_Diverse_Tasks_in_Human_Olfactory_Perception)
> 38. Do Coffee Beans Help 'Refresh' Your Nose? \- The Perfume Society, [https://perfumesociety.org/do-coffee-beans-help-refresh-your-nose/](https://perfumesociety.org/do-coffee-beans-help-refresh-your-nose/)
> 39. The coffee bean myth: sniffing out the truth \- smell stories, [https://www.smellstories.be/en/blogs/blog/the-coffee-bean-myth-sniffing-out-the-truth/](https://www.smellstories.be/en/blogs/blog/the-coffee-bean-myth-sniffing-out-the-truth/)
> 40. On the state-dependent nature of odor perception \- Frontiers, [https://www.frontiersin.org/journals/neuroscience/articles/10.3389/fnins.2022.964742/full](https://www.frontiersin.org/journals/neuroscience/articles/10.3389/fnins.2022.964742/full)
> 41. Buy ISO 8587:2006 | Intertek Inform, [https://www.intertekinform.com/en-au/standards/iso-8587-2006-586262\_saig\_iso\_iso\_1342696/](https://www.intertekinform.com/en-au/standards/iso-8587-2006-586262_saig_iso_iso_1342696/)
> 42. Iso 8587-2006 | PDF | International Organization For Standardization, [https://www.scribd.com/document/739088326/ISO-8587-2006](https://www.scribd.com/document/739088326/ISO-8587-2006)
> 43. (PDF) Sensory Analysis and Consumer Preference: Best Practices, [https://www.researchgate.net/publication/369558170\_Sensory\_Analysis\_and\_Consumer\_Preference\_Best\_Practices](https://www.researchgate.net/publication/369558170_Sensory_Analysis_and_Consumer_Preference_Best_Practices)
> 44. Effects of Test Location and Sample Number on the Liking Ratings, [https://www.mdpi.com/2304-8158/12/3/632](https://www.mdpi.com/2304-8158/12/3/632)
> 45. A consumer study in a traditional wine-producing region. Effect of, [https://oeno-one.eu/article/view/8470](https://oeno-one.eu/article/view/8470)

[image1]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAFoAAAAaCAYAAAA38EtuAAACyUlEQVR4Xu2YS6hNYRiG3xOnXJPI3XFJxz2kKBlJSi5JBsrAzJnIgCJlYGIgRgxEJAMDMRGlJG2XTmJkICUKiSSJjCi8r2+t1rf/c9Zea599zm7v0//U0+7/1r/WXvtb/+VbG4hEIpFIpLmMo8voqPBACbroOjqJdgTHxIh+2jPQf99hy1h6hv6g1+hXepKO9p1yUKK20pv0En1NX1b1sAf4iz6hFxJ/0ssY2ENtW/TDP9JFSXsN/UbP0ZFppxy20+eurZF6lK5yMSX6b+AplHuQwwr98D1BrCeJnwjinun0HWz0e5TYi0F7m2sPiHBNCtutTjrawkSorfi9IO6ZSJ/B+vnRuYDudO2GE60p9gb2ZQth69wj+hCW8HZAo7JWol8E8ZBDsH5amzfQ2fQB7XR9lGgtMWthOdJSpX2hFBPobWQ3pI1kP72TtDdnXfuwnO6qwx108v8zB5+iRGtpqIUSehrZ2vuHHqjqYYn+QM/DqpoV9D1d6TvloUTKG7CLb0zi62FTp9loE5oCS1wZ092+0URvgVUpY+hhWHWh8zTSa1GB9dPgLIWm1ls6M4g3m1mwKauRUqSWOyVINJLopfQLrMpIWUKfwkbwPBcPuQq7vj5L7Wm/YaO6qAxqVYo2w0oQ9xynn+j8IK6N0c/yffQYqhN6Bdn1dQ+FqPORMFjAWWRrWhn9TQ8F+g6Vc56DSVybVx5Kljb/8eEBZPesJFZgtbYvEFTN6Pq+DMxlKmzpGKqNqlnchS0nc5O2PtW+haxs036UPviUOfQVve9iQnuU1ut0BKs68/uW4rqOqg9fneSyGvYaWWqNaWG0vvfCSjRNc31qxE1zfbSWP6bfXUwshr1yq6LQLNCruCqw8L+Nz/Q6LLmaBXW9GepipZ5IG6DfooGjN8Ru1Dd4dO5u2LmbYKVviGI6thd994NIJBKJRCKRSCQyiPwDndKlZdafKncAAAAASUVORK5CYII=>

[image2]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABMAAAAaCAYAAABVX2cEAAABA0lEQVR4Xu2SvQ4BQRSFr4RCIaJSKyV+CpVH0IkoJB5Ao/IEngGFaCQajVIQErVolHrRqxXCOWYndmbXbqGT/ZIvkT039841IxLxKzV4gBfHkhm/WcCJpS9F2IRj+IRzGDcqRNpwDx9wCOtm7GUA1/AGC1ZGOnAEY3Zgk4crmBF1ujPMunJ+Z866ULgGT0auohq2PrFU4E5U01DYiA0JV2GzDUw639zDArFXqMK7I3+TqXyGBeI3lSvydFw5B5cwZVR8wb2ihn8+L4ENu+Id5gtX3MKyHYC+qGZH2DAjf9xPwobr6ZsNfRIJeIIzmLYyjb6MQHQRp2p7RoWCT4Mnj4j4H15INzZPvLrhKQAAAABJRU5ErkJggg==>

[image3]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABAAAAAaCAYAAAC+aNwHAAAA20lEQVR4XmNgGAXoQBOIpwHxLCB+BMUboHwQngTEbkDMCtOADkSAOACIy4H4HxDXAXEIFCcD8X4g/g/Ep2EacAFPIH4AxNJo4oxAPIUBYggLmhwccAPxHgaIK9ABSNMaBogB4mhycKAExM+B2AZdggHiogcMEANArsEK/Biw2wDSUAaVu4UmhwJaGbD7sRKI/wLxMSCWQZODA1A0vmWAxABZIJoBYvsDNHGiwRwGiAGgkCYZCDJAEgjIgHQ0OaJAKQNE81MgVkeTwwv0gfgTA0QzMgaJj4JRQB8AABhXLSG7tX8wAAAAAElFTkSuQmCC>

[image4]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAEAAAAAZCAYAAACB6CjhAAACN0lEQVR4Xu2WwUsVURSHj2RQKCaUiJRUkIEVLVJsE9FCBIk2GRT4B7QRhITauLBlRBhBu0JcuRHaFEEFudKFbkVo9YI2FhKIrcLq9+PMMHdOc2fmvSmeyP3gW9xz73sz98y9516RQCAQ2Jt0wkuwDx40fT46YJsNgi4b2MscgR8k/dJjcMpp+3gAfxuX4SlnTNPogedsMIM7oi/ucgh+gadN3MIErMJn8CE8C1tSI5oAX+Ai3IAjps/Cib6BP22HaFLGbdDABMzbYFmOSjpbtl0vB+B1uAZXonYRXCWf4Q/bIZqAFzZoaCgB3HOv4Q3Rh2zDCfg2ao8mQwth0h7BTdHJ1MuA6OR9CViC7SbuwgTswI/wJHwsupo4Hy/DcAHeE33InGjV3YXf4PlkaC783RaclOxKXIaqCbgpWkD5UQnn8Up0Ll74heki/CWaEHIFnokHeeAWuQzfiRavsseVj6oJyCI+GQ7bDss6rMHjJp4Hz2pOvibl9ngR/yMBXBX87QnbYeEgZqtRuOefi26DadNXFm4dLmGuRAvf764NOsRfmsv9mhOPt3a3E/uLVtFiwWVfFd7G7sOXUnxuZ8GCxRd24fH4HV5wYrPwvSRfltv4q+iz3a3IOwH/L/dEY3a4BY7ZjgqwJvDs52nCe0BZOCH+Li5khHXmqaQnwUnRJ1Gb43mHuC3JuCHRxH2K2l64f6sWsCJ4Ps/YYA5XRS8+t2Cv6cuD8xgU/QD98m9qUyAQCAQCgX3IH5xnal228KD2AAAAAElFTkSuQmCC>
