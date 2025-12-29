---
title: "Fragrance Rater"
schema_type: common
status: published
owner: core-maintainer
purpose: "Documentation home page for Fragrance Rater."
tags:
  - documentation
  - home
---

Personal fragrance evaluation and recommendation system for family use with LLM-powered recommendations

## Quick Start

```bash
# Install the package
pip install fragrance-rater

# Or install with development dependencies
uv sync --all-extras
```

## CLI Usage

```bash
# Show help
fragrance-rater --help

# Example command
fragrance-rater hello --name "World"
```
## Features

- Modern Python 3.12+ support
- Type-safe with BasedPyright strict mode
- Comprehensive test coverage
- Structured logging with structlog
- CLI interface with Click
- Docker support
## Documentation

- [User Guide](guides/overview.md) - Getting started and usage
- [API Reference](api-reference.md) - Complete API documentation
- [Development](development/architecture.md) - Architecture and contributing
- [Project](project/roadmap.md) - Roadmap and changelog

## License

This project is licensed under the MIT License - see the [LICENSE](project/license.md) file for details.
