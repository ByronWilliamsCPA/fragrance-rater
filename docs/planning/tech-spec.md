# Technical Implementation Spec: Fragrance Rater

> **Status**: Draft
> **Version**: 1.0 | **Updated**: 2025-12-28

## TL;DR

A Docker Compose stack (React + FastAPI + PostgreSQL) for personal fragrance tracking. Uses tiered data acquisition (Kaggle → manual → API), weighted affinity scoring for recommendations, and OpenRouter LLM for natural language explanations. Deployed self-hosted on Unraid.

## Technology Stack

### Core

- **Language**: Python 3.12 (backend), TypeScript 5.x (frontend)
- **Package Manager**: UV (backend), npm (frontend)
- **Frameworks**: FastAPI 0.109+, React 18+, Vite 5+

### Code Quality

- **Linter**: Ruff (backend), ESLint (frontend)
- **Type Checker**: BasedPyright (backend), TypeScript strict (frontend)
- **Formatter**: Ruff (88 chars), Prettier (frontend)
- **Testing**: pytest (backend), Vitest (frontend)

### Data Layer

- **Database**: PostgreSQL 16 - See [ADR-001](./adr/adr-001-initial-architecture.md)
- **ORM**: SQLAlchemy 2.0 with async support
- **Migrations**: Alembic

### Infrastructure

- **Container**: Docker Compose
- **CI/CD**: GitHub Actions
- **Deployment**: Unraid Community Applications

## Architecture

### Pattern

Monolithic Docker Compose stack - See [ADR-001](./adr/adr-001-initial-architecture.md)

### Component Diagram

```text
┌─────────────────────────────────────────────────────────────────┐
│                    DOCKER COMPOSE STACK                          │
├─────────────────────────────────────────────────────────────────┤
│  ┌─────────────┐    ┌──────────────────┐    ┌────────────────┐  │
│  │   React     │    │     FastAPI      │    │   PostgreSQL   │  │
│  │  Frontend   │◄──►│     Backend      │◄──►│    Database    │  │
│  │   :3000     │    │      :8000       │    │     :5432      │  │
│  └─────────────┘    └────────┬─────────┘    └────────────────┘  │
│                              │                                   │
│         ┌────────────────────┼────────────────────┐             │
│         ▼                    ▼                    ▼             │
│   ┌──────────┐        ┌──────────┐        ┌──────────────┐      │
│   │ Fragella │        │  Kaggle  │        │  OpenRouter  │      │
│   │   API    │        │   CSV    │        │     LLM      │      │
│   └──────────┘        └──────────┘        └──────────────┘      │
└─────────────────────────────────────────────────────────────────┘
```

### Component Responsibilities

| Component | Purpose | Key Functions |
|-----------|---------|---------------|
| Frontend | User interface | Evaluation entry, profile view, recommendations |
| Backend | Business logic | CRUD operations, scoring, LLM orchestration |
| Database | Persistence | Fragrances, notes, evaluations, user profiles |
| Fragella | Data enrichment | Note/accord metadata for manual entries |
| OpenRouter | AI explanations | Natural language recommendation reasons |

## Data Model

### Core Entities

```python
# Fragrance - core entity with classification data
class Fragrance(Base):
    __tablename__ = "fragrances"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(255), index=True)
    brand: Mapped[str] = mapped_column(String(255), index=True)
    concentration: Mapped[str] = mapped_column(String(50))  # EDT, EDP, Parfum
    launch_year: Mapped[int | None]
    gender_target: Mapped[str] = mapped_column(String(20))  # Masculine, Feminine, Unisex

    # Classification (Michael Edwards Wheel)
    primary_family: Mapped[str] = mapped_column(String(50))  # Fresh, Floral, Amber, Woody
    subfamily: Mapped[str] = mapped_column(String(50))
    intensity: Mapped[str | None] = mapped_column(String(20))  # Fresh, Crisp, Classical, Rich

    # Data provenance
    data_source: Mapped[str] = mapped_column(String(20))  # manual, kaggle, fragella
    external_id: Mapped[str | None] = mapped_column(String(100))

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(default=func.now())
    updated_at: Mapped[datetime] = mapped_column(default=func.now(), onupdate=func.now())

    # Relationships
    notes: Mapped[list["FragranceNote"]] = relationship(back_populates="fragrance")
    accords: Mapped[list["FragranceAccord"]] = relationship(back_populates="fragrance")
    evaluations: Mapped[list["Evaluation"]] = relationship(back_populates="fragrance")


# Note - individual scent component
class Note(Base):
    __tablename__ = "notes"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    category: Mapped[str] = mapped_column(String(50))  # Citrus, Floral, Wood, etc.
    subcategory: Mapped[str | None] = mapped_column(String(50))


# FragranceNote - junction table with note position
class FragranceNote(Base):
    __tablename__ = "fragrance_notes"

    fragrance_id: Mapped[UUID] = mapped_column(ForeignKey("fragrances.id"), primary_key=True)
    note_id: Mapped[UUID] = mapped_column(ForeignKey("notes.id"), primary_key=True)
    position: Mapped[str] = mapped_column(String(10))  # top, heart, base

    fragrance: Mapped["Fragrance"] = relationship(back_populates="notes")
    note: Mapped["Note"] = relationship()


# FragranceAccord - accord with intensity weight
class FragranceAccord(Base):
    __tablename__ = "fragrance_accords"

    fragrance_id: Mapped[UUID] = mapped_column(ForeignKey("fragrances.id"), primary_key=True)
    accord_type: Mapped[str] = mapped_column(String(50), primary_key=True)
    intensity: Mapped[float] = mapped_column(Float)  # 0.0 to 1.0


# Reviewer - family member profile
class Reviewer(Base):
    __tablename__ = "reviewers"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    created_at: Mapped[datetime] = mapped_column(default=func.now())

    evaluations: Mapped[list["Evaluation"]] = relationship(back_populates="reviewer")


# Evaluation - a reviewer's rating of a fragrance
class Evaluation(Base):
    __tablename__ = "evaluations"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    fragrance_id: Mapped[UUID] = mapped_column(ForeignKey("fragrances.id"))
    reviewer_id: Mapped[UUID] = mapped_column(ForeignKey("reviewers.id"))
    rating: Mapped[int] = mapped_column(Integer)  # 1-5
    notes: Mapped[str | None] = mapped_column(Text)  # Free-form observations

    # Optional structured feedback
    longevity_rating: Mapped[int | None]
    sillage_rating: Mapped[int | None]

    evaluated_at: Mapped[datetime] = mapped_column(default=func.now())
    created_at: Mapped[datetime] = mapped_column(default=func.now())

    fragrance: Mapped["Fragrance"] = relationship(back_populates="evaluations")
    reviewer: Mapped["Reviewer"] = relationship(back_populates="evaluations")
```

### Relationships

- Fragrance → Notes: Many-to-many (via FragranceNote with position)
- Fragrance → Accords: One-to-many (accord types with intensity)
- Fragrance → Evaluations: One-to-many
- Reviewer → Evaluations: One-to-many

### Database Indexing Strategy

Critical indexes for recommendation performance (<500ms target):

```sql
-- Evaluations: Fast lookup of user's rated fragrances
CREATE INDEX idx_evaluations_reviewer ON evaluations(reviewer_id);
CREATE INDEX idx_evaluations_reviewer_fragrance ON evaluations(reviewer_id, fragrance_id);

-- FragranceNote: Fast lookup of notes for scoring
CREATE INDEX idx_fragrance_notes_fragrance ON fragrance_notes(fragrance_id);
CREATE INDEX idx_fragrance_notes_note ON fragrance_notes(note_id);

-- FragranceAccord: Fast lookup of accords for scoring
CREATE INDEX idx_fragrance_accords_fragrance ON fragrance_accords(fragrance_id);

-- Fragrances: Fast search by name/brand
CREATE INDEX idx_fragrances_name ON fragrances(name);
CREATE INDEX idx_fragrances_brand ON fragrances(brand);
CREATE INDEX idx_fragrances_name_brand ON fragrances(name, brand);
```

### Query Optimization Notes

The recommendation algorithm queries notes and accords separately to preserve domain semantics (notes are ingredients, accords are perceptual descriptors). This is intentional per the concept document's data model. For MVP scale (~1000 fragrances, 4 users), separate queries with proper indexing will meet performance targets. Consider denormalization only if scaling beyond 10K fragrances.

## API Specification

### Endpoints

| Method | Path | Purpose | Auth |
|--------|------|---------|------|
| GET | `/api/v1/fragrances` | List/search fragrances | No |
| GET | `/api/v1/fragrances/{id}` | Get fragrance details | No |
| POST | `/api/v1/fragrances` | Create fragrance (manual) | No |
| POST | `/api/v1/fragrances/lookup` | Search & import from external | No |
| GET | `/api/v1/reviewers` | List reviewers | No |
| POST | `/api/v1/reviewers` | Create reviewer | No |
| GET | `/api/v1/evaluations` | List evaluations (filterable) | No |
| POST | `/api/v1/evaluations` | Create evaluation | No |
| GET | `/api/v1/recommendations/{reviewer_id}` | Get recommendations | No |
| GET | `/api/v1/recommendations/{reviewer_id}/profile` | Get preference profile | No |
| POST | `/api/v1/recommendations/{reviewer_id}/feedback` | Thumbs up/down | No |
| POST | `/api/v1/import/kaggle` | Upload Kaggle CSV | No |
| POST | `/api/v1/import/seed-reviewers` | Create default family reviewers | No |

### Request/Response Examples

```json
// POST /api/v1/evaluations
{
  "fragrance_id": "550e8400-e29b-41d4-a716-446655440000",
  "reviewer_id": "550e8400-e29b-41d4-a716-446655440001",
  "rating": 4,
  "notes": "Nice citrus opening, fades too quickly"
}

// GET /api/v1/recommendations/{reviewer_id}
{
  "recommendations": [
    {
      "fragrance": { "id": "...", "name": "Terre d'Hermès", "brand": "Hermès" },
      "match_score": 0.89,
      "vetoed": false,
      "explanation": "Strong citrus notes align with your preferences...",
      "explanation_loading": false
    }
  ],
  "profile_summary": "Prefers citrus-forward fresh scents with woody bases",
  "evaluation_count": 12
}
```

## CLI Specification

### Commands

| Command | Purpose | Example |
|---------|---------|---------|
| `fragrance-rater import kaggle` | Import Kaggle CSV | `fragrance-rater import kaggle data.csv` |
| `fragrance-rater seed-reviewers` | Create family profiles | `fragrance-rater seed-reviewers` |
| `fragrance-rater profile <name>` | Show user's preference profile | `fragrance-rater profile Bayden` |

### Arguments

- `--db-url`: Database connection string (default: from env)
- `--dry-run`: Preview without writing (import commands)

## Security

### Authentication

**None for MVP** - Family-only use on home network. User selection via dropdown.

### Authorization

**None for MVP** - All endpoints public. All users can see all data.

### Data Protection

- **At Rest**: PostgreSQL default (no encryption needed for personal data)
- **In Transit**: HTTP on LAN; HTTPS via reverse proxy for remote access (future)
- **Sensitive Data**: API keys stored in environment variables, not committed

### Future Considerations

- Add simple PIN per user if privacy between family members needed
- Add Nginx reverse proxy with TLS for remote access

## Error Handling

### Strategy

Fail fast with descriptive errors. API returns structured error responses.

### Error Codes

| Code | HTTP Status | Meaning | User Action |
|------|-------------|---------|-------------|
| `FRAGRANCE_NOT_FOUND` | 404 | Fragrance ID doesn't exist | Check ID or create new |
| `REVIEWER_NOT_FOUND` | 404 | Reviewer ID doesn't exist | Use seed-reviewers |
| `INSUFFICIENT_EVALUATIONS` | 400 | <3 evaluations for recommendations | Rate more fragrances |
| `EXTERNAL_API_ERROR` | 502 | Fragella/OpenRouter unavailable | Retry or use manual entry |
| `VALIDATION_ERROR` | 422 | Invalid request data | Fix input per error details |

### Logging

- **Format**: Structured JSON (structlog)
- **Levels**: DEBUG, INFO, WARNING, ERROR
- **Sensitive**: Never log API keys or full request bodies

## Performance Requirements

| Metric | Target | Measurement |
|--------|--------|-------------|
| API response time (CRUD) | < 200ms p95 | FastAPI middleware timing |
| API response time (recommendations) | < 500ms p95 (scores only) | FastAPI middleware timing |
| LLM explanation load | < 3s | Frontend loading state |
| Database queries | < 50ms | SQLAlchemy query timing |
| Frontend initial load | < 2s | Lighthouse |

## Testing Strategy

### Coverage Target

- Minimum: 80%
- Critical paths (recommendations, evaluations): 100%

### Test Types

- **Unit**: Services, scoring algorithm, data transformations
- **Integration**: API endpoints with test database, Kaggle import
- **E2E**: Evaluation → Recommendation flow (Playwright, deferred to Phase 3)

### Test Commands

```bash
# Backend
uv run pytest tests/ -v --cov=src --cov-report=html

# Frontend
npm run test
npm run test:coverage
```

## Related Documents

- [Project Vision](./project-vision.md)
- [Architecture Decisions](./adr/)
- [Development Roadmap](./roadmap.md)
