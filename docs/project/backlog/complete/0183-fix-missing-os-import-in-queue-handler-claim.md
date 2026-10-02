---
id: 0183
title: Fix Missing os Import in Queue Handler Claim Action
status: Complete
governing_adrs:
- ADR-0001
- ADR-0002
- ADR-0003
governing_prds:
- PRD-0003
governing_stories:
- US-0001
target_bc: cli
signed_off_by: Ty Evans <tyevans@gmail.com>
signed_off_at: '2026-10-02T02:03:17.116474+00:00'
commit_signature_status: SIGNED
persona: Jordan (The AI-Native Engineering Lead) & Alex (The Agentic Systems Architect)
has_signed_commits: true
---

# TASK-0183: Fix Missing os Import in Queue Handler Claim Action

## Summary
In `src/spec_ops/cli/queue_handler.py`, the `claim` action accesses `os.environ.get("SPECOPS_WORKER_ID")` and `os.environ.get("SPECOPS_CLAIMANT")` on line 62, but `os` is never imported at module or function scope. Invoking `spec-ops queue claim` crashes immediately with `NameError: name 'os' is not defined. Did you forget to import 'os'?`.

## Problem Statement & Reproduction
1. Execute:
   ```bash
   uv run spec-ops queue claim 0172
   ```
2. Execution crashes with:
   ```text
   Traceback (most recent call last):
     File "/home/ty/workspace/spec-ops/src/spec_ops/cli/main.py", line 251, in main
       return handle_queue_command(args, config, parser)
     File "/home/ty/workspace/spec-ops/src/spec_ops/cli/queue_handler.py", line 62, in handle_queue_command
       claimant = getattr(args, "worker_id", None) or os.environ.get("SPECOPS_WORKER_ID") or os.environ.get("SPECOPS_CLAIMANT") or "spec-ops-worker"
                                                      ^^
   NameError: name 'os' is not defined. Did you forget to import 'os'?
   ```

## Proposed Fix
1. Add `import os` to `src/spec_ops/cli/queue_handler.py`.
2. Ensure `src/spec_ops/cli/queue_handler.py` maintains length under 400 lines (currently at 386 lines, adding one import will be ~387 lines).
3. Add a test in `tests/test_cli_queue.py` or unit test asserting `spec-ops queue claim` does not throw `NameError`.

## Definition of Done (Blackbox Frontdoor TDD)
1. `uv run spec-ops queue claim --help` and `uv run spec-ops queue claim` execute without `NameError`.
2. Unit and CLI tests pass cleanly without private backdoors.
3. Module stays under length limit (<500 lines).

## Acceptance Criteria

```gherkin
Scenario: Verify Fix Missing os Import in Queue Handler Claim Action
  Given the system is initialized and ready
  When the user executes the workflow for "Fix Missing os Import in Queue Handler Claim Action"
  Then observable outputs satisfy public contracts without backdoor tampering
  And no internal invariants are violated.
```

## Mutation Testing Scope
- Target domain module: `src/spec_ops/cli/...`
- Minimum mutation kill score: >=80% under Mutmut (ADR-0009).

## Hypothesis Invariant Properties
- `@given(...)`: Generative property tests asserting state invariants across randomized inputs without shrinking failures (ADR-0009).
