Feature: Relational Graph Traceability and Architecture Radar Visualization for ADR Amendments

  Scenario: Compiling bidirectional ADR-to-ADR amends and supersedes edges into relational graph
    Given a set of ADRs where ADR-0116 has frontmatter "amends: [ADR-0102]" and ADR-0120 has "supersedes: [ADR-0118]"
    When the relational graph compiler runs via "spec-ops graph compile"
    Then the graph includes directed edge "(ADR-0116)-[:amends]->(ADR-0102)"
    And the graph includes directed edge "(ADR-0120)-[:supersedes]->(ADR-0118)"
    And "spec-ops trace --verify" passes with 100% graph connectivity

  Scenario: Rendering amended ADRs with distinct active badges and evolution drawers in Architecture Radar
    Given an ADR "ADR-0101" that is amended by "ADR-0135" and "ADR-0136"
    When viewing the Architecture Radar or ADR tab in the living visualizer
    Then ADR-0101 is rendered with an active status badge rather than a strikethrough red badge
    And opening the ADR detail drawer displays an "Amendments" lineage section linking directly to ADR-0135 and ADR-0136
    And viewing ADR-0135 in the drawer displays "Amends: ADR-0101"

  Scenario: Hydrating amending ADR context into pathfinder and autonomous worker contracts
    Given task "TASK-0012" cites "governing_adrs: [ADR-0102]"
    And ADR-0102 has recorded amendments [ADR-0116, ADR-0127]
    When an autonomous worker session or "spec-ops pathfinder inspect TASK-0012" runs
    Then the hydrated task context includes both the primary governing decision ADR-0102 and the active amending decisions ADR-0116 and ADR-0127
