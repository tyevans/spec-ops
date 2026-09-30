# How-To: Diagnose and Self-Heal Backlog Health

This guide explains how to audit and automatically resolve structural backlog drift, broken dependency references, ghost index entries, and unindexed task files using `spec-ops queue doctor`.

---

## Auditing Backlog Defects

As autonomous agents and human developers create, complete, and branch tasks across git worktrees, structural drift can occur. To run a proactive diagnostic health audit across `docs/project/backlog/`:

```bash
uv run spec-ops queue doctor
```

*(Note: `spec-ops backlog doctor` is also supported as an alias.)*

### Defects Detected by Doctor

1. **Broken & Dangling Dependencies**: Tasks declaring dependencies in frontmatter (`dependencies: [...]`) that do not exist anywhere on disk in `complete/`, `refined/`, or `proposed/`. The exact file and line number are reported.
2. **Ghost Index References**: Entries in `PRIORITY.md` pointing to tasks or file paths that have been deleted or moved.
3. **Unindexed Task Files**: Task files present on disk in `complete/`, `refined/`, or `proposed/` that are omitted from `PRIORITY.md`.
4. **Status & Folder Drift**: Discrepancies between a task's disk folder (e.g. `refined/` vs `proposed/`) and its entry in `PRIORITY.md`.
5. **Broken Relative Links**: Markdown links between backlog documents that point to non-existent target files.

---

## Automated Self-Healing Repair

To automatically repair detected discrepancies in-place:

```bash
uv run spec-ops queue doctor --fix
```

*(Note: `--repair` is also accepted as an alias for `--fix`.)*

### Repair Actions Performed

- **Clean Dangling Dependencies**: Atomically removes non-existent task IDs from frontmatter `dependencies` in task files while preserving valid dependencies, titles, and body content.
- **Clean Ghost Entries**: Strips deleted task references from `PRIORITY.md`.
- **Append Unindexed Tasks**: Deterministically indexes orphan task files at the end of `PRIORITY.md` sorted by task number under their corresponding status.
- **Synchronize Status Drift**: Updates `PRIORITY.md` status tags and folder paths to reflect disk reality.

---

## Machine-Readable JSON Telemetry

For CI pipelines and automated preflight scripts, the doctor supports structured JSON output:

```bash
uv run spec-ops queue doctor --json
```

Output format:

```json
{
  "is_healthy": true,
  "issues_count": 0,
  "remediated_count": 0,
  "remediations": [],
  "defects": []
}
```
