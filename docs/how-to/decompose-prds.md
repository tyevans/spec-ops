# How-To: Decompose PRDs and Curate the Backlog

This guide explains how to break high-level PRD documents into thin vertical slices and maintain a healthy backlog buffer.

---

## Decomposing a PRD into Vertical Slices

When a PRD is approved in `docs/project/product/accepted/`, decompose it into vertical slices:

```bash
spec-ops prd decompose PRD-0001
```

This:
1. Inspects checkable outcomes and user stories in the PRD.
2. Emits granular vertical slice tasks into `docs/project/backlog/proposed/`.
3. Emits an initial architectural spike task (unless `--no-spike` is provided).
4. Links the newly created tasks in the PRD frontmatter.

---

## Decomposing by Checkable Outcomes (BDD Scenario Slices)

To decompose each discrete outcome under `## Checkable Outcomes` into a dedicated BDD user story with an executable Gherkin skeleton:

```bash
spec-ops prd decompose PRD-0001 --by-outcomes
```

This:
1. Parses every checkable outcome under `## Checkable Outcomes`.
2. Validates falsifiability heuristics (rejecting subjective or non-falsifiable language with exit code 1).
3. Synthesizes a dedicated BDD user story file under `docs/project/user_stories/accepted/us-XXXX-*.md` with an executable Gherkin skeleton.
4. Generates implementing vertical slice tasks in `docs/project/backlog/proposed/` linked to each story and outcome ID.
5. Updates `## Linked User Stories` and `## Implementing Backlog Tasks` in the PRD and appends tasks to `PRIORITY.md`.

---

## Incremental Delta Scope Evolution (`--diff`)

As product scope evolves over time, running decomposition again must not overwrite active worktrees or destroy git commit provenance:

```bash
spec-ops prd decompose PRD-0001 --diff
```

This:
1. Compares current PRD checkable outcomes against existing user stories and backlog tasks.
2. Detects newly added outcomes and synthesizes only the targeted delta stories and proposed tasks.
3. Preserves existing completed (`docs/project/backlog/complete/`) and refined (`docs/project/backlog/refined/`) tasks byte-identically in git.
4. Appends newly created delta tasks to `PRIORITY.md` without reordering or modifying existing queue entries.
5. Emits real-time warnings if an outcome was removed but has active pending tasks in `proposed/` or `refined/`.

---

## Replenishing the Refined Buffer Just-in-Time

To promote unblocked proposed tasks and maintain an optimal ready buffer:

```bash
spec-ops curate
```

### Cognitive Inference-Driven Refinement

To critically audit candidate tasks against living repository reality, reconcile architectural drift across superseded ADRs and refactored modules, slice oversized tasks (>500 lines) into thin vertical slices, and synthesize Definition of Ready (DoR) acceptance criteria:

```bash
# Preview proposed reconciliations and decompositions without modifying disk state
spec-ops curate --infer --dry-run

# Execute cognitive curation and replenishment
spec-ops curate --infer
```

