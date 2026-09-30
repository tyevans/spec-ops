@us_0041
Feature: Living Diataxis Documentation Drift Guard for IC Feature Work

  Scenario: Detecting undocumented public CLI command additions
    Given a developer has added a new CLI subcommand "spec-ops task archive" in "src/spec_ops/cli/main.py"
    And no matching reference spec exists in "docs/reference/" or how-to guide in "docs/how-to/"
    When the engineer runs "spec-ops docs check"
    Then the command fails with a documentation drift alert:
      """
      Documentation Drift Detected: Public CLI command 'spec-ops task archive' is not documented.
      """
    And the exit code is non-zero.

  Scenario: Passing documentation check when Diataxis docs are synchronized
    Given the developer has added "docs/how-to/archive-tasks.md" documenting the new command
    When the engineer runs "spec-ops docs check"
    Then the command passes with "All public interfaces and CLI commands are documented."
    And "spec-ops docs build" completes with 0 warnings.
