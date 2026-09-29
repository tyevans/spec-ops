@security @us_0110
Feature: Real-Time Secret and High-Entropy Credential Detection in Worktree Diffs

  Scenario: Blocking commits containing high-entropy secrets or private tokens
    Given an autonomous agent worktree where an agent or developer has written an OpenAI API key, AWS secret access key, or RSA private key into a source file
    When the worker engine executes "spec-ops health --security" prior to git commit
    Then the scanner detects the high-entropy credential pattern
    And the preflight check exits with returncode 1, aborting the commit
    And diagnostic feedback listing the offending file path, line number, and masked token snippet (e.g., "sk-proj-****4x9Z") is returned to the agent prompt for self-healing remediation.

  Scenario: Blocking inclusion of unignored sensitive dotfiles in git tracking
    Given an autonomous worker session where the agent generates a ".env", ".env.production", or "id_rsa" file
    When the worker engine executes preflight verification
    Then "spec-ops health --security" flags the presence of unignored sensitive files
    And the commit is aborted with actionable instructions to add the file to ".gitignore" and remove it from git staging.

  Scenario: Clean worktree passes preflight credential scan
    Given an autonomous agent worktree with feature modifications referencing credentials strictly through environment variables
    When the preflight command "spec-ops health --security" executes
    Then the check exits with returncode 0
    And reports "Security Invariant Met: 0 credential leaks detected in working tree".
