---
id: '0039'
title: Interactive Web PRD Studio and Low-Code Gherkin BDD Authoring Assistant
status: Refined
created: 2026-09-29
dependencies:
  - TASK-0035
  - TASK-0038
governing_adrs:
  - ADR-0001
  - ADR-0002
  - ADR-0003
  - ADR-0006
  - ADR-0007
  - ADR-0008
  - ADR-0009
  - ADR-0013
governing_prds:
  - PRD-0003
governing_stories:
  - US-0043
  - US-0045
target_bc: prd
---

# TASK-0039: Interactive Web PRD Studio and Low-Code Gherkin BDD Authoring Assistant

## Summary
Implement the interactive Web PRD Studio and Low-Code Gherkin BDD Authoring Assistant embedded within the SpecOps visualizer (`spec-ops prd studio [--open]` and visualizer tabs). Provide a form-based PRD authoring interface with real-time Diataxis Markdown split-pane preview, instant structural quality validation (enforcing checkable outcomes and persona mapping), and direct git commit capabilities. In the Story Studio, provide Gherkin step autocompletion extracted from registered public frontdoor fixtures and an active backdoor detector that warns against private internals (ADR-0003), saving accepted stories directly to `docs/project/user_stories/accepted/`.

## Problem Statement & Context
Writing raw Markdown files, escaping YAML frontmatter, and memorizing git commands creates friction for product managers and technical writers. When PMs write BDD user stories without tooling support, they often craft unfalsifiable criteria or inadvertently specify private backdoor steps (e.g. "Given database table users contains..."), violating ADR-0003. We need a polished in-browser studio that empowers non-technical users to author valid PMaC documents with live validation and frontdoor autocomplete without terminal intimidation.

## User Stories & Scenarios Satisfied
- **US-0043: Interactive Web-Based PRD Studio and Template Scaffolder**
  - *Scenario: Scaffolding a New PRD Draft via Visualizer Web Studio*
  - *Scenario: Enforcing PRD Structural Quality Invariants in Real Time*
  - *Scenario: Split-Pane Markdown Preview and Direct Git Commit*
- **US-0045: Low-Code Gherkin BDD Story Authoring and Frontdoor Step Assistant**
  - *Scenario: Autocompleting Established Frontdoor Steps during Story Creation*
  - *Scenario: Detecting and Flagging Private Backdoors (ADR-0003 Invariant)*
  - *Scenario: Saving and Linking Generated User Story*

## Architectural Invariants & Seams
- **File Length Limit (<500 lines)**: Visualizer extensions must be decomposed into `src/spec_ops/visualizer/prd_studio.py` and `src/spec_ops/visualizer/story_assistant.py`, keeping all files under 400 lines (ADR-0002).
- **Hypothesis Invariant Property (ADR-0009)**: Generative property tests using `@given(...)` across randomized Gherkin scenarios assert that backdoor pattern detection reliably flags database and private mock keywords while never false-flagging legitimate CLI flags, public HTTP endpoints, or frontdoor steps.
- **Mutmut Mutation Scope**: Frontdoor step introspection and backdoor heuristic matching in `src/spec_ops/visualizer/story_assistant.py` achieve >=80% mutant kill score under `mutmut`.

## Definition of Done (Blackbox Frontdoor TDD)
1. Executing `spec-ops prd studio --open` serves the visualizer on local port and displays the "PRDs & Features" and "Story Studio" views.
2. Filling out the form and clicking "Save PRD Draft" writes a valid Markdown file under `docs/project/product/idea/` with status "Idea" and target persona.
3. Attempting to submit a PRD lacking checkable outcomes or a target persona triggers real-time visual alerts citing ADR-0001 and prevents saving.
4. Editing a PRD updates the Diataxis Markdown split-pane preview in real time, and clicking "Commit Specification" records changes directly to git with proper author metadata.
5. In Story Studio, typing `Given ` triggers autocomplete of registered frontdoor steps; typing private backdoor patterns displays an ADR-0003 architectural warning and suggests public alternatives.
6. Accepting a completed story writes to `docs/project/user_stories/accepted/us-XXXX-*.md` and links it to the governing PRD.
7. Verified via blackbox Playwright and `pytest-bdd` end-to-end tests without mock backdoors (ADR-0003, ADR-0006).
