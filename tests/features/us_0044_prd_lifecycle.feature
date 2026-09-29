Feature: PRD Lifecycle Stage Gate Progression and Validation
  As a product manager
  I want to inspect and advance PRDs through explicit lifecycle stages with automated stage-gate readiness validation
  So that product discovery ideas are systematically hardened before engineering decomposition, and delivered capabilities are verifiably marked shipped without manual directory renames or broken cross-links.

  Scenario: Promoting an Idea PRD to Shaped Stage
    Given a PRD "PRD-0002" residing in "docs/project/product/idea/" with defined user pain points
    When Taylor runs "spec-ops prd promote PRD-0002 --stage shaped" or clicks "Promote to Shaped" in the visualizer
    Then the PRD file is moved to "docs/project/product/shaped/"
    And the frontmatter status updates to "Shaped"
    And "docs/project/product/REGISTRY.md" updates atomically to reflect the new stage.

  Scenario: Blocking Promotion to Accepted When Quality Gates Fail
    Given a shaped PRD lacking linked user personas or falsifiable checkable outcomes
    When Taylor attempts to promote the PRD to "accepted"
    Then the promotion command exits with a stage-gate violation error
    And the output lists missing prerequisites: "No checkable outcomes defined" and "Target persona unmapped"
    And the PRD remains in "docs/project/product/shaped/" without invalid decomposition.

  Scenario: Transitioning Accepted PRD to Shipped upon 100% Backlog Completion
    Given an accepted PRD "PRD-0001" where all 23 implementing backlog tasks are marked "Complete"
    And all linked executable BDD user story scenarios pass with a 100% success rate
    When Taylor executes "spec-ops prd ship PRD-0001" or confirms shipping in the visualizer
    Then the file is archived to "docs/project/product/shipped/"
    And the status updates to "Shipped"
    And "docs/project/product/REGISTRY.md" updates atomically to reflect the new stage.
    And "docs/project/backlog/ROADMAP.md" records the milestone completion date and marks the horizon closed.
