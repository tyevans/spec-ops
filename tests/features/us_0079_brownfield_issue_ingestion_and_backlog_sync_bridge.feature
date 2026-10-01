@us_0079
Feature: US-0079: Brownfield Issue Ingestion and External Backlog Synchronization Bridge
  As a product manager
  I want to execute spec-ops backlog import to ingest issues from GitHub Issues, Jira, or Linear and spec-ops backlog export to generate executive summaries
  So that our team can adopt SpecOps JIT backlogs without abandoning legacy tracking tools or suffering double-entry administrative toil.

  Scenario: Ingesting GitHub Issues into Validated Proposed Task Files
    Given a GitHub repository with open issues labeled "backlog"
    When the product manager runs "spec-ops backlog import --source github --repo org/repo --label backlog"
    Then SpecOps converts each open issue into a Markdown task file in "docs/project/backlog/proposed/"
    And synthesizes frontmatter containing sequential ID, title, target bounded context, and imported issue URL
    And appends the new tasks to "PRIORITY.md" without altering existing completed or refined entries.

  Scenario: Ingesting Structured CSV/JSON Export from Jira or Linear
    Given an issue export file "tickets.json" containing issue key, summary, description, and dependency links
    When the product manager runs "spec-ops backlog import --file tickets.json"
    Then SpecOps parses issue dependencies, mapping external keys to SpecOps canonical task IDs
    And runs the Definition of Ready validator on all imported tasks, flagging incomplete specifications
    And outputs an ingestion summary: "Imported 12 tasks (8 ready for refinement, 4 requiring DoR completion)".

  Scenario: Bi-directional Export of Backlog Status for Executive Roadmaps
    Given a refined backlog with milestone assignments and completion timestamps
    When the product manager executes "spec-ops backlog export --format markdown --out docs/reference/backlog-snapshot.md"
    Then SpecOps generates a structured Diataxis reference document displaying completion burn-up, buffer health, and milestone delivery estimates
    And the document is ready for inclusion in executive stakeholder reviews.
