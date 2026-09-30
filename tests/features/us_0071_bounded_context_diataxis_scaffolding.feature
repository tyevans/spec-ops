@scaffold @us_0071
Feature: Bounded-Context Diataxis Documentation Scaffolding and Living Spec Linking

  Scenario: Scaffolding Diataxis quadrant for a new bounded context
    Given an active SpecOps repository with bounded contexts
    When the developer executes "spec-ops scaffold docs --bc billing --title 'Billing Subsystem'"
    Then documentation directories are created with boilerplate index files across all four Diataxis quadrants
    And starter markdown templates are installed with metadata linking to governing PRDs and user stories
    And the main documentation index "docs/index.md" is updated with a section for the new bounded context.

  Scenario: Embedding deep links to the living 2D visualizer
    Given scaffolded bounded-context documentation
    When viewing the generated reference documents
    Then markdown files include URL hash deep links targeting the bounded context in the 2D visualizer
    When the builder compiles documentation with "spec-ops docs build"
    Then the rendered HTML page includes an embedded interactive link to the visualizer pre-filtered to the "billing" component ("visualizer/?focus=billing")
    And verifies that all internal cross-links to user stories in "docs/project/user_stories/" resolve cleanly.

  Scenario: Preventing duplicate bounded context scaffolding
    Given an existing bounded context documentation tree
    When attempting to scaffold the same bounded context without "--force"
    Then the command warns the user and preserves existing documentation intact
    And exits cleanly without overwriting existing files.
