# Project Vision & Scope: Fragrance Rater

> **Status**: Active | **Version**: 1.0 | **Updated**: 2025-12-28

## TL;DR

A personal fragrance evaluation and recommendation system for the Williams family (Byron, Veronica, Bayden, Ariannah). Users rate perfumes with simple 1-5 ratings and free-form notes; the system enriches entries with professional fragrance classification data and uses AI-powered preference analysis to predict which new fragrances each person would enjoy.

## Problem Statement

### Pain Point

Selecting perfumes for family members is expensive trial-and-error because:

- Personal scent preferences are highly individual and difficult to articulate
- The fragrance industry uses specialized vocabulary (notes, accords, families) that consumers don't know
- Without systematic tracking, patterns in what someone likes/dislikes remain invisible
- Nuanced preferences are hard to remember (e.g., "Bayden likes citrus but specifically dislikes lemon")

### Target Users

- **Primary**: Williams family (4 members) evaluating fragrances together
- **Context**: In-store testing, home collection evaluation, gift selection

### Success Metrics

- **Evaluations captured**: 0 → 50+ evaluations within first month
- **Preference accuracy**: After 10+ evaluations, 80%+ of AI recommendations marked "interesting" by user (via thumbs-up/down on recommendation cards)
- **Time to evaluate**: < 30 seconds per rating entry

## Solution Overview

### Core Value

Track fragrance ratings from multiple family members, automatically enrich with professional classification data, and use AI to explain preferences and predict new fragrance matches.

### Key Capabilities (MVP)

1. **Multi-user evaluation entry**: Each family member rates fragrances 1-5 with optional notes
2. **Automatic data enrichment**: Pulls notes, accords, and family classification from external sources
3. **Preference profiling**: Learns which notes/accords each person likes or dislikes
4. **AI-powered recommendations**: LLM generates explanations and suggests new fragrances

## Scope Definition

### In Scope (MVP)

- **Evaluation CRUD**: Create, read, update, delete ratings for any family member
- **User selection**: Simple dropdown to switch between pre-seeded family profiles (no authentication)
- **Fragrance lookup**: Search local DB with tiered data acquisition:
  1. **Bulk seed**: One-time Kaggle dataset import for baseline offline data
  2. **Manual fallback**: Copy-paste notes from Fragrantica when fragrance not found
  3. **API enrichment**: Fragella API to enhance manually-entered fragrances (preserves scarce API calls)
- **Preference profiles**: Show liked/disliked notes per user with confidence scores
- **Basic recommendations**: Match score calculation with AI-generated explanations
- **Recommendation feedback**: Thumbs-up/down on recommendations to measure accuracy
- **Simple web UI**: Mobile-friendly React frontend for in-store use (requires home network connection)

### Out of Scope

- **User authentication**: Family-only use, no login required initially
- **Price tracking**: No retail/shopping integrations
- **Barcode scanning**: Manual fragrance search only
- **Social features**: No sharing or public profiles
- **Advanced ML**: Simple weighted scoring first; collaborative filtering deferred

### Deferred to Phase 2+

- **Natural language processing** of free-form notes
- **Collection/wishlist management**
- **Retailer availability integration**
- **Mobile native app**

## Constraints

### Technical

- **Platform**: Self-hosted Docker Compose on Unraid server
- **Language**: Python 3.12 (backend), React/TypeScript (frontend)
- **Database**: PostgreSQL (structured fragrance data)
- **Performance**: API response < 500ms, UI usable on mobile

### Business

- **Budget**: Minimal - prefer free data sources (Kaggle, scraping) over paid APIs
- **Resources**: Single developer (Byron), family beta testers
- **Maintenance**: Low-touch after initial build
- **Connectivity**: Requires connection to home LAN (Unraid server); true offline/PWA deferred to Phase 2

## Assumptions to Validate

- [ ] Kaggle fragrance datasets have adequate note/accord data for bulk seed
- [ ] OpenRouter LLM costs acceptable for recommendation explanations (~$0.01-0.05 per recommendation)
- [ ] Family members will consistently use the system after initial novelty
- [ ] Home LAN connectivity sufficient for in-store use (VPN or mobile hotspot)

## Related Documents

- [Architecture Decisions](./adr/)
- [Technical Spec](./tech-spec.md)
- [Roadmap](./roadmap.md)
