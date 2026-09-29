---
id: '0044'
title: PRD Lifecycle Stage Gate Progression and Validation
status: Accepted
created: 2026-09-29
persona: Taylor (The Product Manager)
feature: FEAT-PRD-03
governing_prd: PRD-0001
---

# US-0044 — PRD Lifecycle Stage Gate Progression and Validation

## Governing PRD
- [`PRD-0001: SpecOps Autonomous Project Management Engine`](../../product/accepted/prd-0001-spec-ops-autonomous-project-management-engine.md)

## User Story

**As an** product manager,  
**I want** to inspect and advance PRDs through explicit lifecycle stages (idea -> shaped -> accepted -> shipped) with automated stage-gate readiness validation,  
**So that** product discovery ideas are systematically hardened before engineering decomposition, and delivered capabilities are verifiably marked shipped without manual directory renames or broken cross-links.

## Acceptance Criteria

```gherkin
Scenario: Promoting an Idea PRD to Shaped Stage
Given a PRD "PRD-0002" residing in "docs/project/product/idea/" with defined user pain points
When Taylor runs "spec-ops prd promote PRD-0002 --stage shaped" or clicks "Promote to Shaped" in the visualizer
Then the PRD file is moved to "docs/project/product/shaped/"
And the frontmatter status updates to "Shaped"
And "docs/project/product/REGISTRY.md" updates atomically to reflect the new stage.
```

```gherkin
Scenario: Blocking Promotion to Accepted When Quality Gates Fail
Given a shaped PRD lacking linked user personas or falsifiable checkable outcomes
When Taylor attempts to promote the PRD to "accepted"
Then the promotion command exits with a stage-gate violation error
And the output lists missing prerequisites: "No checkable outcomes defined" and "Target persona unmapped"
And the PRD remains in "docs/project/product/shaped/" without invalid decomposition.
```

```gherkin
Scenario: Transitioning Accepted PRD to Shipped upon 100% Backlog Completion
Given an accepted PRD "PRD-0001" where all 23 implementing backlog tasks are marked "Complete"
And all linked executable BDD user story scenarios pass with a 100% success rate
When Taylor executes "spec-ops prd ship PRD-0001" or confirms shipping in the visualizer
Then the file is archived to "docs/project/product/shipped/"
And the status updates to "Shipped"
And "docs/project/backlog/ROADMAP.md" records the milestone completion date and marks the horizon closed.
```

## Rationale & Compelling Value
Automates filesystem hygiene and gives PMs a clear lifecycle pipeline in git, preventing premature engineering on unhardened ideas while ensuring that 'Shipped' represents genuine completion.
