---
title: "Usage"
schema_type: common
status: published
owner: core-maintainer
purpose: "Usage guide for Fragrance Rater."
tags:
  - guide
  - usage
---

This guide covers common usage patterns for Fragrance Rater.

## Installation

### From PyPI

```bash
pip install fragrance-rater
```

### From Source

```bash
git clone https://github.com/ByronWilliamsCPA/fragrance-rater
cd fragrance_rater
uv sync --all-extras
```

## Command Line Interface

### Available Commands

```bash
# Show help
fragrance-rater --help

# Hello command
fragrance-rater hello --name "World"

# Show configuration
fragrance-rater config
```

### Debug Mode

Enable debug logging:

```bash
fragrance-rater --debug hello --name "Test"
```
## Library Usage

### Basic Import

```python
from fragrance_rater import __version__

print(f"Version: {__version__}")
```

### Logging

```python
from fragrance_rater.utils.logging import get_logger, setup_logging

# Setup logging
setup_logging(level="DEBUG", json_logs=False)

# Get a logger
logger = get_logger(__name__)
logger.info("Hello from Fragrance Rater")
```
