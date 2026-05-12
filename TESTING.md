# Testing Guide for Fragrance Rater

## Quick Start Testing

### Option 1: Comprehensive Test with Temporary Database (Recommended)

This runs all tests with an isolated PostgreSQL container:

```bash
./test_with_postgres.sh
```

This script will:
1. ✓ Start a temporary PostgreSQL container
2. ✓ Run database migrations
3. ✓ Run critical fixes verification
4. ✓ Run unit tests with coverage
5. ✓ Start the API server
6. ✓ Run integration tests
7. ✓ Clean up automatically

**Requirements**:
- Docker installed and running
- `jq` installed (`sudo apt install jq` or `brew install jq`)

### Option 2: Python Critical Fixes Test

Test only the critical fixes without starting a server:

```bash
# Set up database first
export DATABASE_URL="postgresql+asyncpg://user:pass@localhost:5432/dbname"
uv run alembic upgrade head

# Run verification tests
uv run python test_critical_fixes.py
```

### Option 3: Manual Testing with Docker Compose

```bash
# Start all services
docker-compose up -d

# Run migrations
uv run alembic upgrade head

# Start development server
uv run uvicorn fragrance_rater.main:app --reload

# Access API docs
open http://localhost:8000/docs
```

## What Gets Tested

### Critical Fixes Verified

1. **Type Errors Fixed** ✓
   - `FragranceNote.position` (was `note_type`)
   - `Fragrance.primary_family` (was `family`)
   - `FragranceAccord.accord_type` (was `accord`)
   - `Field(default=None)` syntax in health checks

2. **Exception Handling** ✓
   - `SQLAlchemyError` instead of bare `Exception`
   - Proper rollback on database errors

3. **Logger Calls** ✓
   - All logger calls use proper string formatting
   - Print statements replaced with `logger.error()`

4. **Integration** ✓
   - Health endpoints work
   - Recommendation endpoint doesn't crash
   - Profile summary endpoint works
   - Database sessions work correctly

## Test Coverage

Current coverage: **20.95%** (Target: **80%**)

Run coverage report:

```bash
uv run pytest --cov=src/fragrance_rater --cov-report=html
open htmlcov/index.html
```

## Manual API Testing

### 1. Health Checks

```bash
# Liveness (is app running?)
curl http://localhost:8000/health/liveness | jq

# Readiness (can serve traffic?)
curl http://localhost:8000/health/readiness | jq

# Full health check
curl http://localhost:8000/health | jq
```

### 2. Create Test Data

```bash
# Create reviewer
REVIEWER=$(curl -X POST http://localhost:8000/api/v1/reviewers \
  -H "Content-Type: application/json" \
  -d '{"name": "Byron", "email": "byron@example.com"}' | jq)

REVIEWER_ID=$(echo $REVIEWER | jq -r '.id')

# Create fragrance
FRAGRANCE=$(curl -X POST http://localhost:8000/api/v1/fragrances \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Aventus",
    "brand": "Creed",
    "concentration": "EDP",
    "gender_target": "masculine",
    "primary_family": "Fresh",
    "subfamily": "Citrus",
    "data_source": "manual"
  }' | jq)

FRAGRANCE_ID=$(echo $FRAGRANCE | jq -r '.id')

# Add evaluation
curl -X POST http://localhost:8000/api/v1/evaluations \
  -H "Content-Type: application/json" \
  -d "{
    \"fragrance_id\": \"$FRAGRANCE_ID\",
    \"reviewer_id\": \"$REVIEWER_ID\",
    \"rating\": 5
  }" | jq
```

### 3. Test Recommendations (Critical Fix)

```bash
# Get recommendations (this was crashing before the fixes)
curl "http://localhost:8000/api/v1/recommendations/${REVIEWER_ID}?limit=10" | jq

# Get profile summary
curl "http://localhost:8000/api/v1/recommendations/${REVIEWER_ID}/profile?include_llm=false" | jq
```

## Environment Variables for Testing

```bash
# Minimal configuration for testing
export DATABASE_URL="postgresql+asyncpg://fragrance_rater:password@localhost:5432/fragrance_rater_test"
export DEBUG=true
export LOG_LEVEL=DEBUG
export LLM_ENABLED=false  # Disable LLM for faster tests
```

## Troubleshooting

### PostgreSQL Connection Issues

```bash
# Check if PostgreSQL is running
docker ps | grep postgres

# Check PostgreSQL logs
docker logs <postgres-container-name>

# Test connection
docker exec <postgres-container-name> pg_isready -U fragrance_rater
```

### API Server Issues

```bash
# Check if server is running
curl http://localhost:8000/health/liveness

# View server logs
# (server outputs to stdout when run with --reload)

# Kill existing server
pkill -f uvicorn
```

### Database Migration Issues

```bash
# Check migration status
uv run alembic current

# View migration history
uv run alembic history

# Rollback one migration
uv run alembic downgrade -1

# Reset database (nuclear option)
docker-compose down -v
docker-compose up -d
uv run alembic upgrade head
```

## Pre-Commit Testing

Before committing, run:

```bash
# Format and lint
uv run ruff format .
uv run ruff check . --fix

# Type check
uv run basedpyright src/

# Run tests
uv run pytest

# Pre-commit hooks
pre-commit run --all-files
```

## Continuous Integration

The GitHub Actions workflow runs:
1. Linting (Ruff)
2. Type checking (BasedPyright)
3. Security scanning (Bandit)
4. Unit tests with coverage
5. Integration tests

View results at: https://github.com/ByronWilliamsCPA/fragrance-rater/actions

## Next Steps

After verifying fixes work:

1. **Add more tests** to reach 80% coverage
2. **Add RAD assumption tags** to critical paths
3. **Create pull request** with these fixes
4. **Run full CI/CD pipeline**

## Interactive API Documentation

Once the server is running, access interactive docs:

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

These provide:
- Full API reference
- Try-it-out functionality
- Request/response examples
- Schema documentation
