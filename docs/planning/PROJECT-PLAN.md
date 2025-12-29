# Fragrance Rater: Project Plan

> **Version**: 1.0 | **Status**: Active | **Updated**: 2025-12-28

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
| Fragella API integration for background enrichment | Manually entered fragrances are enriched via a background task. |
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
| Fragella API quota insufficient | Low | Medium | Rely on the tiered acquisition strategy; manual entry is the primary fallback. |

## 7. Related Documents

- [Project Vision & Scope](./project-vision.md)
- [Technical Specification](./tech-spec.md)
- [Development Roadmap](./roadmap.md)
- [ADR Index](./adr/README.md)
