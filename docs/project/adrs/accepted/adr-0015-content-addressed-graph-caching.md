# ADR-0015: Content-Addressed SHA-256 Relational Graph Caching and Resilient AST Parsing

## Status
Accepted

## Context
As SpecOps repositories expand to hundreds or thousands of user stories, tasks, PRDs, and ADRs, full filesystem re-scanning and naive markdown re-parsing on every CLI invocation degrades interactive CLI latency and CI preflight performance. Furthermore, malformed YAML frontmatter (such as unquoted colons, invalid indentation, or missing delimiters) can cause unhandled parser crashes or catastrophic context drops during autonomous agent execution. SpecOps requires a verified content-addressed caching architecture and resilient AST error handling to achieve sub-50ms graph compilation and deterministic developer diagnostics.

## Decision
We prototype and recommend adopting content-addressed SHA-256 graph caching and resilient AST parsing:

1. **Content-Addressed Cache Payload**:
   - Cache artifact stored at `.specops/cache/graph.json` containing SHA-256 content hashes, serialized entity models, dependency links, and global traceability edges.
   - Cache payload integrity verified via a SHA-256 checksum computed across entities and edges.
   - Corrupted or truncated cache payloads are automatically detected, logged with an actionable warning, and discarded in favor of a clean cold rebuild.

2. **Downstream Dependency Invalidation**:
   - Single-file edits are detected via SHA-256 hash deltas.
   - Invalidation is strictly bounded to the mutated node and its immediate downstream dependents in the cached dependency tree.
   - All unchanged entities are retrieved directly from cache, avoiding disk I/O and markdown re-parsing.

3. **Resilient AST Parsing with Precision Diagnostics**:
   - Markdown parser extracts frontmatter and body AST, preserving custom HTML comments, tables, and fenced code blocks verbatim.
   - Missing frontmatter delimiters (`---`) emit clear diagnostic hints recommending `spec-ops scaffold task`.
   - Malformed YAML indentation and syntax errors produce compiler-grade diagnostic spans highlighting precise line, column, and caret indicators without throwing unhandled exceptions.

## Recommended Cache Schema
```json
{
  "version": 1,
  "checksum": "sha256-hex-digest",
  "entities": {
    "docs/project/backlog/refined/0042-new-api.md": {
      "rel_path": "docs/project/backlog/refined/0042-new-api.md",
      "sha256": "3a7b...",
      "entity_type": "task",
      "canonical_id": "TASK-0042",
      "data": { ... },
      "dependencies": ["TASK-0001"],
      "dependents": ["TASK-0043"]
    }
  },
  "edges": [
    {
      "source_type": "task",
      "source_id": "TASK-0042",
      "target_type": "task",
      "target_id": "TASK-0001",
      "relation": "depends_on"
    }
  ]
}
```

## Empirical Benchmark Findings
- **Synthetic Graph Size**: 1,000 specification documents (50 PRDs, 50 ADRs, 200 User Stories, 699 Tasks, 1 Persona file).
- **Cold Compilation Time**: ~0.19 seconds (Target: < 1.20s).
- **Warm Incremental Compilation Time**: ~36 milliseconds (Target: < 45ms).
- **Single-File Edit Invalidation**: Verified 1 file invalidated, 999 cache hits.
- **Corrupted Cache Recovery**: Self-healing clean cold rebuild in < 0.20s with exit code 0.

## Consequences
- **Positive**: Sub-50ms CLI responsiveness; instant developer feedback on YAML typos with rustc/elm-style diagnostic error spans; zero unhandled parser crashes during autonomous agent cycles.
- **Negative**: Requires maintaining cache invalidation correctness and dependency tracking across complex multi-entity relationships.
