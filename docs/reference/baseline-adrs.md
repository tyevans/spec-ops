# Baseline Architectural Decision Records (ADRs)

SpecOps bundles 7 foundational ADRs organized across architectural profiles.

---

## Profile: `core`

- **ADR-0001: Specification as Code (PMaC)**: All personas, stories, PRDs, tasks, and decisions live in git as Markdown with YAML frontmatter.
- **ADR-0002: Modular File Length Limits (<500 lines)**: Keeps source files small to eliminate LLM context truncation and decay.
- **ADR-0003: Blackbox Frontdoor Verification**: Feature development driven through public interfaces without private backdoor mutation.
- **ADR-0004: Continuous Preflight & Self-Healing CI**: Enforces health checks before remote push with retry loops on failures.
- **ADR-0005: Worktree Concurrency & Backlog Isolation**: Isolated git worktrees prevent multi-agent merge conflicts on shared index files.

---

## Profile: `bdd`

- **ADR-0006: BDD Gherkin User Stories & Playwright E2E**: User stories written as executable Gherkin scenarios verified through browser automation.

---

## Profile: `ddd`

- **ADR-0007: Domain-Driven Design & Bounded Contexts**: Code organized by business domains with strict state encapsulation.
