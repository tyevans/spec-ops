Feature: US-0116 Inference-Driven Backlog Refinement, Architectural Drift Reconciliation, and Scope Slicing

  Scenario: Detecting Architectural Drift and Reconciling Stale Task Specifications
    Given a proposed task "TASK-0062" authored against a legacy module that has since been refactored
    And the project ADR registry contains superseding decisions adopted since the task was drafted
    When the lead runs "spec-ops curate --infer"
    Then the curation engine analyzes current repository files, the relational knowledge graph, and recent ADRs
    And updates the task frontmatter and specification text to align with active bounded contexts and module paths
    And notes reconciled architectural changes in the curation audit trail.

  Scenario: Autonomously Slicing Oversized Monolithic Tasks into Thin Vertical Slices
    Given a proposed task whose specification touches multiple bounded contexts and is estimated to exceed the 500-line modular limit (ADR-0002)
    When "spec-ops curate --infer" audits the task for refinement
    Then the curation inference engine identifies the scope violation
    And decomposes the task into discrete INVEST-compliant vertical slices and an initial architectural spike
    And scaffolds sequential child tasks in "docs/project/backlog/proposed/" linked to the parent PRD
    And promotes only the initial thin slice or spike to "docs/project/backlog/refined/".

  Scenario: Generative Definition of Ready (DoR) Synthesis instead of Dumb Rejection
    Given a proposed task lacking executable Gherkin scenarios or property-based testing invariants
    When "spec-ops curate --infer" processes the task for buffer replenishment
    Then rather than aborting with a hard rejection error, the engine inspects the governing PRD checkable outcomes and public frontdoors
    And synthesizes executable Gherkin scenarios ("Given ... When ... Then") and Hypothesis invariant specifications
    And writes the complete DoR-compliant contract into the task markdown before promoting it to "docs/project/backlog/refined/".

  Scenario: Interactive AI-Native /curate Slash Command Skill
    Given an autonomous coding agent operating in Antigravity or Claude Code
    When the developer or lead triggers "/curate"
    Then the agent executes an interactive cognitive refinement workflow: auditing the under-buffered queue, evaluating proposed tasks against repository reality, proposing vertical decompositions for oversized tasks, and presenting a human-in-the-loop review before moving tasks to "docs/project/backlog/refined/".
