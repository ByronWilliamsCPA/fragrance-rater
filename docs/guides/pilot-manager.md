---
title: "Pilot manager guide"
schema_type: common
status: published
owner: core-maintainer
purpose: "Explain preparation, operation, disclosure, recovery, and closeout for the family pilot."
tags:
  - guide
  - usage
  - deployment
---

The manager is responsible for exact-version identity, physical labels, recorder access, blind
disclosure, recovery, and retained evidence. Complete the
[P6 pilot-readiness runbook](../deployment/p6-pilot-readiness.md) with synthetic data before
using actual pilot perfumes.

## Prepare the release and accounts

Record the deployed commit and image digests. Confirm that traffic enters through the dedicated
Traefik and Authentik boundary, the API and database have no public host ports, and
`AUTHENTIK_REQUIRED=true`. Use separate manager, recorder, and participant accounts. Verify the
configured manager usernames before opening the program.

## Build and freeze a program

1. Open **Program setup** and create a named, versioned draft.
2. Search the catalog and select the exact name, house, concentration, and `version_key` shown on
   the physical sample.
3. Record the identity evidence and assign the intended role. Link hidden repeats to the exact
   baseline membership.
4. Compare the draft with the reviewed physical manifest. Resolve every mismatch; never guess a
   version.
5. Review the frozen-definition preview and confirm activation. Activation is irreversible for
   that program definition.

## Enroll, label, and operate

Enroll the named evaluator and grant only the recorder usernames that need access. Generate the
manager-only mapping and print the blind labels. Keep the mapping away from participants and
remove discarded labels from the work area.

Use the progress overview to follow blotter completion, the finalized skin plan, planned skin
work, and reveal blockers. A holdout does not block the main reveal merely because its own
blotter is unfinished; its identity remains hidden until its own blotter is locked. Confirm any
consequential action in the application and inspect the returned state.

## Measure and close the workflow

Use the recommendation report with an explicit evaluator and UTC time window. Review population,
exclusions, denominators, algorithm versions, strategies, filters, and source snapshots before
export. Store exported evidence in the private P6 evidence directory after redaction review.

Record connectivity failures and manual recoveries in **Pilot operations**. Operational entries
must describe the user impact and recovery action without hostnames, credentials, tokens, blind
mappings, or private observations.

## Outage procedure

1. Confirm the outage from a second authorized device without bypassing Authentik.
2. Tell participants to stop submitting and switch to the
   [printed evaluation and outage form](../printable-evaluation-form.md).
3. Preserve blind codes, stages, elapsed minutes, and local times without adding identities.
4. Follow the owned alert and recovery procedure. Do not expose the API or database as a shortcut.
5. After recovery, verify readiness, enter each paper response once, and compare it with the
   signed paper record.
6. Record the failure and recovery events, then store the drill evidence privately.

## Before approving real testing

Review every P6 record, all known limitations, the participant instructions, backup and restore
results, and the target-device matrix. Only a signed `go` in the readiness record permits F1.
Any failed or missing item keeps the decision at `no-go` and returns the issue to its owning P
sprint.
