# Fragrance Tracker

A personal fragrance evaluation and recommendation system for family use. Track perfume preferences, build taste profiles, and get AI-powered recommendations.

## Features

- **Multi-person evaluation tracking** - Each family member rates fragrances 1-5 with notes
- **Automatic data enrichment** - Pulls fragrance details from Kaggle datasets, Fragella API, and Fragrantica
- **Preference profiling** - Learns what notes and accords each person likes/dislikes
- **AI-powered recommendations** - Uses OpenRouter LLM to explain matches and suggest new fragrances
- **Note tracking** - Bayden likes citrus but not lemon? The system remembers

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    DOCKER COMPOSE STACK                     │
├─────────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │
│  │   React     │  │   FastAPI   │  │     PostgreSQL      │  │
│  │  Frontend   │◄─│   Backend   │◄─│     Database        │  │
│  │  :3000      │  │   :8000     │  │     :5432           │  │
│  └─────────────┘  └──────┬──────┘  └─────────────────────┘  │
│                          │                                   │
│         ┌────────────────┼────────────────┐                  │
│         ▼                ▼                ▼                  │
│   ┌──────────┐    ┌──────────┐    ┌──────────────┐          │
│   │ Fragella │    │Fragrantica│   │  OpenRouter  │          │
│   │   API    │    │ Scraper   │   │  (LLM Recs)  │          │
│   └──────────┘    └──────────┘    └──────────────┘          │
└─────────────────────────────────────────────────────────────┘
```

### Data Source Priority

1. **Local Database** - Previously imported fragrances
2. **Kaggle Dataset** - Bulk import from downloaded CSVs
3. **Fragella API** - High-quality API (20 req/month free)
4. **Fragrantica Scraper** - Web scraping fallback
5. **Manual Entry** - User-entered data

Each record tracks its source for future updates.

## Quick Start

### 1. Clone and Configure

```bash
cd fragrance-tracker
cp .env.example .env
```

Edit `.env` with your API keys:

```env
# Required
POSTGRES_PASSWORD=your_secure_password

# Optional but recommended
FRAGELLA_API_KEY=your_fragella_key      # Get from api.fragella.com
OPENROUTER_API_KEY=your_openrouter_key  # Get from openrouter.ai
```

### 2. Start Services

```bash
docker-compose up -d
```

Services will be available at:
- Frontend: http://localhost:3000
- API: http://localhost:8000
- API Docs: http://localhost:8000/docs

### 3. Initialize Data

1. Open http://localhost:3000/import
2. Click "Create Family Reviewers" to add Byron, Veronica, Bayden, Ariannah
3. Download a Kaggle dataset (links provided on Import page)
4. Upload the CSV to populate the fragrance database

### 4. Start Evaluating!

Go to http://localhost:3000/evaluate and start rating perfumes.

## Usage Guide

### Evaluating Fragrances

1. Go to **Evaluate** page
2. Type fragrance name (auto-searches database)
3. Select who's reviewing
4. Give 1-5 stars
5. Add optional notes

If a fragrance isn't found locally, the system will automatically:
- Check Fragella API (if configured)
- Scrape Fragrantica (fallback)
- Create a basic entry for manual completion

### Viewing Recommendations

After 3+ evaluations, each person's profile page shows:
- Preference summary (AI-generated if OpenRouter configured)
- Preferred and disliked notes
- Ranked recommendations from the database
- AI suggestions for new fragrances to try

### Understanding Scores

- **Match Score** - How well a fragrance matches preference profile (0-100%)
- **Reasons** - Why it might work (e.g., "Contains bergamot which you love")
- **Warnings** - Potential issues (e.g., "Contains lemon which you dislike")

## API Reference

Full OpenAPI docs at http://localhost:8000/docs

Key endpoints:

```
# Fragrances
GET  /api/v1/fragrances                    # List/search
GET  /api/v1/fragrances/{id}               # Get details
POST /api/v1/fragrances/lookup             # Search & import from external

# Evaluations
GET  /api/v1/evaluations                   # List
POST /api/v1/evaluations                   # Create
POST /api/v1/evaluate                      # Quick entry with auto-lookup

# Recommendations
GET  /api/v1/recommendations/{reviewer_id}           # Get recommendations
GET  /api/v1/recommendations/{reviewer_id}/profile   # Preference profile
GET  /api/v1/recommendations/{reviewer_id}/suggest   # AI suggestions

# Import
POST /api/v1/import/kaggle                 # Upload CSV
POST /api/v1/import/seed-reviewers         # Create default reviewers
```

## Fragrance Classification

Based on the Michael Edwards Fragrance Wheel:

### Primary Families (4)
- **Fresh** - Citrus, aromatic, green, aquatic
- **Floral** - Flower-forward scents
- **Amber** (Oriental) - Warm, spicy, vanilla
- **Woody** - Cedar, sandalwood, vetiver

### Subfamilies (14)
Fresh: Aromatic, Citrus, Water, Green, Fruity
Floral: Floral, Soft Floral, Floral Amber
Amber: Soft Amber, Amber, Woody Amber
Woody: Woods, Mossy Woods, Dry Woods

### Note Pyramid
- **Top Notes** - First impression (5-20 min)
- **Heart Notes** - Core character (20 min - 2 hrs)
- **Base Notes** - Lasting foundation (2+ hrs)

## Development

### Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

### Database Migrations

Using Alembic (when schema changes):

```bash
cd backend
alembic revision --autogenerate -m "Description"
alembic upgrade head
```

## Configuration

| Variable | Required | Description |
|----------|----------|-------------|
| `POSTGRES_PASSWORD` | Yes | Database password |
| `FRAGELLA_API_KEY` | No | Fragella API key (20 req/month free) |
| `OPENROUTER_API_KEY` | No | OpenRouter key for LLM recommendations |
| `SECRET_KEY` | No | JWT secret (default provided) |

## Contributing

This is a personal/family project, but suggestions welcome!

## License

MIT
