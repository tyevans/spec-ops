Feature: Redstring Relational Knowledge Graph and AST Projection

  Scenario: Redstring Entity and Relationship Extraction
    Given a project repository with accepted PRDs, tasks, and ADRs
    When the extractor parses the repository frontmatter
    Then a Redstring InMemoryGraphStore is populated with typed entities and relationships
    And graph queries for dependencies return valid topological neighbors

  Scenario: Content-Addressed Graph Caching
    Given a compiled Redstring graph cached to disk at ".specops/cache/graph.json"
    When no markdown files have been modified
    Then compiling the graph loads from the cache snapshot in under 50 milliseconds
