# Fragrance Rater: Project Plan

> **Version**: 1.1 | **Status**: Active | **Updated**: 2026-09-11

## Current planning authority and implementation status

This update incorporates the [Scent chords analysis](../research/scent-chords-analysis.md).
The phase tables below are the original delivery outline, not a verified completion ledger.
Current code takes precedence over older planning documents and ADR assumptions.

At audited `main` commit `ff026eff620a7922eb3f7dcd54f29533135df84f`, the backend already
contains catalog/reviewer/evaluation services, deterministic recommendations, Kaggle import,
Parfumo scraping and LLM scoring. The React application is a scaffold. Controlled calibration
and encounter-history changes are prepared separately on `feat/controlled-calibration`; they
are **pending integration**, not deployed functionality. This documentation change neither
ships those changes nor imports external data.

Approved product decisions for that pending work:

- Each ordinary re-rating creates a dated encounter; retain all ordinary ratings on their
  original scale. The modeling policy determines contributions independently of storage.
- For each evaluator, identities remain hidden until baseline repeats and planned blind skin
  tests are locked and the skin plan is finalized. Post-reveal responses remain separate.
- Ordinary and controlled workflows share canonical version and reviewer identities and one
  preference history with explicit measurement provenance.
- Holdout exclusion applies across all observations of the held-out version in the experiment
  scope, including ordinary ratings. Blind information must not leak through discovery,
  history, recommendation explanations or derived profiles.

## 1. Executive Summary

This project will create a personal fragrance evaluation and recommendation system for the Williams family (4 users). The system will be a self-hosted Docker Compose stack featuring a React frontend, FastAPI backend, and PostgreSQL database. It will use a weighted affinity scoring algorithm based on the Michael Edwards Fragrance Wheel to generate recommendations, with the goal of achieving over 80% accuracy in predicting fragrances a user will find "interesting". Data will be sourced via a tiered strategy (Kaggle seed → manual entry → API enrichment), and an OpenRouter LLM integration will provide natural language explanations for recommendations.

## 2. Quick Start

This guide maps project phases to git branches and provides initial commands for developers.

| Phase | Objective | Git Branch Pattern | Quick Start Command |
| :---- | :---------- | :----------------- | :------------------ |
| **0** | Foundation | `feat/phase-0-*` | `git checkout -b feat/phase-0-docker-setup` |
| **1** | Data & Seed | `feat/phase-1-*` | `git checkout -b feat/phase-1-kaggle-import` |
| **2** | Core Features | `feat/phase-2-*` | `git checkout -b feat/phase-2-evaluations` |
| **3** | Enhancement | `feat/phase-3-*` | `git checkout -b feat/phase-3-llm-explanations` |
| **4** | Polish | `chore/phase-4-*` | `git checkout -b chore/phase-4-test-coverage` |

## 3. Phase Details

### Phase 0: Foundation

*   **Objective**: Establish the development environment and core infrastructure.
*   **Git Branches**: `feat/phase-0-*` (e.g., `feat/phase-0-docker-setup`, `feat/phase-0-db-schema`)
*   **Dependencies**: None

| Deliverables | Acceptance Criteria |
| :--- | :--- |
| Docker Compose stack (PostgreSQL, FastAPI, React) | `docker-compose up -d` starts all three services without errors. |
| Database schema with Alembic migrations | API responds at `http://localhost:8000/docs`. |
| CI/CD pipeline (GitHub Actions) | Frontend loads at `http://localhost:3000`. |
| Pre-commit hooks configured | `uv run pytest` passes with initial test structure. |
| Local development guide documented | Pre-commit hooks run automatically on commit. |

### Phase 1: Data & Seed

*   **Objective**: Populate the database with fragrance data so users have fragrances to evaluate.
*   **Git Branches**: `feat/phase-1-*` (e.g., `feat/phase-1-kaggle-import`, `feat/phase-1-manual-entry`)
*   **Dependencies**: Phase 0 must be complete.

| Deliverables | Acceptance Criteria |
| :--- | :--- |
| Kaggle CSV import functionality (CLI and API) | `fragrance-rater import kaggle data.csv` imports 1000+ fragrances with notes. |
| Manual fragrance entry form with note input | Manual entry form captures and saves top/heart/base notes. |
| Pre-seeded family reviewer profiles | 4 reviewer profiles (Byron, Veronica, Bayden, Ariannah) exist in the database. |
| Basic fragrance search UI | Fragrance search returns results from imported data. |
| Offline functionality verified | App remains functional with external APIs disabled. |

### Phase 2: Core Features

*   **Objective**: Implement core user workflows: evaluating fragrances and viewing recommendations.
*   **Git Branches**: `feat/phase-2-*` (e.g., `feat/phase-2-evaluation-crud`, `feat/phase-2-scoring-engine`)
*   **Dependencies**: Phase 1 must be complete.

| Deliverables | Acceptance Criteria |
| :--- | :--- |
| Evaluation CRUD API & UI | Family members can rate fragrances 1-5 via the UI. |
| Recommendation engine (per ADR-004) | Recommendations display with a numeric match score (0-100%). |
| User preference profile display | Preference profiles show top liked/disliked notes based on evaluations. |
| Recommendation feedback mechanism | Adding a 1-star rating for a fragrance with lemon lowers all lemon-containing recommendations. |
| Match score performance | Match scores update within 1 second of submitting a new evaluation. |
| Personalized recommendations | Recommendations differ meaningfully between family members. |

### Phase 3: Enhancement

*   **Objective**: Add LLM-powered explanations and background data enrichment.
*   **Git Branches**: `feat/phase-3-*` (e.g., `feat/phase-3-llm-explanations`, `feat/phase-3-api-enrichment`)
*   **Dependencies**: Phase 2 must be complete.

| Deliverables | Acceptance Criteria |
| :--- | :--- |
| Parfumo source preservation and refresh integration | Verified version links can be refreshed without overwriting evaluator observations; background scheduling remains planned. |
| OpenRouter LLM integration | Recommendations load with scores in <500ms, with explanations populating asynchronously within 3 seconds. |
| AI-generated recommendation explanations | Explanations are cached and reused for repeat views. |
| Recommendation feedback tracking (thumbs up/down) | User feedback on recommendations is stored for accuracy measurement. |
| Cost control | Average cost per recommendation is <$0.02. |

### Phase 4: Polish

*   **Objective**: Finalize testing, documentation, and prepare for deployment.
*   **Git Branches**: `chore/phase-4-*` (e.g., `chore/phase-4-add-tests`, `chore/phase-4-docs`)
*   **Dependencies**: Phase 3 must be complete.

| Deliverables | Acceptance Criteria |
| :--- | :--- |
| Test coverage ≥ 80% | All CI checks passing on the `main` branch. |
| Complete API documentation | No critical/high security issues found by Bandit or Safety scans. |
| User guide and deployment instructions | README covers all setup, development, and deployment scenarios. |
| Performance and security validation | Deployed successfully on the target Unraid server. |

## 4. Architecture Reference

The system is a Docker Compose monolith with three services: a React frontend, a FastAPI backend, and a PostgreSQL database. This architecture was chosen for its balance of development speed and production-ready deployment on the target Unraid server. Data is acquired through a tiered strategy to ensure offline functionality, and the core recommendation logic is a deterministic, weighted scoring algorithm.

Key decisions are documented in the following ADRs:
*   [**ADR-001**](./adr/adr-001-initial-architecture.md): Docker Compose Monolith
*   [**ADR-002**](./adr/adr-002-data-source-strategy.md): Tiered Data Acquisition
*   [**ADR-003**](./adr/adr-003-llm-integration.md): OpenRouter for Explanations
*   [**ADR-004**](./adr/adr-004-recommendation-algorithm.md): Weighted Affinity Scoring Algorithm

## 5. Success Metrics

| Metric | Target | Source |
| :--- | :--- | :--- |
| **Recommendation Accuracy** | **80%+** of recommendations marked "interesting" | Thumbs-up/down feedback on recommendations |
| **User Engagement** | **50+** evaluations captured | Database count within the first month |
| **Usability** | **< 30 seconds** per evaluation entry | User feedback and observation |
| **API Performance** | **< 500ms** for recommendation scores (p95) | API monitoring |

## 6. Risk Mitigation

| Risk | Probability | Impact | Mitigation Strategy |
| :--- | :--- | :--- | :--- |
| Kaggle dataset has poor data quality | Medium | High | Validate a sample before full import; plan for manual cleanup tasks. |
| Recommendation accuracy below 80% | Medium | High | Tune algorithm weights based on feedback; add more evaluation context (e.g., longevity). |
| Family adoption drops after novelty | Medium | Medium | Ensure evaluation entry is fast (<30s) and the value (recommendations) is immediate. |
| OpenRouter costs exceed budget | Low | Medium | Default to cheap models (e.g., Claude Haiku); cache explanations aggressively. |
| Source access or reuse rights unavailable | Medium | High | Record permissions and provenance per source; preserve manual entry and offline operation. |

## 7. Follow-up: Explore and Candidate Discovery

**Decision:** Learn from Scent chords' source-note exploration and precomputed statistics.
Build discovery around our own verified catalog and authorized source snapshots. Do not adopt
its corpus as the baseline catalog, treat co-occurrence as preference evidence, or copy code
without a software license. See the [reference analysis](../research/scent-chords-analysis.md)
for evidence, limitations, formulas and integration options.

This is proposed follow-up scope. It must not delay a usable controlled capture workflow.

| Work item | Dependency | Deliverable and acceptance criteria |
| :--- | :--- | :--- |
| D0: Calibration integration and catalog verification | Pending calibration change | Complete migration/reveal/holdout gates; verify the full baseline manifest against exact concentrations and versions. Preserve all encounter history. Run live PostgreSQL migration and concurrency validation before deployment. |
| D1: Source and vocabulary foundation | D0 for calibration use | Maintain versioned note aliases and taxonomy mappings separately from source labels and perceived notes. Preserve ambiguous terms, raw labels, source URL, retrieval time, license/permission evidence and snapshot hash. Unknown concentration remains unknown. Evaluate Parfica vocabulary assets under their per-asset licenses; do not assume perfume metadata is included. |
| D2: Reproducible catalog statistics | D1 and authorized source corpus | Compute note totals, pair counts, lift and support from the same eligible population and filter. Deduplicate aliases within a fragrance before counting. Record population size, exclusions, taxonomy/version and source hash. Show minimum support and distinguish frequency from association. Recompute every denominator when filters change. |
| D3: Post-reveal exploration | D0, D2 | Add a fragrance profile that separates published notes, evaluator perception and model interpretation. Show raw and beyond-chance pair views with accessible lists/tables alongside any wheel. Do not infer composition percentages from note rank. Reuse authorization and reveal policies on every endpoint and cache. |
| D4: Candidate discovery pilot | D1, D2; D0 for experiments | Generate candidates from published-note similarity and contrasting profiles; verify version identity and sample availability. Keep concentration variants visible as distinct candidates. Record selection reason, algorithm/version, score type, source snapshot and model run. Similarity is labeled “Similar published note profile.” |
| D5: Prospective evaluation | D4 and frozen experimental inputs | Compare against existing affinity recommendations on a separate development/validation design. Track coverage, variety and selection usefulness; evaluate liking predictions only when a calibrated liking predictor exists. Freeze choices before final holdout outcomes; never tune on those outcomes. |

### Scope and design constraints

- An external link is the lowest-cost reference option. An iframe remains optional and requires
  reveal gating, explicit external-service dependency handling, and origin/source validation
  for any `postMessage` integration. Never send evaluator responses to it.
- Prefer independently implemented statistics and local precomputed assets for reproducibility
  and offline operation. The inspected site exposes static files, not a documented service API.
- High lift indicates catalog association, not causal ingredients, personal liking, statistical
  confidence or expected information gain. Small-support pairs require explicit filtering or
  regularization; algorithm choices and thresholds must be versioned.
- Keep raw 1–5 ordinary and 0–10 controlled scales. A match percentage is an affinity score,
  not a probability or a predicted 0–10 rating. Do not claim MAE/Brier calibration for it.
- The original 80% “interesting” target is a product feedback goal, not established predictive
  accuracy. Report its denominator and evaluation protocol separately from controlled outcomes.
- Automated active learning, learned note interactions, advanced reliability weighting and a
  full interactive chord wheel are later experiments, not prerequisites for V1.

### Verification gates for implementation PRs

Use meaningful fixtures for alias collisions, unknown terms, zero/sparse pair support,
filtered-population denominators, duplicate notes and exact version resolution. Verify that
same-name concentrations coexist and minimalist fragrances remain eligible even with few
published notes. Exercise blind access through profiles, search-derived summaries, histories,
recommendation explanations and caches; visible catalog browsing must not disclose a blind-code
mapping. Confirm holdout exclusion across ordinary and controlled inputs and immutability of
frozen input/source snapshots. Check accessible alternatives and offline behavior for visuals.

### Source decisions requiring later resolution

| Question | Recommended default |
| :--- | :--- |
| Reuse the inspected project's code? | Independently implement ideas until an explicit software license or permission is obtained. |
| Import its Fragrantica-derived corpus? | No automatic import. Review dataset terms, upstream permissions and intended distribution first. |
| Use Parfica identifiers/taxonomy? | Pilot only the explicitly licensed assets; retain source attribution and mapping provenance. |
| Display one global fragrance family? | Preserve source-specific and versioned taxonomy mappings; do not silently replace existing classifications. |

## 8. Related Documents

- [Project Vision & Scope](./project-vision.md)
- [Technical Specification](./tech-spec.md)
- [Development Roadmap](./roadmap.md)
- [ADR Index](./adr/README.md)

- [Scent chords: analysis and integration reference](../research/scent-chords-analysis.md)
