"""Built-in baseline ADR profiles for opinionated projects."""

from __future__ import annotations

from .models import BaselineADR, Profile

# Core Profile ADRs
CORE_ADR_0001 = BaselineADR(
    number=1,
    slug="specification-as-code-architecture",
    title="Specification as Code and Opinionated SDLC Guardrails",
    content="""# ADR-0001: Specification as Code and Opinionated SDLC Guardrails

## Status
Accepted

## Context
Traditional agile tooling isolates user stories and backlog items in external web silos, leading to specification drift, context blindness for coding agents, and merge conflicts across parallel streams.

## Decision
We adopt **Project Management as Code**:
1. All project specifications (Personas, PRDs, User Stories, ADRs, Backlog Tasks) live inside `docs/project/` as Markdown documents with YAML frontmatter.
2. Specifications branch, review, and merge directly alongside production code.
3. Automated tools parse documentation into machine-readable relational graphs, ensuring zero specification drift.

## Consequences
- **Positive**: Full version-locking of requirements and code; conflict-free parallel worker execution; living interactive visualizer directly from git history.
- **Negative**: Requires discipline to maintain frontmatter metadata and lean JIT buffers.
""",
)

CORE_ADR_0002 = BaselineADR(
    number=2,
    slug="modular-file-length-limits-anti-rot",
    title="Modular Source File Length Limit (<500 Lines Anti-Rot Rule)",
    content="""# ADR-0002: Modular Source File Length Limit (<500 Lines Anti-Rot Rule)

## Status
Accepted

## Context
Large monolithic files (>500 lines) are the primary cause of architectural decay and LLM degradation in AI-assisted codebases. When files grow too large, coding agents suffer from lost attention, generate conflicting diffs, and introduce subtle regressions.

## Decision
We establish a non-negotiable **Hard Invariant: Source files must remain under 500 lines**:
1. Any module approaching or exceeding 500 lines must be proactively decomposed into single-responsibility submodules (e.g. modular routers, domain handlers, or split test suites).
2. The `spec-ops health` scanner verifies this rule continuously. Pull requests violating this limit will be blocked.

## Consequences
- **Positive**: Sharp LLM attention windows, faster code reviews, clean surgical diffs, and modular decoupled architectures.
- **Negative**: Increases the number of files and requires explicit barrel exports (`__init__.py` or index modules).
""",
)

CORE_ADR_0003 = BaselineADR(
    number=3,
    slug="blackbox-frontdoor-verification",
    title="Blackbox Frontdoor Verification and Zero Backdoor Testing",
    content="""# ADR-0003: Blackbox Frontdoor Verification and Zero Backdoor Testing

## Status
Accepted

## Context
Tests that manipulate internal state via private backdoors (e.g., executing raw `INSERT INTO` queries in integration tests or spying on private methods) create brittle test suites. When internal implementations change, mock-heavy tests break even when public user behavior remains completely correct. Worse, backdoors bypass aggregate validation and authorization checks, masking production failure modes.

## Decision
We mandate **Blackbox Frontdoor Testing (Hard Invariant)**:
1. All tests must interact exclusively through public entrypoints: public REST endpoints, WebSockets, public domain events, or user interface forms.
2. Test setup (`Given`) must use public API fixtures or standard session injection; direct database manipulation in feature tests is strictly forbidden.
3. Assertions (`Then`) must verify observable outputs: rendered DOM elements, status codes, query projections, or emitted domain events.

## Consequences
- **Positive**: Tests verify true behavioral contracts; refactoring private internals does not break tests; eliminates false-positive mock pass rates.
- **Negative**: Setting up complex test states via public frontdoor APIs requires running supporting platform dependencies.
""",
)

CORE_ADR_0004 = BaselineADR(
    number=4,
    slug="continuous-preflight-and-self-healing-ci",
    title="Continuous Pre-flight Verification and Self-Healing CI Loops",
    content="""# ADR-0004: Continuous Pre-flight Verification and Self-Healing CI Loops

## Status
Accepted

## Context
Autonomous coding agents operating in git worktrees can push unverified code or fail CI checks without realizing it, abandoning broken branches in pull request limbo.

## Decision
We establish automated **Pre-flight Verification and In-Worktree CI Healing**:
1. Before any commit or PR is dispatched, workers run local preflight checks (`make preflight` / `spec-ops health`).
2. If preflight fails, the agent is prompted with failure diagnostics up to 3 repair attempts.
3. When pull requests fail remote CI checks, the orchestrator captures failed job logs via CLI (`gh run view --log-failed`) and prompts the agent directly in the isolated worktree to repair the failure before re-pushing.

## Consequences
- **Positive**: Branches merged to `main` have an extraordinarily high pass rate; CI failures are treated as immediate feedback loops rather than discarded work.
- **Negative**: Requires robust local tooling and access to GitHub CLI.
""",
)

CORE_ADR_0005 = BaselineADR(
    number=5,
    slug="worktree-concurrency-and-backlog-isolation",
    title="Git Worktree Concurrency and Strict Backlog Isolation",
    content="""# ADR-0005: Git Worktree Concurrency and Strict Backlog Isolation

## Status
Accepted

## Context
When multiple coding agents work concurrently on adjacent backlog tasks, having feature branches modify shared planning files (like `PRIORITY.md` or moving task files) causes guaranteed merge conflicts upon PR integration.

## Decision
We enforce **Strict Backlog Isolation on Feature Branches**:
1. Autonomous worker streams execute in isolated git worktrees (`feat/<task-slug>`).
2. Feature branches are **strictly forbidden from modifying `docs/project/backlog/`**.
3. Backlog state transitions (moving the task from `refined/` to `complete/` and updating `PRIORITY.md`) are executed exclusively by the orchestrator under `MERGE_LOCK` directly on `main` upon PR merge.

## Consequences
- **Positive**: Enables N concurrent worker streams to merge cleanly in parallel without merge conflicts.
- **Negative**: Backlog state changes can only be finalized upon integration into `main`.
""",
)

BDD_ADR_0006 = BaselineADR(
    number=6,
    slug="bdd-gherkin-user-stories-and-playwright-e2e",
    title="Behavior-Driven Development (BDD) with Gherkin User Stories and Playwright",
    content="""# ADR-0006: Behavior-Driven Development (BDD) with Gherkin User Stories and Playwright

## Status
Accepted

## Context
Requirements written as passive prose frequently diverge from actual UI implementations, resulting in untested journeys, broken client-side routing, and dead buttons.

## Decision
We adopt **Behavior-Driven Development (BDD)**:
1. User stories in `docs/project/user_stories/accepted/` must specify executable Gherkin scenarios (`Given ... When ... Then`).
2. Scenarios are automated via Playwright end-to-end browser tests running across Chromium, Firefox, and WebKit.
3. UI tasks cannot move to `complete/` until their Playwright BDD suite passes cleanly without backdoors.

## Consequences
- **Positive**: User stories act as living, executable test suites; guarantees consistent cross-browser user journeys.
- **Negative**: Browser automation suites take longer to execute than headless unit tests.
""",
)

DDD_ADR_0007 = BaselineADR(
    number=7,
    slug="domain-driven-design-and-bounded-contexts",
    title="Domain-Driven Design (DDD) Layering and Explicit Bounded Contexts",
    content="""# ADR-0007: Domain-Driven Design (DDD) Layering and Explicit Bounded Contexts

## Status
Accepted

## Context
Codebases without explicit architectural boundaries rapidly devolve into tangled dependency graphs where business logic, transport layers, and persistence concerns are hopelessly mixed.

## Decision
We enforce **Domain-Driven Design (DDD) and Bounded Contexts**:
1. Code is strictly segmented into bounded contexts with explicit ubiquitous language.
2. Domain logic remains pure and isolated from infrastructure and web frameworks.
3. State transitions flow through explicit aggregates and domain events.

## Consequences
- **Positive**: High coherence, low coupling, and clear boundaries that allow agents to reason about sub-domains in isolation.
- **Negative**: Requires disciplined domain modeling and event definition upfront.
""",
)

from .security import SECURITY_PROFILE

PROFILES: dict[str, Profile] = {
    "core": Profile(
        id="core",
        name="SpecOps Core Baseline",
        description="The foundational 5 SDLC invariants: Spec as Code, <500 lines limit, Frontdoors only, Self-healing CI, and Backlog Isolation.",
        adrs=[CORE_ADR_0001, CORE_ADR_0002, CORE_ADR_0003, CORE_ADR_0004, CORE_ADR_0005],
    ),
    "bdd": Profile(
        id="bdd",
        name="Behavior-Driven Development (BDD)",
        description="Gherkin user stories and Playwright browser automation for frontdoor end-to-end verification.",
        adrs=[BDD_ADR_0006],
    ),
    "ddd": Profile(
        id="ddd",
        name="Domain-Driven Design (DDD)",
        description="Explicit bounded contexts, ubiquitous language, and declarative aggregate state boundaries.",
        adrs=[DDD_ADR_0007],
    ),
    "security": SECURITY_PROFILE,
}


def get_profile(profile_id: str) -> Profile | None:
    return PROFILES.get(profile_id.lower())


def list_profiles() -> list[Profile]:
    return list(PROFILES.values())


def resolve_adrs_for_profiles(profile_ids: list[str]) -> list[BaselineADR]:
    """Combines ADRs from selected profiles, renumbering them sequentially."""
    seen_slugs: set[str] = set()
    combined: list[BaselineADR] = []

    for pid in profile_ids:
        p = get_profile(pid)
        if not p:
            continue
        for adr in p.adrs:
            if adr.slug not in seen_slugs:
                seen_slugs.add(adr.slug)
                combined.append(adr)

    # Renumber sequentially
    result: list[BaselineADR] = []
    for idx, adr in enumerate(combined, start=1):
        # Update title line in content if needed
        old_id = f"ADR-{adr.number:04d}"
        new_id = f"ADR-{idx:04d}"
        new_content = adr.content.replace(old_id, new_id)
        result.append(
            BaselineADR(
                number=idx,
                slug=adr.slug,
                title=adr.title,
                status=adr.status,
                date=adr.date,
                content=new_content,
            )
        )
    return result
