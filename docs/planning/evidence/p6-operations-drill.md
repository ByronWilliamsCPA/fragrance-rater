---
title: "P6 operations drill"
schema_type: common
status: published
owner: core-maintainer
purpose: "Retain backup, recovery, alert, logging, secret ownership, and outage rehearsal evidence."
tags:
  - planning
  - deployment
  - observability
  - security
---

**Status:** Pending target deployment

**Private evidence location:** Pending

**Release commit and image digests:** Pending

| Drill | Required evidence | Owner | Result | Evidence reference |
| :--- | :--- | :--- | :--- | :--- |
| Backup creation | Native PostgreSQL archive, exit status, SHA-256, retention class | Pending | Pending | Pending |
| Isolated restore | PostgreSQL version, duration, archive list, row counts, redacted hashes | Pending | Pending | Pending |
| Candidate migration | Before/after inventory, Alembic head, no-op rerun, query plans | Pending | Pending | Pending |
| Recovery objective | Measured recovery point and recovery time against declared objectives | Pending | Pending | Pending |
| Rollback decision | Named authority, decision deadline, restore path, outcome | Pending | Pending | Pending |
| Connectivity outage | Detection, printed capture, recovery, single-entry reconciliation | Pending | Pending | Pending |
| LLM-provider outage | Deterministic recommendation and core workflow availability | Pending | Pending | Pending |
| Alerts | Recipient and delivery evidence for availability, disk, and database growth | Pending | Pending | Pending |
| Structured logs | Correlation without secrets, mappings, or private response content | Pending | Pending | Pending |
| Secret rotation ownership | Named owners, test-secret exercise, rollback and verification | Pending | Pending | Pending |
| Upgrade ownership | Operator, approver, backup owner, rollback owner, communication route | Pending | Pending | Pending |

The printed outage packet must include the participant instructions and manual form, identify the
assigned recorder, and preserve blind code, stage, elapsed minutes, and local time without the
concealed identity. Reconciliation records who entered each form and how duplicate entry was
prevented.

Do not commit backup names, hostnames, account names, alert addresses, secret identifiers, raw
logs, or private observations. Record only redacted outcomes and private evidence references.

**Operations result:** Pending

**Reviewer and UTC date:** Pending
