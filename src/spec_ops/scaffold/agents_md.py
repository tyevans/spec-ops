"""Profile-driven AGENTS.md constitution generator for SpecOps."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..profiles.models import ADRDefinition


def generate_agents_md(
    project_name: str,
    profiles: list[str],
    adrs: list[ADRDefinition] | None = None,
) -> str:
    """Generates an opinionated AGENTS.md constitution tailored to active architectural profiles."""
    profiles_lower = {p.lower() for p in profiles}

    invariants = [
        "1. **File Length Limit (<500 lines)**:\n"
        "   - Source files over ~500 lines are strictly forbidden. Decompose large files into focused, single-responsibility modules.\n"
        "   - Enforced by `uv run spec-ops health`.",
        "2. **Blackbox Frontdoor Verification**:\n"
        "   - Tests must exercise public interfaces (CLI commands, public module entry points, domain models) rather than reaching into private internals or backdoor state manipulation.\n"
        "   - Governed by ADR-0003.",
        "3. **Strict Backlog Isolation**:\n"
        "   - Multi-agent workers execute in isolated git worktrees (`.worktrees/<task-id>`) on dedicated task branches (`task/<task-id>` or `feat/<task-id>`).\n"
        "   - Shared backlog files (`docs/project/backlog/`) must never be modified directly on feature branches; transitions are synchronized upon integration.\n"
        "   - Governed by ADR-0005.",
        "4. **UV Workspace Package Management**:\n"
        "   - All Python tools and dependencies are managed through root UV workspace (`uv run pytest`, `uv run spec-ops ...`). Never invoke bare `pip` or create ad-hoc virtual environments.",
        "5. **Specification as Code (PMaC)**:\n"
        "   - Every requirement, persona, architectural decision, and work item lives under `docs/project/` as Markdown with YAML frontmatter.\n"
        "   - Governed by ADR-0001.",
    ]

    if "bdd" in profiles_lower:
        invariants.append(
            "6. **Executable BDD User Stories & Frontdoor Testing**:\n"
            "   - User stories in `docs/project/user_stories/accepted/` must provide executable Gherkin scenarios.\n"
            "   - All acceptance tests must verify observable outcomes without private mock backdoors.\n"
            "   - Governed by ADR-0006."
        )

    if "ddd" in profiles_lower:
        invariants.append(
            "7. **Domain-Driven Design (DDD) & Bounded Contexts**:\n"
            "   - Code is segmented into explicit bounded contexts with pure domain models isolated from infrastructure.\n"
            "   - Governed by ADR-0007."
        )

    invariants_text = "\n".join(invariants)

    content = f"""# {project_name} Agent Operating Manual

Welcome to **{project_name}**, managed via **SpecOps**—the opinionated, autonomous Project Management as Code (PMaC) engine for human architects and AI coding assistants.

All specifications, user stories, tasks, and architectural decisions are version-locked directly in git alongside implementation code.

---

## Hard Invariants

These rules are non-negotiable. Autonomous agents and human contributors must follow them without exception:

{invariants_text}

---

## Design Principles

- **Version-Locked Specifications**: Requirements, user stories, and tasks live in the exact same git commit history as implementation code.
- **Thin Vertical Slicing**: Decompose PRDs into thin, single-pass vertical slices and architectural spikes rather than speculative horizontal layers.
- **Just-In-Time (JIT) Refinement**: Maintain a lean buffer of ~10 ready tasks in `refined/` to prevent specification rot before work begins.
- **Living Relational Graph**: Maintain bidirectional traceability from Personas -> PRDs -> Stories -> Tasks -> ADRs -> Commits.

---

## Project Structure & Navigation

All project management specifications live under `docs/project/`:

| Directory | Purpose |
|---|---|
| `docs/project/user_stories/PERSONAS.md` | Core user personas defining user needs and pain points |
| `docs/project/product/` | PRDs progressing from `idea/` to `shaped/`, `accepted/`, and `shipped/` |
| `docs/project/user_stories/` | Gherkin user stories defining end-to-end user journeys |
| `docs/project/adrs/` | Architectural Decision Records organized with `REGISTRY.md` |
| `docs/project/backlog/` | Work items in `complete/`, `refined/`, and `proposed/` |
| `docs/project/backlog/PRIORITY.md` | Strict sequential priority queue for engineering tasks |
| `docs/project/backlog/ROADMAP.md` | High-level delivery milestones |

---

## Documentation Directives (Diataxis Standards)

All system documentation outside `docs/project/` follows the **Diataxis framework** (`tutorials/`, `how-to/`, `reference/`, `explanation/`):

1. **Consult Existing Docs**: Search `docs/` before implementing changes or adding new conventions.
2. **Fix Stale Documentation**: Update inaccurate or outdated documentation discovered during your work.
3. **Document Reusable Capabilities**: When introducing or modifying public CLI flags, APIs, or architectural patterns, author corresponding how-to recipes or reference specs in `docs/`.

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
"""
    return content.strip() + "\n"
