# How-To: Audit Bidirectional Traceability and Contributor Provenance

This guide explains how to audit unbroken traceability from personas down to merged commits and attribute velocity between autonomous coding agents and human developers using `spec-ops audit provenance`.

---

## 1. Traceability Audit Overview

In hybrid engineering teams where autonomous agents and human developers commit concurrently, changes can become disconnected from governing specifications. SpecOps continuously audits git history and project specifications to verify that every commit is anchored to an accepted task, story, and persona.

Run the traceability audit across the repository:

```bash
uv run spec-ops audit provenance
```

*(Note: `spec-ops audit traceability` is supported as an alias).*

### What the Audit Inspects
- **Commit Trailers**: Scans commits for `SpecOps-Task: TASK-XXXX` or `Task-ID: TASK-XXXX` trailers in git commit bodies.
- **Unanchored Commits**: Warns about any commit lacking recognized task trailers.
- **Orphaned Tasks**: Warns about tasks in `docs/project/backlog/complete/` that have no corresponding commit trailers.
- **Lineage Verification**: Traces each task back to its governing user story, PRD, and customer persona.
- **Traceability Integrity Metric**: Calculates overall traceability percentage:
  ```text
  Traceability Integrity: 100% (0 unanchored commits, 0 orphaned stories)
  ```

---

## 2. Enforcing Strict CI Gates

To prevent unanchored commits or orphaned tasks from landing in production, run the provenance audit with `--strict` in CI:

```bash
uv run spec-ops audit provenance --strict
```

In `--strict` mode:
- If any commit lacks a valid `SpecOps-Task` or `Task-ID` trailer, the command exits with code `1`.
- If any commit references a task file that does not exist in `docs/project/backlog/`, the command exits with code `1`.
- If any completed task lacks delivery provenance commits, the command exits with code `1`.

---

## 3. Contributor Provenance Attribution

SpecOps distinguishes between autonomous agents and human contributors by inspecting git signatures and commit trailers such as:

```text
Provenance: spec-ops autonomous worker
```

To view a breakdown of tasks delivered, commits merged, and verification pass rates:

```bash
uv run spec-ops audit provenance --contributions
```

### Example Breakdown

```text
| Contributor Class   | Tasks Delivered | Merged Commits | Verification Pass Rate |
| Autonomous Agents   | 14              | 28             | 93.3%                  |
| Human Developers    | 9               | 15             | 100.0%                 |
```

---

## 4. Visualizing Contributor Provenance in the Living Matrix

When generating the living 2D visualizer (`uv run spec-ops docs build`):
1. Navigate to the **Matrix** tab.
2. Contributor filter chips (**All**, **Autonomous Agents**, **Human Developers**) allow filtering the traceability grid dynamically.
3. Each commit badge displays its contributor provenance type and links directly to commit metadata.
