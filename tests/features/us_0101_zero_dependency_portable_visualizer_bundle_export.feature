Feature: Zero-Dependency Portable Visualizer Bundle and Air-Gapped Export

  Scenario: Compiling Single-File Standalone HTML Bundle
    Given a SpecOps project containing parsed personas, PRDs, stories, tasks, and ADRs
    When the architect executes "spec-ops visualizer --build dist/spec-ops-visualizer.html"
    Then the command exits with return code 0
    And a single self-contained HTML file is created at "dist/spec-ops-visualizer.html"
    And all CSS styles, client-side JavaScript scripts, and JSON payloads are embedded directly in the file
    And the file contains zero external "<link rel='stylesheet'>" or "<script src='https://...'>" CDN dependencies.

  Scenario: Air-Gapped Offline Execution via Local File Protocol
    Given the standalone artifact "dist/spec-ops-visualizer.html" has been generated
    When an auditor opens the file in any modern web browser via "file://" URI with network access disabled
    Then the visualizer mounts cleanly without JavaScript console errors
    And the interactive 2D Canvas force-directed graph renders all nodes and edges
    And all dashboard tabs ("Relationship Graph", "Gantt & Timeline", "Kanban Board", "PRDs & Features", "ADR Architecture", "Personas & Stories") function with full interactivity.

  Scenario: Automated Documentation Site Asset Generation
    Given a project repository configured with automated Diataxis documentation building
    When the build pipeline executes "spec-ops docs build --include-visualizer"
    Then the visualizer HTML bundle is emitted to "site/visualizer/index.html"
    And the top-left navigation button renders a valid relative link "← Back to Docs" pointing to "../index.html".
