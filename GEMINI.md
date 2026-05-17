# Gemini Session Context: fragrance-rater

## Project Summary

fragrance-rater is a personal fragrance evaluation and recommendation system
built for family use. It is a Python 3.12 application managed with UV, exposing
a Click-based CLI. The system stores fragrance evaluations and uses LLM-powered
recommendations (via OpenRouter) to surface suggestions based on family members'
scent preferences. The stack includes FastAPI for the API layer, PostgreSQL for
persistence, React for the frontend, and Docker Compose for the development
environment. Code quality is enforced by Ruff, BasedPyright (strict mode), and
pytest with an 80% coverage floor.

## Development Standards

See `CLAUDE.md` for the full set of development standards, branch workflow rules,
security-first requirements, testing thresholds, pre-commit checklist, and
project-specific configuration.

Key reference files:

- `CLAUDE.md` - Full project and development guidelines
- `AGENTS.md` - Claude Code subagent catalog and invocation patterns
- `CONTRIBUTING.md` - Contribution workflow
- `SECURITY.md` - Vulnerability reporting and security policy
- `docs/planning/PROJECT-PLAN.md` - Phased implementation plan

## Quick Orientation

```bash
uv sync --all-extras          # Install all dependencies
uv run pytest --cov=src       # Run tests with coverage
uv run ruff check .           # Lint
uv run basedpyright src/      # Type check
pre-commit run --all-files    # Run all pre-commit hooks
```

Last updated: 2026-05-16
