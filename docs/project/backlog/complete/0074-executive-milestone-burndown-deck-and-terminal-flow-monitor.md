---
id: '0074'
title: Executive Milestone Burndown Deck Exporter and Interactive Terminal Flow Monitor
status: Complete
dependencies:
- TASK-0013
- TASK-0068
governing_adrs:
- ADR-0001
- ADR-0002
- ADR-0003
- ADR-0007
- ADR-0008
governing_prds:
- PRD-0005
governing_stories:
- US-0105
- US-0078
target_bc: visualizer
signed_off_by: Ty Evans <tyler@poorlythoughtout.com>
signed_off_at: '2026-09-30T18:00:00+00:00'
has_signed_commits: true
commit_signature_status: SIGNED
---


# TASK-0074: Executive Milestone Burndown Deck Exporter and Interactive Terminal Flow Monitor

## Summary
Provide multi-format executive presentation reporting (`spec-ops report burndown --format html|deck`) and an interactive terminal backlog flow monitor (`spec-ops queue monitor`) visualizing JIT buffer waterlines with single-keystroke task promotion and worktree provisioning.

## Problem Statement & Context
Engineering leads need automated slide deck generation displaying milestone burndown velocity, scope stability, and completion trajectories for executive reviews without manually constructing presentation charts. Additionally, developers need an ergonomic curses/terminal monitor to observe buffer waterlines and promote or claim tasks with single keystrokes.

## User Stories & Scenarios Satisfied
- **US-0105: Executive Milestone Burndown and Multi-Format Presentation Deck Exporter**
  - *Scenario: Generating Milestone Executive Summary via CLI*
  - *Scenario: Interactive Zero-Dependency Slide Deck Export from Visualizer*
  - *Scenario: Automated Detection of Unanchored Scope Creep*
- **US-0078: Interactive Terminal Backlog Flow Monitor and JIT Buffer Telemetry**
  - *Scenario: Visualizing Live JIT Buffer Waterline and Worker Telemetry in TUI*
  - *Scenario: Single-Keystroke Ergonomic Task Promotion from TUI*
  - *Scenario: Single-Keystroke Worktree Provisioning and Claiming for Human IC*

## Architectural Invariants & Seams
- **File Length Limit (<500 lines)**: Burndown exporter in `src/spec_ops/visualizer/burndown_deck.py` and terminal flow monitor in `src/spec_ops/tui/flow_monitor.py` must stay strictly under 400 lines (ADR-0002).
- **Hypothesis Invariant Property (ADR-0009)**: Generative property tests using `@given(...)` assert that HTML slide deck generation functions with zero external CDN dependencies and renders cleanly in headless browsers.
- **Mutmut Mutation Scope**: Burndown calculations and terminal keybinding handlers achieve >=80% mutant kill score under `mutmut`.

## Definition of Done (Blackbox Frontdoor TDD)
1. Executing `spec-ops queue monitor` launches an interactive terminal flow monitor showing JIT buffer waterlines, active workers, and single-keystroke task promotion.
2. Executing `spec-ops report burndown --milestone M1 --format deck` exports an interactive zero-dependency HTML slide deck displaying milestone burndown velocity.
3. All scenarios verified via public frontdoor CLI and Playwright browser tests without mock backdoors (ADR-0003, ADR-0006).
