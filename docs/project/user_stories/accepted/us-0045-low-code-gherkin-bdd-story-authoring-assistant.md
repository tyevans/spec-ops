---
id: '0045'
title: Low-Code Gherkin BDD Story Authoring and Frontdoor Step Assistant
status: Accepted
created: 2026-09-29
persona: Taylor (The Product Manager)
feature: FEAT-BDD-02
governing_prd: PRD-0003
---

# US-0045 — Low-Code Gherkin BDD Story Authoring and Frontdoor Step Assistant

## Governing PRD
- [`PRD-0003: Product Discovery, Web PRD Studio & Living UAT Verification`](../../product/accepted/prd-0003-product-discovery-web-prd-studio-and-living-uat-verification.md)

## User Story

**As an** product manager,  
**I want** to author executable user stories using an interactive Gherkin scenario assistant that autocompletes existing public frontdoor steps and validates INVEST criteria,  
**So that** I can write falsifiable acceptance criteria linked to business outcomes without writing test automation code or violating blackbox invariants.

## Acceptance Criteria

```gherkin
Scenario: Autocompleting Established Frontdoor Steps during Story Creation
Given Taylor is authoring a new user story for "PRD-0001" in the visualizer Story Studio
When Taylor types "Given " into the scenario editor
Then the step assistant displays an autocomplete dropdown of registered frontdoor fixtures:
  | Step Pattern                                            | Domain Area |
  | Given a project initialized with SpecOps               | CLI / Setup |
  | Given the standalone visualizer is open in a browser    | Web / UI    |
  | Given an accepted PRD with linked user stories          | Backlog     |
And selecting a step populates the scenario with valid Gherkin syntax.
```

```gherkin
Scenario: Detecting and Flagging Private Backdoors (ADR-0003 Invariant)
Given Taylor is authoring a Gherkin scenario
When Taylor enters a step referencing private internals such as "Given the database table users has record 'admin'"
Then the scenario assistant displays an architectural warning:
  "Backdoor violation (ADR-0003): Tests must exercise public frontdoors. Direct state manipulation is prohibited."
And suggests the compliant frontdoor alternative.
```

```gherkin
Scenario: Saving and Linking Generated User Story
Given a completed Gherkin scenario meeting INVEST criteria
When Taylor clicks "Accept User Story"
Then a specification file is written to "docs/project/user_stories/accepted/us-0045-*.md"
And the story is linked to the governing PRD in "docs/project/product/"
And the story becomes immediately available for engineering vertical slice decomposition.
```

## Rationale & Compelling Value
Enforces ADR-0003 (Blackbox Frontdoor Verification) and ADR-0006 (BDD User Stories) upstream during specification time, eliminating the 'Silo of Mocked Perfection' before coding begins.
