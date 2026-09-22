# Preference-Prediction Data Capture Assessment

> **Status**: Draft for product-owner review
> **Version**: 1.4
> **Updated**: 2026-09-21
> **Perspective**: Future data scientist responsible for preference-model development
> **Companions**: [ML Structure Review](ml-structure-review-2026-09.md),
> [Data Model Gap Analysis](data-model-gap-analysis.md),
> [ML Decisions](ml-decisions-2026-09.md), and
> [Perfume-Purchasing Research Validation](../research/perfume-purchasing-research-validation.md)
> **Purpose**: Determine whether the current system captures the perfume, evaluator, encounter,
> context, and outcome data required to predict smell liking, wear intent, and purchase intent by
> setting and season. This is advisory planning input and does not change `PROJECT-PLAN.md`, an
> ADR, the calibration protocol, or an approved milestone.

## 1. Executive verdict

**No. The system captures a strong controlled baseline core, but it does not yet capture all of
the data needed for the stated prediction product.**

The current implementation is well positioned for an initial model of intrinsic fragrance liking:
it preserves exact fragrance-version identity, blind and holdout roles, repeated presentations,
typed liking and perceptual responses, timepoint/stage, immutable recommendation impressions, and
prospective prediction snapshots. These are difficult foundations to retrofit and are genuine
strengths.

The most consequential missing information is not another smell scale. It is the information that
separates the three intended outcomes:

- **Smell liking** needs controlled exposure, detection, intrinsic response, perceived attributes,
  and normalized fragrance features.
- **Would wear** needs actual or hypothetical setting, season, climate, occasion, desired effect,
  dose, application, and later real wear behavior.
- **Would buy** needs wear intent plus price, currency, size/format, availability, ownership state,
  and subsequent purchase behavior. A context-free `would_buy` score cannot separate dislike from
  “I like it but not at this price or bottle size.”

Today, season/setting is absent, ordinary reviews are too sparse, physical exposure metadata is
mostly untyped, perfume vocabularies are not normalized enough for stable ML features, and real
wear/purchase events are not captured outside narrow recommendation feedback. Those gaps must be
closed before the first baseline is treated as the permanent foundation for contextual ML.

The correct goal is not to collect every imaginable variable. It is to establish a small,
versioned, hypothesis-driven data contract that can distinguish perfume effects, evaluator effects,
exposure effects, context effects, and economic constraints without exhausting the evaluator.

## 2. Prediction contract implied by the product goal

The three outcomes must be modeled and evaluated separately. They are related, not interchangeable.

| Target | Recommended operational label | Required conditioning data | Primary evaluation |
| :--- | :--- | :--- | :--- |
| Smell liking | Locked pre-reveal `liking` on its original 0-10 scale, with stage/timepoint declared | Evaluator, exact fragrance version, controlled perfume features, exposure method, timepoint, detection, familiarity | MAE and rank correlation against prospectively frozen holdouts, bounded by repeat reliability |
| Would wear | Scenario-specific wear likelihood plus later actual wear/rewear events | Everything above plus season, climate, occasion, desired effect, indoor/outdoor, activity/formality, dose/application, performance, and ownership/sample access | Ranking/classification metrics with evaluator-grouped splits and actual-wear follow-up |
| Would buy | Intent at a declared offer plus later purchase-funnel events | Everything above plus format, size, price, currency, availability, ownership, budget/price acceptability, and purchase outcome | Ranking/classification metrics; report intent and observed purchase separately |

“Would wear this at all?” and “would wear this to work in summer” are different labels. Likewise,
“would buy a 2 ml sample for $8” and “would buy a 100 ml bottle for $250” are different decisions.
The model should return an ordinal score, rank, or broad class such as unlikely/possible/likely; it
does not need to claim a calibrated percentage probability.

### 2.1 Unit of analysis

The core training unit should be one evaluator’s observation of one exact fragrance version under
one declared exposure and context. A later wear or purchase event may link to that observation but
must remain a separate event with its own timestamp and context.

### 2.2 Do not collapse these distinctions

- Fragrance concept versus concentration/formulation/version
- Published note/accord data versus what the evaluator perceived
- Descriptive intensity versus whether that attribute helped or hurt liking
- Blotter response versus skin response
- First exposure versus familiar/owned fragrance
- Hypothetical suitability versus an actual wear
- Generic wear intent versus scenario-specific wear intent
- Purchase intent versus an observed purchase
- Intrinsic preference versus availability, price, or format constraints
- Missing/not asked versus a true zero or negative response

## 3. Current readiness by data layer

| Layer | Current status | Assessment |
| :--- | :--- | :--- |
| Exact perfume-version identity | Partial/strong | Name, brand, concentration, version key, year, and source identifiers exist; identity verification and physical sample facts are incomplete or untyped |
| Published perfume features | Partial | Notes, positions, accords, family/subfamily, perfumer, and provenance exist, but aliases, accord vocabulary, rank, taxonomy versioning, and source-quality distinctions remain incomplete |
| Controlled evaluator response | Strong core | Detection, liking, sensory dimensions, wear/buy intent, performance, confidence, perceived notes, and comments are typed; protocol revisions are not all implemented |
| Ordinary encounter | Weak for ML | Only 1-5 rating, notes, longevity, sillage, time, reviewer, and worn-by subject are captured |
| Season/setting/context | Missing | Session has an unused JSON `context`; no first-class season, climate, occasion, desired effect, or actual-wear entity exists |
| Exposure conditions | Partial/weak | Stage, elapsed minutes, order, and locks exist; application time, dose/sprays, site, container, sample/batch provenance, and actual test day are missing |
| Wear behavior | Missing generally | Recommendation feedback can record boolean would-wear, but actual wore/rewore events are not first-class |
| Purchase behavior | Missing generally | Recommendation feedback can record boolean would-buy and sampling state, but price-conditioned intent, format, acquisition, repurchase, finish, sell, or give-away events are absent |
| Pairwise/rank preference | Missing | Planned session ranking and `PairwiseComparison` are not implemented |
| Data eligibility/leakage | Partial/strong design | Holdouts and repeats are protected in the calibration path; evidence-row eligibility and the planned database training view are not implemented |
| Prospective ML evidence | Partial/strong design | Prediction snapshots, manifests, a dataset skeleton, scorer registry, repeat reliability, and scorecards exist; no learned model has been fit |
| Fragella candidate discovery | Planned, not implemented | Current client supports search/usage for reference lookup only; `/match`, `/similar`, provider-term mapping, transient candidate scoring, and full run snapshots remain future work |

## 4. Perfume-level datapoints

### 4.1 Captured and usable now

- Stable local fragrance UUID
- Name and brand string
- Concentration
- Version/formulation key
- Launch year
- Marketed gender target
- Primary family and subfamily strings
- Intensity label
- Published notes with top/heart/base/flat position
- Published accords with numeric intensity
- Perfumer attribution with source URL
- Catalog source, external identifier, and source URL where available
- Soft deletion and created/updated timestamps
- Feature-space version in frozen model vectors

### 4.2 Captured but not yet reliable enough as learned features

| Datapoint | Problem | Required remediation |
| :--- | :--- | :--- |
| Brand | Free string across ingestion paths | Stable brand entity/alias mapping; preserve original source label |
| Notes | Case-sensitive names with no alias/version layer | Canonical note IDs, aliases, hierarchy/group, mapping version, and unresolved raw label |
| Note position | Position exists, source order/rank does not | Add rank and controlled position semantics |
| Accords | Free-string key | Controlled accord vocabulary and aliases |
| Accord intensity | Measured and importer-derived positional values share one field | Add intensity source/method and exclude synthetic values by default |
| Family/subfamily | One unversioned mixed-source taxonomy; subfamily can be empty or duplicate family | Versioned classification system and mapping; exclude unreliable subfamily until then |
| Perfumer | Structurally sound but the trusted write path is unresolved | Manufacturer/manual provenance path, confidence, and explicit scoring decision |
| Source provenance | Mostly fragrance-level | Snapshot revision, retrieval time, content hash, parser version, license/permission evidence, verification actor, and per-feature source where necessary |

### 4.3 Missing perfume and physical-sample data

The following are plausible confounders or required commercial inputs. They should be added only
where the source is reliable and there is a concrete consumer.

**Required before contextual prediction:**

- Physical sample source type: manufacturer sample, retailer sample, decant, owned bottle, unknown
- Container/delivery format: atomizer, dab vial, rollerball, bottle
- Batch/lot code when known
- Sample acquisition/decant/open date when known
- Concentration and identity verification status
- Sample provenance and authenticity/verification evidence
- Application method and dose/spray count at the encounter level

**Required before meaningful purchase prediction:**

- Offer timestamp
- Currency
- Price and size/volume, allowing derived price per ml
- Purchase format: sample, decant, travel, bottle
- Availability and region/market
- Discounted versus regular price where known

**Useful later, not baseline blockers:**

- Manufacturer-published longevity/projection claims, kept separate from evaluator observations
- Discontinued/limited-availability state
- Version-specific reformulation or batch evidence
- Structured chemical/ingredient or learned embedding features, only if a licensed source and a
  concrete modeling need emerge

Price, availability, and manufacturer claims change over time; they must be timestamped snapshots,
not timeless fragrance attributes.

## 5. Evaluator and review-level datapoints

### 5.1 Controlled baseline data captured now

The controlled `Observation` is a credible starting record:

- Reviewer and recorder provenance through enrollment/presentation joins
- Blind sample code, session, order, and exact fragrance membership
- Blotter or skin stage
- Pre/post-reveal phase
- Elapsed minutes
- Detection and perceived intensity
- Overall liking
- Opening and drydown liking
- Would-wear and would-buy 0-10 responses
- Artistic appreciation
- Projection and longevity minutes
- Sweetness, freshness, density, dryness, clean/soapy, earthy/rooty, bodily/animalic, and discomfort
- Confidence and numeric familiarity
- Free-text perceived notes, likes, dislikes, associations, and comments
- Append-only submission time and recorder identity

### 5.2 Ordinary encounters are currently under-specified

An ordinary review captures rating, free text, optional longevity and sillage, encounter time,
reviewer, recorder, and whether the fragrance was worn by somebody else. It does **not** capture:

- smell liking on the controlled scale;
- would-wear or scenario-specific wear likelihood;
- purchase intent or offer details;
- familiarity/ownership state;
- season, weather, occasion, desired effect, or setting;
- application method, sprays/dose, body location, or sample/container;
- detection, confidence, perceived dimensions, or controlled preference drivers;
- whether the fragrance was blind or identified at evaluation time;
- scrub-off, actual duration, or later rewear/purchase behavior;
- an evidence-quality/training-eligibility status.

Ordinary encounters therefore cannot yet become the high-volume contextual training stream the
third milestone requires.

### 5.3 Missing evaluator-level information

`Reviewer` currently stores only an ID, name, timestamps, and deletion state. That is appropriate
for a small initial system: demographic profiling should not be added simply because ML can consume
it. The minimum useful evaluator information is behavioral and time-varying, not demographic:

- familiarity and ownership state per fragrance at the time of an encounter;
- response-level `not_detected`/`unable_to_evaluate` states and, only when operationally necessary,
  an optional consented self-reported olfactory limitation, not a molecular or genetic profile;
- preference evidence accumulated from observations, never a manually overwritten “taste profile”;
- stable evaluator identity linked to authorization without conflating the recorder with the palate;
- optional stated constraints such as scent-free workplace or sensitivity, with consent and a
  documented product use.

Age, gender, medical information, and other sensitive traits should not be collected without a
specific hypothesis, consent, access controls, and proof that the expected benefit justifies the
privacy cost. Four household users do not provide enough data to learn safe demographic effects.

## 6. Season, setting, and exposure context

This is the largest gap relative to the stated goal. `CalibrationSession.context` is created as an
empty JSON object and no schema, API, or UI contract writes a meaningful context.

### 6.1 Actual wear context

For an observed skin wear, capture a compact structured record:

- season as the user experienced it;
- local date and time of application;
- climate/temperature band and optional numeric temperature;
- humidity band and optional numeric humidity;
- indoor/outdoor/mixed;
- occasion and formality;
- activity level;
- desired effect or role: professional, comforting, energetic, romantic, understated, and so on;
- social setting when useful: alone, close contact, group/crowd;
- application site, delivery method, and dose/spray count;
- clothing versus skin application;
- elapsed-time observations;
- expectation versus actual performance;
- would wear again in the same context;
- contextual comfort/problems, including scrub-off and time to scrub.

Weather values may later be enriched from time and location, but the system should store the raw
user-selected band and the external source/time of any enrichment. Location should be as coarse as
the product needs; precise location is unnecessary for this use case.

### 6.2 Hypothetical scenario suitability

Keep this distinct from actual wear. A concise hypothetical record can hold:

- one or more seasons;
- one or more occasions/settings;
- desired effect;
- fit/suitability score;
- wear-likelihood score;
- confidence;
- whether the judgment followed blotter, skin, or known ownership experience.

Do not ask for the Cartesian product of every season and occasion after every sample. Collect a
small number of likely and unlikely contexts, or ask scenario questions only when the candidate
strategy needs them. Otherwise respondent fatigue and sparse cells will overwhelm the signal.

## 7. Preference drivers and perceived features

The system records how sweet, fresh, dense, dry, clean, earthy, or animalic a perfume seemed, but
not whether each perceived property improved or harmed the evaluator’s response. A high sweetness
score plus low liking does not prove that sweetness caused the dislike.

Before using these dimensions as individual preference explanations, add a sparse directional
follow-up such as “which attributes pushed your rating up or down?” with at most two or three
choices. Preserve:

- dimension/concept;
- positive or negative direction;
- optional strength;
- stage/timepoint;
- confidence;
- raw free-text reason.

Perceived notes also need normalized links to the catalog note vocabulary with an unresolved raw
label fallback. Never replace a user’s original text with a model-extracted label; store derived
extractions separately with model/version/provenance.

## 8. Behavioral outcomes

Intent labels are useful but should be checked against behavior. Add a general append-only event
stream independent of whether the perfume was recommended:

- sampled;
- wore and rewore;
- wishlisted and removed from wishlist;
- bought sample, decant, travel, or bottle;
- finished sample or bottle;
- repurchased;
- returned, sold, gave away, or gifted;
- declined because of price, availability, performance, redundancy, or another stated reason.

Each event should carry evaluator, exact fragrance version, timestamp, source observation or
recommendation when applicable, format/size/price where relevant, setting where relevant, and
recorder provenance. A purchase is not proof of liking, and no purchase is not proof of dislike;
the reason and offer conditions matter.

## 9. Fragella milestone readiness

The current implementation does **not** yet implement the user’s second milestone.

Current behavior:

- `FragellaClient` supports `/fragrances` search and `/usage`.
- Search results are intentionally limited to identity-disambiguation fields.
- Lookup attempts are retained for operator reference but are not adopted into the catalog.
- The parser intentionally ignores live-response fields such as price, main accords, season
  ranking, and occasion ranking.

Planned but absent:

- `/fragrances/match` and `/fragrances/similar` client methods;
- provider-term mapping from local notes/accords to Fragella’s canonical vocabulary;
- live verification of match parameter semantics and failures;
- a transient fragrance feature object that can be scored without violating the non-storage rule;
- immutable request/response snapshots adequate to reproduce candidate retrieval;
- candidate-source and source-quality labels;
- scoring and merging local and Fragella candidates under one versioned strategy;
- graceful behavior for quota exhaustion and incomplete candidate features.

Fragella should supply **candidates**, not ground-truth liking labels. Its similarity or ordering
must not be presented as predicted preference. Candidate retrieval and local preference scoring
should remain separate, and evaluation should compare candidate strategies prospectively on the
same downstream outcomes.

Fragella’s season/occasion rankings may eventually be useful retrieval inputs or external
covariates, but they are not substitutes for this household’s context-specific labels. They also
require explicit source semantics, provenance, and permission handling before use.

## 10. Modeling implications

### 10.1 Sample size constrains the first learned model

Thirty-three distinct baseline fragrances per evaluator cannot support a high-dimensional
individual model over hundreds or thousands of raw note labels, much less arbitrary interactions
between notes, season, occasion, and person. The first model should use:

- a versioned low-dimensional fragrance basis;
- partial pooling across evaluators;
- strong regularization/shrinkage;
- separate targets for liking, wear, and buy;
- evaluator-grouped or time-aware validation;
- frozen final holdouts;
- hidden repeats to estimate label reliability;
- simple baselines that are difficult to beat accidentally.

Tree ensembles, per-person note interaction models, collaborative filtering over four users, and
large embeddings learned from this project’s own data are not justified by the initial sample.

### 10.2 Context multiplies sparsity

Season and setting should enter as shared, low-cardinality effects with carefully selected
interactions, not as a separate model for every context. Start with additive evaluator, fragrance,
season/climate, and occasion effects, then introduce only predeclared interactions supported by
enough observations.

### 10.3 Avoid target leakage

- Do not use post-reveal published identity as a feature for predictions frozen before reveal
  unless that same feature would be available for every future candidate.
- Do not train on holdouts, hidden-repeat role, manager selection rationale, later recommendation
  response, or later behavioral outcomes when predicting an earlier state.
- Do not randomly split repeated encounters from the same evaluator/fragrance across train and
  test; use evaluator/fragrance-aware grouping and prospective time order.
- Keep features available at recommendation time distinct from post-sampling explanatory features.
- Version every feature transformation, vocabulary, source snapshot, model, and decision rule.

## 11. Minimum data contract by milestone

### Milestone 1: collect the baseline

Before the first baseline observation, implement or verify:

1. Exact version and physical-sample identity, including typed provenance.
2. Normalized/versioned note and accord vocabulary for the 43 baseline/holdout versions.
3. Actual session date and presentation/application timestamp.
4. Familiarity as a categorical state rather than an unanchored integer.
5. Explicit detection, liking, stage/timepoint, confidence, discomfort, and scrub-off behavior.
6. Session ranking/pairwise evidence as already decided by the protocol.
7. Training eligibility and exclusion reason on evidence rows plus one authoritative training view.
8. A written missingness contract: not asked, skipped, unable to assess, non-detected, and true zero.
9. Frozen protocol, feature schema, source manifest, and split declaration.
10. If season/setting prediction is an intended first-generation output, at least a minimal
    actual/hypothetical context contract must land **before** baseline collection. Schema-only
    lookups do not collect labels.

The current plan’s R6-R8 work covers much of this, but those sprints are not implemented in the
reviewed code. The baseline should not start on the assumption that planned fields already exist.

### Milestone 2: retrieve candidates from Fragella

Add:

1. Versioned candidate strategy and selection objective.
2. Provider-term mappings with verification provenance.
3. Live `/match` and `/similar` wrappers with quota/error behavior.
4. Frozen raw request/response snapshot and API/schema version when available.
5. Transient candidate feature representation and explicit missing-feature handling.
6. Candidate-source/quality label and identity deduplication against the local catalog.
7. Local scoring of external candidates; vendor order kept only as retrieval metadata.
8. Prospective recommendation impression and follow-up linkage.
9. Canonical local identity creation from an approved source if a candidate is acquired, never a
   silent copy of the retained Fragella response.

### Milestone 3: predict over the project’s catalog

Add or complete:

1. Versioned, normalized local feature snapshots.
2. Scenario suitability and actual wear context.
3. General behavioral events and ownership/collection state.
4. Price/format/availability snapshots for purchase modeling.
5. Preference-driver and normalized perceived-note data.
6. Population priors and partially pooled learned model.
7. Separate prospective scorecards for liking, would-wear, and would-buy.
8. Drift monitoring for evaluator preferences, catalog revisions, and changing prices/availability.
9. Coverage, diversity, and exploration metrics separate from predictive quality.

## 12. Priority recommendations

### P0: before baseline collection

- Complete R6 vocabulary normalization and feature-space versioning.
- Complete R7 session timing, sample provenance, familiarity, ranking, scrub-off, and context
  capture; require the UI to write the fields rather than creating empty context objects.
- Complete R8 evidence-level eligibility, frozen source/feature provenance, and authoritative
  training view.
- Decide whether minimal season/setting judgments belong in this baseline. If yes, define them now;
  they cannot be reconstructed later.
- Remove `would_buy` from the blind core as the approved protocol requires, or explicitly reconcile
  the current schema/UI, which still offers a 0-10 skin-stage purchase question.
- Freeze a data dictionary with field meaning, scale anchors, allowed missingness, collection stage,
  and leakage eligibility.

### P1: before contextual candidate evaluation

- Implement actual wear context and hypothetical scenario suitability as distinct records.
- Expand ordinary encounters into a lightweight contextual journal without reproducing the full
  calibration form.
- Add general behavioral events, ownership state, and offer-conditioned purchase intent.
- Normalize perceived notes. The companion recommendation to add sparse positive/negative
  preference-driver features is withdrawn per
  `product-research-remediation-implementation-plan.md` DEC-04: it would conflict with ADR-016
  (per-dimension preference capture), which is `Proposed, requires maintainer decision, not
  implemented` and explicitly should not land before F1. Any future preference-driver work follows
  ADR-016's own resolution process, not this list.
- Implement the full Fragella candidate path and immutable retrieval snapshots.

### P2: before claiming model improvement

- Fit the first partially pooled, regularized model only after the P0 feature basis is frozen.
- Compare against `affinity-v2`, simple popularity/profile baselines, and repeat reliability.
- Freeze predictions before outcomes and evaluate all candidate strategies over the same eligible
  rows.
- Report counts, uncertainty, missingness, evaluator-level results, and context coverage.
- Treat “interesting,” sampling conversion, liking, wear, and purchase as separate product metrics.

## 13. Additional changes that should precede baseline collection

The preceding recommendations cover the major feature domains. A second pass identified several
smaller data-contract changes that are cheap now and difficult or impossible to reconstruct after
the first observation. Most concern measurement meaning, time, lineage, and invalid-data handling
rather than additional questions for the evaluator.

### 13.1 Create a versioned, machine-readable data dictionary

No dedicated codebook or schema registry exists today. Python types, SQLAlchemy models, frontend
labels, ADR prose, and generated OpenAPI each describe part of the contract, but none is the one
place a data scientist can use to interpret a historical export.

Create a committed YAML, JSON, or CSV dictionary with one row/object per collected or derived field:

- stable field code and display/question text;
- entity/table and source column;
- semantic definition and unit;
- type, allowed values, bounds, and ordering;
- scale anchors, including the midpoint;
- collection workflow, stage, and timepoint;
- required/optional condition;
- missing-value meanings and non-detection behavior;
- raw, derived, inferred, or external-source classification;
- candidate feature, target, quality flag, identifier, or prohibited/leakage field;
- earliest time the value becomes available for prediction;
- privacy/sensitivity classification;
- first and last instrument/schema versions in which it is valid;
- owning ADR and transformation/version when derived.

Generate validation tests or documentation from this file where practical. Do not hand-maintain
multiple competing dictionaries.

### 13.2 Version the measurement instrument, not only the database schema

`Program.version` can identify a controlled protocol, but the exact question wording, anchors,
display order, requiredness, and skip logic are not frozen data. The frontend scale definitions are
code constants. A later wording or midpoint change could make two numerically identical responses
non-equivalent while the database rows look identical.

Before collection:

- assign an immutable questionnaire/instrument version to every activated program;
- bind it to the complete ordered field definition and anchor set in the data dictionary;
- include it in every export and checkpoint through the program join;
- record a separate ordinary-journal instrument version for noncontrolled encounters;
- require a version bump when wording, anchors, requiredness, timing, or skip logic changes;
- verify that the approved 0/5/10 and 0/5 verbal anchors are actually rendered and accessible.

The instrument version may reuse `Program.version` if activation truly freezes the whole response
contract. A second redundant column is unnecessary if that invariant is enforced and exported.

### 13.3 Store event time, local interpretation, and observation time separately

Naive UTC timestamps preserve ordering but cannot reconstruct local season, calendar day, or time of
day. `created_at` also answers when the server received a row, not necessarily when a perfume was
applied or assessed.

Store or derive explicitly:

- session start and end;
- application/presentation time;
- observation time;
- server receipt time;
- IANA timezone or, at minimum, UTC offset and evaluator-local date;
- elapsed time calculated from application and observation times, while preserving the submitted
  elapsed value for audit;
- correction time separately from original encounter time.

This matters for season, circadian effects, same-day spacing, and interval-censored longevity. It
also lets validation identify impossible or mistimed observations instead of silently accepting
them.

### 13.4 Represent missingness and evaluability explicitly

NULL currently combines several states. Questionnaire version can establish that a field was not
asked, but it cannot distinguish skipped, forgot, unable to assess, interrupted, technical failure,
and not applicable.

Avoid adding a reason column beside every optional scale. Instead add a compact response-status
contract for each required timepoint or question group:

- `completed`;
- `not_detected`;
- `skipped_optional`;
- `unable_to_assess`;
- `interrupted`;
- `not_asked_by_instrument`;
- `invalidated`;
- `technical_failure`.

Allow an optional reason/detail and retain field-level status only where a primary outcome needs it.
Never convert one of these states to a numerical zero during export.

### 13.5 Freeze observation-time catalog and sample features

An observation currently points to a mutable catalog row. If notes, family, concentration,
classification, or provenance are corrected later, a live join rewrites the apparent features of
past evidence. Model checkpoints help later, but the baseline should have an immutable source and
feature snapshot from program activation onward.

Before collection:

- freeze the exact identity, source revision, vocabulary/taxonomy versions, published features,
  and physical-sample evidence used for the active program;
- assign each membership/presentation a `feature_snapshot_id` or equivalent immutable reference;
- distinguish later catalog correction from the historical facts shown to or available to the
  experiment;
- preserve raw source labels alongside normalized feature IDs;
- include the snapshot digest in dataset exports and prediction checkpoints.

This refines planned R8 `FeatureSnapshot` work and should be treated as baseline provenance, not
only as a future-model artifact.

### 13.6 Persist protocol execution and deviation evidence

The approved protocol now includes balanced order, maximum daily load, spacing, clean-air breaks,
session context, detected-only ranking, and fixed skin timepoints. Actual order is stored, but the
assignment method and deviations are not represented adequately.

Record:

- randomization/balancing algorithm and version;
- intended and actual position/order;
- assignment seed or immutable assignment digest when reproducibility permits;
- session start/end and clean-air interval compliance;
- whether the session exceeded daily load or minimum spacing;
- sample substitution, spill, mislabeled-code suspicion, competing odor, interruption, or recorder
  assistance;
- whether a field was collected outside its planned time window;
- structured severity and an explicit include/exclude/review disposition.

Do not encode every deviation by deleting or overwriting an observation. Keep the raw evidence and
let a versioned eligibility decision determine whether it enters a particular analysis.

### 13.7 Separate data quality from training eligibility

Training eligibility answers whether a row may be used for a particular model. Data quality
describes what happened. A valid but unusual row may be eligible; a protocol-deviating row may be
useful for sensitivity analysis but excluded from the primary model.

Add structured quality flags or a child event table with:

- stable code;
- severity;
- source: automatic validation, evaluator, recorder, or manager;
- recorded time and actor;
- explanation;
- resolution/disposition;
- rule/version that converted the flags into training eligibility.

The frozen dataset should retain both the raw flags and the eligibility decision used for that run.

### 13.8 Preserve correction and supersession history

Controlled observations are append-only, but ordinary evaluations can be patched in place. Once
ordinary encounters become ML evidence, in-place correction erases the value a prior dataset or
prediction actually used.

Before ordinary data is used for learning:

- replace analytical in-place mutation with an append-only revision or `supersedes_id` pattern;
- preserve original and corrected values, reason, actor, and timestamps;
- let exports select the latest valid revision as of a declared cutoff;
- keep soft deletion as an auditable exclusion rather than physical disappearance;
- ensure frozen model inputs continue to resolve to the exact revision used.

The UI may still present correction as “Edit”; the storage semantics should preserve history.

### 13.9 Define outcome opportunity, maturity, and censoring

The absence of a wear or purchase event is not automatically a negative outcome. A user may never
have obtained a sample, may not have encountered the relevant season, or may not have reached the
follow-up date.

For prospective wear/buy evaluation, define and store:

- when the opportunity window opens;
- follow-up due date and closure date;
- whether the evaluator acquired or had access to the fragrance;
- whether the relevant season/setting occurred;
- pending, observed-positive, observed-negative, unavailable, and censored states;
- reason for unavailability or censoring;
- offer details in force during a purchase decision.

Metrics must use mature outcomes and report censoring/coverage separately. Missing events should
never be silently labeled `false`.

### 13.10 Make ownership and exposure history time-varying

The approved familiarity change correctly separates recognition from prior ownership/exposure, but
a single current ownership flag will still rewrite history. Use timestamped state transitions or
behavioral events so an export can answer what the evaluator knew and owned **at prediction time**.

At minimum preserve:

- recognition state at encounter;
- prior sampled/worn/owned state at encounter;
- acquisition and disposition events;
- current collection state derived as of a timestamp, not stored as the only historical truth.

### 13.11 Establish consent, retention, and research-export rules

Session context may include illness, allergy symptoms, sensitivities, or optional hormonal context.
Those fields are more sensitive than a perfume rating. Before collecting them, define:

- consent text/version and consent timestamp;
- which context fields are optional and explicitly refusable;
- who can view raw context versus derived quality flags;
- export de-identification/pseudonymization rules;
- retention and deletion policy;
- withdrawal behavior for future training and for already frozen aggregate reports;
- backup and audit-log implications of a deletion request.

Do not make a sensitive optional field a prerequisite for completing baseline evaluation.

### 13.12 Define a reproducible dataset-release manifest

In addition to model checkpoints, every analytical export should produce a small immutable manifest:

- dataset release ID and creation time;
- code commit and migration head;
- program/instrument versions;
- source, feature-space, alias, and taxonomy versions/digests;
- eligibility and target-selection rule versions;
- cutoff time and outcome-maturity rule;
- included evaluator/fragrance/row counts by workflow, split, and target;
- exclusions and missingness counts by reason;
- content hash of the exported rows and ordered columns;
- query or builder version used to construct it.

This makes a notebook result reproducible without turning the application database into a feature
store.

### 13.13 Pre-baseline decision table

| Change | Timing | Why it cannot wait |
| :--- | :--- | :--- |
| Machine-readable dictionary and instrument version | Before first response | Historical numeric answers cannot recover changed wording or anchors |
| Local/event/application/observation timestamps | Before first session | Local season, time of day, spacing, and elapsed time cannot be reconstructed reliably |
| Response status and missingness meanings | Before first response | NULL cannot reveal why a value is absent |
| Program feature/sample snapshot | Before activation | Later catalog corrections otherwise rewrite past feature meaning |
| Randomization and deviation records | Before session generation | Intended balance and actual protocol adherence cannot be inferred afterward |
| Quality flags separate from eligibility | Before first exception | Deleted/excluded rows lose useful sensitivity-analysis evidence |
| Correction/supersession semantics | Before ordinary encounters train models | In-place edits erase what earlier analyses consumed |
| Follow-up windows and censoring | Before first prospective wear/buy task | A missing event cannot later be classified honestly |
| Time-varying ownership/exposure | Before first acquisition/state change | Current state cannot reconstruct state at prediction time |
| Consent/retention/export contract | Before sensitive context collection | Consent cannot be assumed retroactively |
| Dataset-release manifest | Define before collection; implement before first export | Ensures the first analysis is reproducible rather than a one-off query |

These changes should be folded into R6-R8 or a narrow pre-baseline data-contract sprint. They do
not justify widening the baseline questionnaire indiscriminately. Most add metadata, constraints,
or audit records around observations already being collected.

## 14. Acceptance criteria for data readiness

The dataset is ready for the first learned model only when all of the following are true:

- Every training row resolves to one evaluator, exact fragrance version, source observation,
  timestamp, workflow, target, scale, split, and eligibility reason.
- Every fragrance feature resolves through a versioned vocabulary and source snapshot.
- Published, perceived, derived, and inferred values are distinguishable.
- Holdouts and repeats cannot enter training through either application code or a direct database
  export.
- Controlled observations record real session/application timing and physical-sample provenance.
- Season/setting labels are present for the model that claims to condition on them.
- Wear and purchase targets have explicit denominators and are not inferred from missing events.
- Purchase intent is tied to an offer or explicitly labeled as format/price-unspecified.
- Corrections and behavioral changes remain append-only or fully audited.
- A frozen dataset can be replayed into the same feature matrix after catalog data changes.
- A baseline model, metric set, grouping/split policy, and adoption rule are declared before final
  holdout outcomes are opened.

## 15. Effect of the perfume-purchasing research review

The two LLM-generated research reports were audited claim by claim before changing this assessment.
The [validation ledger](../research/perfume-purchasing-research-validation.md) found genuine primary
research mixed with commercial claims, weak surveys, adjacent-domain experiments, citation errors,
and substantial overstatement.

Validated evidence strengthens a limited part of the existing plan:

- keep detection/non-detection, familiarity, perceived intensity, and liking separate;
- preserve optional odor-evoked associations and desired emotional effect;
- distinguish blotter from skin evidence and record application, dose, timepoint, and elapsed time;
- treat performance as time-varying and keep it separate from intrinsic liking;
- record sample access/acquisition so downstream wear and purchase denominators are honest.

Independent consumer-product field experiments support the general proposition that sampling can
increase sales and have effects lasting beyond the promotion. A fragrance-specific YSL campaign
also reported that 8.33% of targeted sample recipients bought a full-size product within 30 days.
That campaign was vendor-reported and did not disclose a control group or complete methodology, so
it supports commercial plausibility, not a universal conversion benchmark or causal lift estimate.
The application should preserve an eligible unsampled comparison group where practical and report
incremental conversion, not merely post-sample purchases.

It does **not** justify adding genetics/MHC, ancestry, personality inventories, gender-derived rules,
skin microbiome, required skin type, influencer trends, packaging embeddings, GC-MS, or molecular
odor embeddings to the first baseline. It also does not justify model boosts for familiarity,
intensity, brand prestige, price, or sample availability. Those remain hypotheses requiring
prospective evaluation against the application's own outcomes.

The review therefore narrows rather than expands the recommendation: complete the versioned,
low-burden observation and context contract first. Defer sensitive, stereotype-prone, expensive,
or unavailable features until they have a decision-matched hypothesis and can demonstrate
incremental value over the controlled baseline.

## 16. Conclusion

The system is structurally closer to ML readiness than its current product surface suggests. It
already has the hardest experimental safeguards: exact-version observations, blind presentation,
holdouts, repeats, append-only controlled responses, immutable recommendation records, and frozen
prediction snapshots.

It is **not data-complete** for the intended product. Without context and behavior, it can learn
an approximation of “did this person like this smell under this test?” but not reliably answer
“would this person wear it in this setting and season?” or “would they buy it under this offer?”
Without normalized perfume vocabularies and physical-exposure provenance, even the intrinsic-like
model risks learning importer spelling, source artifacts, or delivery method instead of preference.

The best remediation is not a broad feature grab. Complete the already planned R6-R8 foundation,
add the smallest usable context and behavioral contracts before data collection, and preserve the
three outcomes as separate labels throughout retrieval, training, and evaluation.

## 17. Primary implementation evidence

- `src/fragrance_rater/models/fragrance.py`
- `src/fragrance_rater/models/evaluation.py`
- `src/fragrance_rater/models/calibration.py`
- `src/fragrance_rater/models/recommendation_measurement.py`
- `src/fragrance_rater/models/prediction.py`
- `src/fragrance_rater/schemas/evaluation.py`
- `src/fragrance_rater/schemas/calibration.py`
- `src/fragrance_rater/services/preference_history.py`
- `src/fragrance_rater/services/fragella_client.py`
- `src/fragrance_rater/services/fragella_lookup_service.py`
- `src/fragrance_rater/ml/feature_space.py`
- `src/fragrance_rater/ml/dataset.py`
- `frontend/src/content/calibrationScales.ts`
- `docs/planning/PROJECT-PLAN.md`
- `docs/planning/adr/adr-004-recommendation-algorithm.md`
- `docs/planning/adr/adr-005-controlled-calibration.md`
- `docs/planning/adr/adr-007-preference-evidence-and-score-semantics.md`
- `docs/planning/adr/adr-009-prospective-evaluation-and-checkpoints.md`
- `docs/planning/adr/adr-010-preference-learning-and-scenario-data-model.md`
- `docs/planning/adr/adr-016-per-dimension-preference-capture.md`
- `docs/planning/data-model-gap-analysis.md`
- `docs/planning/ml-structure-review-2026-09.md`
- `docs/research/perfume-purchasing-research-validation.md`

## 18. Data-capture additions from the future-state ML architecture review

An internally authored, unreviewed architecture proposal argued for a broad future-state data
model spanning multi-tenant household scoping, a mobile client, federated learning, and a wide
event-sourced schema. Most of that proposal's infrastructure is out of scope here: it is
comparatively cheap to add later, and the project's own commercialization staging already places
multi-tenancy, billing, and tenant-scoped deletion at a post-paid-validation stage, not before it.
A senior-architecture review of the same proposal reached the same conclusion independently.

One distinction from that review does belong in this assessment. Infrastructure is reversible;
a moment's price, context, offer, or consent state that goes unrecorded is not. The five items
below are the data-capture additions worth adopting now, at low cost, without adopting the
proposal's infrastructure framing. None of them require a new ADR; none change
`PROJECT-PLAN.md` sequence, status, or `ml-decisions-2026-09.md`.

### 18.1 Offer choice set at purchase time

Section 4.3 already requires offer timestamp, currency, price, size, and availability for the
purchased item. It does not capture what else was on offer at that moment. A `would_buy` or
purchase event recorded against a single price point cannot separate "I would not buy this
fragrance" from "I would not buy this fragrance at this price when a comparable option was
cheaper." Add, alongside the existing offer snapshot:

- the alternative formats/sizes and prices visible at the same offer timestamp, when known;
- shipping, fees, and other landed-cost components, so a derived landed cost can be compared
  across formats and retailers;
- a reference to which alternative, if any, was chosen instead.

This is an extension of the offer snapshot already required by 4.3, not a new entity. Record it
as part of the same timestamped, immutable offer record.

### 18.2 Acquisition format and access mode

Section 4.3's purchase format list (sample, decant, travel, bottle) does not distinguish a
partial/split purchase or a discovery set from a single-item purchase, and no existing field
records how the evaluator physically accessed the fragrance being rated. Add:

- two acquisition-format values, `bought_split_or_partial` and `bought_discovery_set`, alongside
  the existing sample/decant/travel/bottle values;
- an access-mode code at the encounter level: local tester, free sample, paid sample, discovery
  set, or bottle-only.

Access mode is a confounder for both liking and purchase intent: a paid sample and a free tester
carry different selection pressure even when the sensory encounter is identical.

### 18.3 Wear-log coverage flag

Section 13.9 establishes that a missing wear or purchase event must resolve to pending,
unavailable, or censored, never a silent negative. That contract assumes a wear log exists to be
absent from. It does not yet distinguish an evaluator who was never asked to keep a wear log from
one who was asked and did not respond. Add a wear-log coverage flag per evaluator/fragrance
opportunity window, recorded alongside the existing censoring states, so absence of any wear
events can be read as "no log requested" rather than defaulting to the same unresolved-opportunity
state as "log requested, nothing recorded yet."

### 18.4 Tenant/household scope column

No model in `src/fragrance_rater/models/` carries a household, tenant, or scope identifier today;
the household is implicit in a single shared database. This is not a request to build
multi-tenancy now. It is a request to add one unused, constant-valued scope column to the core
private-data tables (evaluator, observation, encounter, offer/behavioral-event records) while
those tables are still small and their schema is still cheap to change. A column that is always
the same value costs nothing to carry and nothing to migrate later; backfilling a scope key onto
years of accumulated rows after the fact, if a future stage ever needs it, is materially more
expensive and risks silently misattributing historical rows during the backfill.

### 18.5 Consent/contribution-state field

Section 13.11 already requires a consent text/version and timestamp before collecting sensitive
optional context. It does not yet capture what an evaluator has agreed a given record may be used
for. Add a consent/contribution-state field, recorded per evaluator or per consent event, covering
at minimum: research use within the household, inclusion in aggregate reporting, and future model
training contribution. This is distinct from the sensitive-field consent in 13.11; it applies to
ordinary observations as much as to sensitive context, and it is the field a future export or
aggregate-benchmark decision would need to check before including a given evaluator's rows, per
this project's rule that new commercial uses require specific, informed opt-in rather than a
buried terms update.

None of the five items above is required before F1's blind pass. 18.1 and 18.2 must exist before
the first recorded offer or purchase event, which can only occur post-reveal; 18.3 before the
first follow-up wear-log window opens, also post-reveal; 18.5 rides on the consent screen that
13.11 already requires before session-context collection, so it costs nothing extra if that screen
is being built anyway; 18.4 may land whenever a migration next touches the relevant tables. The
data that genuinely cannot wait, because the initial four evaluators get exactly one pre-reveal
exposure per fragrance, is scoped in sections 5.1, 6, 11 (Milestone 1), 12 (P0), and 13.13, and is
tracked in `PROJECT-PLAN.md`'s R7a/R7b sprint rows, not here.

## 19. Change-control note

This assessment identifies data requirements and sequencing risks. Changes to the baseline panel,
blind core, outcome placement, Fragella use, training eligibility, or accepted model decision rule
must be reconciled through the relevant ADR and `PROJECT-PLAN.md` before implementation.
