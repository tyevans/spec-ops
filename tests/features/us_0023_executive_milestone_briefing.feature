Feature: Automated Executive Milestone Briefing and Roadmap Alignment Digest
  As an AI-native engineering lead (Jordan)
  I want to execute spec-ops report milestone to produce an automated executive briefing
  So that I can deliver polished, mathematically verified status reports to non-technical executives and VP stakeholders

  Scenario: Generating Milestone Executive Summary
    Given an accepted roadmap milestone "M1-MVP" in "docs/project/backlog/ROADMAP.md"
    And linked PRDs, user stories, and tasks with varying completion statuses
    When the lead runs "spec-ops report milestone M1-MVP"
    Then the command outputs an executive briefing containing:
      | Milestone progress percentage |
      | Customer value delivered mapped to Personas |
      | Verified public frontdoor test count and mutation score |
      | Remaining deliverables and projected completion horizons |
      | Top delivery risks and blocked dependency items |
    And formats the summary cleanly for direct pasting into Slack, email, or executive slide decks.

  Scenario: Detecting Unanchored Scope Creep against Roadmap
    Given tasks completed on feature branches that are not linked to any milestone in ROADMAP.md
    When the lead runs "spec-ops report milestone --audit-scope"
    Then the command reports "Roadmap Alignment Warning: 3 completed tasks have no milestone association"
    And lists the unanchored tasks and their target bounded contexts.

  Scenario: Standalone Executive HTML One-Pager
    Given milestone progress data
    When the lead runs "spec-ops report milestone M1-MVP --export html -o dist/briefing.html"
    Then a self-contained, responsive HTML briefing document is generated
    And includes visual progress rings, persona impact quotes, and delivery horizon timelines with zero CDN dependencies.
