# Project Vision & Scope: Fragrance Rater

> **Status**: Active | **Version**: 2.0 | **Updated**: 2026-09-11

## Vision

Fragrance Rater helps the Williams family make better fragrance choices by preserving what
each person actually experienced, connecting those observations to verified fragrance versions,
and testing recommendation strategies prospectively.

The product succeeds when it reduces expensive trial and error while giving each evaluator a
clear, trustworthy record of their preferences. Recommendation explanations and catalog
visualizations support that outcome; they are not substitutes for measured experience.

## Problem statement

Fragrance selection is difficult because preferences are personal, vocabulary is specialized,
versions and concentrations are easily confused, and memory is unreliable across repeated
encounters. Published notes describe a source's representation of a fragrance, not necessarily
what an evaluator perceives. An appealing recommendation is also not proof that the person will
like the fragrance after sampling it.

The system therefore preserves three kinds of evidence without conflating them:

1. Published catalog metadata and its source provenance.
2. Ordinary and controlled observations recorded by an evaluator.
3. Model interpretations, candidate scores, and explanations derived from frozen inputs.

## Users and contexts

- **Evaluators**: Byron, Veronica, Bayden, and Ariannah record ordinary encounters and controlled
  observations.
- **Recorders**: An authenticated family member may enter observations for more than one
  evaluator during a shared session.
- **Experiment managers**: Authorized users create controlled programs, verify exact versions,
  manage mappings, freeze checkpoints, and reveal identities.
- **Primary contexts**: Home evaluation, blind blotter and skin sessions, collection review,
  in-store research through a secure home connection, and gift selection.

## Product outcomes

### Primary outcome

Increase the proportion of sampled recommendations that evaluators actually like, would wear,
or would consider buying, compared with a declared baseline strategy.

### Supporting outcomes

- Capture encounters in under 30 seconds for the ordinary workflow.
- Preserve every ordinary encounter and controlled observation with its original scale,
  timestamp, provenance, and authorship.
- Explain preference patterns without presenting affinity scores as probabilities or inferred
  ingredient composition.
- Broaden useful discovery while maintaining catalog coverage and variety.
- Keep blind identities and holdout outcomes from leaking into participant views, caches,
  profiles, explanations, or training inputs.
- Operate on the home server without requiring enrichment or LLM services for core capture and
  deterministic scoring.

## Success measures

All reported metrics must include the eligible population, numerator, denominator, time window,
model version, candidate strategy, and source snapshot where applicable.

| Measure | Initial target | Interpretation |
| :--- | :--- | :--- |
| Ordinary adoption | At least 50 encounters in the first active month | Usage signal, reported per evaluator |
| Entry usability | Median ordinary entry time under 30 seconds | Measured task time, not anecdotal recall |
| Recommendation interest | At least 80% positive among explicit interest responses after 10+ contributing versions | Funnel metric, not predictive accuracy |
| Sampling conversion | Baseline established during F1 after P6 UI readiness | Fraction of shown recommendations actually sampled |
| Post-sample liking | Improvement over a frozen baseline strategy | Primary recommendation outcome |
| Would-wear / would-buy | Reported separately from liking | Practical decision outcomes |
| Catalog coverage and variety | Baseline and thresholds established before D4 | Guard against repetitive or narrow recommendations |
| Blind integrity | Zero unauthorized identity or holdout disclosures | Release-blocking invariant |
| Score latency | Recommendation scores under 500 ms p95 on the target deployment | Excludes optional LLM explanation latency |

The former “80% accuracy” statement is retained only as an interest target. A calibrated liking
claim requires prospective predictions, frozen inputs, held-out outcomes, a declared loss or
classification rule, and uncertainty reporting.

## Scope

### Current product baseline

- Canonical fragrance-version catalog with source evidence.
- Reviewer, fragrance, and ordinary encounter CRUD.
- Retained dated 1–5 ordinary ratings.
- Deterministic note, accord, and family affinity recommendations.
- Optional OpenRouter explanations with deterministic fallback.
- Kaggle import and Parfumo source capture.
- Controlled programs with hidden repeats and holdouts, randomized presentations, blotter and
  skin observations, locking, reveal, and post-reveal append-only observations.
- Shared preference history, holdout exclusion, and frozen model checkpoints.
- Functional React prototype for ordinary encounters, controlled capture, program setup, and
  recommendation interest; P3-P6 complete and rehearse the family-facing product.

### Planned before discovery work

- Production-grade migration, concurrency, backup/restore, and proxy-boundary validation (P1).
- Recommendation impression, interest, sampling, and outcome measurement with reproducible
  reporting (P2).
- Role-aware product foundation, complete participant and manager workflows, and a deployed
  synthetic rehearsal before real perfume testing (P3-P6).
- Initial family perfume pilot using only the completed interface (F1).

### Planned discovery work

- Versioned note aliases and taxonomy mappings with authorized source snapshots (D1).
- Reproducible catalog frequency and association statistics (D2).
- Accessible post-reveal source/perception/model profiles (D3).
- Candidate generation from published-note similarity and controlled contrasts (D4).
- Prospective comparison of candidate strategies with frozen experimental inputs (D5).

### Out of scope through D5

- Public accounts or social sharing.
- Retail price and availability integrations beyond manually recorded sample availability.
- Barcode scanning and native mobile applications.
- Claims about chemical formulation or ingredient percentages from published-note ranks.
- Collaborative filtering that depends on a large external user population.
- Automated active learning or calibrated confidence claims before prospective evidence supports
  them.
- Automatic import of data or code without documented reuse rights.

## Product principles

1. **Preserve raw evidence.** Corrections append or retain revision history; modeling policy is
   separate from storage policy.
2. **Resolve exact versions.** Concentrations and materially different versions remain distinct;
   unknown values remain unknown.
3. **Keep evidence layers visible.** Published notes, evaluator perception, and model
   interpretation are labeled separately.
4. **Protect blind evaluation.** Every endpoint, cache, export, and derived summary applies the
   same disclosure policy.
5. **Evaluate prospectively.** Freeze candidate choices and model inputs before holdout outcomes.
6. **Use honest labels.** Match percentages are affinity scores until calibration is demonstrated.
7. **Prefer reproducibility.** Record algorithm versions, filters, denominators, taxonomy
   versions, source hashes, and exclusions.
8. **Keep core operation local.** Capture, history, and deterministic scores continue when
   external enrichment and LLM services are unavailable.

## Constraints

- Single primary developer and four family evaluators.
- Self-hosted Docker Compose deployment on Unraid with PostgreSQL.
- React/TypeScript frontend and FastAPI/SQLAlchemy backend.
- Minimal recurring cost and low operational burden.
- Authentik/Traefik is the production trust boundary; the backend must not be directly reachable.
- Small-sample results require transparent denominators and uncertainty rather than broad claims.

## Assumptions and validation gates

| Assumption | Validation | Gate |
| :--- | :--- | :--- |
| The merged calibration migration preserves production history | Restore a production backup clone, upgrade it, validate counts/IDs, and exercise concurrent writes | P1 |
| Authentik/Traefik prevents direct mutation and mapping access | Test supported routes and direct backend bypass from the deployed network | P1 |
| The completed UI supports family tasks without API or database help | Run participant and manager end-to-end tests plus a deployed synthetic rehearsal | P3-P6 |
| Family members will use recommendation feedback consistently | Instrument impressions and outcomes; review missing-response rates after UI readiness | F1 |
| Interest predicts useful sampling | Compare interest with subsequent blind liking and wear/buy outcomes | F1/D5 |
| Authorized source material is sufficient for D1/D2 | Record license/permission evidence and coverage before adoption | D1 |
| Alias and taxonomy choices improve retrieval without erasing raw labels | Version mappings and test collisions, ambiguous terms, and coverage | D1/D2 |
| Candidate discovery improves outcomes over existing affinity scoring | Freeze strategies and compare prospectively | D5 |
| Home connectivity supports intended use | Rehearse failure handling in P6 and measure failures during F1 | P6/F1 |

## Related documents

- [Authoritative Project Plan](PROJECT-PLAN.md)
- [Technical Specification](tech-spec.md)
- [Execution Roadmap](roadmap.md)
- [Architecture Decisions](adr/README.md)
- [Controlled Calibration V1](../calibration-v1.md)
