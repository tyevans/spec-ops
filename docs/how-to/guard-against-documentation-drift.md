# How-To: Guard Against Living Diataxis Documentation Drift

This guide demonstrates how to use `spec-ops docs check` to ensure all public CLI commands and interfaces are continuously documented across Diataxis technical documentation before pull request integration.

---

## Overview

When developers or autonomous agents introduce new CLI commands or public capabilities, documentation often drifts or falls behind. SpecOps enforces documentation synchronization as code via the living Diataxis drift guard.

The drift guard introspects the running CLI command tree and audits against:
- **Reference Specifications**: `docs/reference/*.md` (e.g. `docs/reference/cli.md`)
- **How-To Guides**: `docs/how-to/*.md`

If a public command exists in code but lacks documentation in either quadrant, the check fails with an actionable drift alert and non-zero exit code.

---

## Running the Documentation Drift Check

To audit public commands against Diataxis documentation:

```bash
spec-ops docs check
```

When all public interfaces and CLI subcommands are documented, the command outputs:

```text
All public interfaces and CLI commands are documented.
```

And exits with code `0`.

---

## Detecting and Resolving Drift

When a developer introduces a new subcommand (for example, `spec-ops task publish`):

```bash
spec-ops docs check
```

Output:

```text
Documentation Drift Detected: Public CLI command 'spec-ops task publish' is not documented.
```

Exit code: `1`.

### Resolving the Drift Alert

To resolve the alert, document the command in either:
1. `docs/reference/cli.md` under the subcommands table or list.
2. A new or existing how-to recipe under `docs/how-to/` (e.g. `docs/how-to/archive-tasks.md`).

Once documented, re-running `spec-ops docs check` passes cleanly, and `spec-ops docs build` verifies documentation build integrity with 0 warnings.
