---
id: '0175'
title: Fix Docs Audit Dir Fallback to Respect Configured Docs Dir and Brownfield Layouts
status: Refined
governing_adrs:
- ADR-0001
governing_prds:
- PRD-0003
governing_stories:
- US-0001
target_bc: core
persona: Jordan (The AI-Native Engineering Lead) & Alex (The Agentic Systems Architect)
---

# TASK-0175: Fix Docs Audit Dir Fallback to Respect Configured Docs Dir and Brownfield Layouts

## Summary
`spec-ops docs audit` and `spec-ops docs check` fail to fall back to `config.docs_dir` because the CLI parser sets a default `--dir docs/`. In addition, when run on a brownfield codebase where `docs/` contains non-quadrant documentation (e.g. `docs/adr`, `docs/plans`, `docs/history`), `DocsAuditor` hard-fails asserting that every folder under `docs/` must strictly match one of the four Diataxis quadrants.

## Problem Statement & Context
1. In `src/spec_ops/cli/main.py`:
   ```python
   docs_dir = Path(args.dir).resolve() if getattr(args, "dir", None) else config.docs_dir
   ```
   However, in `src/spec_ops/cli/parser.py`, `p_docs_audit.add_argument("--dir", default="docs/", ...)` sets a non-None default. Consequently, `getattr(args, "dir", None)` is always `"docs/"`, overriding whatever `docs_dir` is configured in `specops.toml` (such as `docs/project`).
2. In `src/spec_ops/docs/auditor.py`, `DocsAuditor` checks that all subdirectories under the audited directory are only `tutorials`, `how-to`, `reference`, `explanation`, or `project`. In existing brownfield codebases with existing documentation folders (e.g. `docs/adr`, `docs/examples`, `docs/plans`), this immediately fails with dozens of errors.
3. Code snippet validation in `DocsAuditor` also fails on valid Markdown bash snippets containing placeholders like `git commit -F <message file>`.

## Proposed Fix
1. In `src/spec_ops/cli/parser.py`, set `default=None` for `--dir` on `docs audit` and `docs check` subcommands so that `config.docs_dir` is used when no flag is supplied.
2. In `DocsAuditor`, allow configuring ignored or grandfathered documentation directories in `specops.toml` (e.g. `[documentation.ignored_dirs]`).
3. Sanitize or ignore shell placeholders like `<...>` when parsing bash code snippets in Markdown.

## Definition of Done (Blackbox Frontdoor TDD)
1. CLI test verifying that omitting `--dir` uses `config.docs_dir`.
2. `spec-ops docs audit` gracefully supports brownfield documentation layouts when configured.
3. All source files strictly under 500 lines.

## Acceptance Criteria

```gherkin
Scenario: Verify Fix Docs Audit Dir Fallback to Respect Configured Docs Dir and Brownfield Layouts
  Given the system is initialized and ready
  When the user executes the workflow for "Fix Docs Audit Dir Fallback to Respect Configured Docs Dir and Brownfield Layouts"
  Then observable outputs satisfy public contracts without backdoor tampering
  And no internal invariants are violated.
```

## Mutation Testing Scope
- Target domain module: `src/spec_ops/core/...`
- Minimum mutation kill score: >=80% under Mutmut (ADR-0009).

## Hypothesis Invariant Properties
- `@given(...)`: Generative property tests asserting state invariants across randomized inputs without shrinking failures (ADR-0009).

## Scope & Architectural Invariants
- Target Bounded Context: `core` (single bounded context)
- Estimated Implementation Diff: <400 lines
- File Length Limit: all touched source files strictly <500 lines (ADR-0002).
