@us_0039
Feature: US-0039: Ergonomic Human Task and Bug Authoring with Definition of Ready Scaffolding
  As a human software engineer discovering a bug or necessary refactoring during active development
  I want to scaffold a new task via spec-ops task create with interactive prompts that validate the Definition of Ready (DoR)
  So that I can file structured PMaC tasks directly from the CLI without handwriting boilerplate YAML frontmatter or violating backlog schemas.

  Scenario: Scaffolding a new proposed task via CLI flags
    Given a clean repository with accepted PRD "PRD-0001" and user story "US-0002"
    When the engineer executes "spec-ops task create --title 'Extract Visualizer Drawer Script' --bc visualizer --prd PRD-0001 --story US-0002 --stage proposed"
    Then a new task file "docs/project/backlog/proposed/XXXX-extract-visualizer-drawer-script.md" is generated
    And the file contains valid YAML frontmatter with canonical ID, title, target_bc, governing_prds, and governing_stories
    And "docs/project/backlog/PRIORITY.md" is updated with the newly proposed task.

  Scenario: Definition of Ready (DoR) validation when promoting to refined
    Given a task file in "docs/project/backlog/proposed/" missing governing ADRs and BDD user stories
    When the engineer attempts to promote the task to "refined" via "spec-ops queue refine TASK-0025"
    Then the command rejects the transition with clear DoR violation errors:
      | Error                                                                          |
      | Missing governing ADRs: task must link at least 1 accepted ADR                |
      | Missing governing story: task must trace back to an accepted BDD user story   |
    And the task remains in "proposed/" until the criteria are satisfied.
