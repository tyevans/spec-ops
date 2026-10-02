Feature: ADR Supersession and Evolution Engine
  As an agentic systems architect
  I want to supersede an architectural decision with a replacement decision
  So that architectural lineage is maintained cleanly without circular cycles or broken references

  Scenario: Superseding an accepted ADR with a new decision
    Given an existing accepted ADR in "docs/project/adrs/accepted/"
    When the architect runs spec-ops adr supersede with the target ADR ID and new title
    Then the old ADR is updated with status Superseded and superseded_by pointer
    And a new ADR is created with supersedes pointer
    And docs/project/adrs/REGISTRY.md reflects the updated statuses

  Scenario: Preventing circular supersession references
    Given an ADR that already supersedes another decision
    When an attempt is made to create a circular supersession cycle
    Then the operation is rejected with an error message
    And the existing ADR files remain unmodified
