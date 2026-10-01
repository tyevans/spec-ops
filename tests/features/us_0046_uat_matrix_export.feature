Feature: US-0046 Customer-Ready User Acceptance Testing Verification Matrix HTML Export

  Scenario: Standalone HTML Customer UAT Acceptance Matrix
    Given an accepted PRD "PRD-0003" with checkable outcomes and approved customer signatures
    When the engineer runs "spec-ops prd uat export --prd PRD-0003 --format html"
    Then a standalone HTML matrix is generated
    And the HTML contains verified checkable outcomes and cryptographic verification badges

  Scenario: Tamper-Evident Digest in Exported Acceptance Matrix
    Given a generated HTML UAT acceptance matrix for "PRD-0003"
    When the file contents are validated
    Then the embedded cryptographic verification proof matches the signed ledger
