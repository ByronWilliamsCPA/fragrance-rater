---
title: "Known Vulnerabilities"
schema_type: common
status: published
owner: core-maintainer
purpose: "Track pip-audit findings that cannot be immediately resolved, per project security policy."
tags:
  - security
  - vulnerabilities
---

Documented per project policy: vulnerabilities found by `pip-audit` that cannot
be immediately resolved are tracked here. Review quarterly. No entry ages past
60 days without reassessment.

**Last assessed**: 2026-05-11
**Next review due**: 2026-08-11
**Tool**: `uv run pip-audit` (56 findings across 25 packages)

---

## How to Re-Assess

```bash
uv run pip-audit
```

For each package with a fix version available, attempt upgrade:

```bash
uv add "package>=fix_version"
uv run pytest --tb=short
```

If tests pass, commit the upgrade and remove the entry from this file.

---

## Production Dependencies

These packages are used in the running application.

### authlib 1.6.6

| CVE | Fix Version | Summary |
|-----|------------|---------|
| CVE-2026-28802 | 1.6.7 | OAuth token handling issue |
| CVE-2026-27962 | 1.6.9 | JWT validation bypass |
| CVE-2026-28490 | 1.6.9 | PKCE downgrade attack |
| CVE-2026-41425 | 1.6.11 | Token leakage in redirect |

**Why deferred**: Upgrading to 1.6.11 requires verifying OAuth flow compatibility
across all authentication paths. Planned for next sprint.

**Exposure**: Medium. OAuth is only used when `openrouter_api_key` is configured.

---

### cryptography 46.0.3

| CVE | Fix Version | Summary |
|-----|------------|---------|
| CVE-2026-26007 | 46.0.5 | Memory corruption in X.509 parsing |
| CVE-2026-34073 | 46.0.6 | RSA key generation weakness |
| CVE-2026-39892 | 46.0.7 | Timing attack in symmetric operations |

**Why deferred**: Pinned transitively by several packages. Upgrade requires
coordinating with dependent packages. Planned for dependency audit sprint.

**Exposure**: Low. Cryptography operations are limited to token signing.

---

### python-multipart 0.0.21

| CVE | Fix Version | Summary |
|-----|------------|---------|
| CVE-2026-24486 | 0.0.22 | Multipart boundary DoS |
| CVE-2026-40347 | 0.0.26 | Denial of service via malformed body |
| CVE-2026-42561 | 0.0.27 | Content-Disposition header injection |

**Why deferred**: File upload endpoints are internal-only (no external user uploads
in current phase). Will upgrade before enabling public file upload features.

**Exposure**: Low in current deployment. Upload endpoints require authentication.

---

### requests 2.32.5

| CVE | Fix Version | Summary |
|-----|------------|---------|
| CVE-2026-25645 | 2.33.0 | Proxy-Authorization header leakage |

**Why deferred**: Minor release upgrade. Testing against OpenRouter API needed
before promoting. Scheduled for next dependency update pass.

**Exposure**: Low. Proxy auth is not used in this application.

---

### python-dotenv 1.2.1

| CVE | Fix Version | Summary |
|-----|------------|---------|
| CVE-2026-28684 | 1.2.2 | Malformed .env file path traversal |

**Why deferred**: Patch release. Will be upgraded in next routine dependency
update. Low risk as `.env` files are developer-controlled.

**Exposure**: Negligible. `.env` files are never user-supplied.

---

## Development-Only Dependencies

These packages are only present in the dev/test environment and are not
shipped to production. Severity is significantly reduced.

### jupyter-server 2.17.0

| CVE | Fix Version |
|-----|------------|
| CVE-2025-61669 | 2.18.0 |
| CVE-2026-40110 | 2.18.0 |
| CVE-2026-35397 | 2.18.0 |
| CVE-2026-40934 | 2.18.0 |

**Scope**: Dev only. Not present in production image.

---

### jupyterlab 4.5.1

| CVE | Fix Version |
|-----|------------|
| CVE-2026-42266 | 4.5.7 |
| CVE-2026-42557 | 4.5.7 |

**Scope**: Dev only.

---

### gitpython 3.1.45

| CVE | Fix Version |
|-----|------------|
| CVE-2026-42215 | 3.1.47 |
| CVE-2026-42284 | 3.1.47 |
| CVE-2026-44244 | 3.1.49 |
| GHSA-mv93-w799-cj2w | 3.1.50 |

**Scope**: Dev only (used by pre-commit and test tooling).

---

### nltk 3.9.2

| CVE | Fix Version |
|-----|------------|
| CVE-2025-14009 | 3.9.3 |
| GHSA-rf74-v2fm-23pw | unknown |
| CVE-2026-33230 | 3.9.4 |
| CVE-2026-33231 | 3.9.4 |
| CVE-2026-0846 | 3.9.3 |
| CVE-2026-0847 | unknown |

**Scope**: Dev only (transitive via test tooling).

---

### nbconvert 7.16.6

| CVE | Fix Version |
|-----|------------|
| CVE-2025-53000 | 7.17.0 |
| CVE-2026-39378 | 7.17.1 |
| CVE-2026-39377 | 7.17.1 |

**Scope**: Dev only.

---

### notebook 7.5.1

| CVE | Fix Version |
|-----|------------|
| CVE-2026-40171 | 7.5.6 |

**Scope**: Dev only.

---

### mistune 3.2.0

| CVE | Fix Version |
|-----|------------|
| CVE-2026-33079 | 3.2.1 |
| CVE-2026-44708 | unknown |
| CVE-2026-44896 | unknown |
| CVE-2026-44897 | 3.2.1 |

**Scope**: Dev only (transitive via nbconvert).

---

### pip 25.3

| CVE | Fix Version |
|-----|------------|
| CVE-2026-1703 | 26.0 |
| CVE-2026-3219 | unknown |
| CVE-2026-6357 | 26.1 |

**Scope**: Dev tooling only. Production image does not expose pip.

---

### pytest 9.0.2

| CVE | Fix Version |
|-----|------------|
| CVE-2025-71176 | 9.0.3 |

**Scope**: Test-only dependency.

---

### tornado 6.5.4

| CVE | Fix Version |
|-----|------------|
| GHSA-78cv-mqj4-43f7 | 6.5.5 |
| CVE-2026-31958 | 6.5.5 |
| CVE-2026-35536 | 6.5.5 |

**Scope**: Dev only (transitive via jupyter-server).

---

### urllib3 2.6.2

| CVE | Fix Version |
|-----|------------|
| CVE-2026-21441 | 2.6.3 |
| CVE-2026-44431 | 2.7.0 |
| CVE-2026-44432 | 2.7.0 |

**Scope**: Dev only (transitive via requests in dev extras).

---

### protobuf 6.33.2

| CVE | Fix Version |
|-----|------------|
| CVE-2026-0994 | 6.33.5 |

**Scope**: Dev only (transitive via grpcio tooling).

---

### pygments 2.19.2

| CVE | Fix Version |
|-----|------------|
| CVE-2026-4539 | 2.20.0 |

**Scope**: Dev only (transitive via rich and pytest output).

---

### filelock 3.20.1

| CVE | Fix Version |
|-----|------------|
| CVE-2026-22701 | 3.20.3 |

**Scope**: Dev only (transitive via virtualenv).

---

### virtualenv 20.35.4

| CVE | Fix Version |
|-----|------------|
| CVE-2026-22702 | 20.36.1 |

**Scope**: Dev only (used by pre-commit).

---

### jaraco-context 6.0.2

| CVE | Fix Version |
|-----|------------|
| CVE-2026-23949 | 6.1.0 |

**Scope**: Dev only (transitive).

---

### pyasn1 0.6.1

| CVE | Fix Version |
|-----|------------|
| CVE-2026-23490 | 0.6.2 |
| CVE-2026-30922 | 0.6.3 |

**Scope**: Dev only (transitive via oauth tooling).

---

### lxml 6.0.2

| CVE | Fix Version |
|-----|------------|
| CVE-2026-41066 | 6.1.0 |

**Scope**: Dev only (transitive via nbconvert).

---

### mako 1.3.10

| CVE | Fix Version |
|-----|------------|
| CVE-2026-44307 | 1.3.12 |

**Scope**: Dev only (transitive via alembic).

---

### py 1.11.0

| CVE | Fix Version |
|-----|------------|
| PYSEC-2022-42969 | unknown |

**Scope**: Dev only (transitive legacy dependency). The `py` package is
deprecated; this vulnerability has no known fix in the package itself.
The package will be removed when its dependents migrate away from it.

---

## Remediation Plan

1. **Next sprint**: Upgrade authlib to 1.6.11, python-multipart to 0.0.27,
   requests to 2.33.0, python-dotenv to 1.2.2 after compatibility testing.
2. **Dependency audit sprint**: Coordinate cryptography upgrade with all
   transitive dependents.
3. **Dev tooling**: Bulk-upgrade jupyter stack, pytest, tornado, urllib3 in
   a single `uv sync --upgrade` pass and verify test suite.
