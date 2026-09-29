---
id: '0042'
title: Executive Roadmap Exporter and Customer-Facing Release Notes Generator
status: Proposed
created: 2026-09-29
dependencies:
  - TASK-0015
  - TASK-0041
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
  - US-0047
  - US-0049
target_bc: prd
---

# TASK-0042: Executive Roadmap Exporter and Customer-Facing Release Notes Generator

## Summary
Implement the executive roadmap visualizer/exporter (`spec-ops export roadmap --format svg|html`) and automated customer-facing release notes generator (`spec-ops release notes --milestone <id> --format markdown|html`). Parse milestone delivery horizons and progress bars from `docs/project/backlog/ROADMAP.md` and git commit logs, generating standalone vector SVG graphics and interactive single-file HTML presentations for leadership. Synthesize business-focused release notes categorizing shipped PRD capabilities, passed Gherkin scenario summaries, and persona impacts while filtering internal engineering refactors and invisible spike commits.

## Problem Statement & Context
Engineering leads and product managers spend substantial time each sprint copying statuses into slide decks or summarizing technical git commit logs for executive leadership and external users. Standard git changelogs are cluttered with low-level developer chores, dependency bumps, and spike experiments that obscure customer value. SpecOps needs zero-overhead export tools that translate version-locked specifications and shipped outcomes directly into polished executive presentation decks and customer-ready release notes rooted in git truth.

## User Stories & Scenarios Satisfied
- **US-0047: Executive Roadmap Exporter and Zero-Overhead Presentation Generator**
  - *Scenario: Exporting Executive Roadmap Visual via CLI*
  - *Scenario: Generating Standalone Stakeholder Slide Deck in the Visualizer*
  - *Scenario: Automated CI Synchronization of Stakeholder Visuals*
- **US-0049: Automated Customer-Facing Release Notes and Business Value Changelog Generator**
  - *Scenario: Generating Customer Release Notes for a Completed Milestone*
  - *Scenario: Exporting Clean HTML for Stakeholder Newsletters*

## Architectural Invariants & Seams
- **File Length Limit (<500 lines)**: Decompose rendering and export engines across `src/spec_ops/prd/exporter.py` and `src/spec_ops/prd/release_notes.py`, keeping each module below 400 lines (ADR-0002).
- **Hypothesis Invariant Property (ADR-0009)**: Generative property tests using `@given(...)` across randomly generated roadmap structures and task lists assert that generated SVG files are strictly well-formed XML and HTML presentations contain zero unescaped user strings or script injection vectors.
- **Mutmut Mutation Scope**: Filtering and formatting algorithms in `src/spec_ops/prd/release_notes.py` achieve >=80% mutant kill score under `mutmut`.

## Definition of Done (Blackbox Frontdoor TDD)
1. Executing `spec-ops export roadmap --format svg --out dist/roadmap.svg` generates a clean vector graphic grouped by delivery horizon with progress calculated from git commit history.
2. Clicking "Export Executive Summary" in the visualizer Gantt view downloads a self-contained, single-file HTML slide deck with interactive progress dials that functions offline without external dependencies.
3. Executing `spec-ops release notes --milestone M1 --format markdown` writes `docs/reference/release-notes-m1.md` containing New Capabilities, User Scenarios Added, and Persona Impacts, completely omitting internal chore and spike commits.
4. Executing `spec-ops release notes --milestone M1 --format html --branded` outputs a styled, standalone HTML email template with permalinks to documentation.
5. All scenarios verified via public frontdoor `pytest-bdd` tests without private mock backdoors (ADR-0003, ADR-0006).
