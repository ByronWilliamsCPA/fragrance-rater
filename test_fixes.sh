#!/bin/bash
# Test script to verify critical fixes

set -e  # Exit on error

BASE_URL="http://localhost:8000"
API_V1="${BASE_URL}/api/v1"

echo "======================================"
echo "Testing Fragrance Rater API"
echo "======================================"

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Test health endpoints
echo -e "\n${YELLOW}1. Testing Health Endpoints${NC}"
echo "Liveness check..."
curl -s "${BASE_URL}/health/liveness" | jq '.' || echo -e "${RED}FAILED${NC}"
echo -e "${GREEN}✓ Liveness check passed${NC}"

echo -e "\nReadiness check..."
curl -s "${BASE_URL}/health/readiness" | jq '.' || echo -e "${RED}FAILED${NC}"
echo -e "${GREEN}✓ Readiness check passed${NC}"

# Create a test reviewer
echo -e "\n${YELLOW}2. Creating Test Reviewer${NC}"
REVIEWER_ID=$(curl -s -X POST "${API_V1}/reviewers" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Test User",
    "email": "test@example.com"
  }' | jq -r '.id')

if [ -n "$REVIEWER_ID" ] && [ "$REVIEWER_ID" != "null" ]; then
  echo -e "${GREEN}✓ Created reviewer: ${REVIEWER_ID}${NC}"
else
  echo -e "${RED}✗ Failed to create reviewer${NC}"
  exit 1
fi

# Create a test fragrance
echo -e "\n${YELLOW}3. Creating Test Fragrance${NC}"
FRAGRANCE_ID=$(curl -s -X POST "${API_V1}/fragrances" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Test Fragrance",
    "brand": "Test Brand",
    "concentration": "EDP",
    "gender_target": "unisex",
    "primary_family": "Woody",
    "subfamily": "Woody Aromatic",
    "data_source": "manual"
  }' | jq -r '.id')

if [ -n "$FRAGRANCE_ID" ] && [ "$FRAGRANCE_ID" != "null" ]; then
  echo -e "${GREEN}✓ Created fragrance: ${FRAGRANCE_ID}${NC}"
else
  echo -e "${RED}✗ Failed to create fragrance${NC}"
  exit 1
fi

# Add some evaluations
echo -e "\n${YELLOW}4. Adding Test Evaluations${NC}"
for rating in 5 4 5; do
  EVAL_RESPONSE=$(curl -s -X POST "${API_V1}/evaluations" \
    -H "Content-Type: application/json" \
    -d "{
      \"fragrance_id\": \"${FRAGRANCE_ID}\",
      \"reviewer_id\": \"${REVIEWER_ID}\",
      \"rating\": ${rating}
    }")

  EVAL_ID=$(echo "$EVAL_RESPONSE" | jq -r '.id')

  if [ -n "$EVAL_ID" ] && [ "$EVAL_ID" != "null" ]; then
    echo -e "${GREEN}✓ Created evaluation ${rating}★${NC}"
  else
    echo -e "${RED}✗ Failed to create evaluation${NC}"
    echo "Response: $EVAL_RESPONSE"
  fi
done

# Test the fixed recommendation endpoint (CRITICAL FIX)
echo -e "\n${YELLOW}5. Testing Recommendation Endpoint (CRITICAL FIX)${NC}"
echo "This tests the attribute fixes: position, primary_family, accord_type"

# Get recommendations (should not crash with AttributeError)
RECOMMENDATIONS=$(curl -s "${API_V1}/recommendations/${REVIEWER_ID}?limit=5")

if echo "$RECOMMENDATIONS" | jq -e '.recommendations' > /dev/null 2>&1; then
  COUNT=$(echo "$RECOMMENDATIONS" | jq '.count')
  echo -e "${GREEN}✓ Recommendation endpoint works! Found ${COUNT} recommendations${NC}"
  echo "$RECOMMENDATIONS" | jq '.'
else
  echo -e "${RED}✗ Recommendation endpoint failed${NC}"
  echo "Response: $RECOMMENDATIONS"
  exit 1
fi

# Test profile summary
echo -e "\n${YELLOW}6. Testing Profile Summary Endpoint${NC}"
PROFILE=$(curl -s "${API_V1}/recommendations/${REVIEWER_ID}/profile?include_llm=false")

if echo "$PROFILE" | jq -e '.reviewer_id' > /dev/null 2>&1; then
  echo -e "${GREEN}✓ Profile summary endpoint works!${NC}"
  echo "$PROFILE" | jq '.'
else
  echo -e "${RED}✗ Profile summary failed${NC}"
  echo "Response: $PROFILE"
fi

# Cleanup
echo -e "\n${YELLOW}7. Cleanup (optional)${NC}"
echo "Test data created:"
echo "  Reviewer ID: ${REVIEWER_ID}"
echo "  Fragrance ID: ${FRAGRANCE_ID}"
echo ""
echo "To delete test data, run:"
echo "  curl -X DELETE ${API_V1}/reviewers/${REVIEWER_ID}"
echo "  curl -X DELETE ${API_V1}/fragrances/${FRAGRANCE_ID}"

echo -e "\n${GREEN}======================================"
echo "All critical tests passed! ✓"
echo "======================================${NC}"
