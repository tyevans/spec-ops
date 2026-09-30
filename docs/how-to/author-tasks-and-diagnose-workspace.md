# How to Author Definition-of-Ready Tasks and Diagnose Workspaces

This guide explains how to scaffold compliant Project Management as Code (PMaC) tasks with Definition of Ready (DoR) scaffolding and how to audit and repair your local developer environment with `spec-ops doctor`.

---

## Overview

SpecOps enforces rigorous Definition of Ready (DoR) and codebase health invariants (ADR-0001, ADR-0002). To reduce manual friction when authoring work items and onboarding developers to the repository, SpecOps provides:
- `spec-ops task create`: Scaffolds a new task file under `docs/project/backlog/` with pre-populated frontmatter and Gherkin BDD template sections.
- `spec-ops doctor`: Audits Python runtime, UV workspace configuration, pre-commit hooks, worktree ignores, and file length health.

---

## Authoring Compliant Tasks

### Interactive Task Scaffolding

Launch the guided wizard to create a new task interactively:

```bash
spec-ops task create
```

The wizard prompts for:
1. **Title**: Action-oriented task summary.
2. **Target Bounded Context**: Core domain boundary (`core`, `backlog`, `visualizer`, `security`, `rescue`, `prd`).
3. **Governing PRD**: Linked product requirements document (`PRD-0005`).
4. **Governing User Story**: Linked BDD user story (`US-0020`).
5. **Governing ADRs**: Linked architectural decisions (`ADR-0001`, `ADR-0003`).
6. **Dependencies**: Prerequisites required before refinement.

### Non-Interactive Task Scaffolding

For scripted pipelines or quick ticket authoring, pass CLI flags:

```bash
spec-ops task create --title "AST Anti-Mock Linter" --bc core --prd PRD-0005 --story US-0020 --adr ADR-0001 --stage proposed --non-interactive
```

The generated task file in `docs/project/backlog/proposed/` includes:
- Machine-readable YAML frontmatter.
- Gherkin acceptance criteria section (`Given ... When ... Then`).
- Architectural invariants and seams (file length limits, Hypothesis property tests, Mutmut mutation scope).
- Definition of Done (DoD) checklist.

---

## Diagnosing and Repairing Developer Workspaces

### Auditing Workspace Health

Inspect your local developer workspace to ensure all tools and hooks are configured properly:

```bash
spec-ops doctor
```

`spec-ops doctor` checks:
1. **UV Workspace**: Verifies `uv` is installed and workspace dependencies are synced.
2. **Pre-commit Hooks**: Verifies git pre-commit hooks are installed in `.git/hooks/`.
3. **Worktree Directory**: Verifies `.worktrees/` directory exists and is ignored in `.gitignore`.
4. **File Length Health**: Scans source files against the 500-line hard invariant (ADR-0002).

### Automated Environment Repair

If any checks fail (for example, missing pre-commit hooks or unignored worktrees), run automated repair:

```bash
spec-ops doctor --fix
```

This installs missing pre-commit hooks, creates and ignores `.worktrees/`, and ensures virtual environments are properly symlinked.

### Structured JSON Output for CI

Export machine-readable diagnostics for automated onboarding or CI checks:

```bash
spec-ops doctor --json
```
