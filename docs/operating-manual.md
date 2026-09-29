# SpecOps Agent Operating Manual

Welcome to **SpecOps**, the opinionated, autonomous Project Management as Code (PMaC) engine for human architects and AI coding assistants.

SpecOps version-locks specifications directly in git alongside source code—eliminating context drift, multi-agent merge conflicts, and monolithic file rot.

---

## Hard Invariants

These rules are non-negotiable. Autonomous agents and human contributors must follow them without exception.

1. **File Length Limit (<500 lines)**:
   - Source files over ~500 lines are strictly forbidden. Decompose large files into focused, single-responsibility modules.
   - Enforced by `uv run spec-ops health`.
2. **Blackbox Frontdoor Verification**:
   - Tests must exercise public interfaces (CLI commands, public module entry points, domain models) rather than reaching into private internals or backdoor state manipulation.
3. **Strict Backlog Isolation**:
   - Multi-agent workers execute in isolated git worktrees (`.worktrees/<task-id>`) on dedicated task branches (`task/<task-id>`).
   - Shared backlog index files (`PRIORITY.md`) must never be modified directly on feature branches; transitions are synchronized upon integration.
4. **UV Workspace Package Management**:
   - All Python tools and dependencies are managed through root UV workspace (`uv run pytest`, `uv run spec-ops ...`). Never invoke bare `pip` or create ad-hoc virtual environments.
5. **Specification as Code (PMaC)**:
   - Every requirement, persona, architectural decision, and work item lives under `docs/project/` as Markdown with YAML frontmatter.

---

## Design Principles

- **Version-Locked Specifications**: Specifications, user stories, and tasks live in the exact same git commit history as the implementation code.
- **Thin Vertical Slicing**: Decompose PRDs into thin, single-pass vertical slices and architectural spikes rather than horizontal speculative layers.
- **Just-In-Time (JIT) Refinement**: Maintain a lean buffer of ~10 ready tasks in `refined/` to prevent specification rot before work begins.
- **Living Relational Graph**: Maintain full bidirectional traceability from Personas -> PRDs -> Stories -> Tasks -> ADRs -> Commits.

---

## Project Structure & Navigation

All project management specifications live under `docs/project/`:

| Directory | Purpose |
|---|---|
| `docs/project/user_stories/PERSONAS.md` | Core user personas (Alex, Jordan, Morgan, Riley, Taylor, Sasha) |
| `docs/project/product/` | PRDs progressing from `idea/` to `accepted/` and `shipped/` |
| `docs/project/user_stories/` | Gherkin user stories defining end-to-end user value |
| `docs/project/adrs/` | Architectural Decision Records organized with `REGISTRY.md` |
| `docs/project/backlog/` | Work items in `complete/`, `refined/`, and `proposed/` |
| `docs/project/backlog/PRIORITY.md` | Strict sequential priority queue for backlog tasks |
| `docs/project/backlog/ROADMAP.md` | High-level delivery milestones |

---

## Task Execution Workflow

When picking up engineering work:

1. **Select Task**: Always select the highest-priority unassigned task in `docs/project/backlog/PRIORITY.md` located in `refined/`.
2. **Review Invariants**: Read the governing ADRs, PRDs, and user stories cited in the task's frontmatter.
3. **Implement**: Develop the solution using test-driven development through public frontdoors.
4. **Preflight Verification**:
   - Run `uv run spec-ops health` (verify 0 file limit violations and PRIORITY.md sync).
   - Run `uv run pytest` (verify 100% test pass rate).
5. **Complete**: Move task to `complete/` or use `spec-ops queue complete <task-id>`, update `PRIORITY.md`, and link commit or PR.
