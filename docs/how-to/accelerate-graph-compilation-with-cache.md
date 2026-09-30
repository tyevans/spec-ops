# How-To: Accelerate Graph Compilation with Content-Addressed Caching

This guide demonstrates using content-addressed SHA-256 caching and resilient markdown parsing to achieve sub-50ms graph compilation in large SpecOps repositories.

---

## Compiling Relational Graphs with Cache Acceleration

To compile the repository specification graph using content-addressed caching:

```bash
spec-ops stats --cache
```

### Cold Compilation

When no cache artifact exists in `.specops/cache/graph.json` or when force-rebuilding:

```text
Graph compiled in cold state: 250 entities indexed, cache written
=== SpecOps Project Statistics (SpecOps) ===
Total Tasks: 250 (100 Complete, 50 Refined, 100 Proposed)
User Stories: 40 | PRDs: 15 | ADRs: 12 | Personas: 6
Traceability Edges: 480 | Ready Buffer Health: OPTIMAL
```

### Incremental Compilation

When editing a single specification document, SpecOps compares SHA-256 content hashes, invalidates only the modified entity and its immediate downstream dependents in the dependency graph, and re-links traceability in milliseconds:

```text
Incremental graph sync: 1 file invalidated, 249 cache hits
=== SpecOps Project Statistics (SpecOps) ===
...
```

---

## Parsing Specification Markdown with Resilient Diagnostics

To validate and inspect a markdown specification file:

```bash
spec-ops parse docs/project/backlog/refined/0042-sample.md
```

### Handling Missing Frontmatter Delimiters

If a file omits the opening YAML frontmatter delimiter `---`, SpecOps provides actionable scaffolding guidance:

```text
Missing Frontmatter: File does not start with standard YAML '---' delimiter
Run 'spec-ops scaffold task' to generate a valid frontmatter template
```

### Compiler-Grade Diagnostic Error Spans

When malformed YAML or invalid indentation occurs, SpecOps pinpoints the exact line and column with an interactive diagnostic caret rather than throwing unhandled parser exceptions:

```text
error: Frontmatter YAML Syntax Error in docs/project/backlog/proposed/0051-bad-yaml.md:4:3
|
4 |   dependencies: [TASK-0001]
|   ^ unexpected mapping indentation
```

---

## Automatic Cache Self-Healing

If the `.specops/cache/graph.json` payload is corrupted or fails its cryptographic checksum, the graph compiler logs a warning, falls back to a clean cold parse from disk, and rewrites a verified cache payload without crashing.
