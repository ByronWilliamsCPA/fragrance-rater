# Project-owned vocabularies

`fr-core-v0.yaml` is fragrance-rater's own olfactory vocabulary: primary families plus
descriptors that a note, material, or fragrance can carry at ranks 1 to 5, and a display tree
for browsing and teaching. Design and rules:
[olfactory vocabulary spec](../../docs/superpowers/specs/2026-09-24-olfactory-vocabulary-design.md)
and ADR-015.

## Rules

- The display tree is for UI and teaching only. Scoring, features, and ML never read it. It
  does not enforce family-under-heading or descriptor-under-family nesting either: that shape
  is a review convention, not a validator rule.
- Families and descriptors are independent lists. `usual_family_hint` is informational.
- `status` changes from `draft` to `published` only by the product owner, after review.
- A new version is a new file (`fr-core-v1.yaml`). Published files are never edited in place.
- Terms are authored independently. Do not copy terms, definitions, or assignments from
  ScenTree or any other published classification into this directory.
- Every key at the header, term, and display-node level is on an allow list; an unrecognized
  key is a validation error, not a silently-ignored typo.

## Validate

```bash
uv run python scripts/validate_vocabulary.py data/vocabulary/fr-core-v0.yaml
```

Exit 0 prints the file's SHA-256 content hash, which the D1 `vocabulary.content_hash` column
will record. The hash excludes `vocabulary.status`, so a draft and the same content later
flipped to `published` hash identically. Exit 1 lists rule violations. Exit 2 means the file
could not be read, including a missing file, an unreadable encoding, or a command-line usage
error (argparse).
