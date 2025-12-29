# Development Roadmap: Fragrance Rater

> **Status**: Active | **Updated**: 2025-12-28

## TL;DR

Build a personal fragrance recommendation system in 5 phases: Foundation (dev environment), Data & Seed (import fragrances), Core Features (evaluations + recommendations), Enhancement (LLM explanations), and Polish (testing + docs).

## Timeline Overview

```text
Phase 0: Foundation     ████░░░░░░░░░░░░░░░░░░░░  Setup & infrastructure
Phase 1: Data & Seed    ░░░░████░░░░░░░░░░░░░░░░  Import data, manual entry
Phase 2: Core Features  ░░░░░░░░████████░░░░░░░░  Evaluations, recommendations
Phase 3: Enhancement    ░░░░░░░░░░░░░░░░████░░░░  LLM explanations, enrichment
Phase 4: Polish         ░░░░░░░░░░░░░░░░░░░░████  Testing & docs
```

## Milestones

| Milestone | Description | Status | Dependencies |
|-----------|-------------|--------|--------------|
| M0: Dev Environment | Docker Compose stack running locally | Planned | None |
| M1: Data Import | Kaggle import + manual entry (populates DB) | Planned | M0 |
| M2: Evaluation CRUD | Create/view evaluations via API | Planned | M0, M1 |
| M3: Recommendations | Basic scoring + profile display | Planned | M2 |
| M4: LLM Integration | AI-generated explanations | Planned | M3 |
| M5: MVP Complete | Full feature set, 80% test coverage | Planned | M1-M4 |

**Critical Sequencing Note**: Data must be populated (M1) before evaluations can be meaningfully tested (M2). The recommendation engine (M3) requires evaluations to exist.

---

## Phase 0: Foundation

### Objective

Establish development environment and core infrastructure per [ADR-001](./adr/adr-001-initial-architecture.md).

### Deliverables

- [ ] Docker Compose stack (PostgreSQL, FastAPI, React) running locally
- [ ] Database schema with Alembic migrations
- [ ] CI/CD pipeline (GitHub Actions)
- [ ] Pre-commit hooks configured
- [ ] Local development guide documented

### Success Criteria

- `docker-compose up -d` starts all services without errors
- API responds at `http://localhost:8000/docs`
- Frontend loads at `http://localhost:3000`
- `uv run pytest` passes with initial test structure
- Pre-commit hooks run on commit

### Tasks

| Task | Priority | Status |
|------|----------|--------|
| Create Docker Compose configuration | High | Pending |
| Implement SQLAlchemy models (Fragrance, Note, Reviewer, Evaluation) | High | Pending |
| Set up Alembic migrations | High | Pending |
| Create FastAPI project structure with routers | High | Pending |
| Scaffold React frontend with Vite | Medium | Pending |
| Configure GitHub Actions CI workflow | Medium | Pending |
| Set up pre-commit hooks (Ruff, BasedPyright) | Medium | Pending |
| Write local development README | Low | Pending |

---

## Phase 1: Data & Seed

### Objective

Populate the database with fragrance data so users have fragrances to evaluate. This phase MUST complete before meaningful evaluation testing.

### Deliverables

- [ ] Kaggle CSV import functionality (CLI and API)
- [ ] Manual fragrance entry form with note input
- [ ] Pre-seeded family reviewer profiles (Byron, Veronica, Bayden, Ariannah)
- [ ] 1000+ fragrances in database from Kaggle import

### Success Criteria

- `fragrance-rater import kaggle data.csv` imports fragrances with notes
- Manual entry form saves fragrance with top/heart/base notes
- Fragrance search returns results from imported data
- 4 reviewer profiles exist in database

### Tasks

| Task | Priority | Status |
|------|----------|--------|
| Create Kaggle CSV parser with note normalization | High | Pending |
| Implement POST /api/v1/import/kaggle endpoint | High | Pending |
| Create CLI command `import kaggle` | High | Pending |
| Create manual fragrance entry form (React) | High | Pending |
| Implement POST /api/v1/fragrances endpoint | High | Pending |
| Implement POST /api/v1/import/seed-reviewers | Medium | Pending |
| Create basic fragrance search/list UI | Medium | Pending |

### Dependencies

- Requires: Phase 0 complete (database schema exists)
- Blocks: Phase 2 (cannot evaluate without fragrances)

---

## Phase 2: Core Features

### Objective

Implement core user workflows: evaluate fragrances and view recommendations.

### Deliverables

- [ ] Evaluation CRUD API endpoints
- [ ] Reviewer management (pre-seeded family profiles)
- [ ] Fragrance CRUD API endpoints
- [ ] Recommendation engine (scoring algorithm per [ADR-004](./adr/adr-004-recommendation-algorithm.md))
- [ ] User preference profile display
- [ ] Basic React UI for evaluation entry

### Success Criteria

- Family members can rate fragrances via UI
- Preference profiles show liked/disliked notes
- Recommendations display with match scores
- All core API endpoints have integration tests

### User Stories

#### US-001: Evaluate a Fragrance

**As a** family member
**I want** to rate a fragrance 1-5 stars with notes
**So that** the system learns my preferences

**Acceptance Criteria**:

- [ ] Can select reviewer from dropdown
- [ ] Can search/select fragrance by name
- [ ] Can enter 1-5 star rating
- [ ] Can optionally add free-form notes
- [ ] Evaluation saved and visible in history

**Tasks**:

| Task | Priority | Status |
|------|----------|--------|
| Implement POST /api/v1/evaluations endpoint | High | Pending |
| Implement GET /api/v1/evaluations endpoint (with filters) | High | Pending |
| Create evaluation entry React component | High | Pending |
| Add fragrance search/autocomplete | Medium | Pending |

#### US-002: View Recommendations

**As a** family member
**I want** to see fragrances I might enjoy
**So that** I can discover new options

**Acceptance Criteria**:

- [ ] See top 10 recommended fragrances
- [ ] Each shows match score (0-100%)
- [ ] Vetoed fragrances shown with warning
- [ ] Profile summary displays at top

**Tasks**:

| Task | Priority | Status |
|------|----------|--------|
| Implement preference profile calculation | High | Pending |
| Implement scoring algorithm | High | Pending |
| Implement GET /api/v1/recommendations/{reviewer_id} | High | Pending |
| Create recommendations React page | High | Pending |
| Add thumbs-up/down feedback mechanism | Medium | Pending |

#### US-003: View Preference Profile

**As a** family member
**I want** to see what notes I like/dislike
**So that** I understand my preferences

**Acceptance Criteria**:

- [ ] Shows top 5 liked notes with scores
- [ ] Shows top 5 disliked notes with scores
- [ ] Shows preferred fragrance families
- [ ] Shows evaluation count and confidence

**Tasks**:

| Task | Priority | Status |
|------|----------|--------|
| Implement GET /api/v1/recommendations/{reviewer_id}/profile | High | Pending |
| Create profile display React component | Medium | Pending |

### Dependencies

- Requires: Phase 1 complete (fragrances in database)
- Blocks: Phase 3 (LLM integration uses recommendation data)

---

## Phase 3: Enhancement

### Objective

Add LLM-powered explanations and background data enrichment per [ADR-002](./adr/adr-002-data-source-strategy.md) and [ADR-003](./adr/adr-003-llm-integration.md).

### Deliverables

- [ ] Fragella API integration for background enrichment
- [ ] OpenRouter LLM integration
- [ ] AI-generated recommendation explanations
- [ ] Explanation caching
- [ ] Recommendation feedback tracking (thumbs up/down)

### Success Criteria

- Manual entries enriched via Fragella (when API quota available)
- Recommendations include natural language explanations
- LLM costs tracked and within budget (<$0.02/recommendation avg)
- Feedback stored for accuracy measurement

### User Stories

#### US-004: Background Data Enrichment

**As a** system
**I want** to enrich manually-entered fragrances with Fragella API data
**So that** preference profiles are more accurate

**Acceptance Criteria**:

- [ ] Background task enriches fragrances missing notes/accords
- [ ] Fragella API client handles rate limiting gracefully
- [ ] Enrichment status visible in fragrance detail view

**Tasks**:

| Task | Priority | Status |
|------|----------|--------|
| Add Fragella API client | High | Pending |
| Implement background enrichment task (FastAPI BackgroundTasks) | High | Pending |
| Add enrichment status to fragrance model | Medium | Pending |

#### US-005: AI Recommendation Explanations

**As a** user
**I want** explanations for why fragrances match
**So that** I understand the recommendations

**Acceptance Criteria**:

- [ ] Each recommendation has a 2-3 sentence explanation
- [ ] Explanations highlight matching notes
- [ ] Explanations warn about potentially disliked notes
- [ ] Explanations load asynchronously (scores shown immediately)

**Tasks**:

| Task | Priority | Status |
|------|----------|--------|
| Create OpenRouter client | High | Pending |
| Implement prompt templates | High | Pending |
| Add explanation caching (PostgreSQL) | Medium | Pending |
| Update recommendation response schema | Medium | Pending |
| Add loading state to UI | Low | Pending |

#### US-006: Recommendation Feedback

**As a** user
**I want** to mark recommendations as "interesting" or "not for me"
**So that** the system can measure and improve accuracy

**Acceptance Criteria**:

- [ ] Each recommendation card has thumbs-up/thumbs-down buttons
- [ ] Feedback stored in database with timestamp
- [ ] Feedback visible in admin/reporting view
- [ ] 80% accuracy target trackable from feedback data

**Tasks**:

| Task | Priority | Status |
|------|----------|--------|
| Implement POST /api/v1/recommendations/{reviewer_id}/feedback | High | Pending |
| Add feedback buttons to recommendation cards | High | Pending |
| Create feedback summary report endpoint | Medium | Pending |

### Dependencies

- Requires: Phase 2 (recommendations working)
- Blocks: Phase 4 (full feature set needed for polish)

---

## Phase 4: Polish

### Objective

Finalize testing, documentation, and release preparation.

### Deliverables

- [ ] Test coverage ≥ 80%
- [ ] API documentation complete
- [ ] User guide written
- [ ] Performance validated
- [ ] Security review complete
- [ ] Unraid deployment tested

### Success Criteria

- All tests passing
- No critical/high security issues (Bandit, Safety)
- README covers all usage scenarios
- CHANGELOG reflects all features
- Deployed successfully on Unraid

### Tasks

| Task | Priority | Status |
|------|----------|--------|
| Increase backend test coverage to 80% | High | Pending |
| Add frontend component tests | Medium | Pending |
| Write user documentation | Medium | Pending |
| Performance test recommendations API | Medium | Pending |
| Run security scans (Bandit, Safety) | High | Pending |
| Create Unraid deployment guide | Medium | Pending |
| Update CHANGELOG | Low | Pending |

---

## Risk Register

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Kaggle dataset has poor data quality | Medium | High | Validate sample before full import; plan for manual cleanup |
| Fragella API quota insufficient | Low | Medium | Tiered acquisition strategy; manual fallback |
| OpenRouter costs exceed budget | Low | Medium | Use cheap models (Haiku); cache aggressively |
| Recommendation accuracy below 80% | Medium | High | Tune weights based on feedback; add evaluation context |
| Family adoption drops after novelty | Medium | Medium | Quick evaluation entry (<30s); show immediate value |

## Definition of Done

A feature is complete when:

- [ ] Code reviewed and approved
- [ ] Unit tests written and passing
- [ ] Integration tests for API endpoints
- [ ] No linting errors (Ruff, ESLint)
- [ ] No type errors (BasedPyright, TypeScript)
- [ ] Documentation updated
- [ ] Merged to main

## Git Branch Strategy

Per [CLAUDE.md](../../CLAUDE.md) branch requirements:

| Phase | Branch Pattern | Example |
|-------|----------------|---------|
| Phase 0 | `feat/phase-0-*` | `feat/phase-0-docker-setup` |
| Phase 1 | `feat/phase-1-*` | `feat/phase-1-kaggle-import` |
| Phase 2 | `feat/phase-2-*` | `feat/phase-2-evaluations` |
| Phase 3 | `feat/phase-3-*` | `feat/phase-3-llm-explanations` |
| Phase 4 | `chore/phase-4-*` | `chore/phase-4-test-coverage` |

## Related Documents

- [Project Vision](./project-vision.md)
- [Technical Spec](./tech-spec.md)
- [Architecture Decisions](./adr/)
