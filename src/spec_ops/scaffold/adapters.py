"""Multi-agent platform adapters and configuration generators.

Provides configuration and rule generators for:
- Claude Code (`CLAUDE.md`)
- Cursor (`.cursorrules`)
- Antigravity rule sets (`GEMINI.md`) and slash command skills (`/curate`, `/health`, `/worker`)
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..profiles.models import ADRDefinition

SUPPORTED_AGENTS = ("antigravity", "claude", "cursor")


def parse_target_agents(agents_input: list[str] | str | None) -> list[str]:
    """Parses and normalizes target agent inputs.

    Supports comma-separated strings (e.g. 'antigravity,claude,cursor'),
    lists of strings, and the special keyword 'all'.
    """
    if agents_input is None:
        return []

    raw_items: list[str] = []
    if isinstance(agents_input, str):
        raw_items = [s.strip().lower() for s in agents_input.split(",") if s.strip()]
    else:
        for item in agents_input:
            if isinstance(item, str):
                raw_items.extend([s.strip().lower() for s in item.split(",") if s.strip()])

    if "all" in raw_items:
        return list(SUPPORTED_AGENTS)

    parsed: list[str] = []
    for item in raw_items:
        if item not in SUPPORTED_AGENTS:
            raise ValueError(
                f"Unsupported agent platform: '{item}'. "
                f"Supported agents: {', '.join(SUPPORTED_AGENTS)}"
            )
        if item not in parsed:
            parsed.append(item)

    # Return in canonical order
    return [a for a in SUPPORTED_AGENTS if a in parsed]


def _format_profile_invariants(profiles: list[str] | None) -> str:
    """Formats optional profile-driven hard invariants."""
    if not profiles:
        return ""
    profiles_lower = {p.lower() for p in profiles}
    lines: list[str] = []
    if "bdd" in profiles_lower:
        lines.append(
            "- **Executable BDD Scenarios (ADR-0006)**: Acceptance tests execute "
            "Gherkin scenarios via `pytest-bdd` through public frontdoors without mock backdoors."
        )
    if "ddd" in profiles_lower:
        lines.append(
            "- **Domain-Driven Design (ADR-0007)**: Code is segmented into explicit bounded "
            "contexts with pure domain models isolated from infrastructure."
        )
    if "bdd" in profiles_lower or "quality" in profiles_lower:
        lines.append(
            "- **Property Testing & Mutation (ADR-0009)**: Generative property tests (`@given`) "
            "verify domain invariants; domain modules target >=80% mutation kill score."
        )
    return "\n".join(lines)


def generate_claude_rules(
    project_name: str,
    profiles: list[str] | None = None,
    adrs: list[ADRDefinition] | None = None,
) -> str:
    """Generates CLAUDE.md configuration and operating rules for Claude Code."""
    extra_invariants = _format_profile_invariants(profiles)
    extra_section = f"\n{extra_invariants}\n" if extra_invariants else ""

    return f"""# Claude Code Operating Guidelines — {project_name}

Welcome to **{project_name}**, managed via **SpecOps** (Project Management as Code).
Specifications, user stories, tasks, and architectural decisions are version-locked in git under `docs/project/`.

## Non-Negotiable Hard Invariants
1. **File Length Limit (<500 lines)**:
   - Source files over ~500 lines are strictly forbidden. Decompose large files into focused, single-responsibility modules.
   - Run `uv run spec-ops health` (warns proactively at >=400 lines). Governed by ADR-0002.
2. **Blackbox Frontdoor Verification**:
   - Tests must exercise observable outcomes strictly through public frontdoors (CLI commands, public module entry points, domain models) without private backdoor mocking or state manipulation. Governed by ADR-0003.
3. **Strict Backlog Isolation**:
   - Feature branches must NEVER modify files in `docs/project/backlog/` directly. Backlog status transitions are synchronized upon integration into `main`. Governed by ADR-0005.
4. **UV Workspace Package Management**:
   - Always run commands via `uv run` (`uv run pytest`, `uv run spec-ops ...`). Never invoke bare `pip` or create ad-hoc virtual environments.
5. **Specification as Code (PMaC)**:
   - Requirements, personas, stories, ADRs, and tasks live under `docs/project/`. Governed by ADR-0001.
{extra_section}
## Essential Commands
- **Health Check**: `uv run spec-ops health`
- **Run Tests**: `uv run pytest`
- **Backlog Curation**: `uv run spec-ops curate`
- **Worker Execution**: `uv run spec-ops worker`
- **Visualizer**: `uv run spec-ops visualizer --serve`
- **Dependency & Lockfile Check**: `uv lock --check`

## Definition of Ready (DoR) & Definition of Done (DoD)
- Tasks in `docs/project/backlog/refined/` must meet DoR before development begins.
- Before completing any task, ensure:
  1. `uv run spec-ops health` reports 0 file limit violations and PRIORITY.md is synchronized.
  2. `uv run pytest` passes 100% blackbox verification tests.
  3. `uv lock --check` passes cleanly.
  4. Commits follow conventional commits with `SpecOps-Task: TASK-XXXX` git trailers.

Consult `AGENTS.md` for the full system constitution and definition of done.
"""


def generate_cursor_rules(
    project_name: str,
    profiles: list[str] | None = None,
    adrs: list[ADRDefinition] | None = None,
) -> str:
    """Generates .cursorrules configuration and operating rules for Cursor."""
    extra_invariants = _format_profile_invariants(profiles)
    extra_section = f"\n{extra_invariants}\n" if extra_invariants else ""

    return f"""# Cursor Rules — {project_name}

You are an expert AI software engineer operating within **{project_name}**, managed with **SpecOps** Project Management as Code (PMaC).

## Hard Invariants
- **File Length Limit**: Strictly <500 lines per file (proactive refactoring warning at >=400 lines). Decompose large files into focused single-responsibility modules. (ADR-0002)
- **Blackbox Frontdoor Verification**: Test observable behavior through public entry points. Zero private mock backdoors or state tampering. (ADR-0003)
- **Strict Backlog Isolation**: Do not edit `docs/project/backlog/` on feature branches. Backlog transitions are managed centrally upon integration. (ADR-0005)
- **UV Package Management**: Always use `uv run <command>` (`uv run pytest`, `uv run spec-ops ...`). Never invoke bare pip.
- **Diataxis Documentation**: Keep documentation under `docs/` synchronized with code changes. (ADR-0008)
{extra_section}
## Key Commands
- Check codebase health: `uv run spec-ops health`
- Run test suite: `uv run pytest`
- Curate ready buffer: `uv run spec-ops curate`
- Run backlog worker: `uv run spec-ops worker`
- Verify dependencies: `uv lock --check`

## Preflight Checklist Before Handoff
1. `uv run spec-ops health` (0 violations, 0 warnings, priority sync OK)
2. `uv run pytest` (100% pass rate)
3. `uv lock --check` (lockfile clean)
4. Reference governing task in commit messages (`SpecOps-Task: TASK-XXXX`)

Refer to `AGENTS.md` and `docs/project/` for architecture context.
"""


def generate_antigravity_rules(
    project_name: str,
    profiles: list[str] | None = None,
    adrs: list[ADRDefinition] | None = None,
) -> str:
    """Generates GEMINI.md configuration and operating rules for Antigravity."""
    extra_invariants = _format_profile_invariants(profiles)
    extra_section = f"\n{extra_invariants}\n" if extra_invariants else ""

    return f"""# Antigravity Operating Rules — {project_name}

Welcome to **{project_name}**, governed by **SpecOps** Project Management as Code (PMaC).

## Hard Invariants
1. **File Length Limit (<500 lines)**: All source and test files must remain strictly under 500 lines. Proactive refactoring warnings trigger at >=400 lines. (ADR-0002)
2. **Blackbox Frontdoor Verification**: Verify behavior exclusively through public frontdoor interfaces (CLI, public APIs). No private mocks or internal backdoors. (ADR-0003)
3. **Strict Backlog Isolation**: Never modify files in `docs/project/backlog/` on task branches. Transitions are synchronized centrally upon integration. (ADR-0005)
4. **UV Workspace**: Always use `uv run pytest` and `uv run spec-ops ...`. Never invoke system pip.
5. **Specification as Code**: Specifications live under `docs/project/` with YAML frontmatter. (ADR-0001)
{extra_section}
## Available Slash Commands
- `/curate`: Perform JIT backlog refinement and buffer alignment (`uv run spec-ops curate`).
- `/health`: Inspect file length limits, proactive warnings, and backlog priority sync (`uv run spec-ops health`).
- `/worker`: Execute next ready backlog task in an isolated git worktree (`uv run spec-ops worker`).

## Preflight Verification
Always run before concluding work:
- `uv run spec-ops health`
- `uv run pytest`
- `uv lock --check`

Consult `AGENTS.md` for the full system constitution and definition of done.
"""


from .skill_templates import (
    CURATE_SKILL_MD,
    HEALTH_SKILL_MD,
    SPEC_OPS_SKILL_MD,
    WORKER_SKILL_MD,
)


def get_antigravity_slash_commands() -> dict[str, str]:
    """Returns mapping of relative file paths to Antigravity skill/slash command content."""
    return {
        ".agents/skills/curate/SKILL.md": CURATE_SKILL_MD.strip() + "\n",
        ".agents/skills/health/SKILL.md": HEALTH_SKILL_MD.strip() + "\n",
        ".agents/skills/worker/SKILL.md": WORKER_SKILL_MD.strip() + "\n",
        ".agents/skills/spec-ops/SKILL.md": SPEC_OPS_SKILL_MD.strip() + "\n",
    }


def scaffold_agent_adapters(
    root: Path,
    project_name: str,
    agents: list[str] | str | None,
    profiles: list[str] | None = None,
    adrs: list[ADRDefinition] | None = None,
    overwrite: bool = False,
) -> list[Path]:
    """Scaffolds target agent platform configurations and rule files."""
    parsed_agents = parse_target_agents(agents)
    created: list[Path] = []

    def _write_file(rel_path: str, content: str) -> None:
        target_path = root / rel_path
        target_path.parent.mkdir(parents=True, exist_ok=True)
        if not target_path.exists() or overwrite:
            target_path.write_text(content.strip() + "\n", encoding="utf-8")
            created.append(target_path)

    if "claude" in parsed_agents:
        claude_content = generate_claude_rules(project_name, profiles, adrs)
        _write_file("CLAUDE.md", claude_content)

    if "cursor" in parsed_agents:
        cursor_content = generate_cursor_rules(project_name, profiles, adrs)
        _write_file(".cursorrules", cursor_content)

    if "antigravity" in parsed_agents:
        gemini_content = generate_antigravity_rules(project_name, profiles, adrs)
        _write_file("GEMINI.md", gemini_content)

        slash_commands = get_antigravity_slash_commands()
        for rel_path, cmd_content in slash_commands.items():
            _write_file(rel_path, cmd_content)

    return created
