---
id: '0256'
title: Sanitize Generated Task Blueprints to Use Workspace-Relative Paths
status: Proposed
dependencies: []
governing_prds:
- PRD-0001
governing_stories:
- US-0001
target_bc: core
---

## Summary
When `spec-ops ingest --baseline .specops/grandfathered_debt.json` scaffolds proposed refactoring tasks for grandfathered files exceeding line limits, it currently writes absolute machine file paths (e.g., `/home/username/...`) into task blueprints and summaries. This causes documentation link checkers (e.g., Lychee in CI) to fail with broken file URI errors on external runners.

## Problem Statement
Generated task markdown files should always use repository-relative paths (e.g., `src/...`, `tests/...`) rather than absolute machine paths.

## Acceptance Criteria
```gherkin
Given a project running spec-ops ingest with grandfathered debt
When proposed refactoring tasks are written to docs/project/backlog/proposed/
Then all embedded file paths in the markdown content are relative to the repository root
And no absolute filesystem paths are included in task titles or blueprints.
```
