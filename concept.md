# Fragrance Preference Tracker
## Project Concept Document

### Executive Summary

A personal fragrance evaluation and recommendation system designed for family use. The application captures subjective perfume ratings from multiple family members while automatically enriching entries with structured fragrance classification data. Over time, the system builds individual preference profiles that can predict which new fragrances each person would likely enjoy.

**Target Users:** Byron, Veronica, Bayden, Ariannah

---

## 1. Problem Statement

Selecting perfumes for family members is challenging because:
- Personal scent preferences are highly individual and difficult to articulate
- The fragrance industry uses specialized vocabulary (notes, accords, families) that most consumers don't know
- Without systematic tracking, it's hard to identify patterns in what someone likes or dislikes
- Trial and error is expensive and time-consuming

**Known Preference Example:** Bayden prefers citrus-forward scents but specifically dislikes lemon. This kind of nuanced preference is exactly what the system should capture and predict.

---

## 2. Classification Framework

### 2.1 The Michael Edwards Fragrance Wheel

The industry-standard classification system, analogous to the UC Davis Wine Aroma Wheel. Created in 1992 and continuously refined, it organizes all fragrances into a hierarchical taxonomy.

#### Primary Families (4)

| Family | Character | Typical Notes |
|--------|-----------|---------------|
| **Fresh** | Light, energetic, daytime | Citrus, herbs, aquatic |
| **Floral** | Feminine, romantic | Rose, jasmine, lily |
| **Amber** (formerly Oriental) | Warm, sensual, exotic | Vanilla, resins, spices |
| **Woody** | Earthy, grounding | Cedar, sandalwood, vetiver |

#### Subfamilies (14)

```
FRESH FAMILY
├── Aromatic (Fougère) - Lavender, herbs, coumarin
├── Citrus - Bergamot, lemon, grapefruit, mandarin
├── Water (Aquatic) - Marine, ozonic, rain
├── Green - Cut grass, leaves, cucumber
└── Fruity - Berries, apple, peach (non-citrus)

FLORAL FAMILY
├── Floral - Single flower or bouquet
├── Soft Floral - Powdery, aldehydic florals
└── Floral Amber - Florals with oriental warmth

AMBER FAMILY
├── Soft Amber - Light resins, incense
├── Amber - Full oriental: vanilla, resins, spices
└── Woody Amber - Oriental + sandalwood/patchouli

WOODY FAMILY
├── Woods - Clean cedar, sandalwood, vetiver
├── Mossy Woods - Oakmoss, patchouli, chypre
└── Dry Woods - Leather, tobacco, smoky woods
```

#### Intensity Gradations

Within each subfamily, fragrances are further classified as:
- **Fresh** - Lightest, most volatile interpretation
- **Crisp** - Clean, defined
- **Classical** - Traditional, balanced
- **Rich** - Deepest, most intense

### 2.2 The Olfactory Pyramid (Note Structure)

Every fragrance unfolds in three temporal phases based on molecular volatility:

```
         ┌─────────────┐
         │  TOP NOTES  │  5-20 minutes
         │   (Head)    │  First impression
         ├─────────────┤  Citrus, light fruits, herbs
         │             │
         │ HEART NOTES │  20 min - 2+ hours
         │  (Middle)   │  Core character
         │             │  Florals, spices, fruits
         ├─────────────┤
         │             │
         │ BASE NOTES  │  2+ hours to days
         │   (Soul)    │  Lasting foundation
         │             │  Woods, musks, vanilla, amber
         └─────────────┘
```

### 2.3 Accords

Accords are perceptual descriptors of how a fragrance "feels" overall, independent of specific ingredients:

**Common Accords:**
- Sweet, Fresh, Warm Spicy, Citrus, Floral, Powdery
- Woody, Balsamic, Musky, Green, Aquatic
- Fruity, Aromatic, Leather, Smoky, Earthy
- Gourmand (edible-smelling), Oriental, Animal

---

## 3. Data Model

### 3.1 Core Entities

```
┌─────────────────────────────────────────────────────────────┐
│                        FRAGRANCE                            │
├─────────────────────────────────────────────────────────────┤
│ id: UUID                                                    │
│ name: String                                                │
│ brand: String                                               │
│ concentration: Enum [EDT, EDP, Parfum, Cologne, etc.]       │
│ launch_year: Integer (nullable)                             │
│ gender_target: Enum [Feminine, Masculine, Unisex]           │
│                                                             │
│ # Classification                                            │
│ primary_family: Enum [Fresh, Floral, Amber, Woody]          │
│ subfamily: Enum [14 options]                                │
│ intensity: Enum [Fresh, Crisp, Classical, Rich]             │
│                                                             │
│ # Note Pyramid                                              │
│ top_notes: Array<NoteReference>                             │
│ heart_notes: Array<NoteReference>                           │
│ base_notes: Array<NoteReference>                            │
│                                                             │
│ # Accords (with intensity weights 0.0-1.0)                  │
│ accords: Map<AccordType, Float>                             │
│                                                             │
│ # Metadata                                                  │
│ data_source: Enum [Manual, Fragrantica, Fragella, etc.]     │
│ external_id: String (nullable)                              │
│ created_at: Timestamp                                       │
│ updated_at: Timestamp                                       │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│                          NOTE                               │
├─────────────────────────────────────────────────────────────┤
│ id: UUID                                                    │
│ name: String                                                │
│ category: Enum [Citrus, Floral, Spice, Wood, Musk, etc.]    │
│ subcategory: String (nullable)                              │
│ description: Text (nullable)                                │
│ synonyms: Array<String>                                     │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│                        REVIEWER                             │
├─────────────────────────────────────────────────────────────┤
│ id: UUID                                                    │
│ name: String                                                │
│ created_at: Timestamp                                       │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│                        EVALUATION                           │
├─────────────────────────────────────────────────────────────┤
│ id: UUID                                                    │
│ fragrance_id: UUID (FK)                                     │
│ reviewer_id: UUID (FK)                                      │
│ rating: Integer [1-5]                                       │
│ notes: Text (free-form observations)                        │
│                                                             │
│ # Optional structured feedback                              │
│ longevity_rating: Integer [1-5] (nullable)                  │
│ sillage_rating: Integer [1-5] (nullable)                    │
│ season_preference: Array<Enum> (nullable)                   │
│ occasion_tags: Array<String> (nullable)                     │
│                                                             │
│ evaluated_at: Timestamp                                     │
│ created_at: Timestamp                                       │
└─────────────────────────────────────────────────────────────┘
```

### 3.2 Computed/Derived Entities

```
┌─────────────────────────────────────────────────────────────┐
│                   REVIEWER_PREFERENCE                       │
├─────────────────────────────────────────────────────────────┤
│ reviewer_id: UUID (FK)                                      │
│ computed_at: Timestamp                                      │
│                                                             │
│ # Aggregated preferences (weighted by ratings)              │
│ family_scores: Map<Family, Float>                           │
│ subfamily_scores: Map<Subfamily, Float>                     │
│ note_affinities: Map<NoteID, Float>  # positive/negative    │
│ accord_affinities: Map<AccordType, Float>                   │
│                                                             │
│ # Identified patterns                                       │
│ preferred_notes: Array<NoteID>                              │
│ disliked_notes: Array<NoteID>                               │
│ preferred_families: Array<Family>                           │
│ preferred_intensity: Enum                                   │
│                                                             │
│ # Sample size / confidence                                  │
│ evaluation_count: Integer                                   │
│ confidence_score: Float                                     │
└─────────────────────────────────────────────────────────────┘
```

---

## 4. External Data Sources

### 4.1 Primary: Fragrantica

**URL:** https://www.fragrantica.com
**Data Available:**
- 60,000+ fragrances
- Top/heart/base notes
- Main accords (with visual intensity bars)
- User ratings, longevity, sillage
- Seasonal and occasion recommendations

**Access Method:** Web scraping (no official API)
**Consideration:** Terms of service compliance; rate limiting

### 4.2 Alternative: Fragella API

**URL:** https://api.fragella.com
**Data Available:**
- 74,000+ fragrances
- Structured JSON responses
- Notes, accords, longevity, sillage
- Brand info, launch year, images
- ML-predicted missing data

**Access Method:** REST API (paid service)
**Consideration:** Cost vs. convenience trade-off

### 4.3 Supplementary: Parfumo

**URL:** https://www.parfumo.com
**Data Available:**
- Extensive note directory with categories
- Community reviews
- Collection tracking features

### 4.4 Offline Reference: Edwards' Fragrances of the World

The authoritative industry database. Available as an annual publication and online subscription. Most accurate family/subfamily classifications.

### 4.5 Pre-built Datasets

**Kaggle:** "Fragrantica.com Fragrance Dataset" - scraped dataset available for download

---

## 5. User Interface Concept

### 5.1 Evaluation Entry (Primary Screen)

```
┌────────────────────────────────────────────────────────────────┐
│                    NEW EVALUATION                              │
├────────────────────────────────────────────────────────────────┤
│                                                                │
│  Fragrance: [___________________________] 🔍                   │
│             (autocomplete from database or add new)            │
│                                                                │
│  Reviewer:  ◉ Byron  ○ Veronica  ○ Bayden  ○ Ariannah         │
│                                                                │
│  Rating:    ☆ ☆ ☆ ☆ ☆                                         │
│             1   2   3   4   5                                  │
│                                                                │
│  Notes:                                                        │
│  ┌──────────────────────────────────────────────────────────┐ │
│  │ Bright opening, fades too quickly. The orange is nice    │ │
│  │ but there's something powdery underneath that isn't      │ │
│  │ working...                                               │ │
│  └──────────────────────────────────────────────────────────┘ │
│                                                                │
│  [+ Add longevity/sillage ratings]  (expandable)               │
│                                                                │
│                              [ Save Evaluation ]               │
│                                                                │
└────────────────────────────────────────────────────────────────┘
```

### 5.2 Fragrance Detail View

```
┌────────────────────────────────────────────────────────────────┐
│  CHANEL CHANCE EAU TENDRE                              EDP     │
├────────────────────────────────────────────────────────────────┤
│                                                                │
│  Family: Floral > Soft Floral > Crisp                          │
│                                                                │
│  ┌─── Notes ───────────────────────────────────────────────┐   │
│  │ TOP:    Grapefruit, Quince                              │   │
│  │ HEART:  Jasmine, Hyacinth, Rose                         │   │
│  │ BASE:   Musk, Iris, Amber, Cedar                        │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                │
│  Accords:  ████████░░ Fresh     ███████░░░ Floral             │
│            █████░░░░░ Powdery   ████░░░░░░ Musky              │
│                                                                │
│  ─────────────────────────────────────────────────────────     │
│  FAMILY EVALUATIONS                                            │
│                                                                │
│  Bayden:    ★★★☆☆  "Too flowery, but the grapefruit is nice"  │
│  Ariannah:  ★★★★★  "Love it! Fresh and feminine"               │
│  Veronica:  ★★★★☆  "Nice for daytime"                          │
│                                                                │
└────────────────────────────────────────────────────────────────┘
```

### 5.3 Preference Profile View

```
┌────────────────────────────────────────────────────────────────┐
│  BAYDEN'S FRAGRANCE PROFILE                                    │
│  Based on 12 evaluations                                       │
├────────────────────────────────────────────────────────────────┤
│                                                                │
│  FAMILY PREFERENCES                                            │
│  ┌────────────────────────────────────────────────────────┐    │
│  │ Fresh   ████████████████░░░░  82%  ← Strongest match   │    │
│  │ Woody   ██████████░░░░░░░░░░  51%                      │    │
│  │ Floral  ████░░░░░░░░░░░░░░░░  23%                      │    │
│  │ Amber   ███░░░░░░░░░░░░░░░░░  18%                      │    │
│  └────────────────────────────────────────────────────────┘    │
│                                                                │
│  NOTES AFFINITY                                                │
│  ┌─ LIKES ───────────────┐  ┌─ DISLIKES ─────────────────┐    │
│  │ ✓ Bergamot      (+0.9)│  │ ✗ Lemon            (-0.8) │    │
│  │ ✓ Grapefruit    (+0.8)│  │ ✗ Jasmine          (-0.4) │    │
│  │ ✓ Orange        (+0.7)│  │ ✗ Powder/Aldehydes (-0.6) │    │
│  │ ✓ Vetiver       (+0.6)│  │ ✗ Strong florals   (-0.5) │    │
│  │ ✓ Cedar         (+0.5)│  │                           │    │
│  └───────────────────────┘  └───────────────────────────┘    │
│                                                                │
│  PATTERN SUMMARY                                               │
│  "Prefers citrus-forward fresh scents (excluding lemon),       │
│   with clean woody bases. Avoids heavy florals and             │
│   powdery/aldehydic fragrances."                               │
│                                                                │
└────────────────────────────────────────────────────────────────┘
```

### 5.4 Recommendation View

```
┌────────────────────────────────────────────────────────────────┐
│  RECOMMENDATIONS FOR BAYDEN                                    │
├────────────────────────────────────────────────────────────────┤
│                                                                │
│  Based on preference profile, these fragrances may appeal:     │
│                                                                │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ 1. ATELIER COLOGNE ORANGE SANGUINE            Match: 94% │  │
│  │    Fresh > Citrus                                        │  │
│  │    Notes: Blood orange, geranium, sandalwood            │  │
│  │    Why: Strong citrus (non-lemon), woody base           │  │
│  ├──────────────────────────────────────────────────────────┤  │
│  │ 2. TERRE D'HERMÈS                             Match: 89% │  │
│  │    Fresh > Aromatic                                      │  │
│  │    Notes: Orange, grapefruit, vetiver, cedar            │  │
│  │    Why: Citrus opening, earthy/woody character          │  │
│  ├──────────────────────────────────────────────────────────┤  │
│  │ 3. JO MALONE LIME BASIL & MANDARIN            Match: 85% │  │
│  │    Fresh > Citrus                                        │  │
│  │    Notes: Mandarin, basil, white musk                   │  │
│  │    ⚠️ Contains lime (citrus OK, but verify)              │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                │
│  [Filter by price range]  [Filter by availability]             │
│                                                                │
└────────────────────────────────────────────────────────────────┘
```

---

## 6. Recommendation Engine Concept

### 6.1 Preference Scoring Algorithm

```python
def calculate_preference_score(reviewer_id, fragrance):
    """
    Calculate predicted preference score for a fragrance.
    Returns value from 0.0 to 1.0
    """
    profile = get_reviewer_profile(reviewer_id)

    score = 0.0
    weights = {
        'family': 0.25,
        'subfamily': 0.20,
        'notes': 0.35,      # Heaviest weight - most predictive
        'accords': 0.20
    }

    # Family match
    family_score = profile.family_scores.get(fragrance.primary_family, 0.5)
    score += weights['family'] * family_score

    # Subfamily match
    subfamily_score = profile.subfamily_scores.get(fragrance.subfamily, 0.5)
    score += weights['subfamily'] * subfamily_score

    # Note affinity (most important)
    all_notes = fragrance.top_notes + fragrance.heart_notes + fragrance.base_notes
    note_scores = []
    for note in all_notes:
        affinity = profile.note_affinities.get(note.id, 0.0)
        note_scores.append(affinity)

    if note_scores:
        # Check for strong dislikes (veto effect)
        if min(note_scores) < -0.7:
            return max(0.0, score * 0.3)  # Heavy penalty

        avg_note_score = sum(note_scores) / len(note_scores)
        # Normalize from [-1, 1] to [0, 1]
        normalized = (avg_note_score + 1) / 2
        score += weights['notes'] * normalized

    # Accord match
    accord_scores = []
    for accord_type, intensity in fragrance.accords.items():
        affinity = profile.accord_affinities.get(accord_type, 0.0)
        accord_scores.append(affinity * intensity)

    if accord_scores:
        avg_accord = sum(accord_scores) / len(accord_scores)
        normalized = (avg_accord + 1) / 2
        score += weights['accords'] * normalized

    return min(1.0, max(0.0, score))
```

### 6.2 Building Preference Profiles

After each evaluation:

1. **Direct Attribution:** Map the rating to all notes/accords in the fragrance
2. **Temporal Weighting:** Recent evaluations weighted more heavily
3. **Confidence Building:** More evaluations = higher confidence in predictions
4. **Negative Signal Amplification:** Strong dislikes (1-2 stars) weighted more heavily than likes (prevents recommending things with dealbreaker notes)

### 6.3 Handling the "Lemon Problem"

Bayden likes citrus but not lemon specifically. The system handles this by:

1. Tracking notes at the specific level (bergamot, orange, lemon, grapefruit separately)
2. Not rolling up to category level unless explicitly positive across all members
3. Flagging fragrances that match overall profile but contain known disliked notes

---

## 7. Technical Architecture Options

### 7.1 Simple (MVP) - Local-First

```
┌─────────────────────────────────────────────────────────────┐
│                    LOCAL APPLICATION                        │
├─────────────────────────────────────────────────────────────┤
│  Frontend: Simple web app or desktop app                    │
│  Database: SQLite (local file)                              │
│  Data Enrichment: Manual entry + periodic batch import      │
│  Deployment: Runs on home server (Unraid)                   │
└─────────────────────────────────────────────────────────────┘
```

**Pros:** No ongoing costs, full data ownership, works offline
**Cons:** Manual data enrichment, no mobile access without VPN

### 7.2 Moderate - Self-Hosted with API Integration

```
┌─────────────────────────────────────────────────────────────┐
│                    DOCKER COMPOSE STACK                     │
├─────────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │
│  │  Frontend   │  │   Backend   │  │     PostgreSQL      │  │
│  │  (React?)   │──│  (FastAPI?) │──│     Database        │  │
│  │             │  │             │  │                     │  │
│  └─────────────┘  └──────┬──────┘  └─────────────────────┘  │
│                          │                                   │
│                   ┌──────▼──────┐                            │
│                   │  Fragrance  │                            │
│                   │  Data API   │                            │
│                   │  (Fragella) │                            │
│                   └─────────────┘                            │
└─────────────────────────────────────────────────────────────┘
```

**Pros:** Automatic data enrichment, accessible from anywhere
**Cons:** API costs, more complex setup

### 7.3 Future State - ML-Enhanced

Add a machine learning component that:
- Uses collaborative filtering (what do people with similar profiles like?)
- Identifies latent features in fragrance descriptions
- Improves predictions beyond simple weighted scoring

---

## 8. Implementation Phases

### Phase 1: Foundation (MVP)
- [ ] Database schema implementation
- [ ] Basic CRUD operations for fragrances, reviewers, evaluations
- [ ] Simple entry form for evaluations
- [ ] Manual fragrance data entry
- [ ] Basic reporting (list evaluations by person)

### Phase 2: Data Enrichment
- [ ] Integration with Fragrantica (scraping) or Fragella API
- [ ] Auto-complete for fragrance entry
- [ ] Automatic note/accord population
- [ ] Note reference database

### Phase 3: Analytics
- [ ] Preference profile calculation
- [ ] Basic recommendation engine
- [ ] Visual profile displays
- [ ] Family/subfamily preference charts

### Phase 4: Polish
- [ ] Mobile-friendly interface
- [ ] Barcode/image scanning for fragrance identification
- [ ] Export/import functionality
- [ ] Wishlist and shopping list features

### Phase 5: Advanced (Optional)
- [ ] ML-based recommendations
- [ ] Natural language processing of notes field
- [ ] Price tracking integration
- [ ] Social features (share profiles)

---

## 9. Open Questions

1. **Data Source Strategy:** Pay for Fragella API vs. scrape Fragrantica vs. manual entry?

2. **Platform Choice:**
   - Web app (accessible anywhere)?
   - Desktop app (simpler, local)?
   - Mobile-first (most convenient for in-store use)?

3. **Evaluation Granularity:**
   - Simple 1-5 rating sufficient?
   - Need structured questions (longevity, sillage, seasons)?
   - Track evaluation context (time of day, weather, mood)?

4. **Recommendation Scope:**
   - Only recommend from database of tried fragrances?
   - Recommend untried fragrances from external database?
   - Integration with retailers for availability/pricing?

5. **Multi-device Sync:**
   - Required for family use?
   - Self-hosted sync vs. cloud service?

---

## 10. Reference Materials

### Key Resources

1. **Michael Edwards' Fragrance Wheel**
   - https://www.fragrancesoftheworld.com
   - The industry standard classification system

2. **Fragrantica**
   - https://www.fragrantica.com
   - Largest community fragrance database
   - Note search: https://www.fragrantica.com/ingredients-search/

3. **Fragella API**
   - https://api.fragella.com
   - Commercial API with 74k+ fragrances

4. **Parfumo Note Directory**
   - https://www.parfumo.com/Fragrance_Notes
   - Detailed note categorization

### Analogous Systems

- **Vivino** (wine): Photo-based identification, community ratings, taste profiles
- **Untappd** (beer): Check-in model, badge gamification, style preferences
- **Goodreads** (books): Rating + review, recommendation engine, lists

---

## Appendix A: Note Categories Reference

| Category | Example Notes |
|----------|---------------|
| **Citrus** | Bergamot, lemon, orange, grapefruit, mandarin, lime, yuzu |
| **Fruits** | Apple, peach, pear, berries, plum, fig, coconut |
| **Florals** | Rose, jasmine, lily, tuberose, iris, violet, peony, orange blossom |
| **Green** | Grass, leaves, galbanum, violet leaf, cucumber |
| **Herbal/Aromatic** | Lavender, rosemary, basil, mint, sage, thyme |
| **Spices** | Cinnamon, cardamom, pepper, nutmeg, clove, ginger, saffron |
| **Woods** | Cedar, sandalwood, oud, vetiver, patchouli, pine |
| **Resins/Balsams** | Frankincense, myrrh, benzoin, labdanum, amber |
| **Musks** | White musk, skin musk, synthetic musks |
| **Animalic** | Leather, castoreum, civet, ambergris |
| **Gourmand** | Vanilla, chocolate, caramel, coffee, honey, tonka |
| **Aquatic/Ozonic** | Sea salt, marine notes, rain, ozone |

---

## Appendix B: Accord Definitions

| Accord | Description |
|--------|-------------|
| **Fresh** | Clean, light, invigorating |
| **Citrus** | Bright, zesty, tangy |
| **Fruity** | Sweet, juicy, non-citrus fruits |
| **Floral** | Flower-dominant |
| **Green** | Leafy, grassy, natural |
| **Aquatic** | Watery, marine, clean |
| **Aromatic** | Herbal, medicinal |
| **Spicy** | Warm spices, peppery |
| **Woody** | Dry woods, earthy |
| **Balsamic** | Resinous, warm |
| **Sweet** | Sugary, dessert-like |
| **Powdery** | Soft, cosmetic, aldehydic |
| **Musky** | Skin-like, soft, warm |
| **Leather** | Animalic, smoky, dry |
| **Smoky** | Incense, tobacco, fire |
| **Oriental** | Rich, exotic, warm |
| **Gourmand** | Edible, dessert-like |

---

*Document Version: 1.0*
*Created: December 2024*
*Status: Concept/Planning*
