Feature: Proactive Backlog Health Diagnostics, Dangling Dependency Auditing, and Self-Healing Repair

  Scenario: Detecting Broken and Dangling Dependency Pointers
    Given task "TASK-0050" in "docs/project/backlog/proposed/" lists "dependencies: [TASK-9999]"
    And "TASK-9999" does not exist in complete, refined, or proposed backlog folders
    When the lead executes "spec-ops backlog doctor"
    Then the command exits with code 1
    And reports "Backlog Defect: TASK-0050 references non-existent dependency 'TASK-9999'"
    And suggests removing the dangling reference or authoring the missing task specification.

  Scenario: Detecting Ghost Entries and Unindexed Files in PRIORITY.md
    Given file "0099-orphan-task.md" exists in "docs/project/backlog/proposed/" but is missing from "PRIORITY.md"
    And "PRIORITY.md" lists a reference to "TASK-0088" whose file has been deleted from disk
    When the lead runs "spec-ops backlog doctor"
    Then the diagnostic report highlights 1 unindexed task file and 1 ghost index reference
    And warns of backlog synchronization drift.

  Scenario: Automated Self-Healing Repair
    Given backlog synchronization drift with 1 unindexed file and 1 ghost entry
    When the lead runs "spec-ops backlog doctor --repair"
    Then "PRIORITY.md" is cleaned of the ghost reference to "TASK-0088"
    And "0099-orphan-task.md" is deterministically appended to "PRIORITY.md" under proposed status
    And the command exits with code 0 and reports "Backlog self-healing complete: 2 issues remediated".

  Scenario: Queue Doctor CLI Interface and Line Numbers
    Given task "TASK-0050" referencing dangling dependency "TASK-9999"
    When the architect runs "spec-ops queue doctor"
    Then dangling dependency IDs are reported with file line numbers and exit code 1.

  Scenario: Automated Repair via Queue Doctor
    Given detected ghost entries and unindexed task files
    When the architect runs "spec-ops queue doctor --fix"
    Then "PRIORITY.md" is rebuilt atomically and dangling dependencies are cleaned up.
