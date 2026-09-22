---
title: "Repository Inconsistencies Review, September 2026"
schema_type: common
status: published
owner: core-maintainer
purpose: "Record documentation-vs-documentation and documentation-vs-code inconsistencies found by a targeted consistency audit, distinct from the broader architecture-review-2026-09.md."
tags:
  - planning
  - analysis
  - documentation
  - quality
---

> **Reviewed commit**: `56397d6` on `main` (2026-09-22) | **Review type**: read-only, evidence-anchored |
> **Authority**: advisory. This document records findings; it does not change plan status. Any
> accepted item must be scheduled through [PROJECT-PLAN.md](PROJECT-PLAN.md) change control and,
> where it touches a durable decision, an ADR.

## 1. Scope and method

This review targets a narrower question than
[architecture-review-2026-09.md](architecture-review-2026-09.md): not "is the design sound" but
"do the project's own documents, ADRs, and code agree with each other." Four independent
read-only passes were run in parallel: scoring/evidence ADRs vs. code, auth/calibration ADRs vs.
code, CI/tooling docs vs. actual config, and cross-consistency among the top-level planning docs
(`CLAUDE.md`, `PROJECT-PLAN.md`, `roadmap.md`). Every finding below was independently verified
against source after the passes reported in. Items already self-acknowledged in the repository
(the duplicate ADR-014 numbering, the un-regenerated `CLAUDE.md` structure section, the S-01
Authentik header-spoofing gap) are noted for completeness but not reported as new findings.

## 2. Findings

| ID | Severity | Finding | Evidence | Suggested action |
| :--- | :--- | :--- | :--- | :--- |
| DC-01 | High | `CLAUDE.md`'s status blockquote states "P0-P5 are complete," but `PROJECT-PLAN.md` — the document `CLAUDE.md` itself names as the authority on milestone status — gives P1's status as "Repository controls implemented; external evidence pending through P6," not complete. The same blockquote sentence then treats P1 evidence as a thing that still "precedes F1," which cannot be true of a "complete" milestone. | `CLAUDE.md` status blockquote (top of file); `docs/planning/PROJECT-PLAN.md:128` (`## 6. Milestone P1`, **Status** line) | Reword the blockquote to "P0, P2-P5 are complete; P1's repository controls are complete but external evidence is pending through P6," matching `PROJECT-PLAN.md`'s own wording. |
| DC-02 | High | `docs/calibration-v1.md` describes `affinity-v1` as the live scoring model ("This explicit `affinity-v1` heuristic preserves..."), but ADR-009's 2026-09-19 amendment made `affinity-v2` the default, and the code confirms it: `DEFAULT_MODEL_KEY = "affinity-v2"`. `calibration-v1.md` was last substantively touched 2026-09-12, before the amendment, and was never updated — yet `CLAUDE.md` points readers to it by name for "controlled workflow and deployment constraints." | `docs/calibration-v1.md:90`; `docs/planning/adr/adr-009-prospective-evaluation-and-checkpoints.md` (2026-09-19 amendment, "Baseline" row); `src/fragrance_rater/ml/registry.py:26` | Update `calibration-v1.md`'s model description to `affinity-v2`, and fold in the ADR-005 2026-09-19 protocol-value amendment (daily load, calendar compression, inter-stimulus procedure) it also does not yet reflect. |
| DC-03 | High (fixed in this review) | Inside `recommendation_service.py`, a class docstring three lines above a constructor comment gave two different defaults for the same field. The docstring (lines 105-107) correctly said the scorer "defaults to the registered default scorer (`affinity-v2`)"; the constructor comment immediately below (line 112) said "Defaults to the frozen affinity-v1 heuristic." The actual runtime default is `affinity-v2` (`DEFAULT_SCORER_FACTORY()` resolves to `ml/registry.py`'s `DEFAULT_MODEL_KEY`). The line-112 comment was a leftover from before the 2026-09-19 affinity-v2 amendment. | `src/fragrance_rater/services/recommendation_service.py:105-107` vs. `:112` (pre-fix); `src/fragrance_rater/ml/registry.py:26` | Fixed: corrected the constructor comment to match the docstring and the actual default. |
| DC-04 | Medium (fixed in this review) | The same file's module docstring said the algorithm uses "Cumulative note/accord/family affinities from user ratings" (line 4), describing the pre-ADR-007 semantics. ADR-007 (Accepted, 2026-09-11) replaced that with "latest live ordinary encounter per reviewer/version, one contribution per fragrance version," and the code in `build_preference_profile` implements exactly the ADR-007 rule, not the cumulative one the docstring described. | `src/fragrance_rater/services/recommendation_service.py:1-6` (pre-fix) vs. `:117-` (`build_preference_profile`); `docs/planning/adr/adr-007-preference-evidence-and-score-semantics.md` | Fixed: updated the module docstring to describe latest-per-version aggregation under ADR-007. |
| DC-05 | Medium | `docs/planning/roadmap.md` (dated 2026-09-19) lists Milestone R's "Immediate queue" as "R1 ... R2 ... R3 ... and R4 ... in parallel, then R5-R8 before F1," presenting all of R1-R8 as pending. `PROJECT-PLAN.md` (dated 2026-09-21, the more current document) marks R1 "done 2026-09-21" and R5 "done 2026-09-19." `roadmap.md` states its own rule that it "must be updated from that plan in the same pull request" — that rule was not followed here. | `docs/planning/roadmap.md:3,40-42`; `docs/planning/PROJECT-PLAN.md:511` (R1 row), `:515` (R5 row) | Update roadmap.md's immediate-queue list whenever an R-sprint closes in PROJECT-PLAN.md, per its own change-control rule. |
| DC-06 | Medium | `CLAUDE.md`'s "Key Architecture Decisions" summary list runs ADR-001 through ADR-013 (skipping straight from ADR-009 to ADR-011) and stops at ADR-013, omitting ADR-010, ADR-014, and ADR-016 entirely, even though all three are live, actively-cited decisions elsewhere in the same planning set (ADR-010 gates R6-R8; ADR-014 closed via PR #103 and is cited repeatedly in `PROJECT-PLAN.md`'s Milestone R section; ADR-016 is a current Proposed record). A reader orienting from `CLAUDE.md` alone would not know these ADRs exist. | `CLAUDE.md` "Key Architecture Decisions" list; `docs/planning/adr/README.md` (full index, ADR-001 through ADR-016) | Add ADR-010, ADR-014 (both records), and ADR-016 to the summary list, or replace the hand-maintained list with a link to the ADR index. |
| DC-07 | Medium | `CLAUDE.md`'s one-line summary of ADR-008 ("Authentik/Traefik production trust boundary") carries no caveat, but the project's own `architecture-review-2026-09.md` records this exact boundary as a **Critical** open finding (S-01): the frontend's nginx forwards client-supplied `X-Authentik-Username/Uid/Email` headers verbatim, and only an out-of-repo Traefik configuration prevents a request on the internal network from forging a manager identity. A reader relying on `CLAUDE.md`'s ADR list alone would believe the boundary is simply "in place." | `CLAUDE.md` "Key Architecture Decisions" list (ADR-008 line); `docs/planning/architecture-review-2026-09.md:145` (finding S-01, Critical); `frontend/nginx.conf:56-67`; `docs/planning/PROJECT-PLAN.md:227-233` | Either drop ADR-008 from the flat "decided" list until S-01 (tracked under R3-adjacent work) closes, or add a one-clause caveat matching PROJECT-PLAN.md's own framing. |
| DC-08 | Low | `CLAUDE.md`'s footer reads "Last Updated: 2025-12-29," but the same document's body describes events from 2026-09-21 (e.g., the P1 PostgreSQL CI automation date) — about nine months later than the stated update date. | `CLAUDE.md` footer vs. body content dated through 2026-09-21 | Bump the footer date whenever the body is edited, or remove the field if it won't be maintained. |
| DC-09 | Low | `CLAUDE.md`'s "PyStrict-Aligned Ruff Rules" section presents `BLE, EM, SLF, INP, ISC, PGH, RSE, TID, YTT, FA, T10, G` as one undifferentiated set. In `pyproject.toml`, `FA`, `T10`, and `G` actually sit in the main rule-selection block, while only `BLE, EM, SLF, INP, ISC, PGH, RSE, TID, YTT` are under the file's own "PyStrict additions" comment. | `CLAUDE.md` "PyStrict-Aligned Ruff Rules"; `pyproject.toml:222-281` | Split the list to match `pyproject.toml`'s actual grouping, or drop the "PyStrict-aligned" label from the rules that aren't in that block. |

## 3. Already self-acknowledged, not re-reported as findings

- **Duplicate ADR-014 numbering.** Two records both claim number 014 (frontend E2E/accessibility,
  and training-eligibility/unclassified-family). `docs/planning/adr/README.md` already documents
  this explicitly, names the responsible PRs (#103, #105), and notes ADR-015 is free.
- **`CLAUDE.md`'s Project Structure section** (under "Project Structure") still shows the original
  cookiecutter skeleton (`core/`, `middleware/`, `utils/` only) and omits `api/`, `models/`,
  `schemas/`, `services/`, `ml/`, `llm/`, `jobs/`, and most of `core/`'s and `middleware/`'s actual
  contents. This is already tracked as finding G-05 in `architecture-review-2026-09.md` and as
  documentation work under Milestone R sprint R14 in `PROJECT-PLAN.md`.
- **ADR-014 (training eligibility) status vs. implementation.** Its header says "Proposed (not yet
  approved by product owner)," while the exclusion logic it documents is already implemented and
  enforced in `recommendation_service.py`. The ADR itself states this plainly ("All of the above
  are implemented and passing as of this ADR"), so this is transparent, not a hidden
  contradiction — noted only in case the maintainer wants to formalize approval.

## 4. Not an inconsistency (checked and confirmed consistent)

For completeness, the following areas were checked and found consistent, so they are not listed
above: `affinity-v2`'s shrinkage/veto/namespace constants match ADR-004's 2026-09-19 amendment;
ADR-011's worn-by exclusion is applied at all four call sites the ADR names; ADR-013's proposed
crosswalk tables are correctly absent from the schema (matches its own "proposed, not built"
framing); ADR-009's checkpoint-closure-after-holdout rule is correctly implemented;
`requires-python`, the Ruff line-length/coverage-threshold numbers, and the claimed deletions of
`.semgrep.yml`/`setup_github_protection.py`/`publish-pypi.yml`/`python-compatibility.yml` all hold
against the actual repository state; `PROJECT-PLAN.md` and `roadmap.md` agree on the R1-R15 sprint
range and F1/P6 gating structure.
