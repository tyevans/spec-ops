# Explanation: Runefoble System Patterns Audit & SpecOps Extraction Matrix

> **Comprehensive audit of the parent Runefoble repository (`/home/ty/workspace/runefoble`) and extraction blueprint for SpecOps.**

---

## 1. Executive Context

The Runefoble repository pioneered an end-to-end, multi-agent development environment managing microservices, frontend microfrontends, Kubernetes deployments, and autonomous gameplay loops. In doing so, it organically developed robust, battle-tested patterns for:
- Agent constitutions and operational rules (`AGENTS.md`)
- Worktree concurrency, preflight verification, and CI repair loops (`tools/backlog_engine/`)
- PRD decomposition and backlog synchronization (`tools/prd_pipeline/`)
- Invariant health checking and proactive warning thresholds (`scripts/health_check.py`)
- Safe worktree audit and cleanup (`scripts/cleanup_worktrees.py`)
- Full Diataxis documentation trees (`docs/`)

**SpecOps** is the extracted, standalone, domain-agnostic Project Management as Code (PMaC) engine that generalizes these patterns into a modular CLI tool for any engineering project.

---

## 2. Comprehensive Extraction Matrix

The table below maps each core subsystem in Runefoble, its source files, its governing design pattern, and its target destination module in SpecOps:

| Runefoble Subsystem | Source Path in Runefoble | Pattern & Capabilities | Target Destination in SpecOps | Status / Associated Task |
|---|---|---|---|---|
| **Agent Constitution** | `AGENTS.md` | Non-negotiable hard invariants, navigation rules, Definition of Ready (DoR), Definition of Done (DoD), agent work delegation protocols | `spec_ops.scaffold.agents_md` | `TASK-0010` (Refined) |
| **Codebase Invariant Health** | `scripts/health_check.py` | Source file length inspection (<500 lines), proactive refactoring warnings (>400 lines), buffer health triage, PRIORITY.md drift detection | `spec_ops.backlog.health` | Extracted (`TASK-0005`), enhancements in `TASK-0020` |
| **Git Worktree Concurrency** | `tools/backlog_engine/worktree.py` | Thread-safe worktree creation (`.worktrees/<task-id>`), backlog isolation enforcement, atomic pruning | `spec_ops.backlog.worker` | Extracted (`TASK-0011`) |
| **Worktree Audit & Cleanup** | `scripts/cleanup_worktrees.py` | Auditing active PIDs, detecting uncommitted work, checking branch merge status, safe garbage collection | `spec_ops.backlog.worktree_ops` | `TASK-0018` (Proposed) |
| **Worktree Takeover & Rescue** | `tools/backlog_engine/orchestrator.py` | Preserving failed worktree context for human takeover when agent attempts stall | `spec_ops.backlog.worker` (`spec-ops rescue`) | `TASK-0018` (Proposed) |
| **Automated CI Watcher & Repair** | `tools/backlog_engine/ci_watcher.py` | Polling remote GitHub Actions status (`gh pr checks`), parsing failed step logs, generating self-healing prompt | `spec_ops.backlog.ci_watcher` | `TASK-0012` (Refined) |
| **Supply-Chain Preflight Gates** | `Makefile` (`make preflight`) | Enforcing lockfile check (`uv lock --check`) and preventing hallucinated dependencies ("slopsquatting") | `spec_ops.config.models` / preflight | `TASK-0019` (Proposed) |
| **Pre-Commit Hook Scaffolding** | `.pre-commit-config.yaml` | Running Ruff, file length scanner, YAML syntax validator, and conflict check pre-commit | `spec_ops.scaffold.hooks` | `TASK-0020` (Proposed) |
| **PRD Lifecycle & Slicing** | `tools/prd_pipeline/decomposer.py` | Thin vertical slicing, architectural spike generation, INVEST criteria validation | `spec_ops.prd.decomposer` | Extracted (`TASK-0006`) |
| **Registry Synchronization** | `tools/prd_pipeline/registry_sync.py` | Bidirectional synchronization across PRDs, User Stories, and Backlog indices | `spec_ops.prd.manager` & `BacklogQueue` | Extracted (`TASK-0007`) |
| **Diataxis Documentation Tree** | `docs/` (tutorials, how-to, reference, explanation) | Strict four-quadrant Diataxis structure with agent authoring directives | `spec_ops.scaffold.docs` | `TASK-0015` (Refined) |
| **Diataxis Drift Verification** | `AGENTS.md` (lines 63-71) | Verifying docs don't drift from public CLI interfaces or configuration models | `spec_ops.docs.auditor` (`spec-ops docs audit`) | `TASK-0021` (Proposed) |
| **Living 2D Graph Visualizer** | `tools/project_visualizer/` | Zero-dependency standalone HTML canvas, force-directed graph, buffer cards | `spec_ops.visualizer` | Extracted (`TASK-0008`, `TASK-0017`) |
| **Interactive TUI Dashboard** | `tools/backlog_engine/cli.py` | Rich interactive terminal interface for backlog browsing and dispatching | `spec_ops.tui` | `TASK-0013` (Refined) |

---

## 3. Key Runefoble Invariants Formalized into SpecOps

The audit identifies four foundational invariants from Runefoble that are now formal requirements of SpecOps:

1. **The Frontdoor-Only Invariant (ADR-0003)**:
   - Runefoble rejected private database mutation and mock-heavy testing because they caused false-positive pass rates while user journeys failed in production.
   - SpecOps enforces blackbox verification through public CLI commands, public REST APIs, and public domain events.
2. **Strict Backlog Isolation (ADR-0005)**:
   - Runefoble proved that when autonomous agents edit `docs/project/backlog/` directly on feature branches, parallel worktrees collide immediately upon integration.
   - SpecOps enforces branch isolation: the worker engine strips branch-level edits to `docs/project/backlog/` and applies transitions under `MERGE_LOCK` directly on `main`.
3. **Hard Modular File Limit (<500 lines) & Warning Threshold (400 lines) (ADR-0002)**:
   - Monolithic files cause LLM context degradation.
   - SpecOps enforces a hard limit of 500 lines in CI, with proactive warnings when files exceed 400 lines.
4. **Diataxis Four-Quadrant Documentation Integrity (ADR-0008)**:
   - Documentation is not an afterthought; it is version-controlled alongside code.
   - Agents must check and update relevant how-to guides and references as part of the Definition of Done.

---

## 4. Extraction Roadmap & Backlog Impact

Following this audit, the SpecOps backlog is organized into sequential implementation priorities:

1. **Immediate Next (`TASK-0010`)**: Profile-driven `AGENTS.md` scaffolding in `spec-ops init`.
2. **Engine Completion (`TASK-0011`, `TASK-0018`, `TASK-0019`)**: Complete worktree worker engine, add worktree rescue (`spec-ops rescue`), and inject `uv lock --check` supply-chain gates into preflight.
3. **Developer Ergonomics (`TASK-0020`)**: Pre-commit hook scaffolding and 400-line proactive warning scanner.
4. **Documentation & Publishing (`TASK-0015`, `TASK-0016`, `TASK-0021`)**: Diataxis static site generator, GitHub Pages pipeline, and documentation drift auditor.
5. **Interactive Operations (`TASK-0013`, `TASK-0014`)**: Terminal UI dashboard and multi-agent platform adapters (Claude, Cursor, Aider, Antigravity).
