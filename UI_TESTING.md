# UI Testing Guide for Fragrance Rater

## Overview

The Fragrance Rater has two components:
1. **Backend API** (FastAPI with Python) - what we just fixed
2. **Frontend UI** (React with TypeScript) - located in `frontend/`

## Quick Start: Test the Full Stack

### Option 1: Docker Compose (Recommended)

Start everything with one command:

```bash
# Start all services
docker-compose up -d

# View logs
docker-compose logs -f

# Services started:
# - PostgreSQL (port 5432)
# - Backend API (port 8000)
# - Frontend UI (port 3000)
```

Then access:
- **Frontend UI**: http://localhost:3000
- **API Docs**: http://localhost:8000/docs
- **Health Check**: http://localhost:8000/health

### Option 2: Manual Setup

#### Terminal 1: Backend API

```bash
# Set up database
export DATABASE_URL="postgresql+asyncpg://fragrance_rater:password@localhost:5432/fragrance_rater"

# Run migrations
uv run alembic upgrade head

# Start API server
uv run uvicorn fragrance_rater.main:app --reload --host 0.0.0.0 --port 8000
```

#### Terminal 2: Frontend UI

```bash
# Navigate to frontend
cd frontend

# Install dependencies (first time only)
npm install

# Start development server
npm run dev

# Frontend will be available at http://localhost:5173 (Vite default)
```

## Frontend Features to Test

Based on the `frontend/` directory structure, the UI should include:

### 1. Home Page
- Project overview
- Navigation to different sections

### 2. Fragrance Management
- List all fragrances
- Add new fragrances
- View fragrance details (with notes and accords)
- Search and filter fragrances

### 3. Evaluation/Rating
- Rate fragrances (1-5 stars)
- View your evaluation history
- See which fragrances you've rated

### 4. Recommendations
- **This is what we fixed!**
- View personalized recommendations based on your ratings
- See match percentages
- View why a fragrance matches your preferences

### 5. Reviewer Profile
- View your preference profile
- See your top liked/disliked notes
- See your preferred fragrance families
- View LLM-generated summary of your preferences

## Testing the Critical Fixes via UI

The fixes we made will be visible when:

1. **Viewing Fragrance Details**
   - Notes should display correctly (top/heart/base)
   - Family should show correctly
   - Accords should display properly

2. **Getting Recommendations**
   - Should not crash (was crashing before)
   - Match percentages should appear
   - Fragrance families should be correct

3. **Viewing Profile**
   - Should show your preferences
   - No crashes when viewing notes/accords

## Frontend Structure

```
frontend/
├── src/
│   ├── App.tsx          # Main application component
│   ├── components/      # React components
│   ├── hooks/          # Custom React hooks
│   ├── services/       # API client code
│   └── types/          # TypeScript type definitions
├── index.html          # HTML entry point
└── package.json        # Dependencies
```

## API Endpoints Used by Frontend

The frontend will call these endpoints (all fixed):

```typescript
// Fragrances
GET    /api/v1/fragrances              // List fragrances
POST   /api/v1/fragrances              // Create fragrance
GET    /api/v1/fragrances/{id}         // Get fragrance (uses primary_family)

// Evaluations
POST   /api/v1/evaluations             // Rate a fragrance
GET    /api/v1/evaluations/{id}        // Get evaluation

// Recommendations (CRITICAL FIXES HERE)
GET    /api/v1/recommendations/{reviewer_id}
    // This was crashing - now uses position, primary_family, accord_type

GET    /api/v1/recommendations/{reviewer_id}/profile
    // Profile summary - also fixed

GET    /api/v1/recommendations/{reviewer_id}/{fragrance_id}/explain
    // LLM explanation - also fixed
```

## Common Issues & Solutions

### Frontend Won't Start

```bash
# Clean install
cd frontend
rm -rf node_modules package-lock.json
npm install
npm run dev
```

### API Connection Errors

Check `.env` or environment variables:

```bash
# Backend should be running on port 8000
curl http://localhost:8000/health

# Frontend API client should point to correct backend URL
# Check frontend/.env or frontend/src/config
```

### CORS Errors

The backend should already have CORS configured in `main.py`. If you see CORS errors:

```python
# In src/fragrance_rater/main.py
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

## Database Schema Mismatch Note

⚠️ **Important**: The test revealed that the `parfumo_url` field exists in the `Fragrance` model but is missing from the Alembic migration. You may need to:

1. Add migration for `parfumo_url` column, OR
2. Remove `parfumo_url` from the model temporarily

To fix (option 1 - add column):

```bash
# Create new migration
uv run alembic revision --autogenerate -m "Add parfumo_url to fragrances"

# Review the generated migration
# Edit if needed, then apply
uv run alembic upgrade head
```

## UI Testing Checklist

- [ ] Homepage loads
- [ ] Can view list of fragrances
- [ ] Can create a new fragrance
- [ ] Can view fragrance details (notes display correctly)
- [ ] Can rate a fragrance (1-5 stars)
- [ ] Can view recommendations (doesn't crash!)
- [ ] Match percentages display
- [ ] Can view profile summary
- [ ] Profile shows liked/disliked notes

## Development Workflow

```bash
# Terminal 1: Backend with auto-reload
uv run uvicorn fragrance_rater.main:app --reload

# Terminal 2: Frontend with hot reload
cd frontend && npm run dev

# Make changes, both will auto-reload!
```

## Production Build

```bash
# Build frontend
cd frontend
npm run build

# Output in frontend/dist/
# Serve with backend or separate web server
```

## Next Steps

1. **Fix the schema mismatch** (parfumo_url)
2. **Test the UI** to verify fixes work end-to-end
3. **Add UI tests** if needed
4. **Consider adding E2E tests** (Playwright, Cypress)

## Screenshots/Demos

Once the UI is running, you can:
1. Create a reviewer profile
2. Add some fragrances
3. Rate them
4. View recommendations
5. See your preference profile

The recommendations page is where you'll see the **critical fixes in action** - it should display properly without crashing now!
