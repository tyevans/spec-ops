---
id: '0034'
title: PRD Discovery Guide, Falsifiable Markdown Linter, and Lifecycle Stage-Gate
  Engine
status: Refined
dependencies:
- TASK-0003
- TASK-0006
governing_adrs:
- ADR-0001
- ADR-0002
- ADR-0003
- ADR-0006
- ADR-0007
- ADR-0008
- ADR-0009
governing_prds:
- PRD-0003
governing_stories:
- US-0044
- US-0099
target_bc: prd
---

# TASK-0034: PRD Discovery Guide, Falsifiable Markdown Linter, and Lifecycle Stage-Gate Engine

## Summary
Implement the interactive PRD discovery guide (`spec-ops prd new`), automated structural and falsifiability markdown linter (`spec-ops prd lint`), and deterministic lifecycle stage-gate engine (`spec-ops prd promote --stage <stage>`). Enforce non-negotiable PRD sections (Problem Statement, What good looks like, What this does not do, Checkable Outcomes, Target Persona), heuristic detection and rejection of subjective adjectives in outcomes, stage migrations across `docs/project/product/{idea,shaped,accepted,shipped}/`, and atomic synchronization of `docs/project/product/REGISTRY.md`.

## Problem Statement & Context
Product managers and non-technical stakeholders adopting PMaC often author qualitative aspirations and subjective statements ("clean and modern", "fast and responsive") instead of falsifiable behavioral contracts. When these ambiguous documents enter autonomous engineering decomposition, coding agents hallucinate requirements or produce non-testable features. Furthermore, teams manually rename directories and break cross-entity links because PRDs lack formal, automated stage-gate transitions from raw discovery `idea/` to hardened `shaped/` and contractual `accepted/`.

## User Stories & Scenarios Satisfied
- **US-0044: PRD Lifecycle Stage Gate Progression and Validation**
  - *Scenario: Promoting an Idea PRD to Shaped Stage*
  - *Scenario: Blocking Promotion to Accepted When Quality Gates Fail*
- **US-0099: Product Discovery Guide and Falsifiable PRD Markdown Linter (`spec-ops prd lint`)**
  - *Scenario: Interactively guiding an author through PRD discovery scaffolding*
  - *Scenario: Catching missing or incomplete sections during PRD markdown linting*
  - *Scenario: Linting checkable outcomes for non-falsifiable language*

## Architectural Invariants & Seams
- **File Length Limit (<500 lines)**: New modules `src/spec_ops/prd/linter.py` and `src/spec_ops/prd/lifecycle.py` must stay strictly under 400 lines (ADR-0002).
- **Hypothesis Invariant Property (ADR-0009)**: Generative property tests using `@given(...)` across arbitrary markdown PRD strings assert that the linter deterministically catches missing required headers (`## What this does not do`, `## Checkable Outcomes`) and detects subjective adjectives ("clean", "intuitive", "modern", "fast") without raising unhandled exceptions or false positives on valid outcomes.
- **Mutmut Mutation Scope**: Core linting logic in `src/spec_ops/prd/linter.py` and stage-gate transition logic in `src/spec_ops/prd/lifecycle.py` achieve >=80% mutant kill score under `mutmut`.

## Definition of Done (Blackbox Frontdoor TDD)
1. Executing `spec-ops prd new` interactively guides the user through target persona selection, friction points, core capabilities, scope boundaries/anti-goals, and checkable outcomes, writing a valid Markdown PRD draft to `docs/project/product/idea/`.
2. Executing `spec-ops prd lint <file>` verifies all mandatory sections, evaluates outcomes against falsifiability heuristics, flags violations with line numbers and remediation hints, and exits with returncode 1 when violations exist.
3. Executing `spec-ops prd promote <prd-id> --stage shaped` moves the document from `idea/` to `shaped/`, updates frontmatter status to `Shaped`, and atomically updates `docs/project/product/REGISTRY.md`.
4. Executing `spec-ops prd promote <prd-id> --stage accepted` evaluates quality gates (mandatory persona link and at least one falsifiable outcome); if gates fail, aborts promotion with exit code 1 and leaves the file in `shaped/`.
5. All scenarios verified via public frontdoor `pytest-bdd` tests without private mock backdoors (ADR-0003, ADR-0006).
