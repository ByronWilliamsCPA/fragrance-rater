---
title: "Fragella integration and source-use boundary"
schema_type: common
status: draft
owner: core-maintainer
purpose: "Describe the existing bounded lookup integration and the limits on publishing or reusing vendor material."
tags:
  - api
  - reference
---

Reviewed September 25, 2026. This project reference links to the
[vendor API documentation](https://api.fragella.com/docs.html) rather than
maintaining a copy of its full specification, examples or catalog data.
For Fragrance Rater's own API, use the [API reference](api-reference.md).

## Existing implementation

`src/fragrance_rater/services/fragella_client.py` implements search and usage
lookups. `FragellaLookupService.run_lookup()` persists the query, requesting
operator, status, error information and parsed result objects in
`FragellaLookup`. It does not automatically promote these results into the
catalog or a `SourceSnapshot`. The stored parsed results are still retained
vendor data; an audit purpose does not make the operation non-storing.

The current parser accepts a year represented as an integer or decimal
string, and note entries represented as strings or objects with a `name`.
Those are implementation compatibility facts, not a guarantee of the
vendor's future response contract. Validate shape changes with synthetic
fixtures; do not introduce additional live response payloads into tests.

See [ADR-002](planning/adr/adr-002-data-source-strategy.md) for the lookup
decision and [ADR-012](planning/adr/adr-012-data-source-compliance-and-manufacturer-provenance.md)
for source-policy context. This page does not authorize new endpoint use,
catalog import or model training.

## Permissions and publication

The [public API terms](https://api.fragella.com/terms-of-use.html), displayed
as updated May 4, 2026 and checked September 25, 2026, restrict standalone
distribution of API data and large-scale storage that substitutes for fresh
API access unless the subscription expressly permits it. They also reserve
rights in the service content. Review current terms and any applicable
written permission before the intended use; a paid quota alone does not
establish additional rights.

Project publication policy:

- Keep raw responses, response-derived inventories/aggregates, private
  correspondence, account usage and sample mappings out of the public
  repository, PR attachments and generated documentation.
- Retain original project code, instrument wording and design decisions.
  Use synthetic examples for contract tests and link to vendor documentation.
- Evaluate permissions by source, records, endpoint, purpose, retention term
  and downstream use. Permission for a bounded analysis does not establish
  permission for a larger collection, redistribution, training, embeddings
  or commercial display. Treat unconfirmed uses as unapproved.
- Keep permission evidence and retention obligations in a private record.
  Track derived material as well as original responses so a required purge
  or expiry can be honored. Do not assume a repository license grants rights
  to third-party material placed under it.

Ignoring a local cache prevents ordinary Git staging; it does not grant
storage or reuse rights. Review unresolved retention separately from this
documentation change. Existing stored lookup results and historical fixtures
also need their own scope review; this page is not a certification of them.
