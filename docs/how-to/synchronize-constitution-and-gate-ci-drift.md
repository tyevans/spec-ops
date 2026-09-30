# How to Synchronize Living Constitution and Gate CI Drift

This guide demonstrates how to re-synchronize `AGENTS.md` and `docs/operating-manual.md` from `specops.toml` configuration while preserving custom invariant extensions, and how to enforce constitution synchronization in CI using `spec-ops constitution check`.

---

## Overview

In SpecOps, `AGENTS.md` and `docs/operating-manual.md` act as the machine-executable operating constitution for autonomous coding agents and human developers. When project architectural constraints (such as `file_length_limit` or `quality.preflight` commands) are updated in `specops.toml`, the constitution must be kept strictly in sync.

At the same time, teams frequently author custom operational rules (e.g., local emulator ports, domain service URLs). The constitution synchronizer preserves anything enclosed within `<!-- BEGIN CUSTOM INVARIANTS -->` and `<!-- END CUSTOM INVARIANTS -->` comment delimiters verbatim across updates.

---

## Step 1: Add Custom Invariant Extensions

To add team-specific guidelines that should never be overwritten during scaffolding or profile updates, place them within the marked custom invariants block in `AGENTS.md`:

```markdown
<!-- BEGIN CUSTOM INVARIANTS -->
Always run local emulator on port 9090 before starting integration tests.
<!-- END CUSTOM INVARIANTS -->
```

Any arbitrary text, code blocks, or compliance requirements inside these delimiters are preserved verbatim across all synchronization passes.

---

## Step 2: Re-synchronize Constitution

When `specops.toml` settings change (e.g. updating `file_length_limit = 350` or adding `ruff check` to quality preflights), re-synchronize the constitution:

```bash
spec-ops constitution sync
```

Alternatively, running:

```bash
spec-ops scaffold agents
```

also triggers the synchronizer, regenerating `AGENTS.md` and updating `docs/operating-manual.md` with adjusted relative links while keeping custom invariant blocks intact.

---

## Step 3: Enforce Synchronization in CI Preflight

To prevent configuration drift from merging into `main`, incorporate the fast-fail drift detection gate into your CI pipeline:

```bash
spec-ops constitution check
```

- **Exit code 0**: `AGENTS.md` is synchronized with `specops.toml`.
- **Exit code 1**: A mismatch is detected; prints actionable diff diagnostics and prompts running `spec-ops scaffold agents` or `spec-ops constitution sync`.
