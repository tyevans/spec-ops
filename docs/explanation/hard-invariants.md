# Explanation: Hard Invariants and Anti-Rot

Why does SpecOps enforce strict invariants like the <500 lines file length limit?

---

## The LLM Monolithic Decay Trap

Large Language Models (LLMs) operate within token and attention constraints. When files grow beyond 500 lines:
1. **Context Truncation**: Agents spend excessive tokens reading irrelevant helper functions instead of core logic.
2. **Hallucinated Edits**: Patching large monolithic files frequently leads to misaligned line replacements and syntax errors.
3. **Loss of Modularity**: High-coupling spaghetti code emerges when developers and agents take the path of least resistance by appending functions to existing files.

---

## Architectural Enforcement

By enforcing `<500 lines per file` as a hard invariant in `spec-ops health`:
- Contributors and agents are forced to decompose code into cohesive, single-responsibility modules.
- Codebases remain modular, easily testable, and friendly to autonomous AI coding agents indefinitely.
