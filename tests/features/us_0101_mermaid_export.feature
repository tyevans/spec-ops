@US-0101 @TASK-0161
Feature: Relational Knowledge Graph Subgraph Export and Interactive Diagram Generator

  Scenario: Generating Mermaid flowchart for a task lineage
    Given a relational knowledge graph with linked tasks and stories
    When the developer exports a Mermaid diagram rooted at a specific task
    Then valid Mermaid flowchart syntax is generated
    And the output contains the task node, its governing story, and dependencies

  Scenario: Traversal depth limiting
    Given a deep dependency graph across PRDs and tasks
    When the developer exports diagram with depth limit of 1
    Then only immediate adjacent neighbors are included in the emitted diagram
