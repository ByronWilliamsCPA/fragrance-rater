# Fragrance Evaluation Form

> **Instructions**: Use this form to record fragrance evaluations when offline.
> Enter data via CLI: `fragrance-rater import-data manual evaluations.csv`
> Or via API: `POST /api/v1/evaluations`

---

## Session Info

| Field | Value |
|-------|-------|
| **Date** | __________________ |
| **Reviewer** | ☐ Byron  ☐ Veronica  ☐ Bayden  ☐ Ariannah |
| **Location** | __________________ |

---

## Evaluation 1

| Field | Value |
|-------|-------|
| **Fragrance Name** | __________________________________ |
| **Brand** | __________________________________ |
| **Concentration** | ☐ EDT  ☐ EDP  ☐ Parfum  ☐ Other: _______ |

### Ratings (circle one)

| Category | Rating |
|----------|--------|
| **Overall** | 1 ⭐  2 ⭐  3 ⭐  4 ⭐  5 ⭐ |
| **Longevity** | 1  2  3  4  5  (or N/A) |
| **Sillage** | 1  2  3  4  5  (or N/A) |

### Notes Detected

| Position | Notes (comma-separated) |
|----------|------------------------|
| **Top** | __________________________________ |
| **Heart** | __________________________________ |
| **Base** | __________________________________ |

### Comments

```
_______________________________________________
_______________________________________________
_______________________________________________
```

---

## Evaluation 2

| Field | Value |
|-------|-------|
| **Fragrance Name** | __________________________________ |
| **Brand** | __________________________________ |
| **Concentration** | ☐ EDT  ☐ EDP  ☐ Parfum  ☐ Other: _______ |

### Ratings (circle one)

| Category | Rating |
|----------|--------|
| **Overall** | 1 ⭐  2 ⭐  3 ⭐  4 ⭐  5 ⭐ |
| **Longevity** | 1  2  3  4  5  (or N/A) |
| **Sillage** | 1  2  3  4  5  (or N/A) |

### Notes Detected

| Position | Notes (comma-separated) |
|----------|------------------------|
| **Top** | __________________________________ |
| **Heart** | __________________________________ |
| **Base** | __________________________________ |

### Comments

```
_______________________________________________
_______________________________________________
_______________________________________________
```

---

## Evaluation 3

| Field | Value |
|-------|-------|
| **Fragrance Name** | __________________________________ |
| **Brand** | __________________________________ |
| **Concentration** | ☐ EDT  ☐ EDP  ☐ Parfum  ☐ Other: _______ |

### Ratings (circle one)

| Category | Rating |
|----------|--------|
| **Overall** | 1 ⭐  2 ⭐  3 ⭐  4 ⭐  5 ⭐ |
| **Longevity** | 1  2  3  4  5  (or N/A) |
| **Sillage** | 1  2  3  4  5  (or N/A) |

### Notes Detected

| Position | Notes (comma-separated) |
|----------|------------------------|
| **Top** | __________________________________ |
| **Heart** | __________________________________ |
| **Base** | __________________________________ |

### Comments

```
_______________________________________________
_______________________________________________
_______________________________________________
```

---

## Evaluation 4

| Field | Value |
|-------|-------|
| **Fragrance Name** | __________________________________ |
| **Brand** | __________________________________ |
| **Concentration** | ☐ EDT  ☐ EDP  ☐ Parfum  ☐ Other: _______ |

### Ratings (circle one)

| Category | Rating |
|----------|--------|
| **Overall** | 1 ⭐  2 ⭐  3 ⭐  4 ⭐  5 ⭐ |
| **Longevity** | 1  2  3  4  5  (or N/A) |
| **Sillage** | 1  2  3  4  5  (or N/A) |

### Notes Detected

| Position | Notes (comma-separated) |
|----------|------------------------|
| **Top** | __________________________________ |
| **Heart** | __________________________________ |
| **Base** | __________________________________ |

### Comments

```
_______________________________________________
_______________________________________________
_______________________________________________
```

---

## Evaluation 5

| Field | Value |
|-------|-------|
| **Fragrance Name** | __________________________________ |
| **Brand** | __________________________________ |
| **Concentration** | ☐ EDT  ☐ EDP  ☐ Parfum  ☐ Other: _______ |

### Ratings (circle one)

| Category | Rating |
|----------|--------|
| **Overall** | 1 ⭐  2 ⭐  3 ⭐  4 ⭐  5 ⭐ |
| **Longevity** | 1  2  3  4  5  (or N/A) |
| **Sillage** | 1  2  3  4  5  (or N/A) |

### Notes Detected

| Position | Notes (comma-separated) |
|----------|------------------------|
| **Top** | __________________________________ |
| **Heart** | __________________________________ |
| **Base** | __________________________________ |

### Comments

```
_______________________________________________
_______________________________________________
_______________________________________________
```

---

## Quick Reference: Rating Guide

| Rating | Meaning | When to Use |
|--------|---------|-------------|
| **5** ⭐ | Excellent | Would buy, signature scent material |
| **4** ⭐ | Good | Enjoyable, would wear regularly |
| **3** ⭐ | Neutral | Neither like nor dislike |
| **2** ⭐ | Poor | Not enjoyable, wouldn't choose |
| **1** ⭐ | Bad | Actively dislike, can't wear |

## Quick Reference: Common Notes

| Category | Common Notes |
|----------|-------------|
| **Citrus** | Bergamot, Lemon, Orange, Grapefruit, Lime |
| **Floral** | Rose, Jasmine, Lavender, Iris, Violet |
| **Woody** | Cedar, Sandalwood, Oud, Vetiver, Pine |
| **Spicy** | Pepper, Cardamom, Cinnamon, Nutmeg, Clove |
| **Sweet** | Vanilla, Tonka, Caramel, Honey, Praline |
| **Fresh** | Mint, Cucumber, Green Tea, Marine, Ozone |
| **Amber** | Amber, Incense, Benzoin, Labdanum |
| **Musk** | White Musk, Skin Musk, Ambroxan |

---

## Data Entry Format (CSV)

When entering data, use this CSV format:

```csv
reviewer,fragrance_name,brand,concentration,rating,longevity,sillage,notes
Byron,Sauvage,Dior,EDT,4,4,5,"Fresh and spicy, great projection"
Veronica,Coco Mademoiselle,Chanel,EDP,5,5,4,"Love the orange and patchouli"
```

**Print multiple copies as needed.**
