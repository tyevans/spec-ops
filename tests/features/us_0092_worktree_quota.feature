@us_0092 @rescue @quota
Feature: Proactive Worktree Disk Quota Monitor and Orphan Pruning Daemon

  Scenario: Auditing disk consumption and candidate orphan worktrees
    Given multiple git worktrees in ".worktrees/" with merged and unmerged tasks
    When the engineer runs "spec-ops rescue quota"
    Then a tabular summary displays directory sizes and associated task statuses
    And flags candidates eligible for safe pruning

  Scenario: Safely pruning merged worktrees with disk reclamation
    Given an abandoned worktree whose task was completed and merged into "main"
    When the engineer executes "spec-ops rescue prune --older-than 1d"
    Then the worktree directory and branch are deleted safely
    And zero active unmerged worktrees are affected
