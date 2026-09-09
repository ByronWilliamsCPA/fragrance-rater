---
title: "Overview"
schema_type: common
status: published
owner: core-maintainer
purpose: "Overview of Fragrance Rater features and capabilities."
tags:
  - guide
  - overview
---

Personal fragrance evaluation and recommendation system for family use with LLM-powered recommendations

## Key Features

### Modern Python Development

- **Python 3.12+** with full type annotations
- **UV** for fast dependency management
- **Ruff** for linting and formatting
- **BasedPyright** for strict type checking

### Quality Assurance

- **pytest** with a graduated coverage gate (80% line, 90% patch)
- **Pre-commit hooks** for automated checks
- **GitHub Actions** CI/CD pipeline

### Command Line Interface

Built with Click for a reliable CLI experience:

```bash
fragrance-rater --help
```
## Getting Started

1. **Installation**: See the [Configuration Guide](configuration.md)
2. **Usage**: Check the [Usage Guide](usage.md)
3. **API**: Browse the [API Reference](../api-reference.md)

## Architecture

For details on the project architecture, see [Architecture](../development/architecture.md).
