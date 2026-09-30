Feature: Automated PRD Shipping Verification and Release Reconciliation Gate

  Scenario: Successfully shipping a fully implemented and verified PRD
    Given an accepted PRD "PRD-0001" where all 23 implementing backlog tasks are marked "Complete"
    And all 58 linked BDD user stories pass "pytest" with a 100% success rate through public frontdoors
    When Jordan runs "spec-ops prd ship PRD-0001"
    Then SpecOps moves the PRD file from "docs/project/product/accepted/" to "docs/project/product/shipped/"
    And updates the frontmatter status to "Shipped" and records "shipped_date: 2026-09-29"
    And updates "docs/project/product/REGISTRY.md" to status "Shipped"
    And marks the corresponding milestone in "docs/project/backlog/ROADMAP.md" as complete with 100% delivery.

  Scenario: Aborting shipping when linked BDD user stories or tasks are incomplete
    Given an accepted PRD "PRD-0002" with 4 implementing tasks
    And task "TASK-0025" is currently in status "Refined"
    When Jordan runs "spec-ops prd ship PRD-0002"
    Then the command aborts with error: "Cannot ship PRD-0002: Incomplete tasks remaining (TASK-0025: Refined)"
    And no files are moved or modified in git.

  Scenario: Generating a customer-facing release verification manifest upon shipping
    Given Jordan successfully executes "spec-ops prd ship PRD-0001"
    Then SpecOps generates a release verification manifest at "dist/releases/PRD-0001-release-manifest.json"
    And the manifest contains:
      | Field |
      | PRD ID, title, and target persona |
      | Full list of completed task IDs and commit SHAs |
      | Executable BDD scenario verification test run summary |
      | Cryptographic SHA-256 digest of verified git tree |
