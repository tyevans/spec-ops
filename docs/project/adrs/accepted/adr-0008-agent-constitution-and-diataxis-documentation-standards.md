# ADR-0008: Agent Constitution (AGENTS.md) and Diataxis Documentation Standards

## Status
Accepted

## Context
When autonomous AI coding assistants (Antigravity, Claude Code, Cursor, Aider) enter a repository without explicit, machine-readable operational rules, they frequently:
1. Violate architectural invariants (e.g., creating monolithic files >500 lines or introducing backdoor mocks).
2. Modify shared backlog tracking files, causing merge conflicts.
3. Treat documentation as an afterthought, creating documentation drift where guides contradict running code.
4. Abandon broken worktrees without clear diagnostics when self-healing loops stall.

Traditional software projects either lack agent instructions altogether or bury them in ad-hoc, unstructured markdown files.

## Decision
We establish **Agent Constitution Standards and Diataxis Documentation Framework Integration**:

1. **Profile-Driven Agent Constitution (`AGENTS.md`)**:
   - Every SpecOps project maintains an opinionated `AGENTS.md` at the repository root, generated dynamically from installed architectural profiles (`core`, `bdd`, `ddd`).
   - The constitution explicitly encodes:
     - **Hard Invariants**: Non-negotiable rules (<500 lines, blackbox frontdoors, worktree backlog isolation, UV workspace management).
     - **Navigation Protocols**: Standard paths to Personas, PRDs, User Stories, and Backlog items under `docs/project/`.
     - **Definition of Ready (DoR)**: Clear criteria for promoting tasks to `refined/`.
     - **Definition of Done (DoD)**: Mandatory verification gates (pytest, health checks, Diataxis documentation updates) before completion.
     - **Worktree Concurrency & Delegation**: Rules for creating, executing, and cleaning up isolated worktrees (`.worktrees/<task-id>`).

2. **Four-Quadrant Diataxis Documentation Framework**:
   - All system documentation outside `docs/project/` must strictly adhere to the Diataxis framework:
     - `docs/tutorials/`: Learning-oriented, step-by-step onboarding walkthroughs.
     - `docs/how-to/`: Task-oriented recipes solving specific problems.
     - `docs/reference/`: Information-oriented technical descriptions, CLI specs, and schemas.
     - `docs/explanation/`: Understanding-oriented discussions of architecture, invariants, and design rationale.

3. **Mandatory Documentation Integrity in DoD**:
   - Autonomous agents and human contributors must:
     - Consult existing Diataxis guides before writing code.
     - Fix stale or inaccurate documentation discovered during implementation.
     - Author or update `how-to/` or `reference/` guides whenever introducing or modifying public CLI commands, APIs, or architectural patterns.

## Consequences
- **Positive**:
  - Immediate, unambiguous alignment for any AI agent or human engineer entering the repository.
  - High documentation accuracy and eliminate specification drift.
  - Consistent operational guardrails across all SpecOps-managed codebases.
- **Negative**:
  - Adds documentation authoring and maintenance to the definition of done for feature tasks.
