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

_No active ignores currently._

## Reassessment log

| Date | Vulnerability | Action |
| --- | --- | --- |
| 2026-05-17 | PYSEC-2022-42969 | Initial doc; ignore added in `pyproject.toml` |
| 2026-09-03 | PYSEC-2022-42969 (CVE-2022-42969, GHSA-w596-4wvx-j9j6) | OSV withdrew the advisory on 2026-06-09; all three alias ignores removed from `osv-scanner.toml`, entry removed here |
