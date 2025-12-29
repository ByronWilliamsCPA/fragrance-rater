"""
Fragrance Tracker API
Main application entry point.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from app.core.config import settings
from app.db import init_db
from app.api import api_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown events."""
    # Startup
    init_db()
    yield
    # Shutdown (cleanup if needed)


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.VERSION,
    description="""
    Personal fragrance evaluation and recommendation system.

    ## Features
    - Track fragrance evaluations from multiple family members
    - Automatic enrichment from Kaggle datasets, Fragella API, and Fragrantica
    - Build preference profiles to predict what each person will like

    ## Data Sources (Priority Order)
    1. **Local Database** - Previously imported fragrances
    2. **Kaggle Dataset** - Bulk imported fragrance data
    3. **Fragella API** - High-quality API data (20 requests/month limit)
    4. **Fragrantica Scraper** - Fallback web scraping
    5. **Manual Entry** - User-entered data
    """,
    lifespan=lifespan,
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routes
app.include_router(api_router, prefix="/api/v1")


@app.get("/")
def root():
    """Root endpoint with API info."""
    return {
        "name": settings.APP_NAME,
        "version": settings.VERSION,
        "docs": "/docs",
        "openapi": "/openapi.json"
    }


@app.get("/health")
def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}
