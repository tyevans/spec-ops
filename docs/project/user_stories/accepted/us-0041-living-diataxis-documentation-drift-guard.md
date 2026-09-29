---
id: '0041'
title: Living Diataxis Documentation Drift Guard for IC Feature Work
status: Accepted
created: 2026-09-29
persona: Riley (The Human IC Developer)
feature: FEAT-DFT-01
governing_prd: PRD-0004
---

# US-0041 — Living Diataxis Documentation Drift Guard for IC Feature Work

## Governing PRD
- [`PRD-0004: Autonomous Multi-Worker Fleet & Preserved Worktree Rescue Engine`](../../product/accepted/prd-0004-autonomous-multi-worker-fleet-and-worktree-rescue-engine.md)

## User Story

**As an** human software engineer introducing or modifying public CLI commands or domain APIs,  
**I want** `spec-ops docs check` to notify me if public interfaces have changed without corresponding updates in `docs/how-to/` or `docs/reference/`,  
**So that** I prevent documentation debt and keep our Diataxis technical documentation synchronized with running code.

## Acceptance Criteria

```gherkin
Scenario: Detecting undocumented public CLI command additions
Given a developer has added a new CLI subcommand "spec-ops task archive" in "src/spec_ops/cli/main.py"
And no matching reference spec exists in "docs/reference/" or how-to guide in "docs/how-to/"
When the engineer runs "spec-ops docs check"
Then the command fails with a documentation drift alert:
  "Documentation Drift Detected: Public CLI command 'spec-ops task archive' is not documented."
And the exit code is non-zero.
```

```gherkin
Scenario: Passing documentation check when Diataxis docs are synchronized
Given the developer has added "docs/how-to/archive-tasks.md" documenting the new command
When the engineer runs "spec-ops docs check"
Then the command passes with "All public interfaces and CLI commands are documented."
And "spec-ops docs build" completes with 0 warnings.
```

## Rationale & Compelling Value
Replaces nagging manual PR review comments with an automated, helpful diagnostic. Keeps the repo perpetually self-documenting for humans and future agents.
