# How-To: Audit PRD Outcomes and Trace Persona Coverage

This guide explains how to continuously audit checkable outcome coverage in accepted PRDs, inspect persona-to-commit traceability, and resolve stakeholder queries using permalinks.

---

## 1. Deep PRD Outcome Coverage Audit

To prevent specification drift, SpecOps verifies that 100% of checkable outcomes in accepted PRDs are backed by executable BDD user stories and implementing backlog tasks.

Run deep outcome auditing across all accepted PRDs:

```bash
uv run spec-ops prd audit --deep
```

To audit a specific PRD:

```bash
uv run spec-ops prd audit PRD-0001 --deep
```

### What the Audit Detects
- **Checkable Outcomes**: Discovers all bulleted/checkable outcome statements in accepted PRD specifications.
- **Orphaned Outcomes**: Flags outcomes lacking an implementing user story or backlog task, exiting with code 1.
- **Unanchored Backlog Tasks**: Flags backlog tasks citing a PRD without implementing any defined outcome.

---

## 2. Persona Coverage & Neglect Detection

SpecOps tracks customer personas defined in `docs/project/user_stories/PERSONAS.md` and audits the distribution of active backlog tasks and stories across personas:

```bash
uv run spec-ops stats --persona-coverage
```

### Output Insights
- **Active Task & Story Counts**: Counts backlog tasks in `refined/` or `proposed/` associated with each persona.
- **Neglected Persona Warnings**: Proactively warns when a documented persona has zero active work items in the current milestone.
- **Orphan Tasks**: Flags tasks that are not mapped to any recognized customer persona.

---

## 3. Interactive Lineage Matrix & Permalinks

In the SpecOps interactive visualizer:
1. Navigate to the **Matrix** tab.
2. Filter by a customer persona to view the multi-column lineage view:
   `Persona -> PRD -> User Story -> Backlog Task -> Git Commit -> Status`.
3. Click **🔗 Copy Shareable Link** to generate a direct permalink:
   ```text
   #tab=prds&entity=PRD-0001&filter=FEAT-ID
   ```
