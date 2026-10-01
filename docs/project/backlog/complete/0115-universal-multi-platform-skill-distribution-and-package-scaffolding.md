---
id: '0115'
title: Universal Multi-Platform Skill Distribution and Package Scaffolding
status: Complete
dependencies:
- TASK-0109
- TASK-0114
governing_adrs:
- ADR-0001
- ADR-0002
- ADR-0003
- ADR-0007
- ADR-0008
governing_prds:
- PRD-0006
governing_stories:
- US-0117
target_bc: scaffold
signed_off_by: Ty Evans <tyler@poorlythoughtout.com>
signed_off_at: '2026-10-01T11:00:00+00:00'
has_signed_commits: true
commit_signature_status: SIGNED
---

# TASK-0115: Universal Multi-Platform Skill Distribution and Package Scaffolding

## Summary
Implement universal distribution and multi-platform packaging for the SpecOps orchestrator skill (`spec-ops scaffold skill [--target antigravity|claude|cursor|all]`). Package and export the full SDLC orchestrator, CLI primers, and subagent runbooks into portable skill bundles that can be installed into any target agent platform or repository.

## Problem Statement & Context
While the initial POC targets Antigravity via `.agents/skills/spec-ops/`, users and engineering teams use a diverse range of coding agents (Claude Code, Cursor, Aider, OpenHands). To serve as the universal "company in a box", the orchestrator skill must be exportable, versioned, and easily installed into any new or existing repository regardless of the agent harness used.

## User Stories & Scenarios Satisfied
- **US-0117: Autonomous Full-Lifecycle SDLC Orchestrator Skill & Multi-Agent Coordination**
  - *Scenario: Universal Multi-Platform Skill Scaffolding*
    - Given a user repository initialized with SpecOps
    - When the user runs "spec-ops scaffold skill --target all"
    - Then portable skill definitions, slash commands, and rule files are scaffolded across ".agents/skills/", "CLAUDE.md", and ".cursorrules"
    - And references and CLI primers are packaged without broken links.

## Architectural Invariants & Seams
- **File Length Limit (<500 lines)**: Skill packaging module in `src/spec_ops/profiles/packager.py` must stay strictly under 400 lines (ADR-0002).
- **Zero-Dependency Portability**: Generated skill packages must not depend on proprietary agent runtimes; they must use standard Markdown, frontmatter, and POSIX shell scripts.
- **Mutmut Mutation Scope**: Skill bundler and platform mapping achieves >=80% mutant kill score under `mutmut`.

## Definition of Done (Blackbox Frontdoor TDD)
1. CLI command `spec-ops scaffold skill` generates platform-specific skill bundles.
2. Supports Antigravity, Claude Code, and Cursor target platforms.
3. Automatically validates that references (`cli_primer.md`, `orchestration_protocol.md`) are bundled and accessible.
4. 100% test pass rate verifying observable contracts without private mock backdoors.

## Acceptance Criteria

### Scenario 1: Universal Multi-Platform Skill Scaffolding*
```gherkin
Given the system is initialized and ready
When the user executes the workflow for "Universal Multi-Platform Skill Distribution and Package Scaffolding"
Then Universal Multi-Platform Skill Scaffolding*
And observable outputs satisfy public contracts without backdoor tampering.
```

## Hypothesis Invariant Properties

- `@given(...)`: Generative invariant verification asserting that valid domain operations preserve state consistency across randomized inputs without shrinking failures.
