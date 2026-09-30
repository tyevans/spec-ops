# How-To: Verify Supply-Chain Lockfiles and Slopsquatting Defense

This guide covers verifying dependency lockfile immutability, cryptographic package hashes, and gating integration against unauthorized dependency alterations.

---

## Verifying Lockfile Cryptographic Hashes

To verify that all dependencies in `uv.lock` are strictly pinned, match upstream registry records, and contain valid sha256 hashes:

```bash
spec-ops security verify-lock
```

A clean verification reports:

```text
✅ Lockfile verified: cryptographic hashes and package pins valid.
```

If package drift, unpinned versions, or corrupted hashes are detected, `spec-ops security verify-lock` exits with returncode 1 and lists actionable diagnostics.

---

## Task-Level Dependency Authorization Gate

By default, autonomous agent worktrees reject modifications to `pyproject.toml` or `uv.lock` to prevent AI hallucination attacks ("slopsquatting").

To explicitly authorize dependency modifications for a task, declare `allows_dependencies: true` in the task frontmatter:

```yaml
---
id: '0042'
title: Upgrade Database Driver
status: Refined
allows_dependencies: true
target_bc: infrastructure
---
```

When `allows_dependencies: true` is set:
1. Modifications to `pyproject.toml` or `uv.lock` are permitted in the worktree.
2. `spec-ops security verify-lock` and `uv lock --check` execute during preflight to cryptographically validate all package hashes.

---

## Automatic Non-Dependency Sanitization

Agents sometimes inadvertently modify non-dependency sections in `pyproject.toml` (for example, attempting to adjust test configurations or mutation testing targets under `[tool.mutmut]`).

SpecOps implements proactive guardrails during commit preparation:
- If a task has `allows_dependencies: false` (the default) and only non-dependency sections of `pyproject.toml` were modified, the guardrail automatically resets `pyproject.toml` to `HEAD`.
- If actual dependency sections (`[project.dependencies]`, `dependencies =`, `[project.optional-dependencies]`, `[dependency-groups]`, `[build-system]`) are altered without authorization, the file is left modified so preflight security gates properly block the commit.
- Task hydration prompts explicitly inform autonomous workers that `pyproject.toml` and `uv.lock` are immutable under US-0111 unless authorized.

---

## Gating Backlog Integration Under Merge Lock

To gate and complete an autonomous feature branch against `main`:

```bash
spec-ops queue complete TASK-0042
```

The integration gate enforces:
- Zero unstaged lockfile alterations in the worktree or repository.
- Zero unauthorized lockfile changes across the branch diff against `main`.
- Full cryptographic validation before moving the task to `docs/project/backlog/complete/` and synchronizing `PRIORITY.md`.
