# Security Policy

## Reporting a Vulnerability

Do not open a public issue for security problems. Use one of these private
channels:

1. **GitHub Security Advisory** (preferred): go to the
   [fragrance-rater Security tab](https://github.com/ByronWilliamsCPA/fragrance-rater/security)
   and click **Report a vulnerability**.
2. **Email**: send details to **byronawilliams@gmail.com**. Use the subject
   line `SECURITY:` followed by a short summary.

Both channels are monitored by the maintainer. Reports remain confidential
until a fix is published. The maintainer will acknowledge all reports within
**14 calendar days** of receipt as an initial response SLA.

## What to Include in a Report

A useful report contains, at minimum:

- A clear description of the issue and the security impact (what an attacker
  can do).
- The affected repository, file path, workflow, or commit SHA.
- Steps to reproduce, including any inputs, environment, or configuration
  needed.
- A proof of concept if you have one (snippet, log, or test case).
- Suggested fix or mitigation, if known.
- Your contact details and whether you want public credit in the advisory.

## Supported Versions

fragrance-rater follows a continuous deployment model on `main`. Release tags
follow semver; there are no long-term support branches.

| Version                                    | Supported |
|--------------------------------------------|-----------|
| `main` (latest commit)                     | Yes       |
| Most recent release tag                    | Yes       |
| Earlier release tags and older pinned SHAs | No        |

## Response Timeline

| Stage                                  | Target                                        |
|----------------------------------------|-----------------------------------------------|
| Initial acknowledgement of report      | 14 calendar days from receipt                 |
| Triage and severity (non-critical)     | 10 business days from acknowledgement         |
| Triage and severity (critical)         | 2 business days from acknowledgement          |
| Fix or mitigation for critical reports | 14 calendar days from acknowledgement         |
| Fix released for other severities      | 30 calendar days from acknowledgement         |

These are targets, not guarantees. All windows run from acknowledgement of
the report. The maintainer will keep the reporter updated if a fix needs
longer.

## Security Practices

This project applies the following baseline security controls:

- Static analysis: CodeQL (org-wide), SonarCloud (SAST), Ruff and Bandit
  via pre-commit hooks and CI workflows
- Dependency pinning with Renovate-driven updates and `pip-audit` scanning
- Container scanning with Trivy (Docker and SBOM workflows)
- SBOM generation for tagged releases
- Secret scanning: `detect-secrets` and TruffleHog as `pre-commit` hooks,
  GitHub secret scanning enabled on all public repositories
- Least-privilege workflow tokens and SHA-pinned third-party actions

## CVE and Advisory Workflow

For confirmed vulnerabilities rated Moderate or higher:

1. Request a CVE through GitHub.
2. Draft and publish a GitHub Security Advisory on the affected repository.
3. Record remediation in the advisory and in `CHANGELOG.md`.

Unfixed CVEs are tracked in `docs/known-vulnerabilities.md` and reviewed
quarterly. No entry ages past 60 days without reassessment.

## Disclosure

This project follows coordinated disclosure. Public details are published in
the advisory once a fix or mitigation is available. Reporters who want credit
should say so in the report; otherwise credit is anonymous.

Last updated: 2026-05-16
