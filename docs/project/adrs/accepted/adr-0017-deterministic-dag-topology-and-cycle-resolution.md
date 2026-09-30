# ADR-0017: Deterministic DAG Topology, Tarjan SCC Cycle Resolution, and Blast-Radius Traversal

## Status
Accepted

## Context
As project backlogs, product requirement documents (PRDs), user stories, and architectural decision records (ADRs) grow in size and interdependency, circular dependency deadlocks inevitably arise (e.g. Task A depends on Task B, which transitively depends on Task A, or circular implementation references between PRDs and User Stories).

Standard topological sorting algorithms (such as naive Kahn's algorithm or recursive post-order DFS) fail catastrophically when encountering cycles:
1. **Dispatcher Paralysis**: Incomplete in-degree decrementing leaves circular nodes unprocessed, freezing autonomous worker dispatchers and queue schedulers in infinite loops.
2. **Opaque Diagnostics**: Naive cycle detection indicates that a cycle exists somewhere in the graph, but fails to pinpoint the exact path or actionable feedback edge to break the cycle.
3. **Global Blockage**: A single cyclic loop in an isolated component unnecessarily blocks unrelated, perfectly valid task clusters across the rest of the repository.
4. **Performance at Scale**: Large enterprise backlogs (>1,000 to 5,000 nodes) require sub-15ms cycle detection and sub-5ms blast radius calculation during interactive CLI queries (`spec-ops graph order`, `spec-ops graph inspect`, `spec-ops graph blast-radius`).

## Decision
We prototype and recommend adopting Tarjan's Strongly Connected Components (SCC) algorithm, condensation DAG topological tiering, and breadth-first blast radius traversal:

1. **Tarjan's Strongly Connected Components (SCC) Core**:
   - Single-pass iterative Depth-First Search with $O(V + E)$ time and space complexity.
   - Computes discovery `index` and `lowlink` values to partition the digraph into disjoint maximal strongly connected components.
   - Any SCC with $|C| > 1$ or any single node with a self-loop ($(u, u) \in E$) is identified as a cyclic component.

2. **Deterministic Cycle Path Tracebacks and Remediation**:
   - For every cyclic component, breadth-first traversal extracts the shortest elementary directed cycle starting at the lexicographically lowest node.
   - Formats a human-readable cycle string: e.g. `TASK-0010 -> TASK-0011 -> TASK-0012 -> TASK-0010`.
   - Identifies the feedback edge $(u, v)$ and emits an explicit remediation directive: `Break cycle by removing dependency from TASK-0012 to TASK-0010`.

3. **Deadlock Quarantine and Topological Execution Tiers**:
   - Cyclic SCCs and all downstream nodes transitively dependent upon them are quarantined into a deadlock partition.
   - Independent acyclic components are scheduled into deterministic execution tiers ($0, 1, 2, \dots$) where a node's depth is strictly $1 + \max_{(u, v) \in E} d(v)$.
   - Critical path depth is calculated as $\max_{u} d(u)$.

4. **Transitive Blast-Radius Traversal**:
   - Calculates upstream lineage and downstream dependent transitive closures in $<5\text{ms}$ on graphs up to 1,000 nodes.
   - Classifies blast radius impact into `LOW` ($\le 4$ nodes), `MEDIUM` ($5 \dots 10$ nodes), and `HIGH` ($> 10$ nodes).

## Mathematical Formalization & Proofs

### Definition 1: Directed Dependency Graph
Let $G = (V, E)$ be a directed graph where $V$ represents specification entities (tasks, PRDs, stories, ADRs) and directed edge $(u, v) \in E$ denotes that entity $u$ depends on or is governed by entity $v$.

### Definition 2: Strongly Connected Component (SCC)
A strongly connected component of $G$ is an equivalence class under the mutual reachability relation $\sim$:
$$u \sim v \iff (u \rightsquigarrow v) \land (v \rightsquigarrow u)$$
where $u \rightsquigarrow v$ denotes the existence of a directed path from $u$ to $v$. An SCC $C \subseteq V$ is maximal with respect to inclusion.

### Theorem 1 (Cycle Equivalence)
*A directed graph $G = (V, E)$ contains at least one directed cycle if and only if there exists an SCC $C \in \text{SCC}(G)$ such that $|C| > 1$ or ($|C| = 1$ and $(u, u) \in E$ for $u \in C$).*

**Proof:**
- $(\implies)$ Suppose $G$ contains a directed cycle $\gamma = (v_1, v_2, \dots, v_k, v_1)$ with $k \ge 1$.
  - If $k = 1$, then $(v_1, v_1) \in E$ is a self-loop. Its containing SCC is $C = \{v_1\}$, which has $|C| = 1$ and $(v_1, v_1) \in E$.
  - If $k > 1$, then for any $v_i, v_j$ on $\gamma$, the subpath $v_i \rightsquigarrow v_j$ along $\gamma$ and $v_j \rightsquigarrow v_i$ along $\gamma$ establish mutual reachability ($v_i \sim v_j$). By maximality of SCCs, the entire set $\{v_1, \dots, v_k\} \subseteq C$ for some SCC $C$. Thus $|C| \ge k > 1$.
- $(\impliedby)$ If $|C| = 1$ and $(u, u) \in E$, $(u, u)$ is directly a cycle of length 1. If $|C| > 1$, choose distinct vertices $u, v \in C$. Since $u \sim v$, there exists a path $p_1: u \rightsquigarrow v$ and a path $p_2: v \rightsquigarrow u$. Concatenating $p_1$ and $p_2$ forms a closed directed walk from $u$ to $u$, which contains at least one simple directed cycle of length $\ge 2$. $\blacksquare$

### Theorem 2 (Condensation Graph Acyclicity)
*Let $G_{SCC} = (V_{SCC}, E_{SCC})$ be the condensation graph whose vertices $V_{SCC}$ are the SCCs of $G$, and $(C_i, C_j) \in E_{SCC} \iff \exists u \in C_i, v \in C_j \text{ s.t. } (u, v) \in E \text{ with } C_i \neq C_j$. Then $G_{SCC}$ is strictly an acyclic directed graph (DAG).*

**Proof:**
Assume for contradiction that $G_{SCC}$ contains a directed cycle $C_1 \to C_2 \to \dots \to C_m \to C_1$ with $m \ge 2$. Then there exist edges between components establishing paths $C_1 \rightsquigarrow C_j$ and $C_j \rightsquigarrow C_1$ for all $j \in \{1, \dots, m\}$. For any $u \in C_1$ and $w \in C_j$, internal reachability within each SCC combined with the inter-component edges establishes $u \rightsquigarrow w$ and $w \rightsquigarrow u$. Consequently, $\bigcup_{i=1}^m C_i$ is mutually reachable, contradicting the maximality of each individual component $C_i$. Hence, $G_{SCC}$ contains no cycles and is strictly a DAG. $\blacksquare$

### Theorem 3 (Topological Tiering Monotonicity)
*For any finite DAG $D = (V, E)$, the tier depth function:*
$$d(u) = \begin{cases} 0 & \text{if } \text{Out}(u) = \emptyset \\ 1 + \max_{v \in \text{Out}(u)} d(v) & \text{otherwise} \end{cases}$$
*is unique, well-defined, finite, and satisfies $d(u) > d(v)$ for all $(u, v) \in E$.*

**Proof:**
Since $D$ is a finite DAG, every directed path has length at most $|V| - 1$. The function $d(u)$ equals the length of the longest directed path starting at $u$. For any edge $(u, v) \in E$, any path of length $L$ starting at $v$ can be extended to a path $(u, v) \circ p$ of length $L + 1$ starting at $u$. Thus $\max_{w \in \text{Out}(u)} d(w) \ge d(v)$, implying $d(u) = 1 + \max_{w \in \text{Out}(u)} d(w) \ge 1 + d(v) > d(v)$. $\blacksquare$

## Algorithmic Trade-offs & Comparisons

| Dimension | Tarjan's SCC Algorithm | Kahn's Algorithm | Johnson's Elementary Cycles |
|---|---|---|---|
| **Time Complexity** | $\mathcal{O}(V + E)$ | $\mathcal{O}(V + E)$ | $\mathcal{O}((V + E)(c + 1))$ |
| **Space Complexity** | $\mathcal{O}(V)$ | $\mathcal{O}(V)$ | $\mathcal{O}(V + E)$ |
| **Cycle Presence Check** | Instantaneous ($\exists \|C\| > 1$ or self-loop) | Instantaneous ($\|order\| < \|V\|$) | Exhaustive |
| **Cycle Path Extraction** | Linear BFS per cyclic SCC | Requires secondary DFS search | Native exhaustive enumeration |
| **Worst-Case Scalability** | Linear up to millions of nodes | Linear up to millions of nodes | Exponential blowup on dense graphs |
| **Quarantine Isolation** | Natural condensation partition | Fails to separate disjoint cycles | High overhead |
| **Feedback Edge Pinpointing** | Direct elementary path back-edge | Not supported natively | Redundant overlapping cycles |

**Evaluation Summary**:
- **Kahn's Algorithm** is ideal as a fast acyclicity validator, but completely fails when cycles are present because all nodes in cycles and downstream of cycles simply stall with non-zero in-degrees.
- **Johnson's Algorithm** is computationally prohibitive for autonomous agent dispatchers; on interconnected graphs with dense feedback paths, the number of elementary cycles $c$ grows super-exponentially ($\mathcal{O}(n!)$), causing CLI freezes.
- **Tarjan's SCC Algorithm** provides the optimal balance: strict linear $\mathcal{O}(V + E)$ runtime, deterministic component partitioning, complete cycle isolation, and minimal BFS extraction of feedback edges.

## Empirical Benchmark Findings

Benchmarks executed via `benchmark_topology_spike(num_nodes=5000, num_cycles=10)`:
- **Synthetic Graph Size**: 5,000 nodes, 4,999 backbone edges, 10 injected circular loops.
- **Tarjan SCC Detection Time**: ~7.26 milliseconds (Target: $< 15\text{ms}$).
- **Cycle Detection Accuracy**: 10/10 injected circular loops detected (100%).
- **Kahn's Algorithm Detection Time**: ~1.75 milliseconds (presence verification only).
- **Blast Radius Calculation Time**: ~3.57 milliseconds on 1,000-node graph (Target: $< 5\text{ms}$).

## Consequences
- **Positive**:
  - Deterministic execution tiers prevent queue deadlocks in autonomous dispatchers.
  - Actionable cycle remediation strings (`Break cycle by removing dependency from X to Y`) guide human developers and AI agents to instantly resolve deadlocks.
  - Sub-15ms performance at 5,000 nodes guarantees snappy CLI and CI responsiveness.
- **Negative**:
  - Requires maintaining in-memory reverse adjacency lists for sub-5ms blast-radius calculations.
