# Baseline Architectural Decision Records (ADRs)

SpecOps bundles 7 foundational ADRs organized across architectural profiles.

---

## Profile: `core`

- **ADR-0001: Specification as Code (PMaC)**: All personas, stories, PRDs, tasks, and decisions live in git as Markdown with YAML frontmatter.
- **ADR-0002: Modular File Length Limits (<500 lines)**: Keeps source files small to eliminate LLM context truncation and decay.
- **ADR-0003: Blackbox Frontdoor Verification**: Feature development driven through public interfaces without private backdoor mutation.
- **ADR-0004: Continuous Preflight & Self-Healing CI**: Enforces health checks before remote push with retry loops on failures.
- **ADR-0005: Worktree Concurrency & Backlog Isolation**: Isolated git worktrees prevent multi-agent merge conflicts on shared index files.
- **ADR-0008: Agent Constitution & Diataxis Documentation Standards**: Machine-executable constitutional rules in AGENTS.md and four-quadrant Diataxis documentation structure.
- **ADR-0009: Property-Based & Mutation Testing with Hypothesis and Mutmut**: Generative property verification for state spaces and minimum 80% mutation kill score.

---

## Profile: `bdd`

- **ADR-0006: BDD Gherkin User Stories & Playwright E2E**: User stories written as executable Gherkin scenarios verified through browser automation.

---

## Profile: `ddd`

- **ADR-0007: Domain-Driven Design & Bounded Contexts**: Code organized by business domains with strict state encapsulation.
- **ADR-0021: Application Orchestration Layer and Dependency Inversion Boundaries**: Application service orchestration layer (`spec_ops.app`) at Layer 4, downward foundation relocation, and dependency inversion for projections and introspection.

---

## Profile: `security`

- **ADR-0010: Zero-Trust Security Invariants and Autonomous Agent Guardrails**: Machine-executable security guardrails in AGENTS.md, docs/project/SECURITY.md vulnerability disclosure, and health auditing.
- **ADR-0011: Supply Chain and Lockfile Integrity Defenses**: Strict lockfile verification, prohibited ad-hoc package installations, and dependency vulnerability scanning.
- **ADR-0012: Sandboxed Worker Execution and Non-Allowlisted Command Interception**: Execution sandboxing for autonomous workers and command allowlist interception.
