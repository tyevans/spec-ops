---
id: '0033'
title: Living Security Posture and Compliance Radar Visualizer Dashboard
status: Proposed
created: 2026-09-29
dependencies:
  - TASK-0023
  - TASK-0032
governing_adrs:
  - ADR-0001
  - ADR-0002
  - ADR-0003
  - ADR-0006
governing_prds:
  - PRD-0002
governing_stories:
  - US-0058
  - US-0114
target_bc: security
---

# TASK-0033: Living Security Posture and Compliance Radar Visualizer Dashboard

## Summary
Add a dedicated "Security & Compliance Radar" tab (`#tab=security`) to the SpecOps standalone project visualizer. Display 5 real-time summary metric cards (Secret Scan Status, Lockfile Integrity, Signed Commit Coverage, Human Sign-off Rate, and Known Vulnerability Count), alongside an interactive compliance triage table with "Show Only Unsigned / Unreviewed" filtering and deep links to task entity detail drawers.

## Problem Statement & Context
Executive stakeholders, compliance auditors, and engineering leads need an at-a-glance visual radar of organizational security posture and release cut-off readiness without having to manually run terminal commands or inspect git histories. They need immediate visibility into tasks lacking human review sign-offs, unsigned commits, or un-waived CVEs blocking release readiness.

## User Stories & Scenarios Satisfied
- **US-0058: Living Security Posture and Compliance Radar in Project Visualizer**
  - *Scenario*: Rendering the Security & Compliance Radar view
  - *Scenario*: Filtering tasks by compliance readiness
- **US-0114: Tamper-Evident Merkle Tree Compliance Audit Manifests and Living Security Radar**
  - *Scenario*: Rendering the Security & Compliance Radar view in the visualizer for release cut-offs

## Architectural Invariants & Seams
- **File Length Limit (<500 lines)**: Visualizer dashboard logic separated into `src/spec_ops/visualizer/security_metrics.py` and modular front-end templates under `src/spec_ops/visualizer/templates/security_radar.js`, strictly under 400 lines (ADR-0002).
- **Hypothesis Invariant Property (ADR-0009)**: Generative property tests using `@given(...)` verify compliance metric calculators across random distributions of signed/unsigned, reviewed/unreviewed, and vulnerable tasks, asserting that all calculated percentages, counts, and ratios are mathematically sound (`0.0 <= rate <= 100.0%`).
- **Mutmut Mutation Scope**: Metric aggregation and threshold evaluation in `src/spec_ops/visualizer/security_metrics.py` achieve >=80% mutant kill score under `mutmut`.

## Definition of Done (Blackbox Frontdoor TDD)
1. Opening the standalone visualizer and navigating to `#tab=security` renders the five summary metric cards:
   - Secret Scan Status (Pass / Fail)
   - Lockfile Integrity (Synchronized / Modified)
   - Signed Commit Coverage (Percentage)
   - Human Sign-off Rate (Percentage)
   - Known Vulnerability Count (Low / Med / High)
2. Interactive compliance triage table lists all tasks pending human sign-off, unsigned commits, or open CVEs.
3. Toggling the "Show Only Unsigned / Unreviewed" filter narrows the triage table to display only non-compliant items blocking release cut-off.
4. Clicking any triage row opens the entity detail drawer displaying the exact missing compliance artifacts and permalink URL.
5. All UI interactions and visual states verified via Playwright / `pytest-bdd` blackbox tests without mock backdoors (ADR-0003, ADR-0006).
