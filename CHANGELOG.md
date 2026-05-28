# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Initial project setup and structure
- `AGENTS.md` cataloguing the Claude Code subagents configured for the project.
- `GEMINI.md` providing Gemini-session orientation pointing at `CLAUDE.md`.
- `SECURITY.md` documenting the vulnerability reporting policy, response SLAs,
  and CVE/advisory workflow.
- `.claude/settings.json` declaring the project's Claude Code permission
  allowlist (narrowed to specific `uv run` subcommands rather than a wildcard).
- Pre-commit hook `no-em-dash` enforcing the project's writing-style rule that
  bans U+2014 from all committed text files.
- `Model Selection` section in `CLAUDE.md` describing when to use Opus, Sonnet,
  and Haiku for subagents.
- Tag allowlist expanded with `project`, `feedback`, and `template`; the
  `template` tag is now applied to `docs/ADRs/adr-template.md`.

### Changed

- Pinned five third-party pre-commit hook revisions to upstream commit SHAs
  (`pre-commit-hooks`, `bandit`, `conventional-pre-commit`, `validate-pyproject`,
  `check-jsonschema`, `interrogate`) with `# frozen: vX.Y.Z` comments to satisfy
  OpenSSF Scorecard Pinned-Dependencies.
- TruffleHog pre-commit hook now fails loudly with install instructions when
  the binary is missing, replacing the prior silent-skip behavior.
- `mkdocs.yml` `repo_name` corrected from `fragrance_rater` to `fragrance-rater`
  so the Material theme "Edit this page" link resolves correctly. Copyright
  notice extended to 2025-2026.

### Removed

- `safety` dependency removed from `pyproject.toml` (`dev` and `supply-chain`
  extras), `CLAUDE.md`, `CONTRIBUTING.md`, `.claude/commands/security.md`,
  `.claude/skills/security/SKILL.md`. `pip-audit` continues to provide
  equivalent vulnerability scanning coverage.

### Fixed

- ADR template: aligned the body `Status:` blockquote with the front matter
  (`draft` instead of `proposed`) so authors using the template see consistent
  guidance.
- `tools/validate_front_matter.py`: replaced an em-dash in the redundant-H1
  error message with a semicolon to satisfy the new `no-em-dash` hook.
- CI: override `no-build: false` for callers of the reusable `python-ci.yml`
  and `python-docs.yml` workflows so editable package install succeeds (`ci.yml`,
  `pr-validation.yml`, `docs.yml`).
- CI: extend the same `no-build: false` override to `sbom.yml` (caller of
  `python-sbom.yml`) so editable package install succeeds during SBOM generation;
  resolves three consecutive "Generate SBOMs" failures (closes #36).
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
- Renovate: switched `enabledManagers` and `packageRules.matchManagers` from
  `poetry` to `pep621` so Renovate correctly discovers Python dependencies
  declared under `[project.dependencies]` in `pyproject.toml`; updated
  `matchDepTypes` to `project.dependencies` and `dependency-groups` /
  `tool.uv.dev-dependencies` to match pep621 manager depType names; removed
  the now-unused `poetry` manager config block and `poetryMassage` post-update
  option.

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
