@us_0125 @adoption @docs
Feature: Intelligent Pre-Existing Documentation Bridging and Workflow Deconfliction

  Scenario: Detecting pre-existing documentation tools and configuration files
    Given an existing brownfield repository containing "mkdocs.yml" or "docs/conf.py"
    When the migration engineer runs "spec-ops adopt"
    Then the command detects the existing documentation framework
    And prints informational warnings outlining bridging and co-existence options.

  Scenario: Flagging and deconflicting duplicate GitHub Pages deployment workflows
    Given a target repository with an existing workflow deploying to GitHub Pages under concurrency group "pages"
    When running "spec-ops adopt --github-pages"
    Then it detects the duplicate Pages deployment configuration
    And warns the user of the conflicting concurrency group
    And with "--deconflict-workflow" safely updates or namespaces the deployment workflow.

  Scenario: Generating cross-navigation bridging guidance for legacy documentation sites
    Given a repository retaining an existing MkDocs documentation site
    When running "spec-ops adopt --bridge-docs"
    Then SpecOps outputs configuration recommendations to link the "/visualizer/" route from the existing navigation
    And provides artifact co-location directives without pipeline conflicts.
