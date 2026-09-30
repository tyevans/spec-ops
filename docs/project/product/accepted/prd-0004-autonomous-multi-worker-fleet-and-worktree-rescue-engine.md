---
id: '0004'
title: Autonomous Multi-Worker Fleet & Preserved Worktree Rescue Engine
status: Accepted
created: 2026-09-29
target_persona: Morgan (The Autonomous Coding Agent) & Riley (The Full-Stack Developer)
component: worker
---

# PRD-0004 — Autonomous Multi-Worker Fleet & Preserved Worktree Rescue Engine

## Who this is for

- **Morgan (The Autonomous Coding Agent)**: Needs conflict-free worktree execution, self-healing diagnostic loops, and machine-readable task contracts.
- **Riley (The Human IC Developer & Agent Collaborator)**: Needs instant failure triage, selective patch salvage, and zero-pollution worktree cleanup.
- **Jordan (The AI-Native Engineering Lead)**: Needs deterministic multi-worker batch processing with auto-rebase and transactional merge locking.

## What the person cannot do today

- **Concurrent Agent Conflicts**: Parallel coding agents step on each other's toes, modifying shared backlog files and causing merge conflicts upon pull request integration.
- **Hallucinatory Self-Healing**: When an autonomous agent encounters unexpected test or syntax failures, it often hallucinates repetitive broken fixes or gives up and discards valuable progress.
- **Lost Developer Context**: When an agent fails its retry limit, developers rescuing the task must manually reconstruct git state without knowing what the agent attempted or why preflight checks failed.
- **Filesystem Pollution**: Abandoned worktree directories accumulate indefinitely, consuming gigabytes of disk space and causing orphan branch clutter.

## What good looks like

1. **Pluggable Runner Templates & Dry-Run Simulation**:
   - Extensible agent runners with simulation modes verifying worktree creation, branch isolation, and prompt hydration before spawning live LLM processes.
2. **Concurrent Multi-Worker Execution & Transactional Merge Lock**:
   - Parallel agent execution in isolated worktrees (`.worktrees/<task-id>`) with automated rebase under `MERGE_LOCK` ensuring zero git conflicts on integration.
3. **Multi-Stage Preflight Validation & AST Diagnostic Injection**:
   - Fast-fail preflight pipeline (`uv lock`, `pytest`, `spec-ops health`) injecting AST line/column diagnostics into the agent's self-healing loop.
4. **Interactive Preserved Worktree Triage & AI-to-Human Handover**:
   - Preserved worktrees generating structured `HANDOVER.md` briefs with reproducer commands, diff summaries, and failure breakdown.
5. **Selective Patch Takeover & Zero-Pollution Pruning**:
   - Developer ergonomics allowing humans to cherry-pick working files, discard failed attempts with anti-loop memory, and prune stale worktrees safely.

## What this does not do

- It does not replace the LLM inference provider; it governs agent execution with deterministic git and PMaC contracts.
- It does not permit unverified code to merge directly to `main` without passing all blackbox frontdoor gates.

## Checkable Outcomes

1. Running `spec-ops cycle --max-workers 3` executes multiple autonomous workers concurrently without git conflicts or dirty shared backlogs.
2. Running `spec-ops rescue inspect TASK-XXXX` displays an interactive failure diagnostic breakdown and diff summary in the preserved worktree.
3. Running `spec-ops rescue salvage TASK-XXXX --files src/core/` stages valid changes into a human feature branch while resetting task state to refined.
4. Running `spec-ops rescue prune --older-than 7d` safely cleans up orphaned worktree directories and branches with zero data loss.
5. Preserved worktrees automatically generate an up-to-date `HANDOVER.md` debugging cheatsheet with exact reproducer commands.

## Linked User Stories

- `US-0027`
- `US-0028`
- `US-0029`
- `US-0030`
- `US-0031`
- `US-0032`
- `US-0033`
- `US-0034`
- `US-0035`
- `US-0036`
- `US-0037`
- `US-0038`
- `US-0039`
- `US-0040`
- `US-0041`
- `US-0042`
- `US-0080`
- `US-0081`
- `US-0082`
- `US-0083`
- `US-0084`
- `US-0085`
- `US-0086`
- `US-0087`
- `US-0088`
- `US-0089`
- `US-0090`
- `US-0091`
- `US-0092`
- `US-0093`
- `US-0115`

## Implementing Backlog Tasks

- `TASK-0044`
- `TASK-0045`
- `TASK-0046`
- `TASK-0047`
- `TASK-0048`
- `TASK-0049`
- `TASK-0050`
- `TASK-0051`
- `TASK-0052`
- `TASK-0053`
- `TASK-0054`
- `TASK-0055`
- `TASK-0072`
- `TASK-0073`
- `TASK-0082`
