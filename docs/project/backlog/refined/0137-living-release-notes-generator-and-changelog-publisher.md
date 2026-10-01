---
id: '0137'
title: Living Release Notes Generator and Changelog Publisher
status: Refined
dependencies:
- TASK-0041
- TASK-0112
governing_adrs:
- ADR-0001
- ADR-0002
- ADR-0003
- ADR-0006
- ADR-0008
- ADR-0009
governing_prds:
- PRD-0003
governing_stories:
- US-0049
target_bc: release
---

# TASK-0137: Living Release Notes Generator and Changelog Publisher

## Summary
Implement the customer-facing living release notes generator (`spec-ops release notes [PRD-ID] [--format markdown|html|json] [--output <path>]`). Automatically compile shipped checkable outcomes, persona benefits, completed user journeys, and commit metadata into non-technical customer release notes, eliminating internal jargon and publishing directly to project documentation.

## Problem Statement & Context
Engineering changelogs frequently consist of raw git commit messages (`fix: bump timeout`, `refactor AST parser`) that fail to communicate business value to non-technical stakeholders, product managers, and customers. A PMaC engine requires automated synthesis of customer-facing release notes extracted directly from verified PRD checkable outcomes and persona acceptance criteria.

## Key Requirements & Scope
1. **Persona-Oriented Release Notes Synthesis (`src/spec_ops/release/customer_notes.py`)**:
   - `spec-ops release notes [PRD-ID]` extracts shipped outcomes from `docs/project/product/shipped/`.
   - Groups changes by affected user persona (`Taylor`, `Alex`, `Jordan`, `Riley`) and describes user-facing benefits.
   - Formats outputs in GitHub Markdown, self-contained HTML, or structured JSON.
2. **Automated Changelog Publishing**:
   - Updates `docs/explanation/changelog.md` or dedicated release note files under `docs/releases/`.
   - Verifies zero broken links or unescaped markdown syntax.
3. **Blackbox Frontdoor Verification**:
   - 100% test pass rate with zero mock backdoors.

## Architectural Invariants & Seams
- **File Length Limit (<500 lines)**: Release notes module in `src/spec_ops/release/customer_notes.py` must stay strictly under 400 lines (ADR-0002).
- **Non-Technical Language Invariant**: Output must summarize user benefits and checkable outcomes rather than raw commit SHAs or internal variable names.
- **Mutation Testing Scope**: Target modules for mutmut mutation testing include `src/spec_ops/release/customer_notes.py` with target >=80% mutant kill score (ADR-0009).

## Acceptance Criteria

### Scenario 1: Compiling customer-facing release notes from shipped PRD
```gherkin
Given a shipped PRD "PRD-0001" with verified checkable outcomes and linked persona "Taylor"
When the product lead executes "spec-ops release notes PRD-0001"
Then customer-facing release notes are generated
And the notes group changes by target persona benefits without internal git commit jargon
```

### Scenario 2: Multi-format export for customer communications
```gherkin
Given a shipped PRD "PRD-0001"
When the user runs "spec-ops release notes PRD-0001 --format html"
Then a standalone HTML release announcement is produced
And includes verifiable customer UAT checkmarks
```

## Hypothesis Invariant Properties

- `@given(...)`: Generative property tests asserting that for any arbitrary set of shipped outcomes and personas, release notes rendering produces valid non-empty documentation without raw exception traces.
