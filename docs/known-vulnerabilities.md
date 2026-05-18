---
title: "Known Vulnerabilities"
schema_type: common
status: published
owner: core-maintainer
purpose: >
  Track dependency vulnerabilities that cannot currently be resolved,
  paired with documented justification and a 60-day reassessment window.
tags:
  - security
  - compliance
  - dependencies
---

> **Purpose**: Document any dependency vulnerability that `pip-audit` cannot
> resolve immediately, paired with the reasoning for the ignore and a
> reassessment date. Per the global standard in `~/.claude/CLAUDE.md`, no
> entry ages past 60 days without reassessment. The OpenSSF release gate
> blocks releases for any vulnerability older than 60 days regardless of
> reassessment status.

## Active ignores

### PYSEC-2022-42969

- **Package**: `py` 1.11.0
- **CVE / advisory**: [PYSEC-2022-42969](https://github.com/pytest-dev/py/issues/287).
  ReDoS (Regular Expression Denial of Service) in the SVN-WC parser
- **Source**: Transitive dependency of `interrogate` 1.7.0 (docstring coverage tool, dev-only)
- **Fix status**: No upstream fix. The `py` package is archived; the
  `interrogate` maintainers have not yet replaced or vendored the dependency
- **Exposure assessment**: The vulnerable code path is `py.path.svnwc`,
  which parses XML output from the Subversion CLI. This project does not
  use SVN and `interrogate`'s docstring scan does not invoke `py.path.svnwc`
- **Date documented**: 2026-05-17
- **Reassessment due**: 2026-07-16

## Reassessment log

| Date | Vulnerability | Action |
| --- | --- | --- |
| 2026-05-17 | PYSEC-2022-42969 | Initial doc; ignore added in `pyproject.toml` |
