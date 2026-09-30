---
id: '0041'
title: Living Customer UAT Verification Matrix and Automated PRD Shipping Gate
status: Complete
dependencies:
- TASK-0034
- TASK-0036
- TASK-0040
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
- US-0046
- US-0100
target_bc: prd
---

# TASK-0041: Living Customer UAT Verification Matrix and Automated PRD Shipping Gate

## Summary
Implement the living Customer UAT Verification Matrix in the visualizer and the automated PRD shipping gate (`spec-ops prd ship PRD-XXXX`). Provide an interactive UAT dashboard mapping real-time BDD test execution results against checkable outcomes, recording PM business sign-offs in `docs/project/product/uat-signoff.json`. Add CI preflight gate `spec-ops health --check-uat` to block releases lacking approved PM sign-off. Implement automated shipping verification that confirms 100% backlog task completion and 100% BDD frontdoor test pass rate, archives the PRD to `docs/project/product/shipped/`, updates `REGISTRY.md` and `ROADMAP.md`, and generates a cryptographic release verification manifest (`dist/releases/PRD-XXXX-release-manifest.json`).

## Problem Statement & Context
Passing engineering unit tests does not guarantee that a software deliverable satisfies business requirements or customer workflows. In conventional teams, product managers lack visibility into live test runs, leading to disconnected UAT spreadsheets or premature releases. Furthermore, marking a feature "shipped" is often an error-prone manual chore prone to forgotten tickets and lingering unverified stories. SpecOps needs an automated, tamper-evident gate that bridges automated testing with PM acceptance and mathematically proves 100% completion before a PRD is moved to `shipped/`.

## User Stories & Scenarios Satisfied
- **US-0046: Customer-Ready User Acceptance Testing Verification and Sign-Off Matrix**
  - *Scenario: Inspecting Customer UAT Readiness Matrix*
  - *Scenario: Recording PM Business Acceptance Sign-Off*
  - *Scenario: Preventing Release Integration without Mandatory PM UAT Sign-Off*
- **US-0100: Automated PRD Shipping Verification and Release Reconciliation Gate**
  - *Scenario: Successfully shipping a fully implemented and verified PRD*
  - *Scenario: Aborting shipping when linked BDD user stories or tasks are incomplete*
  - *Scenario: Generating a customer-facing release verification manifest upon shipping*

## Architectural Invariants & Seams
- **File Length Limit (<500 lines)**: Decompose functionality across `src/spec_ops/prd/uat.py` and `src/spec_ops/prd/shipping.py`, ensuring each module remains well under 400 lines (ADR-0002).
- **Hypothesis Invariant Property (ADR-0009)**: Generative property tests using `@given(...)` across permutations of task completion states and test outcomes assert that `spec-ops prd ship` strictly aborts whenever even one task is not in `complete/` or one linked BDD scenario fails, ensuring partial PRDs can never be marked shipped.
- **Mutmut Mutation Scope**: Shipping validation checks and UAT sign-off state reconciliation in `src/spec_ops/prd/shipping.py` achieve >=80% mutant kill score under `mutmut`.

## Definition of Done (Blackbox Frontdoor TDD)
1. Opening the visualizer renders the "UAT Readiness" dashboard displaying all checkable outcomes, linked Gherkin scenario results, approval statuses, and overall readiness percentage.
2. Toggling outcome approval records PM sign-off metadata (reviewer, timestamp, notes) to `docs/project/product/uat-signoff.json` and renders an immediate green badge.
3. Executing `spec-ops health --check-uat` in CI exits with returncode 1 if any high-priority checkable outcome lacks approved PM sign-off.
4. Executing `spec-ops prd ship PRD-XXXX` when tasks or BDD tests are incomplete aborts with an informative error message and leaves files untouched.
5. Executing `spec-ops prd ship PRD-XXXX` on a 100% verified PRD moves the file to `docs/project/product/shipped/`, sets status to "Shipped", records `shipped_date`, updates `REGISTRY.md` and `ROADMAP.md`, and generates `dist/releases/PRD-XXXX-release-manifest.json` containing task commit SHAs, test summary, and tree SHA-256 digest.
6. Verified via blackbox `pytest-bdd` and CLI tests without private mock backdoors (ADR-0003, ADR-0006).
