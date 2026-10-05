Feature: Architectural Decision Record Amendment Workflow and Frontmatter Lineage Tracking

  Scenario: Amending an accepted ADR with a new incremental decision via CLI
    Given an accepted ADR "ADR-0101: Event Log Schema and Granularity" in "docs/project/adrs/accepted/"
    When the architect runs "spec-ops adr amend ADR-0101 --title 'Provenance Value Object Schema'"
    Then a new ADR is scaffolded in "docs/project/adrs/accepted/" with frontmatter "amends: [ADR-0101]"
    And the target ADR "ADR-0101" frontmatter appends the new ADR to its "amended_by" list
    And the target ADR "ADR-0101" maintains status "Accepted"
    And "docs/project/adrs/REGISTRY.md" is synchronized to reflect the amendment relationship without marking ADR-0101 as Superseded

  Scenario: Linking an amendment to an existing draft ADR
    Given an accepted ADR "ADR-0102: Two Store Ports"
    And a drafted ADR "docs/project/adrs/proposed/adr-0116-graph-store-is-five-capabilities.md"
    When the architect runs "spec-ops adr amend ADR-0102 --by docs/project/adrs/proposed/adr-0116-graph-store-is-five-capabilities.md"
    Then "ADR-0116" is promoted to "docs/project/adrs/accepted/" with frontmatter "amends: [ADR-0102]"
    And "ADR-0102" records "amended_by: [ADR-0116]" in its YAML frontmatter
    And both decisions remain active architectural authorities

  Scenario: Preserving active status and backlog task validity for amended ADRs
    Given an accepted ADR "ADR-0101" that has been amended by "ADR-0135" and "ADR-0136"
    And an active task "TASK-0042" in "docs/project/backlog/refined/" citing "governing_adrs: [ADR-0101]"
    When the architect runs "spec-ops health" or "spec-ops check"
    Then the task passes the Definition of Ready (DoR) governing ADR gate
    And "spec-ops reconciler" does not replace ADR-0101 with ADR-0136
    And the audit report notes that ADR-0101 has active amendments [ADR-0135, ADR-0136]

  Scenario: Detecting and rejecting circular amendment chains
    Given ADR-0110 already amends ADR-0105
    When an attempt is made to execute "spec-ops adr amend ADR-0110 --by ADR-0105"
    Then the amendment operation is aborted with a CircularAmendmentError
    And all existing ADR frontmatters remain unmodified
