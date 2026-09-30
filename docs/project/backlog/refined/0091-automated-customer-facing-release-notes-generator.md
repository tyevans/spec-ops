---
id: 0091
title: Automated Customer-Facing Release Notes and Business Value Changelog Generator
status: Refined
dependencies:
- TASK-0042
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
- US-0049
target_bc: prd
claimed_by: worker-3
branch: feat/0091-automated-customer-facing-release-notes-
---

# TASK-0091: Automated Customer-Facing Release Notes and Business Value Changelog Generator

## Summary
Implement automated customer-facing release notes generation (`spec-ops release notes --milestone <id> [--format markdown|html] [--branded]`) categorizing shipped PRD capabilities, passed Gherkin scenario summaries, and persona impacts while filtering internal engineering chores and spike experiments.

## Problem Statement & Context
Product managers and engineering leads spend hours each release manually sifting through raw git commit logs to draft release communications. Technical commits clutter the log with low-level developer chores that obscure customer value. SpecOps requires an automated release notes engine that derives business value changelogs directly from shipped PRD outcomes and verified Gherkin user stories.

## User Stories & Scenarios Satisfied
- **US-0049: Automated Customer-Facing Release Notes and Business Value Changelog Generator**
  - *Scenario: Generating Customer Release Notes for a Completed Milestone*
  - *Scenario: Exporting Clean HTML for Stakeholder Newsletters*

## Architectural Invariants & Seams
- **File Length Limit (<500 lines)**: Release notes synthesis in `src/spec_ops/prd/release_notes.py` must stay strictly under 400 lines (ADR-0002).
- **Hypothesis Invariant Property (ADR-0009)**: Generative property tests using `@given(...)` across randomly synthesized milestone task lists assert that chore and spike commits are strictly omitted and generated HTML output contains zero unescaped content.
- **Mutmut Mutation Scope**: Filtering and formatting algorithms in `src/spec_ops/prd/release_notes.py` achieve >=80% mutant kill score under `mutmut`.

## Definition of Done (Blackbox Frontdoor TDD)
1. Executing `spec-ops release notes --milestone M1 --format markdown` writes `docs/reference/release-notes-m1.md` containing New Capabilities, User Scenarios Added, and Persona Impacts, completely omitting internal chores.
2. Executing `spec-ops release notes --milestone M1 --format html --branded` outputs a styled, standalone HTML email template with links to documentation and visualizer permalinks.
3. All scenarios verified via public frontdoor `pytest-bdd` tests without private mock backdoors (ADR-0003, ADR-0006).
