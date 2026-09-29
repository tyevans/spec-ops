---
id: '0070'
title: Live Autonomous Worker Fleet Telemetry Console, Architectural Review Radar, and Milestone Burndown Exporter
status: Proposed
created: 2026-09-29
dependencies:
  - TASK-0070
  - TASK-0013
governing_adrs:
  - ADR-0001
  - ADR-0002
  - ADR-0003
  - ADR-0005
  - ADR-0006
  - ADR-0007
governing_prds:
  - PRD-0005
governing_stories:
  - US-0104
  - US-0105
  - US-0106
  - US-0018
  - US-0019
  - US-0078
target_bc: visualizer
---

# TASK-0070: Live Autonomous Worker Fleet Telemetry Console, Architectural Review Radar, and Milestone Burndown Exporter

## Summary
Implement live autonomous worker fleet telemetry, living architectural review radar, and multi-format executive presentation reporting: author a real-time worker fleet console monitoring active git worktrees, task allocations, and stalled worker exhaustion with one-click rescue launch; develop a living architectural review radar auditing bounded context couplings, ADR supersession lineage, and orphaned work items; provide a terminal backlog flow monitor (`spec-ops queue monitor`) visualizing JIT buffer waterlines with single-keystroke task promotion; govern architectural spike lifecycles (`spec-ops spike create/graduate`); verify unbroken commit provenance trailers; and generate executive milestone burndown slide decks (`spec-ops report burndown --format html|deck`).

## Problem Statement & Context
Engineering leads overseeing fleets of autonomous AI coding agents face operational blindness: without live telemetry, stalled worker processes in detached worktrees consume system resources unnoticed. Architectural drift occurs when bounded context couplings slip into code unreviewed, or when unanchored commits lack traceability to governing user stories and personas. Furthermore, preparing executive milestone presentations requires manual chart generation and progress tracking. SpecOps requires a unified lead telemetry console, an architectural review radar, a terminal backlog flow monitor, and automated presentation deck generation.

## User Stories & Scenarios Satisfied
- **US-0104: Live Autonomous Worker Fleet Telemetry and Worktree Operations Console**
  - *Scenario: Live Active Worktree Fleet Telemetry Display*
  - *Scenario: Urgent Visual Alerting on Stalled Worker Exhaustion*
  - *Scenario: One-Click Rescue Launch and Diagnostic Handshake*
- **US-0105: Executive Milestone Burndown and Multi-Format Presentation Deck Exporter**
  - *Scenario: Generating Milestone Executive Summary via CLI*
  - *Scenario: Interactive Zero-Dependency Slide Deck Export from Visualizer*
  - *Scenario: Automated Detection of Unanchored Scope Creep*
- **US-0106: Living Architectural Review Radar and Bounded Context Dependency Audit**
  - *Scenario: Bounded Context Boundary and Dependency Flow Inspection*
  - *Scenario: ADR Supersession Lineage and Active Status Radar*
  - *Scenario: Automated Orphan Work Item and Specification Drift Audit*
- **US-0018: Governed Architectural Spike Lifecycle and Invariant De-Risking**
  - *Scenario: Scaffolding an architectural spike task from an idea-stage PRD*
  - *Scenario: Blocking direct production merge of un-graduated spike code*
  - *Scenario: Graduating a validated spike into an accepted ADR and production tasks*
- **US-0019: Bidirectional End-to-End Traceability and Contributor Provenance Audit**
  - *Scenario: Verifying Unbroken Traceability from Persona to Merged Commits*
  - *Scenario: Flagging Unanchored Commits and Orphaned Tasks*
  - *Scenario: Contributor Provenance Attribution*
- **US-0078: Interactive Terminal Backlog Flow Monitor and JIT Buffer Telemetry**
  - *Scenario: Visualizing Live JIT Buffer Waterline and Worker Telemetry in TUI*
  - *Scenario: Single-Keystroke Ergonomic Task Promotion from TUI*
  - *Scenario: Single-Keystroke Worktree Provisioning and Claiming for Human IC*

## Architectural Invariants & Seams
- **File Length Limit (<500 lines)**: Fleet telemetry script in `src/spec_ops/visualizer/telemetry_script.py`, radar generator in `src/spec_ops/visualizer/radar.py`, burndown exporter in `src/spec_ops/visualizer/burndown_deck.py`, and terminal flow monitor in `src/spec_ops/tui/flow_monitor.py` must stay strictly under 400 lines (ADR-0002).
- **Hypothesis Invariant Property (ADR-0009)**: Generative property tests using `@given(...)` across simulated worker fleet state dumps assert that fleet telemetry metrics (active, stalled, rescued, completed counts) strictly partition total worker allocations without undercounts or overflows.
- **Mutmut Mutation Scope**: Worktree telemetry aggregation in `src/spec_ops/visualizer/telemetry_script.py` and provenance commit validation in `src/spec_ops/core/git_metadata.py` achieve >=80% mutant kill score under `mutmut`.

## Definition of Done (Blackbox Frontdoor TDD)
1. Opening the visualizer Fleet Telemetry tab displays real-time active worktrees, current task assignments, memory consumption, and visual alerts for stalled worker leases.
2. Clicking "Rescue Task" from the fleet console generates the exact `spec-ops rescue <task-id>` command with pre-hydrated diagnostic state.
3. Architectural Review Radar tab displays bounded context coupling matrices, highlights illegal cross-context imports, and visualizes ADR supersession trees.
4. Executing `spec-ops queue monitor` launches an interactive curses/Textual terminal flow monitor showing JIT buffer waterlines, active workers, and single-keystroke task promotion.
5. Executing `spec-ops spike scaffold --prd PRD-XXXX` scaffolds a spike task, preventing production merge until `spec-ops spike graduate` records an accepted ADR.
6. Executing `spec-ops audit provenance` validates unbroken commit trailers (`SpecOps-Task: TASK-XXXX`) from personas to commits, flagging unanchored changes.
7. Executing `spec-ops report burndown --milestone M1 --format deck` exports an interactive zero-dependency HTML slide deck displaying milestone burndown velocity and scope stability.
8. All scenarios verified via public frontdoor CLI and Playwright browser tests without mock backdoors (ADR-0003, ADR-0006).
