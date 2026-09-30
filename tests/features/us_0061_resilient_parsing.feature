Feature: Resilient Markdown AST Parsing and Precision Frontmatter Diagnostic Reporting
  As a human IC developer
  I want the core markdown parser to provide precise line-and-column diagnostic reporting on frontmatter syntax errors while preserving markdown AST formatting and comments
  So that syntax mistakes like indentation errors or unescaped colons are immediately highlighted with actionable error spans instead of silently dropping entity metadata or corrupting markdown bodies

  Scenario: Parsing valid markdown file preserving custom comments, tables, and fenced blocks
    Given a task file "docs/project/backlog/proposed/0050-sample.md" containing:
      """
      ---
      id: '0050'
      title: Complex AST Sample
      status: Proposed
      ---
      <!-- Custom Architect Note: Do not remove -->
      # Implementation Notes
      | Step | Component |
      |---|---|
      | 1 | Parser |
      def example():
          return True
      """
    When the developer executes "spec-ops parse docs/project/backlog/proposed/0050-sample.md"
    Then the task entity is instantiated with title "Complex AST Sample"
    And the parsed body retains the exact HTML comment, markdown table, and Python code fence verbatim without byte alteration.

  Scenario: Reporting precision line and column diagnostics on malformed YAML frontmatter
    Given a task file "docs/project/backlog/proposed/0051-bad-yaml.md" with invalid YAML indentation on line 4:
      """
      ---
      id: '0051'
      title: Broken Task
        dependencies: [TASK-0001]
      ---
      # Title
      """
    When the developer executes "spec-ops parse docs/project/backlog/proposed/0051-bad-yaml.md"
    Then the command exits with code 1
    And outputs a compiler-grade diagnostic error:
      """
      error: Frontmatter YAML Syntax Error in docs/project/backlog/proposed/0051-bad-yaml.md:4:3
      |
      4 |   dependencies: [TASK-0001]
      |   ^ unexpected mapping indentation
      """
    And does not silently fallback to an empty metadata dictionary.

  Scenario: Graceful handling of missing frontmatter delimiters with helpful scaffolding hint
    Given a markdown file "docs/project/backlog/proposed/0052-no-delim.md" missing the opening "---"
    When the developer executes "spec-ops parse docs/project/backlog/proposed/0052-no-delim.md"
    Then the command exits with code 1
    And reports "Missing Frontmatter: File does not start with standard YAML '---' delimiter"
    And suggests: "Run 'spec-ops scaffold task' to generate a valid frontmatter template".
