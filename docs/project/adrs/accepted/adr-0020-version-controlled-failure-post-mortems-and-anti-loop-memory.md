# ADR-0020: Version-Controlled Failure Post-Mortems and Anti-Loop Memory

## Status
Accepted

## Context
When autonomous AI agents fail on tasks due to flawed architectural assumptions, invalid implementation approaches (such as introducing private mock backdoors violating ADR-0003, monkey-patching external libraries, or modifying immutable configuration/lockfiles), human software engineers must intervene to rescue the worktree (`spec-ops rescue`).

In the baseline architecture, discarding an irreparably broken worktree via `spec-ops rescue <task-id> --discard` wiped the worktree and branch but retained zero diagnostic telemetry or failure memory in the version-controlled Project Management as Code (PMaC) task specification. Consequently, when the task was returned to the `refined/` backlog buffer for re-assignment, subsequent worker sessions claimed the task with identical context, frequently repeating the exact same flawed strategy in an infinite failure loop.

To break repetitive failure loops and preserve institutional memory, SpecOps requires a version-controlled failure post-mortem schema embedded directly into task specifications, coupled with automatic negative constraint synthesis during worker prompt hydration and automated queue demotion mechanics for specification ambiguities.

## Decision
We establish **Version-Controlled Failure Post-Mortems and Anti-Loop Memory** across the rescue, backlog, and worker bounded contexts:

1. **Lossless Frontmatter Schema (`failure_history`)**:
   - Task YAML frontmatter schema is extended with a monotonic list field `failure_history`.
   - Each entry records:
     - `attempt_date`: ISO 8601 date string (e.g. `2026-09-29`) identifying when the attempt stalled or was discarded.
     - `reason`: String describing the specific failure mode, flawed assumption, or anti-pattern observed.
     - `failed_invariants`: Optional list of governing invariant IDs (e.g., `[ADR-0003]`) breached by the attempt. When omitted during CLI invocation, invariant IDs are automatically inferred via regular expression analysis of the failure reason.
   - Frontmatter serialization guarantees 100% byte-for-byte preservation of the underlying markdown body AST and non-failure frontmatter keys across repeated append-reset cycles.

2. **Worktree Discard & Reset Tooling (`spec-ops rescue reset`)**:
   - The CLI frontdoor is expanded with `spec-ops rescue reset <task-id> --reason "<reason>" [--demote]`.
   - Executing `rescue reset`:
     - Teardowns and deletes the failed `.worktrees/task-<id>` git worktree and associated feature branch (`feat/<task-id>`).
     - Appends the failure record to the task's frontmatter in `docs/project/backlog/refined/`.
     - When `--demote` is specified (e.g., when specification ambiguity or contradictory criteria caused the failure), moves the task file from `refined/` to `proposed/`, sets `status: Proposed`, and atomically updates `docs/project/backlog/PRIORITY.md` references to prevent unrefined tasks from blocking autonomous claiming.

3. **Autonomous Worker Prompt Hydration (`## Prior Attempt Failures & Anti-Patterns`)**:
   - During `.task-prompt.md` compilation in `TaskClaimer`, any existing `failure_history` entries synthesize a dedicated, prominent section:
     ```markdown
     ## Prior Attempt Failures & Anti-Patterns (DO NOT REPEAT)
     - Previous failure: <reason>.
     - Mandate: <governing mandate derived from breached invariant>.
     ```
   - Known invariants are mapped deterministically to explicit prohibitions (e.g., ADR-0003 maps to `"You must strictly use public frontdoor entrypoints with zero mock backdoors"`).
   - Autonomous agents are explicitly commanded not to repeat previous dead-end approaches.

4. **Performance & Round-Trip Latency Benchmark**:
   - The spike benchmark verifies that frontmatter deserialization, post-mortem appending, and serialization execute in under 15ms per cycle (measured average ~10ms), introducing negligible overhead to worktree lifecycle operations.

## Consequences
- **Positive**: Eliminates circular dead-ends where agents repeat failed patterns; turns discarded agent work into actionable, version-controlled institutional knowledge; maintains pure PMaC without out-of-band databases or sidecar state.
- **Negative**: Task specification frontmatter length increases monotonically with repeated failures; requires careful regex/YAML parsing to avoid formatting degradation across multi-iteration resets.
