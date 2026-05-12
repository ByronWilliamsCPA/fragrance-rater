#!/bin/bash
# Simple development environment startup script
# Starts only the database in Docker, runs backend and frontend locally

set -e

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}======================================"
echo "Starting Fragrance Rater Dev Environment"
echo "======================================${NC}"

# Step 1: Start PostgreSQL in Docker
echo -e "\n${YELLOW}Step 1: Starting PostgreSQL...${NC}"
docker compose up -d db

# Wait for PostgreSQL
echo "Waiting for PostgreSQL to be ready..."
sleep 3
docker compose exec db pg_isready -U fragrance_rater || sleep 2

echo -e "${GREEN}✓ PostgreSQL is ready${NC}"

# Step 2: Run migrations
echo -e "\n${YELLOW}Step 2: Running database migrations...${NC}"
export DATABASE_URL="postgresql+asyncpg://fragrance_rater:password@localhost:5432/fragrance_rater"
uv run alembic upgrade head

echo -e "${GREEN}✓ Migrations complete${NC}"

# Step 3: Instructions for backend
echo -e "\n${YELLOW}Step 3: Start the backend (in a new terminal)${NC}"
echo -e "${BLUE}Run this command:${NC}"
echo ""
echo "  cd /home/byron/dev/fragrance_rater"
echo "  DATABASE_URL=\"postgresql+asyncpg://fragrance_rater:password@localhost:5432/fragrance_rater\" \\"
echo "  LLM_ENABLED=false \\"
echo "  uv run uvicorn fragrance_rater.main:app --reload --host 0.0.0.0 --port 8000"
echo ""

# Step 4: Instructions for frontend
echo -e "\n${YELLOW}Step 4: Start the frontend (in another new terminal)${NC}"
echo -e "${BLUE}Run these commands:${NC}"
echo ""
echo "  cd /home/byron/dev/fragrance_rater/frontend"
echo "  npm install  # (first time only)"
echo "  npm run dev"
echo ""

# Summary
echo -e "\n${GREEN}======================================"
echo "Environment Setup Complete!"
echo "======================================${NC}"
echo ""
echo "Next steps:"
echo "  1. Start backend in terminal 2 (see command above)"
echo "  2. Start frontend in terminal 3 (see command above)"
echo ""
echo "Then access:"
echo "  - Frontend UI:  http://localhost:5173"
echo "  - API Docs:     http://localhost:8000/docs"
echo "  - Health Check: http://localhost:8000/health/live"
echo ""
echo -e "${YELLOW}To stop everything:${NC}"
echo "  - Ctrl+C in backend terminal"
echo "  - Ctrl+C in frontend terminal"
echo "  - Run: docker compose down"
echo ""
