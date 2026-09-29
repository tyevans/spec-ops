---
id: '0015'
title: Proactive File Decomposition Suggestions and AST Seam Extraction
status: Accepted
created: 2026-09-29
persona: Alex (The Agentic Systems Architect)
feature: FEAT-DEC-01
governing_prd: PRD-0005
---

# US-0015 — Proactive File Decomposition Suggestions and AST Seam Extraction

## Governing PRD
- [`PRD-0005: Relational Knowledge Graph, Architectural Profiles & Living Reporting`](../../product/accepted/prd-0005-relational-knowledge-graph-architectural-profiles-and-living-reporting.md)

## User Story

**As an** agentic systems architect,  
**I want** `spec-ops health --suggest-splits` to analyze source files approaching the 500-line limit and generate AST-based submodule decomposition blueprints,  
**So that** autonomous agents and developers receive concrete, automated proposals on how to refactor bloated files into cohesive submodules before hitting CI-blocking violations.

## Acceptance Criteria

```gherkin
Scenario: Generating decomposition suggestions for files in the warning threshold (400-500 lines)
Given a source file "src/spec_ops/core/parser.py" with 440 lines
When the architect runs "spec-ops health --suggest-splits"
Then the scanner reports a proactive anti-rot warning (440 lines >= 400 lines threshold)
And analyzes the AST to suggest cohesive module splits (e.g. "parser_markdown.py" and "parser_frontmatter.py")
And outputs the suggested exports for a barrel "__init__.py" file.
```

```gherkin
Scenario: Emitting a proposed refactoring task into the backlog
Given a source file "src/orders/service.py" reaches 460 lines
When the architect runs "spec-ops health --suggest-splits --emit-task"
Then a new task file is written to "docs/project/backlog/proposed/TASK-SPLIT-orders-service.md"
And the task contains the AST decomposition blueprint, suggested submodule boundaries, and INVEST criteria.
```

```gherkin
Scenario: Preserving clean status when all files remain under 400 lines
Given all source files in the repository contain fewer than 400 lines
When the architect runs "spec-ops health --suggest-splits"
Then the command exits with code 0 and reports "0 proactive warnings; codebase modularity optimal".
```

## Rationale & Compelling Value
ADR-0002 mandates <500 lines, but without automated assistance, agents resort to hacky line compression. AST seam analysis blueprints safe refactorings and queues backlog tasks proactively.
