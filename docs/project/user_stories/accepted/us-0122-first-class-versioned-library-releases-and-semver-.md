---
id: '0122'
title: "First-Class Versioned Library Releases and SemVer Progression"
status: Accepted
created: 2026-10-02
persona: "Alex"
target_bc: "core"
feature: "FEAT-REL-02"
governing_prd: "PRD-0001"
scenarios:
  - "Bumping library version across multiple declaration files"
  - "Validating SemVer progression against breaking API changes"
  - "Generating release commit trailers and signed git tag"
---

# US-0122 — First-Class Versioned Library Releases and SemVer Progression

## Governing PRD
- [`PRD-0001: SpecOps Autonomous Project Management Engine`](../../product/accepted/prd-0001-spec-ops-autonomous-project-management-engine.md)

## User Story

**As a** software architect and library maintainer (Alex),  
**I want** SpecOps to support first-class versioned library releases with automated SemVer progression and multi-file declaration sync,  
**So that** published libraries (like redstring) can manage version bumps, changelogs, and git tags under SpecOps governance without manual out-of-band editing.

## Acceptance Criteria

```gherkin
Scenario: Bumping library version across multiple declaration files
  Given a library project configured with version targets "pyproject.toml:project.version" and "src/my_lib/__init__.py:__version__"
  When the maintainer runs "spec-ops release bump --patch"
  Then both declaration files are atomically updated to the new patch version
  And preflight drift verification asserts both declaration sites agree.
```

```gherkin
Scenario: Validating SemVer progression against breaking API changes
  Given a library with breaking public API changes recorded in ADRs or public surface gates
  When the maintainer attempts to run "spec-ops release bump --minor"
  Then the release gate fails with a warning requiring a major version bump
  Unless "--force" or an approved architectural waiver is supplied.
```

```gherkin
Scenario: Generating release commit trailers and signed git tag
  Given a validated library release manifest and passing preflight verification suite
  When the maintainer executes "spec-ops release tag"
  Then a git release commit is formatted with RFC 822 SpecOps release trailers
  And a signed git tag "vX.Y.Z" is created pointing to the release commit.
```

