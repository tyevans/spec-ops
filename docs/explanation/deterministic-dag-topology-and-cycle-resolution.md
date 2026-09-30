# Deterministic DAG Topology, Tarjan SCC Cycle Resolution, and Blast Radius

This document explains the mathematical foundations and design decisions behind dependency cycle resolution, topological sorting tiers, and blast-radius traversal in SpecOps.

---

## The Circular Dependency Trap in Autonomous Workflows

In a version-locked Project Management as Code (PMaC) repository, entity graphs grow rapidly across Personas, PRDs, User Stories, Backlog Tasks, and ADRs. In complex multi-agent repositories, circular dependencies inevitably arise:
- Task A depends on Task B, which transitively depends on Task A.
- Cross-specification loops occur between PRDs and User Stories.

Standard topological sorting (such as naive Kahn's algorithm or simple post-order DFS) fails when encountering circular references:
- **Dispatcher Deadlocks**: Decrementing in-degrees stalls before processing all nodes, trapping autonomous queue workers in infinite loops.
- **Opaque Errors**: Naive cycle detection indicates that a cycle exists somewhere in the graph, but cannot locate the cycle path or provide actionable remediation.
- **Global Paralysis**: A single cyclic cluster in one subsystem unnecessarily blocks independent, valid tasks across the rest of the project.

---

## Tarjan's Strongly Connected Components (SCC) Core

SpecOps resolves dependency topologies using Tarjan's Strongly Connected Components algorithm:

1. **Linear Time Complexity**: Executes in strict $\mathcal{O}(V + E)$ time and space via a single-pass iterative Depth-First Search.
2. **Cycle Equivalence**: A component $C \subseteq V$ represents a cycle if and only if $|C| > 1$ or contains a self-loop $(u, u) \in E$.
3. **Deadlock Quarantine**: Cyclic SCCs and their downstream transitive dependents are isolated into a quarantined deadlock partition, while independent acyclic components proceed with execution without interruption.

---

## Deterministic Cycle Extraction & Feedback Remediation

For every identified cyclic SCC:
1. Breadth-first search traverses the subgraph to extract the shortest elementary directed cycle starting at the lexicographically lowest entity ID.
2. The engine generates a cycle path trace:
   ```
   TASK-0010 -> TASK-0011 -> TASK-0012 -> TASK-0010
   ```
3. An explicit remediation directive identifies the feedback back-edge to break the circular dependency:
   ```
   Remediation: Break cycle by removing dependency from TASK-0012 to TASK-0010.
   ```

---

## Condensation DAGs and Execution Tiers

By collapsing each strongly connected component into a single composite vertex, the resulting condensation graph $G_{SCC}$ is mathematically guaranteed to be a Directed Acyclic Graph (DAG).

Acyclic tasks are scheduled into monotonic execution tiers:
$$d(u) = \begin{cases} 0 & \text{if } \text{Out}(u) = \emptyset \\ 1 + \max_{v \in \text{Out}(u)} d(v) & \text{otherwise} \end{cases}$$

This guarantees that:
- Tier 0 tasks have zero unmet dependencies and can be claimed immediately by autonomous workers.
- Upstream prerequisites strictly execute in earlier tiers than downstream dependents.
- Dispatchers can partition tasks into parallel execution waves with zero deadlock risk.

---

## Transitive Blast-Radius Traversal

When modifying foundational architectural decisions (e.g. ADR-0002) or refactoring core components, developers and agents need to evaluate the blast radius of changes.

Breadth-first transitive traversal computes the downstream impact in $<5\text{ms}$ on graphs up to 1,000 nodes, categorizing impact into:
- **LOW**: $\le 4$ downstream entities affected.
- **MEDIUM**: $5 \dots 10$ downstream entities affected.
- **HIGH**: $> 10$ downstream entities affected.

This powers real-time warnings during PR reviews and prevents accidental breaking changes to shared specifications.
