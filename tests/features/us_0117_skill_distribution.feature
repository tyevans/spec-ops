Feature: Universal Multi-Platform Skill Distribution and Package Scaffolding (US-0117)

  Scenario: Universal Multi-Platform Skill Scaffolding across all platforms
    Given a user repository initialized with SpecOps
    When the user runs "spec-ops scaffold skill --target all"
    Then portable skill definitions, slash commands, and rule files are scaffolded across ".agents/skills/", "CLAUDE.md", and ".cursorrules"
    And references and CLI primers are packaged without broken links.

  Scenario: Targeted Scaffolding for Antigravity platform
    Given a user repository initialized with SpecOps
    When the user runs "spec-ops scaffold skill --target antigravity"
    Then ".agents/skills/spec-ops/SKILL.md" is scaffolded with complete CLI primers and references
    And references and runbooks are packaged without broken links.

  Scenario: Targeted Scaffolding for Claude platform
    Given a user repository initialized with SpecOps
    When the user runs "spec-ops scaffold skill --target claude"
    Then "CLAUDE.md", ".claude/skills/spec-ops/", and ".claude/commands/spec-ops.md" are scaffolded
    And references and runbooks are packaged without broken links.

  Scenario: Targeted Scaffolding for Cursor platform
    Given a user repository initialized with SpecOps
    When the user runs "spec-ops scaffold skill --target cursor"
    Then ".cursorrules" and ".cursor/rules/spec-ops.mdc" are scaffolded
    And references and runbooks are packaged without broken links.

  Scenario: Dry run execution does not modify disk
    Given a user repository initialized with SpecOps
    When the user runs "spec-ops scaffold skill --target all --dry-run"
    Then no files are written to disk
    And link validation succeeds without errors.

  Scenario: Scaffolding agent adapters generates inline skill
    Given a user repository initialized with SpecOps
    When the user runs "spec-ops scaffold --agents antigravity"
    Then ".agents/skills/spec-ops/SKILL.md" is scaffolded with complete CLI primers and references
    And references and runbooks are packaged without broken links.
