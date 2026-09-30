@us_0015 @decomposition
Feature: Proactive File Decomposition Suggestions and AST Seam Extraction

  Scenario: Generating decomposition suggestions for files in the warning threshold (400-500 lines)
    Given a source file "src/spec_ops/core/parser.py" with 440 lines
    When the architect runs "spec-ops health --suggest-splits"
    Then the scanner reports a proactive anti-rot warning (440 lines >= 400 lines threshold)
    And analyzes the AST to suggest cohesive module splits (e.g. "parser_markdown.py" and "parser_frontmatter.py")
    And outputs the suggested exports for a barrel "__init__.py" file

  Scenario: Emitting a proposed refactoring task into the backlog
    Given a source file "src/orders/service.py" reaches 460 lines
    When the architect runs "spec-ops health --suggest-splits --emit-task"
    Then a new task file is written to "docs/project/backlog/proposed/TASK-SPLIT-orders-service.md"
    And the task contains the AST decomposition blueprint, suggested submodule boundaries, and INVEST criteria

  Scenario: Preserving clean status when all files remain under 400 lines
    Given all source files in the repository contain fewer than 400 lines
    When the architect runs "spec-ops health --suggest-splits"
    Then the command exits with code 0 and reports "0 proactive warnings; codebase modularity optimal"
