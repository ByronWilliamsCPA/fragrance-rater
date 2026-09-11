---
title: "Template Feedback"
schema_type: common
status: published
owner: core-maintainer
purpose: "Document template issues for upstream fixes."
tags:
  - documentation
  - tooling
---

> **Purpose**: Document issues discovered in this project that should be addressed in the [cookiecutter-python-template](https://github.com/ByronWilliamsCPA/cookiecutter-python-template).
>
> **Generated From**: cookiecutter-python-template v0.1.0
> **Project Created**: __PROJECT_CREATION_DATE__

---

## How to Use This File

When working on this project, if you discover any issue that originates from the template itself (not project-specific), add it here with the following format:

```markdown
### [Short Title]

- **Priority**: Critical / High / Medium / Low
- **Category**: [Configuration / Documentation / Tooling / Structure / CI/CD / Security / Other]
- **Discovered**: YYYY-MM-DD

**Issue**: [Clear description of what's wrong or missing]

**Context**: [How was this discovered? What were you trying to do?]

**Suggested Fix**: [What should the template do differently?]

**Affected Files**: [List template files that need changes]
```

---

## Feedback Items

<!-- Add your feedback below this line -->

### Generated planning set lacks an authority and status lifecycle

- **Priority**: High
- **Category**: Documentation
- **Discovered**: 2026-09-11

**Issue**: The generated project plan, roadmap, technical specification, vision, and
project-specific section in `CLAUDE.md` can each present independent scope and completion
status. The scaffold does not identify one execution authority, require an audited commit for
implementation state, or define how superseded ADRs and historical roadmaps are retired.

**Context**: During the Fragrance Rater P0 planning review, the project plan called a merged
calibration workflow pending, the roadmap called implemented foundation work planned, the
technical specification still declared no authentication, and `CLAUDE.md` called all planning
complete. All documents were individually plausible, making the contradiction difficult to
detect during implementation.

**Suggested Fix**: Generate one authoritative execution plan with a current-state ledger,
milestone evidence links, definitions of ready/done, and change-control rules. Generate other
roadmap views as explicit mirrors. Add an ADR supersession index and require planning status to
be updated in feature pull requests that change architecture or scope.

**Affected Files**:

- `{{cookiecutter.project_slug}}/docs/planning/PROJECT-PLAN.md`
- `{{cookiecutter.project_slug}}/docs/planning/roadmap.md`
- `{{cookiecutter.project_slug}}/docs/planning/tech-spec.md`
- `{{cookiecutter.project_slug}}/CLAUDE.md`

### Planning documents are excluded from normal documentation validation

- **Priority**: Medium
- **Category**: Tooling
- **Discovered**: 2026-09-11

**Issue**: The generated pre-commit and markdownlint configuration excludes `docs/planning/**`
from front-matter and Markdown validation, while the example project-plan template is published
in the documentation navigation. This allows active planning documents to drift in formatting
and links while exposing template material as project guidance.

**Context**: P0 had to invoke markdownlint with the ignore file disabled to find duplicate
headings in the authoritative project plan. The strict documentation build also showed that the
actual controlled-calibration design was absent from navigation while the generic plan template
was included.

**Suggested Fix**: Validate active planning documents using the same Markdown/front-matter
contracts as other documentation. Exclude only explicitly archived examples, and do not publish
the generic project-plan template in project navigation by default.

**Affected Files**:

- `{{cookiecutter.project_slug}}/.pre-commit-config.yaml`
- `{{cookiecutter.project_slug}}/.markdownlintignore`
- `{{cookiecutter.project_slug}}/mkdocs.yml`
- Planning document templates that currently omit front matter

### Incorrect `$schema` URL in `.claude/settings.json`

- **Priority**: Medium
- **Category**: Configuration
- **Discovered**: 2026-05-19

**Issue**: The generated `.claude/settings.json` uses `"$schema": "https://json.schemastore.org/claude-code-config.json"`, but the Claude Code VS Code extension expects `https://json.schemastore.org/claude-code-settings.json`. The wrong URL causes the extension to report "Settings file failed to parse" and silently disables permission rules and other settings from the file.

**Context**: This regression has now been observed twice in this project. It was reintroduced by the repo-compliance standards-alignment sweep on 2026-05-16 (CLAUDE-005 / commit `a02d3e8`), implying the cookiecutter template or the compliance standards manifest still emits the incorrect URL.

**Suggested Fix**: Update the template's `.claude/settings.json` (and any standards-manifest remediation logic that writes this file) to use `claude-code-settings.json` rather than `claude-code-config.json`.

**Affected Files**:

- `{{cookiecutter.project_slug}}/.claude/settings.json` (template)
- Any compliance/remediation script that emits or rewrites this file (likely in the `claude-docs-auditor` remediation path for CLAUDE-005)

### `coverage.json` not in `.gitignore`

- **Priority**: Low
- **Category**: Configuration
- **Discovered**: 2026-05-19

**Issue**: The template's `.gitignore` covers `.coverage`, `.coverage.*`, and `coverage.xml`, but omits `coverage.json`. `coverage.py` writes `coverage.json` when invoked with `--format=json` (used by Codecov's JSON reporter, several IDE integrations, and the `test-coverage` skill), leaving an untracked artifact in the working tree after every coverage run.

**Context**: Discovered during a "final check" repo audit. `coverage.json` was the only untracked file in an otherwise-clean working tree on `main` and had been produced silently by a prior coverage run.

**Suggested Fix**: Add `coverage.json` to the "Unit test / coverage reports" block in `.gitignore` alongside `coverage.xml`.

**Affected Files**:

- `{{cookiecutter.project_slug}}/.gitignore`

---

## Submitting Feedback

Once you've collected feedback, you can:

1. **Create an issue** in the [cookiecutter-python-template repository](https://github.com/ByronWilliamsCPA/cookiecutter-python-template/issues)
2. **Submit a PR** if you have fixes for the template
3. **Share this file** with the template maintainers

When submitting, reference this project as the source of the feedback.
