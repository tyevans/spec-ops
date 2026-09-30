---
id: '0042'
title: Executive Roadmap Visualizer and Milestone Horizon Exporter
status: Refined
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
target_bc: prd
---

# TASK-0042: Executive Roadmap Visualizer and Milestone Horizon Exporter

## Summary
Implement the executive roadmap visualizer/exporter (`spec-ops export roadmap --format svg|html`). Parse milestone delivery horizons and progress bars from `docs/project/backlog/ROADMAP.md` and git commit logs, generating standalone vector SVG graphics and interactive single-file HTML presentations for leadership.

## Problem Statement & Context
Engineering leads and product managers spend substantial time each sprint copying statuses into slide decks or summarizing technical git commit logs for executive leadership and external users. SpecOps needs zero-overhead export tools that translate version-locked specifications and shipped outcomes directly into polished executive presentation visuals and SVG assets rooted in git truth.

## User Stories & Scenarios Satisfied
- **US-0047: Executive Roadmap Exporter and Zero-Overhead Presentation Generator**
  - *Scenario: Exporting Executive Roadmap Visual via CLI*
  - *Scenario: Generating Standalone Stakeholder Slide Deck in the Visualizer*
  - *Scenario: Automated CI Synchronization of Stakeholder Visuals*

## Architectural Invariants & Seams
- **File Length Limit (<500 lines)**: Roadmap rendering engine in `src/spec_ops/prd/exporter.py` must stay strictly under 400 lines (ADR-0002).
- **Hypothesis Invariant Property (ADR-0009)**: Generative property tests using `@given(...)` across randomly generated roadmap structures and task lists assert that generated SVG files are strictly well-formed XML and HTML presentations contain zero unescaped user strings or script injection vectors.
- **Mutmut Mutation Scope**: SVG XML generation and percentage calculations in `src/spec_ops/prd/exporter.py` achieve >=80% mutant kill score under `mutmut`.

## Definition of Done (Blackbox Frontdoor TDD)
1. Executing `spec-ops export roadmap --format svg --out dist/roadmap.svg` generates a clean vector graphic grouped by delivery horizon with progress calculated from git commit history.
2. Clicking "Export Executive Summary" in the visualizer Gantt view downloads a self-contained, single-file HTML presentation with interactive progress dials that functions offline without external dependencies.
3. All scenarios verified via public frontdoor `pytest-bdd` tests without private mock backdoors (ADR-0003, ADR-0006).
