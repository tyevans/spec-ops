# How-To: Generate Architectural Review Briefs and Conventional Commit Slices

This guide covers generating context-enriched architectural review briefs and standardizing RFC-822 git trailers on task commits.

---

## Generating an Architectural Review Brief

When an autonomous worker or human contributor finishes a task branch, SpecOps generates a structured review brief that provides full architectural context before merging:

```bash
spec-ops review TASK-0048
```

The review brief aggregates:
1. **Governing Artifacts**: Linked user stories, target bounded context, and governing ADRs cited in task frontmatter.
2. **Changed Files & Bounded Contexts**: Breakdown of modified source, test, and documentation files mapped to their architectural modules.
3. **Conventional Commit Message**: Formatted conventional commit subject with structured RFC-822 git trailers.
4. **Invariant Compliance**: File length limit checks, property test validation status, and mutation kill score.

To include full git commit log history and author provenance:

```bash
spec-ops review TASK-0048 --provenance
```

---

## Conventional Commit Slicing & RFC-822 Trailers

All task integration commits follow the Conventional Commits specification with standardized RFC-822 git trailers:

```text
feat(task-0048): Conventional Commit Slicing, Standardized RFC-822 Git Trailers, and Lineage Review Brief

Task-ID: TASK-0048
SpecOps-Task: TASK-0048
SpecOps-Story: US-0084, US-0036
Governing-ADRs: ADR-0001, ADR-0002, ADR-0003, ADR-0005, ADR-0007, ADR-0009
Provenance: spec-ops autonomous worker
```

### Deriving Conventional Types

The conventional commit type is automatically derived based on target bounded contexts and file changes:
- `feat`: New capabilities or user stories.
- `fix`: Bug fixes, rescue patches, or test repairs.
- `docs`: Pure documentation changes under `docs/`.
- `spike`: Architectural spikes under `docs/project/spikes/`.
- `chore`: Scaffolding, dependency bumps, or toolchain updates.

---

## Signing Cryptographic Task Reviews

To record a dual-custody cryptographic review sign-off for a completed task:

```bash
spec-ops review sign TASK-0048 --identity "alex@example.com"
```

This updates the task's frontmatter and records an entry in the repository dual-custody audit log (`.spec-ops/dual-custody.json`), ensuring traceable, tamper-evident sign-offs across human leads and autonomous agents.
