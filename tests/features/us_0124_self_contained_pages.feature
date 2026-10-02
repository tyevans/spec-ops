@us_0124 @adoption @docs
Feature: Self-Contained GitHub Pages and Visualizer Scaffolding for Brownfield Repositories

  Scenario: Scaffolding self-contained GitHub Pages deployment workflow without target lockfile dependency
    Given an existing brownfield project where SpecOps is not present in "pyproject.toml"
    When the migration engineer runs "spec-ops adopt --github-pages"
    Then ".github/workflows/deploy-pages.yml" is scaffolded
    And the workflow invokes "uv tool run --from git+https://... spec-ops docs build" (or published PyPI tool)
    And builds cleanly in clean GitHub Actions runner environments without requiring in-repo dependency modifications.

  Scenario: Detecting pre-existing documentation tools and deployment workflows
    Given a target repository with an existing documentation configuration (such as "mkdocs.yml" or ".github/workflows/docs.yml")
    When "spec-ops adopt" or "spec-ops scaffold ci" inspects the repository
    Then it detects the duplicate or conflicting Pages deployment workflow
    And provides actionable guidance to bridge the living visualizer into the existing site or retire the legacy workflow.

  Scenario: Publishing interactive 2D graph visualizer alongside Diataxis documentation on GitHub Pages
    Given the GitHub Pages site built by "spec-ops docs build"
    When deployed to GitHub Pages
    Then the documentation root serves the Diataxis documentation portal
    And the interactive 2D graph visualizer is available at "/visualizer/" with relationship graphs and burndown telemetry
    And every documentation page includes a header navigation link to "/visualizer/".
