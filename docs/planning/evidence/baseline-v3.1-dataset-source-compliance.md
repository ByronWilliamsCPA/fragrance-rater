---
title: "Baseline/Holdout V3.1 Dataset-Building Source Compliance Check"
schema_type: common
status: published
owner: core-maintainer
purpose: "Checks whether building a fuller public-source dataset (notes/accords/ratings, not just source_url identity) for the 33 baseline + 10 holdout fragrances can proceed under each candidate site's own stated crawler policy, before any further fetching is done."
tags:
  - planning
  - calibration
  - evidence
  - compliance
---

**Date:** 2026-09-15

**Prompted by:** "Using publicly available sources and not violating terms of service, let's
see how much of a base dataset we can create on our 33 baseline fragrances and the 10
evaluation fragrances" - a follow-up to
[Parfumo Source Resolution](baseline-v3.1-parfumo-source-resolution.md), which resolved each
entry's identity (brand/name/concentration/year/`source_url`) but deliberately stopped short
of pulling actual note/accord/rating content at scale.

## Finding: all three candidate sites name Claude's crawler specifically, and exclude it

Before running `ParfumoScraper`/`import-data parfumo-url` against the 43 resolved URLs (or
attempting Fragrantica/Basenotes as ADR-002's manual-copy fallback describes), this fetched
`robots.txt` fresh from all three sites. Each one carries a `User-agent: ClaudeBot` block with
`Disallow: /` - a site-wide exclusion, naming Anthropic's crawler specifically, not merely a
generic `User-agent: *` restriction:

| Site | Generic (`User-agent: *`) | `ClaudeBot`-specific block |
| :--- | :--- | :--- |
| parfumo.com | `Content-Signal: search=yes, ai-input=yes, ai-train=no`; only a handful of `/action/`, `/api/`, search-script paths disallowed - perfume pages are not | Listed by name in a large second group (with GPTBot, Meta-ExternalAgent, Amazonbot, ia_archiver, and ~20 others) carrying `Disallow: /` for the entire site |
| `fragrantica.com` / `www.fragrantica.com` | `Content-Signal: search=yes,ai-train=no,use=reference`; `Allow: /` | Listed individually with `Disallow: /`, alongside Amazonbot, Applebot-Extended, Bytespider, CCBot, GPTBot, Google-Extended, meta-externalagent. A comment even records a deliberate carve-out for a *different* Anthropic agent: `Claude-User (Anthropic's on-demand fetcher for user questions, cites sources) is deliberately NOT listed here: it falls under the User-agent: * rules like ChatGPT-User` - i.e., the operator considered Claude's agents specifically and chose to exclude the bulk/autonomous crawler (`ClaudeBot`) while allowing the on-demand, cites-its-source fetcher (`Claude-User`). This project's scraper identifies as neither; it sends a plain Chrome browser user agent (see below) - it is not `Claude-User` making a cited, user-visible fetch. |
| basenotes.net (redirects to itself; robots.txt read via redirect) | `Allow`-by-default, no distinguishing `Content-Signal` seen | Listed individually with `Disallow: /`, alongside Amazonbot, Applebot-Extended, Bytespider, CCBot, CloudflareBrowserRenderingCrawler, Google-Extended, GPTBot, meta-externalagent |

**Independent re-verification (2026-09-17):** the table above summarizes the 2026-09-15 finding
in prose; for a later reviewer to check it without repeating the research from scratch, here is
the verbatim `ClaudeBot` block fetched directly from each site's `robots.txt` (fetching the
policy document itself, not a content page, so it carries none of this document's own crawl
restriction):

- `https://www.parfumo.com/robots.txt` (fetched 2026-09-17): the `ClaudeBot` line sits in a
  shared `User-agent` list (with `GPTBot`, `Meta-ExternalAgent`, `Amazonbot`, `ia_archiver`, and
  roughly twenty others) followed by a single `Disallow: /` covering the whole list.
- `https://www.fragrantica.com/robots.txt` (fetched 2026-09-17):

  ```text
  User-agent: ClaudeBot
  Disallow: /

  User-agent: Claude-SearchBot
  Disallow: /

  # Claude-User (Anthropic's on-demand fetcher for user questions, cites sources) is deliberately NOT listed here:
  # it falls under the `User-agent: *` rules like ChatGPT-User. Decision 2026-09-10 (AI answer-engine measurement window).
  ```

  This also shows `Claude-SearchBot` excluded alongside `ClaudeBot` (not previously called out
  above), and dates the site operator's `Claude-User` carve-out decision to 2026-09-10, before
  this dataset-building pass even started. Note: this re-fetch found no `Content-Signal` line on
  `fragrantica.com`; the 2026-09-15 finding recorded one
  (`search=yes,ai-train=no,use=reference`). Both observations are recorded as fetched rather than
  reconciled, since `robots.txt` is not a versioned document and either snapshot could have been
  accurate at its own fetch time.
- `basenotes.net/robots.txt` and `basenotes.com/robots.txt` both returned `HTTP 403` to this
  re-fetch attempt (no body), consistent with the 2026-09-15 finding's note that basenotes.net
  needed a redirect to read at all; this document retains the original transcription for
  basenotes.net on trust rather than re-verifying it, since the site currently blocks even the
  robots.txt fetch itself.

This is a materially different situation from the generic "ToS concerns, fragile" risk ADR-002
already recorded for Fragrantica scraping, and from the Cloudflare bot-challenge finding in
[Parfumo Source Resolution](baseline-v3.1-parfumo-source-resolution.md#supplemental-source-exploration-2026-09-12).
Those were about *technical* access control (a JS challenge) or a general AI-training
objection (`ai-train=no`). This is the operator naming this agent's own crawler and refusing it
crawl access outright, on all three sites - not a training-data objection, a crawling
exclusion.

`ParfumoScraper.HEADERS` (`src/fragrance_rater/services/parfumo_scraper.py`) sends a plain
desktop Chrome `User-Agent` string - "Keep headers minimal to avoid Cloudflare issues," per its
own comment - and does not identify as `ClaudeBot` or any other bot. That was written to get
past Cloudflare's bot challenge, not to route around a robots.txt exclusion; nothing in ADR-002
or the scraper's design considered whether Parfumo's robots.txt names Claude specifically,
because nobody had checked. Now that it is known that Parfumo, Fragrantica, and Basenotes all
name `ClaudeBot` with a site-wide `Disallow: /`, continuing to fetch their content pages from
this session - regardless of what `User-Agent` string the request carries - would mean this
agent knowingly disregarding an exclusion the site operator wrote for it by name. That holds
whether the fetch goes through `ParfumoScraper`, a fresh `curl`, or anything else run from this
session; the browser-like `User-Agent` was never a considered decision to identify as something
other than what this session is, it just predates this check.

**Consequence for this task: no further content fetches (perfume pages, note pyramids,
accords, ratings) were made against parfumo.com, fragrantica.com, or basenotes.net in this
pass.** The two live Parfumo page fetches recorded in
[P1.9 evidence](../gates/p1.md#p19-evidence-2026-09-12) (Creed Aventus, Chanel Bleu de Chanel,
for parser-fixture verification) and the per-entry identity checks in
[Parfumo Source Resolution](baseline-v3.1-parfumo-source-resolution.md) both predate this
check and are not undone retroactively by it, but they are flagged here for the product owner's
awareness since they used the same scraper/access pattern this finding now calls into question.

## What this does not change

- `WebSearch` (a licensed search API returning indexed snippets, distinct from operating a
  crawler against these sites directly) is unaffected by this finding and remains the path
  [Parfumo Source Resolution](baseline-v3.1-parfumo-source-resolution.md#supplemental-source-exploration-2026-09-12)
  already used for one-off reference lookups (H07, H04, B30, H10). This compliance check itself
  used `WebSearch` no further than that prior document already recorded; the separate,
  later dataset-building pass that did use `WebSearch` at scale is documented below, under
  Follow-up.
- Fragella (`fragella_client.py`, `import-data fragella-lookup`) is a direct API integration
  against a service that publishes and rate-limits its own API for this purpose; it is not a
  site scrape and this finding does not affect it. It remains capped at 20 requests/month and
  reference-only per ADR-002's 2026-09-12 amendment - it cannot alone build a 43-entry dataset.
- Kaggle bulk import (`import-data kaggle`) reads a CSV a human downloads directly from Kaggle
  under Kaggle's own dataset terms; it is not a crawl of any of the three sites above and this
  finding does not affect it. Whether an existing Kaggle fragrance dataset actually covers these
  43 specific entries (many are small/niche houses - Papillon, Akro, Zoologist, Imaginary
  Authors, Indult) is unverified; no such CSV is present in this repository today.
- Manual entry (a person browsing these sites themselves and pasting notes into the app, per
  ADR-002's existing "UI provides copy-paste from Fragrantica" mitigation) is unaffected by
  *this specific finding*: `robots.txt` exclusions bind automated crawlers, not a human reading
  a page in their own browser. That is a statement about crawling, not about redistribution
  rights - a `robots.txt` `Disallow` says nothing about whether copying a site's note pyramid
  or accord description into this application's catalog is permitted under that site's terms of
  use or copyright. ADR-002's existing reuse-rights review requirement for any source still
  applies in full to manual copy-paste; this finding neither satisfies nor waives it.

## Recommendation

- Do not run `import-data parfumo-url`/`parfumo-search` (or any other automated fetch against
  parfumo.com, fragrantica.com, or basenotes.net) from an Anthropic-agent session until the
  product owner decides how to treat the `ClaudeBot` exclusion - this is a policy question, not
  something to route around with a different header.
- ADR-002 should be amended to record this exclusion explicitly (a "current implemented source
  path" that turns out to be crawler-excluded by the source's own policy is exactly the kind of
  fact that ADR is supposed to carry) and to decide a path forward: e.g., restrict `Fragrance`
  catalog enrichment to human-run imports (a person runs `import-data parfumo-url` themselves,
  or pastes notes manually), pursue a licensed/consented data path, or accept `WebSearch`/
  Fragella as the only agent-safe supplements.
- Until that decision is made, this pass answers the prompt directly: **the base dataset this
  session can build from public sources without disregarding a site's stated crawler exclusion
  is the identity/`source_url` resolution already recorded in
  [Parfumo Source Resolution](baseline-v3.1-parfumo-source-resolution.md), plus whatever
  `WebSearch` and Fragella's capped quota can add** - not the fuller notes/accords/ratings
  corpus a direct scrape of the 43 resolved pages would have produced.

## Follow-up: the dataset that was built

Per the product owner's follow-up ("this is a one time exercise, we don't need to build
repeatable processes"), a one-time research pass was run for all 43 entries: primarily
`WebSearch`, with three entries (Baccarat Rouge 540, Mitsouko, Shalimar) also using a direct
`WebFetch` against Wikipedia specifically, which is not one of the three excluded sites and so
carries none of this document's finding. This was not a `WebSearch`-only pass in the strict
sense; it is accurate to call it a `WebSearch`-primary pass with three documented direct-fetch
exceptions, none of them against parfumo.com, fragrantica.com, or basenotes.net. That dataset
(notes/accords/family/perfumer/description content with per-entry source citations) is
intentionally not committed to this repository: it is not published evidence, it lives only in
local working storage as non-published research notes, because it directly documents the
answer key for a blind evaluation (see [Calibration V1](../../calibration-v1.md) and ADR-005)
that family members with repo access will be participating in. This pass added no code,
scraper, or import path; consistent with this document's recommendation above.
