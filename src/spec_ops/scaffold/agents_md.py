"""Profile-driven AGENTS.md constitution generator for SpecOps."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..profiles.models import ADRDefinition


def generate_agents_md(
    project_name: str,
    profiles: list[str],
    adrs: list[ADRDefinition] | None = None,
    file_length_limit: int = 500,
    custom_invariants: list[str] | None = None,
    root_dir: Path | None = None,
    superseded_map: dict[str, str] | None = None,
) -> str:
    """Generates an opinionated AGENTS.md constitution tailored to active architectural profiles."""
    profiles_lower = {p.lower() for p in profiles}
    warn_threshold = max(1, file_length_limit - 100)

    invariants = [
        f"1. **File Length Limit (<{file_length_limit} lines)**:\n"
        f"   - Source files over ~{file_length_limit} lines are strictly forbidden. Decompose large files into focused, single-responsibility modules.\n"
        f"   - Enforced by `uv run spec-ops health` (warns proactively at >={warn_threshold} lines). Governed by ADR-0002.",
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

    has_bdd = "bdd" in profiles_lower
    has_ddd = "ddd" in profiles_lower
    has_security = "security" in profiles_lower

    if has_bdd:
        invariants.append(
            "6. **Executable BDD User Stories & Frontdoor Testing**:\n"
            "   - User stories in `docs/project/user_stories/accepted/` must provide executable Gherkin scenarios.\n"
            "   - All acceptance tests must verify observable outcomes without private mock backdoors.\n"
            "   - Governed by ADR-0006."
        )

    if has_ddd:
        invariants.append(
            "7. **Domain-Driven Design (DDD) & Bounded Contexts**:\n"
            "   - Code is segmented into explicit bounded contexts with pure domain models isolated from infrastructure.\n"
            "   - Governed by ADR-0007."
        )

    if has_bdd or "quality" in profiles_lower:
        invariants.append(
            "8. **Property-Based Testing (Hypothesis) & Mutation Testing (Mutmut)**:\n"
            "   - Domain models, state machines, parsers, and health algorithms must maintain generative property tests (`@given(...)`).\n"
            "   - Core domain modules must maintain a minimum 80% mutation kill score under `mutmut`.\n"
            "   - Governed by ADR-0009."
        )

    if has_security:
        invariants.append(
            "9. **Security & Supply-Chain Hard Invariants**:\n"
            "   - Autonomous agents are strictly forbidden from hardcoding credentials, modifying unapproved lockfiles, or executing non-allowlisted shell commands.\n"
            "   - Enforced by `uv run spec-ops health --security` and preflight secret scanners. Governed by ADR-0010, ADR-0011, and ADR-0012."
        )

    if custom_invariants:
        for idx, inv in enumerate(custom_invariants, start=len(invariants) + 1):
            invariants.append(
                f"{idx}. **Compliance Invariant**:\n"
                f"   - {inv}"
            )

    if superseded_map and root_dir:
        from ..adrs.supersede import find_adr_file, parse_adr_info
        adrs_dir = root_dir / "docs" / "project" / "adrs"
        for i, inv in enumerate(invariants):
            for old_id, new_id in superseded_map.items():
                if old_id in inv:
                    new_title = new_id
                    try:
                        f = find_adr_file(adrs_dir, new_id)
                        _, _, new_title, _ = parse_adr_info(f)
                    except Exception:
                        pass
                    updated = re.sub(r"\*\*([^*]+)\*\*:", f"**{new_title}**:", inv, count=1)
                    updated = re.sub(rf"Governed by {re.escape(old_id)}\.?", f"Governed by {new_id}.", updated)
                    invariants[i] = updated

    invariants_text = "\n".join(invariants)

    dor_items = [
        "1. **Task Metadata Complete**: Task frontmatter contains `id`, `title`, `status: Refined`, `target_bc`, and explicit dependencies.",
        "2. **Governing Artifacts Linked**: Reference PRD in `docs/project/product/accepted/`, Persona in `docs/project/user_stories/PERSONAS.md`, and governing ADRs in `docs/project/adrs/accepted/` are cited.",
    ]
    if has_bdd:
        dor_items.append(
            "3. **Executable BDD Specification**: Governing user story in `docs/project/user_stories/accepted/` provides executable Gherkin scenarios (`Given ... When ... Then`) whose test setup is achievable strictly through public frontdoors without backdoor tampering (ADR-0006)."
        )
    dor_items.extend([
        "4. **Generative Property Invariants Identified**: Core domain state spaces, combinatorial parsers, and health algorithms identify invariant properties for Hypothesis `@given(...)` testing (ADR-0009).",
        "5. **Mutation Testing Scope Defined**: Target modules for Mutmut mutation testing identified with target >=80% mutant kill score (ADR-0009).",
        "6. **INVEST Criteria Satisfied**: Validated as a thin vertical slice (Independent, Negotiable, Valuable, Estimable, Small [<500 lines per file], Testable) with zero speculative horizontal layers.",
        "7. **Documentation Review**: Relevant existing documentation in `docs/` reviewed to prevent conflicting conventions.",
    ])
    dor_text = "\n".join(dor_items)

    dod_items = [
        "1. **Blackbox Frontdoor Verification**: 100% test pass rate (`uv run pytest`) verifying observable contracts through public frontdoors with zero private mock backdoors (ADR-0003).",
    ]
    if has_bdd:
        dod_items.append(
            "2. **Executable BDD Scenarios Passing**: All Gherkin acceptance criteria executed via `pytest-bdd` pass cleanly without mock backdoors (ADR-0006)."
        )
    dod_items.extend([
        "3. **Hypothesis Property Tests Passing**: Generative property tests verify domain invariants across randomized inputs without shrinking failures (ADR-0009).",
        "4. **Mutmut Mutation Score Attained**: Target domain modules achieve >=80% mutant kill score under `mutmut` (ADR-0009).",
        f"5. **Codebase Health Check**: `uv run spec-ops health` reports 0 file limit violations (<{file_length_limit} lines) and 0 proactive warnings (<{warn_threshold} lines), and verifies `PRIORITY.md` sync (ADR-0002).",
        "6. **Lockfile Integrity**: `uv lock --check` passes cleanly without unstaged dependency drifts.",
        "7. **Documentation Integrity (Diataxis)**:\n"
        "   - Inaccurate or stale docs discovered during work are corrected.\n"
        "   - Reusable patterns, CLI commands, and architectural changes documented in `docs/how-to/` or `docs/reference/`.\n"
        "   - Documentation builds cleanly (`uv run spec-ops docs build`).",
        "8. **Strict Backlog Progression**: Task is moved from `refined/` to `complete/` (or via `spec-ops queue complete <task-id>`) and `PRIORITY.md` updated atomically upon integration (ADR-0005).",
        "9. **Commit Provenance**: Commits include structured trailers referencing governing tasks and stories (`SpecOps-Task: TASK-XXXX`).",
    ])
    dod_text = "\n".join(dod_items)

    security_section = ""
    if has_security:
        security_section = """\n\n---

## Security & Supply-Chain Hard Invariants

These security and supply-chain guardrails are non-negotiable across all autonomous worker streams:
1. **No Hardcoded Credentials**: Autonomous agents are strictly forbidden from hardcoding credentials, API keys, tokens, or high-entropy secrets in source code, tests, or git commits.
2. **Lockfile Immutability**: Autonomous agents are strictly forbidden from modifying unapproved lockfiles (`uv.lock`, `package-lock.json`) without explicit human architectural approval.
3. **Allowlisted Command Execution**: Autonomous agents are strictly forbidden from executing non-allowlisted shell commands outside approved development toolchains."""

    content = f"""# {project_name} Agent Operating Manual

Welcome to **{project_name}**, managed via **SpecOps**—the opinionated, autonomous Project Management as Code (PMaC) engine for human architects and AI coding assistants.

All specifications, user stories, tasks, and architectural decisions are version-locked directly in git alongside implementation code.

---

## Hard Invariants

These rules are non-negotiable. Autonomous agents and human contributors must follow them without exception:

{invariants_text}{security_section}

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

## Definition of Ready (DoR)

A backlog task or feature may only be transitioned to `refined/` and pulled into active development when:

{dor_text}

---

## Definition of Done (DoD)

Work is complete and ready for integration into `main` only when:

{dod_text}

---

## Task Execution Workflow

When picking up engineering work:

1. **Select Task**: Always select the highest-priority unassigned task in `docs/project/backlog/PRIORITY.md` located in `refined/`.
2. **Review Invariants & DoR**: Verify task meets the Definition of Ready (DoR); read governing ADRs, PRDs, and user stories cited in the frontmatter.
3. **Implement**: Develop the solution using test-driven development through public frontdoors. Maintain BDD scenarios and Hypothesis property tests alongside feature code.
4. **Preflight Verification**:
   - Run `uv run spec-ops health` (verify 0 file limit violations, 0 warnings, and PRIORITY.md sync).
   - Run `uv run pytest` (verify 100% test pass rate across unit, BDD, and Hypothesis property tests).
   - Run `uv run mutmut run` (verify mutant kill score on mutated domain modules).
   - Run `uv lock --check` (verify lockfile synchronization).
5. **Complete**: Verify all Definition of Done (DoD) criteria; move task to `complete/` or use `spec-ops queue complete <task-id>`, update `PRIORITY.md`, and link commit or PR.
"""
    return content.strip() + "\n"


def scaffold_agents_command(root_dir: Path) -> str:
    """Scaffolds or regenerates AGENTS.md constitution tailored to installed profiles."""
    from ..config.loader import load_config
    from ..profiles.registry import resolve_adrs_for_profiles

    cfg = load_config(root_dir=root_dir)
    profiles = ["core", "bdd", "ddd"]

    if cfg.security is not None:
        if "security" not in profiles:
            profiles.append("security")
    else:
        sec_md = root_dir / "docs" / "project" / "SECURITY.md"
        toml_path = root_dir / "specops.toml"
        if sec_md.exists() or (toml_path.exists() and "[security]" in toml_path.read_text(encoding="utf-8")):
            if "security" not in profiles:
                profiles.append("security")

    adrs_dir = root_dir / "docs" / "project" / "adrs"
    superseded_map: dict[str, str] = {}
    try:
        from ..adrs.supersede import discover_superseded_adrs
        superseded_map = discover_superseded_adrs(adrs_dir)
    except Exception:
        pass

    adrs = resolve_adrs_for_profiles(profiles)
    content = generate_agents_md(
        cfg.project.name,
        profiles,
        adrs,
        root_dir=root_dir,
        superseded_map=superseded_map,
    )
    agents_path = root_dir / "AGENTS.md"
    old_content = agents_path.read_text(encoding="utf-8") if agents_path.exists() else ""
    agents_path.write_text(content, encoding="utf-8")

    if (root_dir / ".git").exists() and superseded_map and content != old_content:
        trailers = [f"SpecOps-ADR: {new_id}" for new_id in sorted(set(superseded_map.values()))]
        trailer_str = "\n".join(trailers)
        commit_msg = f"docs: re-synchronize AGENTS.md constitution\n\n{trailer_str}"
        try:
            subprocess.run(["git", "add", "AGENTS.md"], cwd=root_dir, check=True, capture_output=True)
            subprocess.run(["git", "commit", "-m", commit_msg], cwd=root_dir, check=True, capture_output=True)
        except subprocess.SubprocessError:
            pass

    return "AGENTS.md updated successfully with active profile invariants."

