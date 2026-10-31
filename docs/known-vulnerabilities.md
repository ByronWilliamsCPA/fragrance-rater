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

None. Neither `pyproject.toml` (`[tool.pip-audit] ignore-vuln`) nor `osv-scanner.toml` carries an exception.

## Reassessment log

| Date | Vulnerability | Action |
| --- | --- | --- |
| 2026-05-17 | PYSEC-2022-42969 | Initial doc; ignore added in `pyproject.toml` |
| 2026-09-03 | PYSEC-2022-42969 (CVE-2022-42969, GHSA-w596-4wvx-j9j6) | OSV withdrew the advisory on 2026-06-09; all three alias ignores removed from `osv-scanner.toml`, entry removed here |
| 2026-10-31 | PYSEC-2022-42969 | Re-checked. The `pyproject.toml` pip-audit ignore is still present and its 2026-07-16 reassessment date is overdue. Against the `uv.lock` export (`py` 1.11.0 and `interrogate` 1.7.0 still locked), audited with pip-audit 2.10.1 (`uv export --frozen --all-extras --no-hashes --no-emit-project > req.txt`, then `pip-audit -r req.txt --no-deps --disable-pip`, run from outside the repository so the ignore did not apply), it reported "No known vulnerabilities found" on the default PyPI source, and an earlier run with `-s osv` reported the same. Recommended action: delete the ignore and this ledger row. Not done here; owner decision. |
| 2026-10-31 | PYSEC-2022-42969 | Ignore removed from `pyproject.toml` (`ignore-vuln` is now empty). The advisory was withdrawn upstream on 2026-06-09 and pip-audit no longer reports it (see the entry above), so the exception was unnecessary and its 2026-07-16 reassessment date had passed. |
