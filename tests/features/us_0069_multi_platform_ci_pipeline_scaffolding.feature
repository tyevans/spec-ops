Feature: Multi-Platform CI/CD Pipeline Scaffolding Across GitHub Actions and GitLab CI
  As an AI-native engineering lead
  I want spec-ops to scaffold standardized, platform-native CI quality gate pipelines for GitHub Actions and GitLab CI
  So that our hybrid human-agent engineering teams enjoy identical, enforceable preflight verification, lockfile checks, and SpecOps invariant enforcement regardless of which enterprise git hosting platform we use.

  Scenario: Scaffolding a GitLab CI quality pipeline
    Given a repository configured with SpecOps
    When the architect runs "spec-ops scaffold ci --platform gitlab"
    Then a ".gitlab-ci.yml" file is generated at the repository root
    And the pipeline includes stages for dependency lockfile validation ("uv lock --check"), invariant health scanning ("uv run spec-ops health"), and blackbox test execution ("uv run pytest")
    And configures persistent caching for UV dependencies.

  Scenario: Scaffolding multi-platform CI pipelines simultaneously
    Given a project needing both GitHub and GitLab pipeline configurations
    When "spec-ops scaffold ci --platform all" is executed
    Then both ".github/workflows/specops.yml" and ".gitlab-ci.yml" are written with matrix definitions
    And both configurations execute the exact same sequence of quality checks and invariant gates.

  Scenario: Updating existing CI workflow on toolchain version bump
    Given an existing ".github/workflows/specops.yml"
    When the developer runs "spec-ops scaffold ci --platform github --force"
    Then workflow steps are updated with latest toolchain actions while preserving custom environment variables.

  Scenario: Updating existing CI workflow with preservation tags
    Given an existing ".github/workflows/ci.yml" generated with Python 3.12
    When the engineer updates "specops.toml" to target Python 3.13 and runs "spec-ops scaffold ci --update"
    Then the CI workflow file is updated to Python 3.13 without removing custom organizational job steps marked with preservation tags.

  Scenario: Attempting to overwrite existing CI workflow without force flag
    Given an existing ".github/workflows/specops.yml"
    When the developer runs "spec-ops scaffold ci --platform github" without force
    Then the command fails with exit code 1 and warns that the file already exists.
