---
id: '0123'
title: Add Virtual Environment .venv to Gitignore
status: Complete
governing_adrs:
- ADR-0001
- ADR-0003
governing_prds:
- PRD-0005
governing_stories:
- US-0068
target_bc: scaffold
signed_off_by: Ty Evans <tyler@poorlythoughtout.com>
signed_off_at: '2026-10-01T00:24:59.653760+00:00'
mutation_scope: src/spec_ops/scaffold/diataxis.py
has_signed_commits: true
commit_signature_status: SIGNED
---

# TASK-0123: Add Virtual Environment .venv to Gitignore

## Summary
Add `.venv/` to `.gitignore` to prevent git worktrees from being flagged as dirty due to untracked virtual environments created by uv.

## Problem Statement & Context
When git worktrees are initialized via `spec-ops worktree start`, `uv` or Python environment helpers create `.venv` inside the isolated worktree directory. Because `.venv` is missing from the repository's `.gitignore`, `git status` reports untracked files and `spec-ops rescue` flags the clean worktree as `[DIRTY]`.

Per the SpecOps Dogfooding / SDLC Orchestration Failure Invariant defined in `AGENTS.md`, any orchestration failure is an actionable task documented as a defect in the backlog and remediated.

## Resolution
1. Add `.venv/` to `.gitignore`.
2. Verify git status in all worktrees reports clean.
