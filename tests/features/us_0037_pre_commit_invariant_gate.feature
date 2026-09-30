Feature: Local Pre-Commit Invariant Gate and Proactive Anti-Rot Warnings

  Scenario: Blocking staged file that exceeds hard invariant limit
    Given a staged source file "src/spec_ops/core/parser.py" with 512 lines
    When the engineer executes "git commit -m 'feat: parser extension'"
    Then the "spec-ops-health" pre-commit hook aborts the commit
    And the terminal displays "File Length Violation: src/spec_ops/core/parser.py (512 lines > 500 line limit)"
    And the commit is rejected until the file is decomposed into modular submodules.

  Scenario: Proactive warning on files approaching limit without blocking commit
    Given a staged source file "src/spec_ops/visualizer/generator.py" with 420 lines
    And no source files exceed the hard 500-line invariant limit
    When the engineer executes "git commit -m 'feat: visualizer updates'"
    Then the "spec-ops-health" pre-commit hook allows the commit to proceed
    And the terminal displays a warning: "⚠️ Proactive Refactoring Warning: src/spec_ops/visualizer/generator.py (420 lines >= 400 line warning threshold)".

  Scenario: Verifying PRIORITY.md and disk state synchronization
    Given "docs/project/backlog/PRIORITY.md" is synchronized with tasks on disk
    When the pre-commit hook runs "spec-ops health"
    Then the check passes with "PRIORITY.md is synchronized with disk state.".
