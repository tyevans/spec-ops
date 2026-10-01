"""CLI primer and orchestration protocol references for universal SpecOps skill bundles."""

from __future__ import annotations

CLI_PRIMER_MD = """# SpecOps CLI Primer & Lifecycle Cheatsheet

This primer documents the public CLI entry points of SpecOps for orchestrators, agents, and human leads. SpecOps is managed via `uv run spec-ops <command>`.

---

## 1. Codebase Health & Quality Invariants

Inspect hard invariants, file lengths (<500 lines per ADR-0002), and backlog queue synchronization:

```bash
# Run full codebase health check
uv run spec-ops health

# Check supply-chain security policies and allowed licenses
uv run spec-ops health --security

# Audit project dependencies and lockfile immutability
uv run spec-ops audit

# Check constitution drift between specops.toml and AGENTS.md
uv run spec-ops constitution check

# Re-synchronize AGENTS.md while preserving custom invariants
uv run spec-ops constitution sync
```

---

## 2. Product Discovery & PRDs

PRDs live in `docs/project/product/` across lifecycle stages (`idea/`, `shaped/`, `accepted/`, `shipped/`):

```bash
# List all PRDs and their lifecycle states
uv run spec-ops prd list

# Lint PRDs against falsifiable criteria and checkable outcomes
uv run spec-ops prd lint docs/project/product/accepted/PRD-XXXX.md

# Inspect detailed PRD status and checkable outcomes
uv run spec-ops prd status PRD-XXXX
```

---

## 3. Backlog Management & Task Scaffolding

Tasks live in `docs/project/backlog/` across `proposed/`, `refined/`, and `complete/`:

```bash
# Scaffold a new PMaC task with Definition of Ready frontmatter
uv run spec-ops task create \\
  --title "My New Feature Slice" \\
  --bc core \\
  --prd PRD-0006 \\
  --story US-0117 \\
  --adr ADR-0001,ADR-0003 \\
  --stage proposed \\
  --non-interactive

# Audit backlog flow telemetry, bottleneck detection, and queue depth
uv run spec-ops backlog telemetry

# Diagnose and repair backlog health (orphans, cycle blocks, priority drift)
uv run spec-ops backlog doctor --repair
```

---

## 4. Cognitive Backlog Curation (JIT Refinement)

Curate proposed tasks into the ready buffer (`refined/`) to maintain ~10 ready tasks:

```bash
# Dry-run cognitive curation to inspect proposed tasks and architectural drift
uv run spec-ops curate --infer --dry-run

# Execute cognitive curation (promotes tasks, reconciles drift, synthesizes DoR criteria)
uv run spec-ops curate --infer

# Traditional priority-based curation buffer fill
uv run spec-ops curate
```

---

## 5. Worktree Sandboxing & Worker Execution

SpecOps enforces strict backlog isolation (ADR-0005) by executing in isolated git worktrees:

```bash
# Scaffold a human or agent worktree for a task
uv run spec-ops worktree create TASK-XXXX

# List active worktrees and their status
uv run spec-ops worktree list

# Run autonomous worker on the next ready task
uv run spec-ops worker

# Target a specific refined task
uv run spec-ops worker --task TASK-XXXX --dry-run

# Run full autonomous cycle with concurrent worker batching
uv run spec-ops cycle --max-workers 2
```

---

## 6. Worktree Rescue & Failure Triage

When a task fails or stalls during autonomous development:

```bash
# Inspect stalled worktree diagnostics and error logs
uv run spec-ops rescue inspect TASK-XXXX

# Salvage partial progress and stage clean files into a human branch
uv run spec-ops rescue salvage TASK-XXXX --files src/core/

# Reset stalled task with anti-loop failure memory to prevent recurring errors
uv run spec-ops rescue reset TASK-XXXX --anti-loop

# Clean up orphaned worktree directories and branches safely
uv run spec-ops rescue prune --older-than 7d
```

---

## 7. Quality Gates & Frontdoor Verification

Ensure 100% blackbox frontdoor pass rate before finalizing:

```bash
# Run test suite
uv run pytest

# Check lockfile synchronization
uv lock --check

# Audit for illegal private backdoor mocks (ADR-0003)
uv run spec-ops test anti-mock

# Run property-based invariant checks (Hypothesis)
uv run spec-ops verify properties
```

---

## 8. Documentation, Visualizer & Release Management

```bash
# Build Diataxis documentation site
uv run spec-ops docs build

# Launch zero-dependency living 2D graph visualizer
uv run spec-ops visualizer serve --port 8080

# Generate customer-facing release notes and business changelog
uv run spec-ops release generate --milestone v1.0.0

# Export executive roadmaps and stakeholder presentations
uv run spec-ops report burndown --format html
```
"""

ORCHESTRATION_PROTOCOL_MD = """# SpecOps Multi-Agent SDLC Orchestration Protocol

This document defines the multi-agent coordination protocol used by the SpecOps inline orchestrator. It establishes how autonomous subagents are dispatched, how they consult living specifications, and how failures are treated as first-class actionable work items.

---

## 1. Core Principles

1. **Inline Coordination (No Blind Process Forking)**:
   - The primary orchestrator runs directly within the active agent session.
   - Subagents are invoked via native agent tools (`invoke_subagent`, `send_message`) rather than detached background shell forks. This preserves context, allows dynamic intervention, and keeps the lead orchestrator informed.

2. **Living Specification as Ground Truth**:
   - All subagents must consult version-locked PMaC specifications in `docs/project/` before making architectural or code modifications:
     - Personas: `docs/project/user_stories/PERSONAS.md`
     - PRDs: `docs/project/product/accepted/`
     - User Stories: `docs/project/user_stories/accepted/`
     - ADRs: `docs/project/adrs/accepted/`
     - Backlog: `docs/project/backlog/`

3. **Strict Invariant Governance**:
   - Every subagent must honor hard invariants:
     - File length <500 lines (proactive warning at >=400 lines) per ADR-0002.
     - Blackbox frontdoor verification (ADR-0003, ADR-0006) without private backdoor mocks.
     - Strict backlog isolation on feature branches (ADR-0005).
     - Lockfile immutability and allowlisted commands.

4. **Actionable Orchestration Failure Protocol**:
   - When running on this project, any orchestration failure (subagent stall, tool error, spec ambiguity, preflight failure) is an **actionable task**:
     - Document the failure immediately as a high-priority bug in `docs/project/backlog/proposed/`.
     - Dispatch remediation to resolve the root cause before moving forward.

5. **Autonomous Continuous Balancing Loop**:
   - Maintain continuous development velocity across PRD value, BDD user journeys, ADR architectural invariants, and Diataxis documentation without waiting for manual step-by-step steering. Governed by [Continuous Balancing Loop](./balancing_loop.md).

---

## 2. Specialized Subagent Archetypes

When orchestrating across the SDLC, the lead agent dispatches specialized subagents:

| Role Name | Scope | Primary Inputs | Primary Outputs |
|---|---|---|---|
| `persona-agent` | Persona discovery & maintenance | User feedback, market shifts, codebase evolution | Updates to `docs/project/user_stories/PERSONAS.md` |
| `prd-agent` | Product discovery & PRD authoring | Unmet user needs, persona pain points | PRD draft in `docs/project/product/accepted/` |
| `story-agent` | Multi-faceted BDD user stories | Accepted PRD, personas, bounded contexts | Gherkin stories in `docs/project/user_stories/accepted/` |
| `slicing-agent` | INVEST task decomposition & spikes | User stories, architecture seams | Proposed tasks in `docs/project/backlog/proposed/` |
| `refinement-agent` | JIT backlog curation & DoR validation | Proposed queue, living ADRs, AST seams | Refined tasks in `docs/project/backlog/refined/` |
| `implementation-agent` | In-worktree TDD implementation | Refined task, governing ADRs/stories | Code changes, tests, commit trailers in worktree |
| `review-agent` | Architectural verification & preflight | Task diff, test suite, security policies | Verification report, preflight sign-off |

---

## 3. Step-by-Step Lifecycle Workflow

### Phase 1: Persona Maintenance
1. Dispatch `persona-agent` to evaluate existing personas in `docs/project/user_stories/PERSONAS.md`.
2. Ask: Are new archetypes emerging (e.g. security officers, non-technical PMs, external API consumers)? Are existing pain points addressed or evolving?
3. Update `PERSONAS.md` atomically with clear roles, pain points, and goals.

### Phase 2: Product Discovery & Living PRDs
1. Dispatch `prd-agent` to draft or shape a PRD under `docs/project/product/accepted/`.
2. Include: "Who this is for", "What the person cannot do today", "What good looks like", and "Checkable Outcomes".
3. Verify PRD validity: `uv run spec-ops prd lint docs/project/product/accepted/PRD-XXXX.md`.
4. Register in `docs/project/product/REGISTRY.md`.

### Phase 3: BDD User Story Generation
1. Dispatch `story-agent` to author multi-faceted user stories:
   - By Persona: Grounded in target archetypes.
   - By Bounded Context: Aligned with domain architecture (ADR-0007).
   - By Feature: Clear vertical slices.
2. Author executable Gherkin scenarios (`Given ... When ... Then`) verifiable via public frontdoors.
3. Save in `docs/project/user_stories/accepted/us-XXXX-....md` and register in `REGISTRY.md`.

### Phase 4: INVEST Task Decomposition
1. Dispatch `slicing-agent` to decompose stories into thin vertical slices (<500 lines per file):
   - Independent, Negotiable, Valuable, Estimable, Small, Testable.
   - If technical uncertainty exists, scaffold an architectural spike (`SPIKE-XXXX`).
2. Scaffold tasks using `uv run spec-ops task create` into `docs/project/backlog/proposed/`.

### Phase 5: JIT Refinement & Definition of Ready
1. Maintain a ready buffer of ~10 tasks in `docs/project/backlog/refined/`.
2. Run cognitive curation: `uv run spec-ops curate --infer`.
3. Validate Definition of Ready (DoR):
   - Dependencies mapped.
   - Governing PRDs, stories, and ADRs cited.
   - Executable Gherkin scenarios defined.
   - Property invariants and mutation targets identified.

### Phase 6: Subagent Implementation & Peer Consultation
1. Create isolated task worktree: `uv run spec-ops worktree create TASK-XXXX`.
2. Dispatch `implementation-agent` inside worktree.
3. Subagent must:
   - Consult cited ADRs and stories.
   - Write tests first (TDD) through public frontdoors.
   - Maintain file length <500 lines.
   - Keep commits structured with RFC 822 trailers (`SpecOps-Task: TASK-XXXX`).

### Phase 7: Verification, Preflight & Integration
1. Run preflight verification:
   ```bash
   uv run spec-ops health
   uv run pytest
   uv lock --check
   ```
2. Open pull request or perform merge under `MERGE_LOCK`.
3. Synchronize `PRIORITY.md` and transition task to `complete/` on `main`.

---

## 4. Failure Recovery & Continuous Dogfooding

If any subagent encounters a blocker, stall, or test failure:
1. **Never Silently Discard**: Inspect diagnostics using `uv run spec-ops rescue inspect TASK-XXXX`.
2. **Salvage or Reset**: Salvage working files with `spec-ops rescue salvage` or reset with anti-loop memory via `spec-ops rescue reset --anti-loop`.
3. **Log Orchestration Bug**: If the toolchain, script, or prompt caused the failure, record an actionable task in `docs/project/backlog/proposed/` to fix it for future runs.
"""
