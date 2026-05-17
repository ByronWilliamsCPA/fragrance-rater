# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Initial project setup and structure

### Fixed
- CI: override `no-build: false` for callers of the reusable `python-ci.yml`
  and `python-docs.yml` workflows so editable package install succeeds (`ci.yml`,
  `pr-validation.yml`, `docs.yml`).
- CI: remove `.github/workflows/sonarcloud.yml`; the dual CI scanner + project-level
  Automatic Analysis combination caused every run to error. Automatic Analysis
  continues unchanged at the SonarCloud project level (covers bugs,
  vulnerabilities, quality gate, and PR decoration).
- Lint: clean up ~30 ruff violations surfaced once the install step started
  succeeding: hoist `os` import in `core/cache.py`, restructure `try/return`
  blocks to use `else:`, convert async-iter accumulator to async list
  comprehension, annotate optional lazy imports with explicit
  `# noqa: PLC0415`, add `ClassVar` annotations to `WorkerSettings` lists,
  rename unused `body` parameter to `_body`, and add types to the
  `before_send` Sentry callback in `middleware/correlation.py`.

### Documentation
- `docs/PROJECT_SETUP.md`: mark `sonarcloud.yml` workflow as removed; SonarCloud
  analysis now runs via project-level Automatic Analysis only.

## [0.1.0] - TBD

### Added
- Initial project structure with Poetry package management
- Pydantic v2 JSON schema validation
- Structured logging with structlog and rich console output
- Pre-commit hooks (Ruff format, Ruff lint, BasedPyright, Bandit, Safety)
- Comprehensive test suite with pytest
- GitHub Actions CI/CD pipeline with quality gates
- CLI tool foundation
- License

### Documentation
- README with project overview and quick start
- CONTRIBUTING guidelines with development workflow
- References to ByronWilliamsCPA org-level Security Policy
- References to ByronWilliamsCPA org-level Code of Conduct

### Infrastructure
- Poetry dependency management with lock file
- pytest test framework with coverage reporting
- GitHub issue tracking and templates
- Automated dependency security scanning (Safety, Bandit)
- Code quality enforcement (Ruff, BasedPyright)
- CI/CD pipeline with multiple quality gates

### Security
- Bandit security linting
- Safety dependency vulnerability scanning
- Pre-commit hooks for security validation

[Unreleased]: https://github.com/ByronWilliamsCPA/fragrance_rater/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/ByronWilliamsCPA/fragrance_rater/releases/tag/v0.1.0
