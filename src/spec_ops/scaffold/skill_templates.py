"""Templates for Antigravity skills and slash commands."""

from __future__ import annotations

CURATE_SKILL_MD = """---
name: curate
description: Audit backlog health and perform cognitive, inference-driven refinement to maintain the ready buffer in docs/project/backlog/refined/. Triggered by /curate.
---

# Backlog Curation & Cognitive Refinement

Perform interactive, inference-driven backlog curation and buffer replenishment. Maintain repository backlog health by auditing candidate tasks against living repository reality, reconciling architectural drift across superseded ADRs and refactored modules, autonomously decomposing oversized monolithic tasks (>500 lines) into INVEST-compliant thin vertical slices and spikes, and synthesizing missing Definition of Ready (DoR) criteria.

## Cognitive Refinement Procedure

### Step 1: Audit Candidates with Inference Dry-Run
Run the SpecOps cognitive curation engine in dry-run mode to inspect candidate tasks, architectural drift, and scope slicing without modifying disk state:
```bash
uv run spec-ops curate --infer --dry-run
```

### Step 2: Interactive Architectural Review & Scope Slicing
Review proposed reconciliations and decompositions with the developer or lead:
1. **Audit Under-Buffered Queue**: Check `docs/project/backlog/refined/` and `docs/project/backlog/proposed/` to determine ready buffer deficit.
2. **Reconcile Architectural Drift**: Verify that candidate tasks referencing refactored modules or superseded ADRs are updated to active domain models and active ADR citations.
3. **Decompose Oversized Monolithic Tasks**: Review proposed vertical slices (<400 lines) and exploratory architectural spikes for tasks touching multiple bounded contexts or exceeding modular thresholds.
4. **Synthesize Missing DoR Contracts**: Review generated executable Gherkin scenarios (`Given ... When ... Then`) and Hypothesis property invariants synthesized from PRD checkable outcomes.

### Step 3: Human-in-the-Loop Review & Promotion
Present the architectural diff and decomposition plan for confirmation, then execute live cognitive curation:
```bash
uv run spec-ops curate --infer
```

### Step 4: Verify Invariant Health & PRIORITY.md Sync
Run the SpecOps health checker to verify 0 file limit violations (<500 lines) and strict `PRIORITY.md` index synchronization:
```bash
uv run spec-ops health
```
"""

HEALTH_SKILL_MD = """---
name: health
description: Audit codebase invariants, file length limits (<500 lines), proactive refactoring warnings, and backlog synchronization. Triggered by /health.
---

# Codebase Invariant Health Check

Inspect repository health against non-negotiable hard invariants and operational SDLC guardrails governed by ADR-0001, ADR-0002, and ADR-0005.

## Execution Procedure

### Step 1: Run Health Inspection
Execute the SpecOps health verification CLI command:
```bash
uv run spec-ops health
```

### Step 2: Evaluate Results
1. **File Length Limit (<500 lines)**:
   - Zero production or test files may exceed 500 lines. Decompose oversized files into modular single-responsibility units.
2. **Proactive Refactoring Warnings (>=400 lines)**:
   - Identify modules approaching the threshold and plan JIT decomposition before hard invariants are breached.
3. **Backlog State & Buffer Readiness**:
   - Check completed, refined, and proposed counts. Alert if ready buffer is under-buffered (<6 tasks).
4. **PRIORITY.md Synchronization**:
   - Verify that `docs/project/backlog/PRIORITY.md` is strictly synchronized with disk state in `complete/`, `refined/`, and `proposed/`.
"""

WORKER_SKILL_MD = """---
name: worker
description: Execute the next ready backlog task or a specified task in an isolated git worktree with strict backlog isolation and preflight verification. Triggered by /worker.
---

# Autonomous Backlog Worker Execution

Execute backlog tasks inside isolated git worktrees (`.worktrees/<task-id>`) ensuring zero merge collisions across concurrent streams and verifying observable contracts strictly through public frontdoors.

## Execution Procedure

### Step 1: Dispatch Worker
Run the SpecOps worker engine:
```bash
uv run spec-ops worker
```
Or target a specific task canonical ID:
```bash
uv run spec-ops worker --task TASK-XXXX
```
For dry-run inspection without invoking agent sub-processes:
```bash
uv run spec-ops worker --dry-run
```

### Step 2: Verify Invariants During Task Execution
When working inside a task worktree:
1. **File Length Limit**: Ensure all new or modified files remain strictly <500 lines.
2. **Strict Backlog Isolation**: Never modify `docs/project/backlog/` directly on feature branches. Backlog status transitions are synchronized upon integration into `main`.
3. **Blackbox Frontdoor Testing**: Write tests exercising observable contracts via public CLI commands, APIs, and domain models without private backdoor mocks.
4. **Preflight Verification**: Ensure all preflight checks pass before completion:
   ```bash
   uv run spec-ops health
   uv run pytest
   uv lock --check
   ```
"""

SPEC_OPS_SKILL_MD = """---
name: spec-ops
description: Autonomous full-lifecycle Project Management as Code (PMaC) orchestrator and company-in-a-box. Coordinates personas, living PRDs, BDD stories, task breakdown, JIT refinement, and multi-agent implementation without detached process forks. Triggered by /spec-ops or when orchestrating SDLC workflows.
---

# SpecOps Full-Lifecycle SDLC Orchestrator ("Company in a Box")

You are the **Lead SDLC Orchestrator** for SpecOps. Your objective is to drive end-to-end software development—from initial persona and product discovery down to verified production delivery—with non-negotiable standards for software craftsmanship, architectural clarity, and zero-drift PMaC specifications.

## Operating Philosophy & Non-Negotiable Invariants

1. **Inline Coordination (No Blind Process Forking)**:
   - Run directly in the active agent session. Do not spawn detached background agent forks that blind the host session.
   - Use native subagent capabilities (`invoke_subagent`, `send_message`, `manage_subagents`) to parallelize work while retaining full visibility and control.
2. **Living Specifications as Code**:
   - Everything lives in git: Personas (`docs/project/user_stories/PERSONAS.md`), PRDs (`docs/project/product/`), Stories (`docs/project/user_stories/`), ADRs (`docs/project/adrs/`), and Tasks (`docs/project/backlog/`).
3. **Hard Architectural Invariants**:
   - **File Length Limit (<500 lines)**: Decompose modules exceeding ~400 lines (ADR-0002).
   - **Blackbox Frontdoor Verification**: Test observable behavior via public APIs and CLI entry points; zero private backdoor mocks (ADR-0003, ADR-0006).
   - **Strict Backlog Isolation**: Work in isolated worktrees (`feat/<task-id>`); never touch `docs/project/backlog/` on feature branches (ADR-0005).
   - **Supply-Chain Security**: Zero hardcoded secrets, immutable lockfiles (`uv lock --check`), allowlisted commands only.
4. **Dogfooding & Orchestration Failure Invariant**:
   - When running on this project, any orchestration failure is an **actionable task**:
     - Immediately document the failure as a high-priority bug in `docs/project/backlog/proposed/`.
     - Dispatch remediation to resolve the root cause before moving forward.

## The 7-Phase SDLC Lifecycle Procedure

Follow these phases sequentially or trigger specific phases as requested by the user:

### Phase 1: Persona Discovery & Maintenance
1. Inspect `docs/project/user_stories/PERSONAS.md`.
2. Ask: Are new user archetypes emerging? Are existing pain points out of date?
3. If updates are needed, refine persona profiles with explicit roles, pain points, and SpecOps goals.

### Phase 2: Product Discovery & Living PRDs
1. Draft or refine the PRD under `docs/project/product/accepted/prd-XXXX-<slug>.md`.
2. Ensure required sections: "Who this is for", "What the person cannot do today", "What good looks like", and "Checkable Outcomes".
3. Validate:
   ```bash
   uv run spec-ops prd lint docs/project/product/accepted/prd-XXXX-<slug>.md
   ```
4. Register the PRD in `docs/project/product/REGISTRY.md`.

### Phase 3: Multi-Faceted BDD User Stories
1. Author BDD user stories under `docs/project/user_stories/accepted/us-XXXX-<slug>.md`.
2. Map across facets: target persona, bounded context (ADR-0007), and feature slice.
3. Write executable Gherkin scenarios (`Given ... When ... Then`) verifiable through public frontdoors.
4. Register the story in `docs/project/user_stories/REGISTRY.md`.

### Phase 4: INVEST Task Slicing & Spikes
1. Decompose stories into thin vertical slices (<500 lines per file):
   - Independent, Negotiable, Valuable, Estimable, Small (<500 lines), Testable.
   - For technical uncertainties, scaffold an architectural spike (`SPIKE-XXXX`).
2. Scaffold proposed tasks:
   ```bash
   uv run spec-ops task create --title "..." --bc core --prd PRD-XXXX --story US-XXXX --adr ADR-XXXX --stage proposed --non-interactive
   ```

### Phase 5: JIT Backlog Curation & Definition of Ready
1. Maintain a ready buffer of ~10 tasks in `docs/project/backlog/refined/`.
2. Execute cognitive curation to evaluate candidates, reconcile architectural drift, and synthesize missing DoR criteria:
   ```bash
   uv run spec-ops curate --infer
   ```
3. Verify codebase health and priority index synchronization:
   ```bash
   uv run spec-ops health
   ```

### Phase 6: Subagent Implementation & Peer Consultation
1. Create an isolated worktree for the task:
   ```bash
   uv run spec-ops worktree create TASK-XXXX
   ```
2. Dispatch an `implementation-agent` subagent into the worktree:
   - Instruct the subagent to consult governing ADRs, PRDs, and user stories.
   - Practice test-driven development (TDD) through public frontdoors.
   - Maintain file length <500 lines at all times.
3. If subagents encounter blockers, consult peer agents or rescue stalled state via `uv run spec-ops rescue`.

### Phase 7: Verification, Preflight & Integration Gate
1. Execute full verification suite inside the branch:
   ```bash
   uv run spec-ops health
   uv run pytest
   uv lock --check
   ```
2. Open pull request or perform merge under `MERGE_LOCK`.
3. Transition task to `complete/` and synchronize `docs/project/backlog/PRIORITY.md` upon integration into `main`.
"""
