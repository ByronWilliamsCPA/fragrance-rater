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

---

## Submitting Feedback

Once you've collected feedback, you can:

1. **Create an issue** in the [cookiecutter-python-template repository](https://github.com/ByronWilliamsCPA/cookiecutter-python-template/issues)
2. **Submit a PR** if you have fixes for the template
3. **Share this file** with the template maintainers

When submitting, reference this project as the source of the feedback.
