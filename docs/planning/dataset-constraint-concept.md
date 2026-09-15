# Concept: Data Rights Constraint and Catalog Strategy Change

> **Status**: Draft for product-owner decision | **Version**: 1.0 | **Date**: 2026-09-15
>
> **Scope**: Evaluates viable architectures for fragrance metadata given that a large, locally
> stored catalog is no longer obtainable under acceptable licensing terms. Proposes a replacement
> concept and the milestone/ADR changes it would require.
>
> **Authority**: This document is analysis and a proposal. It changes no code, schema, ADR, or
> milestone status. [PROJECT-PLAN.md](PROJECT-PLAN.md) remains the execution authority until a
> decision here is accepted and the plan and ADRs are amended.

---

## 1. Summary

The project was designed around a **corpus**: import thousands of fragrance records, build
preference profiles from them, compute catalog-wide statistics, and rank the whole catalog to
surface recommendations. Every route to that corpus now has a rights problem. Scraping violates
source terms of service. Fragella can be queried but prohibits bulk storage of its data. Wikidata
is freely reusable but too sparse to be a catalog on its own.

The proposal in this document is to stop trying to own a corpus and to re-center the product on
the asset the family can legitimately hold: **the fragrances they physically own, cataloged once
and confirmed by a human, plus the perception evidence they generate themselves.** Candidates are
then brought to the system one at a time — typed in, or fetched per item — and scored against that
foundation, instead of being discovered by ranking a catalog the system is not allowed to keep.

The important finding is that **this does not invalidate merged work**. Everything through P6 and
F1 — capture, controlled calibration, identity, disclosure, deterministic scoring, outcome
measurement — is unaffected, because none of it needs a corpus. The damage is concentrated in two
planned milestones: D2 (catalog-wide statistics) and D4 (candidate discovery by corpus retrieval).
Those are the capabilities that genuinely die and must be re-scoped rather than re-labeled.

**Recommended route**: a layered architecture (§7) combining a Wikidata-backed identity layer, an
evaluator-confirmed baseline catalog, bring-your-own-candidate scoring with an optional
quota-capped Fragella assist, and an LLM used strictly to *nominate* candidate names — never to
supply metadata or produce a score.

---

## 2. Stating the constraint precisely

"Licensing" is being used as one word for three different questions, and they have different
answers, different remedies, and different risk profiles. Keeping them separate is what makes the
option analysis below tractable.

| Question | What binds us | Can it be negotiated? |
| :--- | :--- | :--- |
| May we **access** the data? | Site/API terms of service; automated-access clauses | Sometimes — an API key is exactly this |
| May we **store/retain** it? | Contract terms (Fragella's bulk-storage prohibition); EU database right | Yes, this is the usual subject of a written permission |
| May we **redistribute or display** it? | Copyright in the compilation; contract | Least relevant to us — this product is family-internal and unpublished |

Three consequences follow that materially change the option space:

1. **The binding constraint is contract, not copyright.** Individual facts ("Aventus contains
   bergamot") are thinly protected at best; the curated compilation is what carries value and
   protection. But a terms-of-service agreement binds regardless of whether the underlying facts
   are copyrightable. This means the constraint attaches **per source**, not to the data itself —
   the same fact obtained a different way carries different obligations.

2. **Data the evaluator enters is not sourced data.** If Byron reads the box in his hand, or a
   brand's own product page, and types the notes in, that record has clean first-party provenance.
   No third party's terms attach to it. This is the single most important lever available.

3. **Redistribution risk is near zero here and should not drive the design.** The deployment is a
   home server behind Authentik/Traefik for four family members. The exposure is contractual and
   reputational, not a publishing question. Design for the retention constraint, which is real,
   not for a redistribution constraint that this product does not trigger.

### 2.1 Claims this document has *not* verified

These are asserted by the product owner or inferred, and each is load-bearing for at least one
option below. Each needs a named owner before a route is committed (see §11).

- The exact wording of Fragella's prohibition on bulk storage, and whether it permits a bounded
  cache, derived values, or a small licensed record count.
- Whether Fragella's paid tiers alter the storage terms or only the quota.
- Wikidata's actual coverage of perfume *versions* and note pyramids. Expected to be weak, but the
  real number is one SPARQL query away and nobody has run it.
- The upstream provenance of the Kaggle dataset behind the implemented importer. Most public
  fragrance datasets are Fragrantica extractions. **A Kaggle uploader's CC0 label does not grant
  rights the uploader never held** — the dataset's licence field is not evidence of clean title.

---

## 3. What the constraint actually breaks

Mapping the constraint onto the current plan, rather than treating it as a general crisis, shows
the blast radius is narrow and specific.

| Capability | Needs a corpus? | Status under the constraint |
| :--- | :--- | :--- |
| Ordinary encounter capture (P1–P4) | No | Unaffected |
| Controlled calibration, blinding, holdouts (P1, P6) | No | Unaffected |
| Version identity and provenance (ADR-006) | No | Unaffected; arguably easier with fewer sources |
| Preference profile from rated fragrances (ADR-007) | No — only the rated set | Unaffected |
| Deterministic affinity scoring of a *named* fragrance | No — only that one item's notes | Unaffected |
| LLM explanation of a score (ADR-003) | No | Unaffected |
| Outcome measurement, prospective evaluation (P2, ADR-009) | No | Unaffected in mechanism |
| **Catalog-wide statistics: lift, co-occurrence (D2)** | **Yes** | **Not achievable as specified** |
| **Ranking the catalog to surface candidates (D4)** | **Yes** | **Not achievable as specified** |
| Coverage and variety metrics (vision success measures) | Yes — presumes a candidate pool | Must be redefined against a smaller pool |

The distinction that does the work:

> **Scoring a candidate needs metadata for one fragrance. Discovering a candidate needs metadata
> for all of them.** The constraint permits the first and forbids the second.

The product can still answer *"how well does this match you?"* for anything the user can name. It
can no longer answer *"out of everything that exists, what should you try?"* from its own data.

---

## 4. The two audiences

The product owner identifies mainstream and indie seekers as distinct audiences. They are affected
very differently, and this turns out to argue **for** the pivot rather than against it.

| | Mainstream | Indie |
| :--- | :--- | :--- |
| Coverage in any scraped corpus | Good | Poor — long tail, frequent releases, small houses |
| Coverage in Fragella | Likely good (unverified) | Likely thin (unverified) |
| LLM parametric knowledge | Strong — widely discussed designer releases | Weak and prone to confident fabrication |
| Brand publishes its own notes | Inconsistently; often marketing copy | **Usually, in detail** — it is the selling point |
| Native discovery channel | Retail, mass review sites | Samples, decants, discovery sets, community |

An indie-focused product was never going to be well served by a bulk corpus; the corpus would have
been systematically worst exactly where this audience lives. Manual, evaluator-confirmed entry
against the brand's own published pyramid, combined with sample-based evaluation, **is** the native
indie workflow. The proposed architecture treats indie as first-class rather than as long-tail
residue.

The honest cost lands on the mainstream side: mainstream users are the ones who would have
benefited most from "rank 60,000 fragrances for me," and they are the ones who lose it.

---

## 5. Options

Each option is assessed on rights posture, coverage by audience, cost, what it preserves of the
existing plan, and what it forecloses.

### Option A — Closed baseline catalog with manual candidate entry

The family's owned fragrances are cataloged once, by hand, from the bottle and the brand's own
published pyramid. Candidates are entered the same way: brand, name, concentration, notes. The
existing deterministic scorer runs unchanged.

- **Rights**: Cleanest available. No third-party corpus, no retention question, no ToS exposure.
  Every stored record is first-party.
- **Coverage**: Complete for anything the user can physically reach or read about — equally good
  for indie and mainstream. Bounded by user effort, not by a vendor.
- **Cost**: Zero recurring. One-time baseline cataloging effort, already partly done for the V3.1
  baseline.
- **Preserves**: All of P1–P6, F1, ADR-006 identity, ADR-007 scoring, ADR-009 evaluation.
- **Forecloses**: Corpus statistics and corpus retrieval (D2, D4 as written).
- **Main weakness**: Entry burden — roughly ten notes per candidate — and it leaves *"where do
  candidates come from?"* unanswered. Mitigated by a note-name autocomplete built from an openly
  licensed vocabulary (Wikidata terms, the already hard-coded Edwards taxonomy, and note names the
  evaluators have themselves entered). Note *names* are vocabulary, not a protected compilation.
- **Verdict**: **Viable as the foundation.** Insufficient alone as a product.

### Option B — Fragella as a per-candidate, non-retained lookup

Option A, plus: when the user names a candidate, one API call fetches its metadata, the user
confirms or corrects it against the bottle or product page in front of them, and the *confirmed*
record is what is stored. The vendor payload itself is not retained as a catalog row.

- **Rights**: Depends entirely on §2.1's unverified terms. The architecture is designed to sit on
  the right side of a bulk-storage prohibition — data is transient input to a computation, not
  inventory — and it extends a boundary ADR-002's 2026-09-12 amendment already drew for
  operator-invoked disambiguation. But the *use* changes from internal decision support to a
  product function, which is precisely what triggers the reuse-rights review ADR-002 and ADR-006
  require. **This option cannot be adopted on the strength of the existing amendment.**
- **A caveat worth stating plainly**: "the human confirmed it, so it is first-party data" is a
  defensible position when the person is verifying against a physical bottle they are holding — the
  actual pilot context. It is not defensible if confirmation degrades into clicking OK. The
  distinction should be enforced in the UI (require the confirming evaluator to have the item, or
  mark the record as unconfirmed and ineligible for controlled assignment), and it should be put to
  the vendor in writing rather than assumed.
- **Reproducibility tension**: ADR-006 requires statistical artifacts to be regenerable from pinned
  inputs. If the payload is not retained, a score cannot be reproduced from its original source.
  The resolution is that the **evaluator-confirmed note set is the pinned input**, not the vendor
  response. That is a coherent provenance story, and it must be written into ADR-006 rather than
  left implicit.
- **Coverage**: Good for mainstream, unverified and probably thin for indie.
- **Cost**: 20 requests/month free — genuinely might suffice if used only where manual entry fails.
  The paid tier (~$29/month, unverified) would comfortably cover four evaluators. For context, a
  single avoided 100ml mistake pays for roughly a year of the paid tier.
- **Verdict**: **Viable as an assist, conditional on the rights review.** Must never become the
  path of least resistance for bulk cataloging, or it recreates the prohibited outcome by accretion.

### Option C — Openly licensed identity layer (Wikidata and brand-published data)

Use Wikidata (CC0 — bulk storage and redistribution unrestricted) for what it is actually good at:
brand, product, launch year, perfumer, and stable identifiers. Pair it with brand-published note
lists read by a human.

- **Rights**: CC0 is as permissive as it gets. No retention question at all.
- **Coverage**: Expected to be weak for products and near-absent for note pyramids — but it maps
  onto ADR-006's hardest problem, **version identity**, at zero rights risk. Coverage is unmeasured
  (§2.1).
- **Cost**: Zero.
- **Verdict**: **Viable as an identity and disambiguation backbone, not as a catalog.** Low effort,
  low risk, worth doing regardless of which other options are chosen.

### Option D — Agent-mediated recommendation

The baseline catalog and the family's preference evidence go into a prompt; the model's own
knowledge of the fragrance world supplies the candidates and their characteristics; the user asks
questions conversationally.

- **Rights**: Clean. No corpus is stored.
- **Coverage**: Strong for widely discussed mainstream releases. Weak for indie, weak for anything
  after the model's cutoff, and **prone to fabricating note lists with total confidence**.
- **The decisive objection**: this option is in direct conflict with the project's foundations. The
  vision requires that published catalog metadata, evaluator perception, and model interpretation
  be preserved as three separate kinds of evidence and never conflated. An LLM's account of a
  fragrance's notes is model interpretation wearing the costume of published data. It cannot be
  frozen, has no source snapshot, has no content hash, and cannot support the frozen-input
  requirement that ADR-009 and D5 are built on. ADR-003 already confines the LLM to *explaining*
  deterministic scores, with deterministic fallback, for exactly this reason.
- **Verdict**: **Not viable as the scorer or as a metadata source.** Genuinely valuable in one
  narrow role — see Option D′.

### Option D′ — Agent as candidate nominator only

The model proposes *names* ("given what you like, consider Chanel Sycomore, Zoologist Hummingbird,
…"). It supplies no notes and no score. Each nominated name is then subject to normal identity
verification, and its metadata comes from manual entry or an Option B lookup before the
deterministic scorer touches it.

- **Rights**: Clean.
- **What it fixes**: This is the missing half of Option A. It answers "where do candidates come
  from?" without letting model output anywhere near the evidence layer.
- **Required guardrails**: nominations are labeled as model-generated suggestions; a nominated name
  is not a catalog row; nothing is scored until its identity is verified and its notes confirmed;
  hallucinated fragrances fail verification and are discarded, which is the system working
  correctly. Nominations must not be able to read holdout outcomes, per existing D4 criteria.
- **Verdict**: **Viable and additive.** Recommended.

### Option E — Negotiate a written licence

Ask Fragella for written permission covering family-internal, non-redistributed storage of a
bounded number of records.

- **Rights**: Definitive if granted — a written permission is exactly the evidence ADR-006 demands.
- **What it preserves**: The **only** option that keeps D2 and D4 substantially as designed.
- **Cost**: One email. Possibly a paid tier.
- **Likelihood**: Unknown, but a non-commercial, private, four-user, no-redistribution request is
  the least threatening ask a data vendor receives.
- **Verdict**: **Worth initiating immediately and in parallel.** It is cheap, it is the only route
  that recovers the lost capabilities, and a "no" costs nothing but confirms the pivot.

### Options rejected outright

| Option | Why not |
| :--- | :--- |
| Continue scraping, accept the risk | Violates the stated constraint; also violates the project's own security-first and rights-review standards. Not a live option. |
| Rely on the existing Kaggle import for production | Provenance unverified and probably Fragrantica-derived (§2.1). A dataset's Kaggle licence field is not title. |
| Crowdsource a public open fragrance database | Right idea, wrong decade for this project. Years of effort before it serves one family. |

---

## 6. Option comparison

| | A: Manual | B: Fragella assist | C: Wikidata | D′: Agent nominate | E: Licence |
| :--- | :--- | :--- | :--- | :--- | :--- |
| Rights risk | None | Conditional | None | None | None if granted |
| Mainstream coverage | Good | Good | Weak | Strong | Good |
| Indie coverage | Good | Thin | Weak | Weak | Thin |
| Recurring cost | $0 | $0–29/mo | $0 | LLM tokens | Vendor-set |
| User effort | High | Medium | n/a | Low | Low |
| Preserves D2/D4 | No | No | No | No | **Yes** |
| Ready to build now | Yes | After review | Yes | Yes | Blocked on vendor |

No single column wins. A, C, and D′ are complements, not alternatives — which is what §7 proposes.

---

## 7. Recommended concept: a layered catalog

Rather than choosing one option, layer them so that each does only what it is entitled to do. The
rule that holds the design together: **each layer may only write into the layer below it through a
human confirmation step.**

```text
Layer 4  Evidence         first-party perception, ordinary + controlled
                          ← the family's own data; unencumbered; the real asset
Layer 3  Nomination       LLM proposes candidate NAMES only (Option D')
                          ← labeled as model output; never a catalog row
Layer 2  Candidate        BYO candidate: manual entry (A), optional per-item
                          Fragella lookup (B), evaluator-confirmed before storage
Layer 1  Foundation       owned baseline catalog, cataloged once, human-confirmed (A)
                          ← the scoring foundation; entirely first-party
Layer 0  Identity         Wikidata CC0 identity backbone: brand, product, year,
                          perfumer, stable IDs (C)
```

**How a recommendation happens under this concept:**

1. The evaluator asks for ideas, or brings a name they encountered in a shop.
2. Layer 3 may propose names, grounded in the Layer 1/4 profile, clearly labeled as suggestions.
3. The evaluator picks a handful. Each is identity-verified against Layer 0.
4. Metadata is entered manually, or fetched once and confirmed against the physical item.
5. The existing deterministic scorer produces an affinity score with its veto rule, unchanged.
6. The LLM explains the score under ADR-003, as it already does.
7. If sampled, the outcome is recorded through the existing P2 measurement path, as designed.

The product's character changes from **recommender** to **decision support for a shortlist**. The
primary outcome measure — post-sample liking against a declared baseline strategy — survives
intact, and arguably improves: candidates are now necessarily ones the family can actually obtain,
which D4 already listed as a criterion.

---

## 8. What this costs us

Stated plainly, because the pivot should not be sold as a pure win:

1. **Open-ended discovery is gone.** "Find me something I've never heard of, from everything that
   exists" is no longer a capability the system's own data can support. Layer 3 approximates it for
   mainstream fragrances and does so unreliably for indie ones.
2. **Association statistics are gone.** Lift, observed-minus-expected, and partner share need
   thousands of fragrances to be meaningful. Computing them over ~43 owned versions would produce
   numbers that look like statistics and are not. D2's own acceptance criteria — minimum support,
   shrinkage policy, denominators — are the reason: they cannot be satisfied at this scale.
3. **User effort rises.** The system now asks the family to do work the corpus was going to do.
4. **Coverage and variety metrics need redefinition.** They currently presume a candidate pool
   large enough for concentration to be a risk.
5. **The system's knowledge is bounded by the family's reach.** That is a real ceiling, and it is
   also, for a four-person household product, a largely acceptable one.

---

## 9. Proposed milestone changes

Proposed only; PROJECT-PLAN.md is amended after a decision, not by this document.

| Milestone | Current intent | Proposed |
| :--- | :--- | :--- |
| P1–P6, F1 | Release readiness through family pilot | **Unchanged.** No dependency on a corpus. |
| D1 | Source and vocabulary foundation | **Retained, re-aimed.** Vocabulary and alias work still matter; source work narrows to Wikidata (CC0), evaluator-entered terms, and the rights record for any Fragella use. Its "decisions due" table already defaults to *do not import* — that default now becomes the decision. |
| D2 | Reproducible catalog statistics | **Re-scoped.** Corpus-wide association statistics are not achievable. Replace with within-baseline descriptive statistics, explicitly labeled small-N, with no lift or beyond-chance claims. Keep the snapshot/manifest/determinism contract, which is still correct and still needed. |
| D3 | Post-reveal exploration | **Largely retained.** Its evidence-boundary labeling requirements become *more* important, since Layer 3 adds a model-generated surface that must be labeled as such. |
| D4 | Candidate discovery pilot | **Replaced.** "Retrieve similar profiles from a corpus" becomes "nominate, verify, confirm, and score user-selected candidates." Most acceptance criteria survive verbatim — per-candidate provenance, distinct concentration variants, identity verified before assignment, separate predicted-liking/novelty/uncertainty/availability fields, no access to holdout outcomes. The retrieval step is what changes. |
| D5 | Prospective evaluation | **Retained, comparison redefined.** Still a real prospective experiment, but comparing *advice strategies over user-nominated candidates* rather than retrieval strategies over a corpus. Four evaluators and a shortlist workflow make the uncertainty reporting requirement more binding, not less. |

---

## 10. Impact on existing code and decisions

Raised for decision. This document changes none of it.

| Item | Issue | Proposed disposition |
| :--- | :--- | :--- |
| `services/parfumo_scraper.py` | **Sharpest live issue.** An implemented scraper against a Cloudflare-protected site, directly in scope of the ToS constraint. Currently writes `Fragrance`, `Note`, and `SourceSnapshot` rows. | Decide explicitly: quarantine, restrict to operator-invoked single-URL fetch with retained snapshots only where permitted, or remove. Leaving it merged and unaddressed is not a neutral choice. |
| `services/kaggle_importer.py` | Upstream provenance unverified; probably Fragrantica-derived. | Do not use for production seeding until provenance is established. Retain for fixtures and tests. |
| `services/fragella_client.py` | Correctly built as a non-storing, quota-capped lookup. Already the right shape for Option B. | Keep. Any promotion to a product-facing candidate lookup requires the ADR-002/006 rights review first. |
| ADR-002 | Its tiered strategy assumed a bulk seed tier that no longer exists. | Supersede with a new ADR recording the layered concept and the retirement of the bulk tier. |
| ADR-006 | Requires reproducibility from pinned inputs; must state that the **evaluator-confirmed** record is the pinned input where a source payload is not retained. | Amend. |
| ADR-004/007 | Scoring mechanics are unaffected — they operate on one fragrance's notes. | No change. |
| ADR-003 | Must be extended to cover the nomination role and its labeling, or nomination must be a new ADR. | Amend or add ADR-012. |
| Vision success measures | Coverage and variety presume a large candidate pool. | Redefine against the shortlist workflow. |

---

## 11. Verification tasks before committing

| # | Task | Blocks | Owner |
| :--- | :--- | :--- | :--- |
| 1 | Read Fragella's terms verbatim; record the exact storage/caching/derived-value language | Option B | Core maintainer |
| 2 | Ask Fragella in writing about a bounded cache, storing derived scores, and a small licensed record count for private family use | Options B, E | Product owner |
| 3 | Run a SPARQL probe for Wikidata perfume coverage: product count, note-pyramid presence, perfumer and year completeness | Option C, D1 | Core maintainer |
| 4 | Establish the upstream provenance of the Kaggle dataset in use | Kaggle disposition | Core maintainer |
| 5 | Time a manual catalog entry end to end; ten entries gives a real per-candidate effort figure | Option A viability | Product owner |
| 6 | Spot-check Fragella and LLM coverage against ten indie fragrances the family would plausibly consider | Audience strategy | Product owner |
| 7 | Decide the disposition of `parfumo_scraper.py` | Release posture | Product owner |

Tasks 1–3 and 7 are the ones that should not wait. Task 2 should be sent today regardless of which
route is chosen: it is the only path that recovers D2 and D4, and a refusal costs nothing.

---

## 12. Decision requested

1. Accept, reject, or amend the layered concept in §7 as the replacement data strategy.
2. Confirm the re-scoping of D2 and D4 in §9, accepting the capability losses in §8.
3. Authorize the verification tasks in §11, and the written approach to Fragella in particular.
4. Decide the disposition of `parfumo_scraper.py` and the Kaggle import path.
5. On acceptance, authorize a superseding ADR for ADR-002 and amendments to ADR-003 and ADR-006,
   followed by a PROJECT-PLAN.md revision.

Until items 1–2 are decided, D-series implementation should not start. P1 evidence, P6, and F1 are
unaffected and may proceed on the current plan.

---

## Related

- [PROJECT-PLAN.md](PROJECT-PLAN.md) — execution authority; D1–D5 as currently written
- [project-vision.md](project-vision.md) — the three-evidence-layer principle this concept preserves
- [ADR-002](adr/adr-002-data-source-strategy.md) — tiered acquisition; the bulk tier this retires
- [ADR-003](adr/adr-003-llm-integration.md) — LLM confined to explanation with deterministic fallback
- [ADR-006](adr/adr-006-version-identity-and-source-provenance.md) — identity, provenance, reuse rights
- [ADR-007](adr/adr-007-preference-evidence-and-score-semantics.md) — score semantics, unchanged here
- [ADR-009](adr/adr-009-prospective-evaluation-and-checkpoints.md) — frozen inputs, prospective evaluation
- [baseline-v3.1-parfumo-source-resolution.md](evidence/baseline-v3.1-parfumo-source-resolution.md) — the manual resolution precedent
