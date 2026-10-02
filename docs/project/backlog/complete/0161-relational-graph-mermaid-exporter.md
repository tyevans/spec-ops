---
id: '0161'
title: Relational Knowledge Graph Subgraph Export and Interactive Diagram Generator
status: Complete
dependencies:
- TASK-0087
- TASK-0133
governing_adrs:
- ADR-0001
- ADR-0002
- ADR-0003
- ADR-0011
- ADR-0015
governing_prds:
- PRD-0005
governing_stories:
- US-0101
target_bc: core
signed_off_by: Ty Evans <tyler@poorlythoughtout.com>
signed_off_at: '2026-10-02T00:37:03.376068+00:00'
commit_signature_status: SIGNED
has_signed_commits: true
---

# TASK-0161: Relational Knowledge Graph Subgraph Export and Interactive Diagram Generator

## Summary
Implement a relational knowledge graph subgraph exporter and Mermaid/Graphviz diagram generator (`src/spec_ops/graph/mermaid_export.py`). Governed by ADR-0011 and PRD-0005, this engine queries the redstring relational knowledge graph and projects targeted subgraphs into syntax-valid Mermaid flowcharts and Graphviz DOT formats for documentation embedding (`spec-ops graph mermaid`).

## Problem Statement & Context
While the web visualizer provides rich interactive 2D graph exploration, engineering architects frequently need static, embeddable graph diagrams directly in Markdown documentation, PR descriptions, and architectural decision records. A CLI diagram generator enables seamless export of focused dependency subgraphs without manual diagramming.

## Key Requirements & Scope
1. **Subgraph Diagram Generator (`src/spec_ops/graph/mermaid_export.py`)**:
   - Queries redstring knowledge graph by root node (e.g. PRD-0001, TASK-0150, ADR-0005) and traversal depth.
   - Extracts nodes (PRDs, Stories, Tasks, ADRs) and directed edges (governs, implements, depends_on).
   - Formats subgraphs into Mermaid flowchart syntax (`graph TD` / `flowchart LR`) with node styling and links.
   - Supports Graphviz DOT format output via `--format dot`.
2. **Diagram CLI (`spec-ops graph mermaid [--root <entity_id>] [--depth <N>] [--format mermaid|dot] [--output <path>]`)**:
   - Generates and writes diagram content to stdout or target file.
3. **Blackbox Frontdoor Verification**:
   - 100% test pass rate verifying public CLI interface and diagram syntax validity.

## Architectural Invariants & Seams
- **File Length Limit (<500 lines)**: Module in `src/spec_ops/graph/mermaid_export.py` must stay strictly under 400 lines (ADR-0002).
- **Relational Knowledge Graph (ADR-0011)**: Leverages redstring graph abstractions without reaching into raw file system parsing.
- **Mutation Testing Scope**: Target module `src/spec_ops/graph/mermaid_export.py` with target >=80% mutant kill score (ADR-0009).

## Acceptance Criteria

### Scenario 1: Generating Mermaid flowchart for a task lineage
```gherkin
Given a relational knowledge graph with linked tasks and stories
When the developer exports a Mermaid diagram rooted at a specific task
Then valid Mermaid flowchart syntax is generated
And the output contains the task node, its governing story, and dependencies
```

### Scenario 2: Traversal depth limiting
```gherkin
Given a deep dependency graph across PRDs and tasks
When the developer exports diagram with depth limit of 1
Then only immediate adjacent neighbors are included in the emitted diagram
```

## Hypothesis Invariant Properties

- `@given(...)`: Generative property tests asserting that for any arbitrary directed graph input, the generated Mermaid string contains no unescaped bracket characters or syntax syntax errors.
