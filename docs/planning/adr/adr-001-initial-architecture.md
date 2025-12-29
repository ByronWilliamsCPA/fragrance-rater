# ADR-001: Initial Architecture - Docker Compose Monolith

> **Status**: Accepted
> **Date**: 2025-12-28

## TL;DR

Use a Docker Compose stack with React frontend, FastAPI backend, and PostgreSQL database, deployed on Unraid for self-hosted family use.

## Context

### Problem

We need an architecture that:

- Supports a web UI accessible on home network and remotely (via VPN)
- Stores structured fragrance data with relationships (notes, accords, evaluations)
- Integrates with external APIs (Fragella) and LLMs (OpenRouter)
- Is maintainable by a single developer
- Runs on existing Unraid home server

### Constraints

- **Technical**: Single developer, Unraid deployment target, PostgreSQL for structured data
- **Business**: Minimal cost, low maintenance, family-only use (4 users)

### Significance

The architecture determines development complexity, operational burden, and future extensibility. Getting this wrong means rewriting core infrastructure.

## Decision

**We will use a Docker Compose monolith with three services (React frontend, FastAPI backend, PostgreSQL) because it balances development speed with production-ready deployment on Unraid.**

### Rationale

- Docker Compose is native to Unraid's Community Applications ecosystem
- FastAPI provides modern async Python with automatic OpenAPI docs
- PostgreSQL handles the relational data model (fragrances → notes, evaluations → users)
- React offers rich component ecosystem for mobile-friendly UI

## Options Considered

### Option 1: Docker Compose Monolith (React + FastAPI + PostgreSQL) ✓

**Pros**:

- ✅ Native Unraid deployment via Community Applications
- ✅ Single `docker-compose up` for full stack
- ✅ Easy local development with volume mounts
- ✅ FastAPI auto-generates OpenAPI docs
- ✅ PostgreSQL handles complex relational queries (note affinities, family scores)

**Cons**:

- ❌ Requires maintaining three services
- ❌ More complex than SQLite-based solutions

### Option 2: SQLite + Flask/Streamlit

**Pros**:

- ✅ Simpler single-file database
- ✅ Faster initial development

**Cons**:

- ❌ SQLite lacks concurrent write handling for multi-user
- ❌ Streamlit less flexible for custom UI
- ❌ No native mobile optimization

### Option 3: Serverless (Supabase + Vercel)

**Pros**:

- ✅ Zero infrastructure management
- ✅ Built-in auth and real-time

**Cons**:

- ❌ Monthly costs for family project
- ❌ Data not self-hosted
- ❌ Dependency on external services

## Consequences

### Positive

- ✅ **Development velocity**: Hot-reload for both frontend and backend
- ✅ **Deployment simplicity**: Single docker-compose.yml for entire stack
- ✅ **Data ownership**: All data stays on home server
- ✅ **API documentation**: Automatic Swagger UI at `/docs`

### Trade-offs

- ⚠️ **Three services to monitor**: Mitigated by Docker health checks and restart policies
- ⚠️ **PostgreSQL overhead**: Acceptable for structured fragrance data model

### Technical Debt

- Consider adding Nginx reverse proxy for production TLS (deferred until remote access needed)

## Implementation

### Components Affected

1. **Backend (fragrance-api)**: FastAPI with SQLAlchemy ORM, Alembic migrations
2. **Frontend (fragrance-ui)**: React with Vite, TypeScript, Tailwind CSS
3. **Database (fragrance-db)**: PostgreSQL 16 with persistent volume

### Directory Structure

```
/home/byron/dev/fragrance_rater/
├── backend/              # FastAPI application
│   ├── app/
│   │   ├── main.py
│   │   ├── models/
│   │   ├── routers/
│   │   └── services/
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/             # React application
│   ├── src/
│   ├── Dockerfile
│   └── package.json
└── docker-compose.yml    # Orchestration
```

### Testing Strategy

- Unit: pytest for backend services, Vitest for frontend components
- Integration: TestClient for API endpoints, database fixtures

## Validation

### Success Criteria

- [ ] `docker-compose up -d` starts all three services without errors
- [ ] API responds at `http://localhost:8000/docs`
- [ ] Frontend loads at `http://localhost:3000`
- [ ] Evaluation CRUD operations work end-to-end

### Review Schedule

- Initial: After Phase 0 (dev environment complete)
- Ongoing: After each major feature phase

## Related

- [ADR-002](./adr-002-data-source-strategy.md): Data acquisition approach
- [ADR-003](./adr-003-llm-integration.md): LLM integration for recommendations
- [Tech Spec](../tech-spec.md): Detailed implementation specifications
