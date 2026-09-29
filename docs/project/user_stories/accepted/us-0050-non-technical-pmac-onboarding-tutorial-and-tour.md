---
id: '0050'
title: Non-Technical PMaC Onboarding Tutorial and Interactive Guided Tour
status: Accepted
created: 2026-09-29
persona: Taylor (The Product Manager)
feature: FEAT-DOC-04
governing_prd: PRD-0003
---

# US-0050 — Non-Technical PMaC Onboarding Tutorial and Interactive Guided Tour

## Governing PRD
- [`PRD-0003: Product Discovery, Web PRD Studio & Living UAT Verification`](../../product/accepted/prd-0003-product-discovery-web-prd-studio-and-living-uat-verification.md)

## User Story

**As an** product manager or non-technical domain expert,  
**I want** a dedicated onboarding guide in Diataxis format and an interactive visualizer walkthrough that explains PMaC concepts in business-friendly terms,  
**So that** I can confidently participate in git-based specification workflows, review user stories, and track deliverables within my first 30 minutes without terminal expertise.

## Acceptance Criteria

```gherkin
Scenario: Accessing the Product Manager Diataxis Onboarding Tutorial
Given a SpecOps documentation site compiled with "spec-ops docs build"
When Taylor navigates to "docs/tutorials/02-product-manager-onboarding.md" in the browser
Then a step-by-step tutorial is displayed covering PMaC philosophy, reading PRDs, writing Gherkin stories, and conducting UAT
And all instructions avoid low-level terminal jargon in favor of browser and editor workflows.
```

```gherkin
Scenario: Launching Interactive In-Browser Visualizer Guided Tour
Given Taylor opens the SpecOps visualizer for the first time
When the application detects no prior tour completion flag in localStorage
Then a lightweight welcome modal offers: "Take a 2-minute tour of SpecOps for Product Managers"
And stepping through the tour highlights PRDs & Features, Gantt timelines, UAT matrix, and deep-link permalinks
And clicking "Finish Tour" saves the preference and dismisses the highlights.
```

```gherkin
Scenario: Completing the Guided First PRD Shaping Exercise
Given Taylor is following the onboarding tutorial in the visualizer sandbox
When Taylor completes the interactive exercise "Create your first Idea PRD"
Then the tutorial verifies the generated Markdown structure locally
And displays a celebratory confirmation badge: "PMaC Ready: Your first specification is git-locked!".
```

## Rationale & Compelling Value
Turns PMs into champions of PMaC rather than resisters. Aligns the entire product and engineering organization around a single unified git repository.
