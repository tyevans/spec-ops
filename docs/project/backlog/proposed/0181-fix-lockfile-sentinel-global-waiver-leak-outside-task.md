---
id: TASK-0181
title: Fix Lockfile Sentinel Global Waiver Leak When Outside Dedicated Task Branch
status: Proposed
target_bc: security
dependencies: []
---

## Summary
In `src/spec_ops/security/lockfile_sentinel.py`, `_check_task_waiver` attempts to inspect backlog task frontmatter to check for `allows_dependencies: true` or `allows_lockfile_mutation: true`.

However, if the worktree directory name does not match `task-(\d+)` (for example, on `main` or in root checkouts), `task_num` is `None`. The loop over `candidate_files.extend(backlog_dir.glob("*/*.md"))` then iterates over all tasks across the entire backlog, and if *any* historical or proposed task anywhere has `allows_dependencies: true`, it returns `True`, globally waiving lockfile mutations across the entire repository.

## Requirements
1. In `_check_task_waiver`, only check the active task matching the current git branch name or worktree path.
2. If neither the git branch nor directory indicates an active task, do not match arbitrary backlog task files.
