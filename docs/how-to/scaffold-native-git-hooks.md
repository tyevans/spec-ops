# How-To: Scaffold Zero-Dependency Native Git Hooks and Guard Autonomous Worktrees

This guide covers installing native POSIX shell git hooks (`pre-commit` and `pre-push`) to enforce backlog isolation, file length limits (<500 lines), and supply chain lockfile integrity across local branches and autonomous worker worktrees.

---

## Scaffolding Native Hooks

To scaffold native git hooks in your SpecOps repository:

```bash
spec-ops scaffold hooks
```

If hooks already exist and you want to overwrite them:

```bash
spec-ops scaffold hooks --force
```

This installs zero-dependency executable POSIX shell scripts directly into:
- `.git/hooks/pre-commit`
- `.git/hooks/pre-push`

---

## Guardrails Enforced

### 1. Strict Backlog Isolation (ADR-0005)
On any non-main/master branch (such as `feat/*` or `task/*`), the pre-commit hook intercepts commits that stage modifications to `docs/project/backlog/`. The commit aborts immediately:

```text
Invariant Violation (ADR-0005): Feature branches are strictly forbidden from modifying docs/project/backlog/. Backlog transitions are managed automatically upon merge to main.
```

### 2. File Length Invariant Gate (ADR-0002)
The hook executes `spec-ops health` and blocks commits if any source file exceeds 500 lines or if backlog sync errors exist.

### 3. Supply-Chain Lockfile Verification (ADR-0011)
When `uv.lock` or `pyproject.toml` is modified, the hook executes `uv lock --check` to ensure dependencies remain cryptographically pinned and synchronized.

### 4. Anti-Mock Frontdoor Verification (ADR-0003)
When test files under `tests/` are staged, the hook runs `spec-ops test audit-anti-mock` to intercept private mock backdoors before commit.

---

## Automatic Worktree Propagation

When autonomous workers provision isolated worktrees (e.g. `.worktrees/TASK-XXXX`), git hooks are automatically propagated to `.git/worktrees/<task>/hooks`, guaranteeing identical guardrails across all concurrent agent streams.
