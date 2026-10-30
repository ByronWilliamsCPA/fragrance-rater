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

Reviewed September 25, 2026, by reading the vendor's published documentation pages at the
linked URLs. This project reference links to the
[vendor API documentation](https://api.fragella.com/docs.html) rather than
maintaining a copy of its full specification, examples or catalog data.
For Fragrance Rater's own API, use the [API reference](api-reference.md).

## Existing implementation

`src/fragrance_rater/services/fragella_client.py` implements `FragellaClient`, the HTTP client
for vendor search and usage lookups. `src/fragrance_rater/services/fragella_lookup_service.py`
implements `FragellaLookupService.run_lookup()`, which persists the query, requesting operator,
status, error information and parsed result objects in `FragellaLookup`. It does not
automatically promote these results into the catalog or a `SourceSnapshot`. The stored parsed
results are still retained vendor data; an audit purpose does not make the operation
non-storing.

The current parser accepts a year represented as an integer or decimal
string, and note entries represented as strings or objects with a `name`.
Those are implementation compatibility facts, not a guarantee of the
vendor's future response contract. Validate shape changes with synthetic
fixtures; do not introduce additional live response payloads into tests.

See [ADR-002](planning/adr/adr-002-data-source-strategy.md) for the lookup
decision and [ADR-012](planning/adr/adr-012-data-source-compliance-and-manufacturer-provenance.md)
for source-policy context. This page does not authorize new endpoint use,
catalog import or model training.

## Integration notes

Reusable findings from live use of the vendor API. They describe observed
behavior, not a vendor guarantee; re-check against the
[vendor documentation](https://api.fragella.com/docs.html) before relying on
them.

### No batch lookups

The vendor's endpoints take one search term, one identifier, one brand name or
one seed name per call. `limit` bounds how many results come back for that one
input; it does not fetch several named fragrances at once. A search for one
name returns variants and near matches of that name, not unrelated items.
Looking up N distinct fragrances therefore costs N requests, and
`FragellaLookupService.run_lookup()` issues exactly one `search()` per call.
Fetching by a known identifier removes fuzzy-match ambiguity but costs the same
single request, so it improves accuracy, not cost.

### Encoding `#` in names and slugs

A literal `#` is the URL fragment delimiter. Interpolated unencoded into a URL
string, it truncates the request client-side: everything after it is dropped
before sending, so the vendor sees a shorter path and typically answers 404.
Always percent-encode it as `%23`. Some vendor identifiers contain a `#`. In
testing, the one path-style by-identifier request made with such an identifier
returned 400 with an empty body even when encoded, so prefer an identifier
without special characters when the same result set offers one.

`FragellaClient.search()` is not exposed to the truncation problem: it passes
the query through `httpx` `params`, which encodes `#` as `%23`. The risk applies
to any future path-style call (such as fetching by identifier) that builds a URL
by string interpolation; encode each path segment explicitly there.

### Live field shapes differ from the vendor docs

- `Year` is documented as an integer but a live response returned a numeric
  string. `_optional_year()` accepts an integer or a decimal string and returns
  `None` for anything else, such as a range or free text.
- `Notes.Top`, `Notes.Middle` and `Notes.Base` entries are documented as
  strings but a live response returned objects with a `name` key. `_str_list()`
  accepts either form and skips entries with no usable name.

The client accepts both forms because a vendor reshaping a field is more likely
to be reversed or mixed than permanent. When another divergence appears, update
the synthetic fixtures and the `#ASSUME` marker in the client module docstring
together, and keep live payloads out of tests and the repository.

### Quota mechanics

Usage is metered per request against a single pool shared across endpoints, and
exhaustion surfaces as HTTP 429 (`FragellaErrorCode.QUOTA_EXHAUSTED`). Treat
every lookup as a cost: validate input before sending (`search()` rejects short
queries locally and clamps `limit`), avoid repeating a lookup whose stored
result is still adequate, and do not call `usage()` automatically before each
search. `run_lookup()` does not consult earlier `FragellaLookup` rows, so callers
that want to avoid repeat spend must check `latest_by_fragrance()` first. Failed
lookups are recorded too, so a quota or key failure is visible rather than
silently retried. Whether a rejected request or a `usage()` call is metered is
not documented by the vendor; do not assume either way.

## Permissions and publication

The [public API terms](https://api.fragella.com/terms-of-use.html), displayed
as updated May 4, 2026 and checked September 25, 2026 by reading that published terms
page, restrict standalone
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
