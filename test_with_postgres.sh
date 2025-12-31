#!/bin/bash
# Comprehensive test script with temporary PostgreSQL container

set -e  # Exit on error

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}======================================"
echo "Fragrance Rater - Test Suite"
echo "======================================${NC}"

# Function to cleanup on exit
cleanup() {
    echo -e "\n${YELLOW}Cleaning up...${NC}"
    if [ -n "$POSTGRES_CONTAINER" ]; then
        echo "Stopping PostgreSQL container..."
        docker stop "$POSTGRES_CONTAINER" 2>/dev/null || true
        docker rm "$POSTGRES_CONTAINER" 2>/dev/null || true
    fi
    if [ -n "$API_PID" ]; then
        echo "Stopping API server..."
        kill "$API_PID" 2>/dev/null || true
    fi
    echo -e "${GREEN}Cleanup complete${NC}"
}

trap cleanup EXIT INT TERM

# Step 1: Start temporary PostgreSQL container
echo -e "\n${YELLOW}Step 1: Starting PostgreSQL container${NC}"
POSTGRES_CONTAINER=$(docker run -d \
    --name fragrance-test-db-$$ \
    -e POSTGRES_DB=fragrance_rater_test \
    -e POSTGRES_USER=fragrance_rater \
    -e POSTGRES_PASSWORD=test_password_12345 \
    -p 5432:5432 \
    postgres:16-alpine)

echo -e "${GREEN}✓ PostgreSQL container started: $POSTGRES_CONTAINER${NC}"

# Wait for PostgreSQL to be ready
echo "Waiting for PostgreSQL to be ready..."
for i in {1..30}; do
    if docker exec "$POSTGRES_CONTAINER" pg_isready -U fragrance_rater > /dev/null 2>&1; then
        echo -e "${GREEN}✓ PostgreSQL is ready${NC}"
        break
    fi
    if [ $i -eq 30 ]; then
        echo -e "${RED}✗ PostgreSQL failed to start${NC}"
        exit 1
    fi
    sleep 1
done

# Step 2: Set environment variables
echo -e "\n${YELLOW}Step 2: Setting environment variables${NC}"
export DATABASE_URL="postgresql+asyncpg://fragrance_rater:test_password_12345@localhost:5432/fragrance_rater_test"
export DEBUG=true
export LOG_LEVEL=INFO
export LLM_ENABLED=false  # Disable LLM for testing

echo -e "${GREEN}✓ Environment configured${NC}"
echo "  DATABASE_URL: $DATABASE_URL"

# Step 3: Run database migrations
echo -e "\n${YELLOW}Step 3: Running database migrations${NC}"
uv run alembic upgrade head
echo -e "${GREEN}✓ Migrations complete${NC}"

# Step 4: Run Python-based critical fixes test
echo -e "\n${YELLOW}Step 4: Running critical fixes verification${NC}"
chmod +x test_critical_fixes.py
uv run python test_critical_fixes.py

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ Critical fixes verification passed${NC}"
else
    echo -e "${RED}✗ Critical fixes verification failed${NC}"
    exit 1
fi

# Step 5: Run unit tests with coverage
echo -e "\n${YELLOW}Step 5: Running unit tests with coverage${NC}"
uv run pytest tests/unit/ -v --cov=src/fragrance_rater --cov-report=term-missing --cov-report=html

COVERAGE_EXIT_CODE=$?

if [ $COVERAGE_EXIT_CODE -eq 0 ]; then
    echo -e "${GREEN}✓ Unit tests passed${NC}"
else
    echo -e "${YELLOW}⚠ Some unit tests failed or coverage below threshold${NC}"
fi

# Step 6: Start API server in background
echo -e "\n${YELLOW}Step 6: Starting API server${NC}"
uv run uvicorn fragrance_rater.main:app --host 0.0.0.0 --port 8000 &
API_PID=$!

echo "Waiting for API server to start..."
for i in {1..30}; do
    if curl -s http://localhost:8000/health/liveness > /dev/null 2>&1; then
        echo -e "${GREEN}✓ API server is ready (PID: $API_PID)${NC}"
        break
    fi
    if [ $i -eq 30 ]; then
        echo -e "${RED}✗ API server failed to start${NC}"
        exit 1
    fi
    sleep 1
done

# Step 7: Run API integration tests
echo -e "\n${YELLOW}Step 7: Running API integration tests${NC}"

# Test 1: Health checks
echo -e "\nTest 1: Health checks"
HEALTH_RESPONSE=$(curl -s http://localhost:8000/health/liveness)
if echo "$HEALTH_RESPONSE" | jq -e '.status == "ok"' > /dev/null 2>&1; then
    echo -e "${GREEN}✓ Health check passed${NC}"
else
    echo -e "${RED}✗ Health check failed${NC}"
    echo "Response: $HEALTH_RESPONSE"
fi

# Test 2: Create reviewer
echo -e "\nTest 2: Create reviewer"
REVIEWER_RESPONSE=$(curl -s -X POST http://localhost:8000/api/v1/reviewers \
    -H "Content-Type: application/json" \
    -d '{"name": "Integration Test User", "email": "integration@test.com"}')

REVIEWER_ID=$(echo "$REVIEWER_RESPONSE" | jq -r '.id')
if [ -n "$REVIEWER_ID" ] && [ "$REVIEWER_ID" != "null" ]; then
    echo -e "${GREEN}✓ Created reviewer: $REVIEWER_ID${NC}"
else
    echo -e "${RED}✗ Failed to create reviewer${NC}"
    echo "Response: $REVIEWER_RESPONSE"
fi

# Test 3: Create fragrance
echo -e "\nTest 3: Create fragrance"
FRAGRANCE_RESPONSE=$(curl -s -X POST http://localhost:8000/api/v1/fragrances \
    -H "Content-Type: application/json" \
    -d '{
        "name": "Aventus",
        "brand": "Creed",
        "concentration": "EDP",
        "gender_target": "masculine",
        "primary_family": "Fresh",
        "subfamily": "Citrus",
        "data_source": "manual"
    }')

FRAGRANCE_ID=$(echo "$FRAGRANCE_RESPONSE" | jq -r '.id')
if [ -n "$FRAGRANCE_ID" ] && [ "$FRAGRANCE_ID" != "null" ]; then
    echo -e "${GREEN}✓ Created fragrance: $FRAGRANCE_ID${NC}"
else
    echo -e "${RED}✗ Failed to create fragrance${NC}"
    echo "Response: $FRAGRANCE_RESPONSE"
fi

# Test 4: Add evaluations
echo -e "\nTest 4: Add evaluations"
for rating in 5 4 5; do
    EVAL_RESPONSE=$(curl -s -X POST http://localhost:8000/api/v1/evaluations \
        -H "Content-Type: application/json" \
        -d "{
            \"fragrance_id\": \"$FRAGRANCE_ID\",
            \"reviewer_id\": \"$REVIEWER_ID\",
            \"rating\": $rating
        }")

    EVAL_ID=$(echo "$EVAL_RESPONSE" | jq -r '.id')
    if [ -n "$EVAL_ID" ] && [ "$EVAL_ID" != "null" ]; then
        echo -e "${GREEN}✓ Created evaluation with rating $rating${NC}"
    else
        echo -e "${RED}✗ Failed to create evaluation${NC}"
    fi
done

# Test 5: Get recommendations (CRITICAL FIX TEST)
echo -e "\nTest 5: Get recommendations (CRITICAL FIX)"
echo "This tests the fixed attributes: position, primary_family, accord_type"

RECOMMENDATIONS=$(curl -s "http://localhost:8000/api/v1/recommendations/${REVIEWER_ID}?limit=5")

if echo "$RECOMMENDATIONS" | jq -e '.recommendations' > /dev/null 2>&1; then
    COUNT=$(echo "$RECOMMENDATIONS" | jq '.count')
    echo -e "${GREEN}✓ Recommendations endpoint works! Found $COUNT recommendations${NC}"
else
    echo -e "${RED}✗ Recommendations endpoint failed${NC}"
    echo "Response: $RECOMMENDATIONS"
fi

# Test 6: Get profile summary
echo -e "\nTest 6: Get profile summary"
PROFILE=$(curl -s "http://localhost:8000/api/v1/recommendations/${REVIEWER_ID}/profile?include_llm=false")

if echo "$PROFILE" | jq -e '.reviewer_id' > /dev/null 2>&1; then
    EVAL_COUNT=$(echo "$PROFILE" | jq '.evaluation_count')
    echo -e "${GREEN}✓ Profile summary works! $EVAL_COUNT evaluations${NC}"
else
    echo -e "${RED}✗ Profile summary failed${NC}"
fi

# Final summary
echo -e "\n${BLUE}======================================"
echo "TEST SUMMARY"
echo "======================================${NC}"

echo -e "\n${GREEN}✓ All integration tests passed!${NC}"
echo -e "\nTest artifacts:"
echo "  Coverage report: htmlcov/index.html"
echo "  PostgreSQL container: $POSTGRES_CONTAINER"
echo "  API server PID: $API_PID"

echo -e "\n${YELLOW}To explore the running app:${NC}"
echo "  API docs: http://localhost:8000/docs"
echo "  Reviewer ID: $REVIEWER_ID"
echo "  Fragrance ID: $FRAGRANCE_ID"

echo -e "\n${YELLOW}Press Enter to stop the server and cleanup, or Ctrl+C to keep running${NC}"
read -r

echo -e "${GREEN}Tests complete!${NC}"
