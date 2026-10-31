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

| Tool | Identifier | Where the ignore is set | Reassess by | Status |
| --- | --- | --- | --- | --- |
| pip-audit | `PYSEC-2022-42969` (`py` 1.11.0, a transitive dependency of `interrogate` 1.7.0) | `[tool.pip-audit] ignore-vuln` in `pyproject.toml` | 2026-07-16 | **Overdue by 107 days as of 2026-10-31** |

The OSV-Scanner side carries no ignore: `osv-scanner.toml` has no active exception, because the advisory was
withdrawn upstream. The `pyproject.toml` pip-audit ignore was not removed with it, so it is still in force and its
own reassessment date has passed. The advisory is no longer reported (see the 2026-10-31 log entry), so the
ignore appears to be unnecessary. It is left in place pending the maintainer's decision to delete it; removing it
is a one-line change to `pyproject.toml` that this documentation pass deliberately did not make.

## Reassessment log

| Date | Vulnerability | Action |
| --- | --- | --- |
| 2026-05-17 | PYSEC-2022-42969 | Initial doc; ignore added in `pyproject.toml` |
| 2026-09-03 | PYSEC-2022-42969 (CVE-2022-42969, GHSA-w596-4wvx-j9j6) | OSV withdrew the advisory on 2026-06-09; all three alias ignores removed from `osv-scanner.toml`, entry removed here |
| 2026-10-31 | PYSEC-2022-42969 | Re-checked. The `pyproject.toml` pip-audit ignore is still present and its 2026-07-16 reassessment date is overdue. Against the `uv.lock` export (`py` 1.11.0 and `interrogate` 1.7.0 still locked), `pip-audit --no-deps --disable-pip` run from outside the repository, so the ignore did not apply, reported "No known vulnerabilities found" on both the default PyPI source and `-s osv`. Recommended action: delete the ignore and this ledger row. Not done here; owner decision. |
