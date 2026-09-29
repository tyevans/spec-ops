"""Scaffolding and project initialization engine for SpecOps."""

from __future__ import annotations

from pathlib import Path


DEFAULT_SPECOPS_TOML = """[project]
name = "{name}"
repo = ""
docs_dir = "docs/project"
site_output = "dist/site"

[architecture]
file_length_limit = 500
buffer_target = 10
buffer_warning_threshold = 6

components = [
  {{ id = "core", name = "Core Engine", path = "src" }}
]

[vertical_slices]
slices = [
  {{ type = "spike", name = "Architectural Spike", prefix = "SPIKE:", requires_adr = true }},
  {{ type = "domain", name = "Domain Model & State Handlers" }},
  {{ type = "api", name = "Public API Contracts" }},
  {{ type = "ui", name = "User Interface & Component Stories" }},
  {{ type = "test", name = "Blackbox Frontdoor Test Suite" }}
]

[quality]
testing_style = "blackbox-frontdoor"
require_bdd = true
preflight = [
  "pytest"
]

[execution]
agent_command = "agy --dangerously-skip-permissions -p {{prompt}}"
agent_max_attempts = 3
git_branch_prefix = "feat/"
backlog_isolation = true
"""

DEFAULT_PERSONAS = """# User Personas

Archetypes representing the core users, operators, and storytellers interacting with this system.

---

## 1. Alex — The Systems Builder
- **Role**: Software engineer and architect.
- **Pain Points**:
  - Context rot when specifications diverge from code.
  - Frustrating merge conflicts when agents work in parallel.
- **Goals with this platform**:
  - Unbroken bidirectional traceability from user story to production commit.
  - Autonomous agents that verify behavior exclusively through public frontdoors.

---

## 2. Jordan — The Product Strategist
- **Role**: Product manager and domain expert.
- **Pain Points**:
  - Unclear delivery status and vague completion criteria.
- **Goals with this platform**:
  - Real-time 2D relationship graph and Gantt roadmap generated directly from git repository files.

---

## 3. Morgan — The Autonomous Agent
- **Role**: LLM-powered coding worker.
- **Pain Points**:
  - Ambiguous ticket descriptions with no clear definition of done.
- **Goals with this platform**:
  - Unambiguous task contracts citing governing ADRs and isolated worktree execution.

---

## 4. Riley — The Human Developer
- **Role**: Software engineer pairing with AI assistants.
- **Pain Points**:
  - PR review fatigue and opaque autonomous changes.
- **Goals with this platform**:
  - Seamless worktree takeover and transparent code provenance.
"""

DEFAULT_ADR_0001 = """# ADR-0001: Specification as Code and Opinionated SDLC Guardrails

## Status
Accepted

## Context
Traditional agile tooling isolates user stories and backlog items in external web silos, leading to specification drift, context blindness for coding agents, and merge conflicts across parallel streams.

## Decision
We adopt **Project Management as Code**:
1. All project specifications (Personas, PRDs, User Stories, ADRs, Backlog Tasks) live inside `docs/project/` as Markdown documents with YAML frontmatter.
2. We enforce **Hard Invariant 6 (File Length Limit < 500 lines)** to guarantee maintainability and LLM reasoning accuracy.
3. We enforce **Hard Invariant 7 (Blackbox Frontdoor Testing)**: tests interact strictly through public frontdoors with zero backdoor state manipulation.
4. We enforce **Strict Backlog Isolation**: feature branches never touch `docs/project/backlog/`, eliminating git merge conflicts across parallel worker streams.

## Consequences
- **Positive**: Full version-locking of requirements and code; conflict-free parallel worker execution; living interactive visualizer directly from git history.
- **Negative**: Requires discipline to maintain frontmatter metadata and lean JIT buffers.
"""

DEFAULT_BACKLOG_README = """# Backlog Management Guide

Tasks move through three lifecycle stages:
- `proposed/`: Unrefined ideas, feature proposals, and discovered refactoring candidates.
- `refined/`: Architectural impact review completed, governing ADRs/PRDs cited, and testable blackbox definition of done established.
- `complete/`: Verified against tests, linted, committed, and integrated into the codebase.

## Core Invariants
1. **Just-In-Time (JIT) Refinement**: Maintain a lean ready buffer of ~10 tasks in `refined/`.
2. **Backlog Isolation**: Feature branches never modify `docs/project/backlog/` to ensure zero-conflict parallel merges.
3. **Blackbox Frontdoor Verification**: Test criteria must verify observable outputs via public entrypoints with zero private backdoor manipulation.
"""

DEFAULT_PRIORITY = """# Backlog Priority Index

Strict sequential order of execution for engineering tasks.

- **TASK-0001 (Refined)**: [`0001-initial-architecture-spike-and-setup`](refined/0001-initial-architecture-spike-and-setup.md)
"""

DEFAULT_TASK_0001 = """---
id: '0001'
title: Initial Architecture Spike and System Foundation
status: Refined
created: 2026-09-29
governing_adrs:
  - ADR-0001
target_bc: core
---

# TASK-0001: Initial Architecture Spike and System Foundation

## Summary
Establish initial system architecture, core domain models, and blackbox test harness.

## Definition of Done
1. Project configuration loaded and validated.
2. Blackbox verification tests pass cleanly.
3. All source files strictly under 500 lines.
"""


from ..profiles.registry import resolve_adrs_for_profiles
from .agents_md import generate_agents_md
from .ci_workflow import generate_ci_workflow
from .diataxis import scaffold_diataxis_docs
from .pages_workflow import generate_pages_workflow
from .pre_commit import generate_pre_commit_config


def init_project(
    target_dir: Path,
    name: str | None = None,
    profiles: list[str] | None = None,
    diataxis: bool = True,
    github_pages: bool = True,
    pre_commit: bool = True,
) -> list[Path]:
    """Scaffolds the full SpecOps directory structure and starter files with baseline ADRs."""
    root = target_dir.resolve()
    project_name = name or root.name
    selected_profiles = profiles or ["core", "bdd", "ddd"]

    docs_project = root / "docs" / "project"
    created_files: list[Path] = []

    def _write(rel_path: Path, content: str) -> None:
        full_path = root / rel_path
        full_path.parent.mkdir(parents=True, exist_ok=True)
        if not full_path.exists():
            full_path.write_text(content.strip() + "\n", encoding="utf-8")
            created_files.append(full_path)

    # 1. specops.toml
    _write(Path("specops.toml"), DEFAULT_SPECOPS_TOML.format(name=project_name))

    # 2. docs/project directories
    for folder in [
        docs_project / "user_stories" / "accepted",
        docs_project / "product" / "accepted",
        docs_project / "product" / "idea",
        docs_project / "product" / "shaped",
        docs_project / "product" / "shipped",
        docs_project / "adrs" / "accepted",
        docs_project / "backlog" / "proposed",
        docs_project / "backlog" / "refined",
        docs_project / "backlog" / "complete",
    ]:
        folder.mkdir(parents=True, exist_ok=True)

    # 3. Baseline ADRs from Profiles
    resolved_adrs = resolve_adrs_for_profiles(selected_profiles)
    adr_registry_rows = []
    governing_adr_ids = []

    for adr in resolved_adrs:
        adr_file = docs_project / "adrs" / "accepted" / adr.filename
        _write(adr_file.relative_to(root), adr.content)
        adr_registry_rows.append(f"| {adr.canonical_id} | {adr.title} | {adr.status} | {adr.date} |")
        governing_adr_ids.append(adr.canonical_id)

    registry_table = "\n".join(adr_registry_rows)
    _write(
        docs_project / "adrs" / "REGISTRY.md",
        f"# ADR Registry\n\n| ID | Title | Status | Date |\n|---|---|---|---|\n{registry_table}\n",
    )

    # 4. Agent Constitution (AGENTS.md)
    agents_md = generate_agents_md(project_name, selected_profiles, resolved_adrs)
    _write(Path("AGENTS.md"), agents_md)

    # 5. Starter documents
    _write(docs_project / "user_stories" / "PERSONAS.md", DEFAULT_PERSONAS)
    _write(docs_project / "product" / "REGISTRY.md", "# PRD Registry\n\n| ID | Title | Status |\n|---|---|---|\n")
    _write(docs_project / "user_stories" / "REGISTRY.md", "# User Stories Registry\n\n| ID | Title | Status | Persona |\n|---|---|---|---|\n")
    _write(docs_project / "backlog" / "README.md", DEFAULT_BACKLOG_README)
    _write(docs_project / "backlog" / "PRIORITY.md", DEFAULT_PRIORITY)
    _write(docs_project / "backlog" / "ROADMAP.md", "# Delivery Roadmap\n\n## Milestone 1: Foundations\n- Core system architecture and blackbox harness.\n")

    task_adrs_yaml = "\n".join(f"  - {aid}" for aid in governing_adr_ids[:2])
    task_0001_content = f"""---
id: '0001'
title: Initial Architecture Spike and System Foundation
status: Refined
created: 2026-09-29
governing_adrs:
{task_adrs_yaml}
target_bc: core
---

# TASK-0001: Initial Architecture Spike and System Foundation

## Summary
Establish initial system architecture, core domain models, and blackbox test harness.

## Definition of Done
1. Project configuration loaded and validated.
2. Blackbox verification tests pass cleanly.
3. All source files strictly under 500 lines.
"""
    _write(docs_project / "backlog" / "refined" / "0001-initial-architecture-spike-and-setup.md", task_0001_content)

    # 6. GitHub Actions CI workflow
    ci_workflow = generate_ci_workflow(project_name)
    _write(Path(".github") / "workflows" / "ci.yml", ci_workflow)

    # 6b. GitHub Pages deployment workflow
    if github_pages:
        pages_workflow = generate_pages_workflow(project_name)
        _write(Path(".github") / "workflows" / "deploy-pages.yml", pages_workflow)

    # 6c. Git pre-commit configuration
    if pre_commit:
        pre_commit_cfg = generate_pre_commit_config()
        _write(Path(".pre-commit-config.yaml"), pre_commit_cfg)

    # 7. .gitignore additions
    gitignore = root / ".gitignore"
    ignores = [".worktrees/", "dist/", "site/", "__pycache__/", "*.pyc", ".pytest_cache/", ".hypothesis/", ".mutmut-cache/", "mutants/", ".task-prompt.md"]
    if gitignore.exists():
        existing = gitignore.read_text(encoding="utf-8")
        to_add = [ig for ig in ignores if ig not in existing]
        if to_add:
            gitignore.write_text(existing.rstrip() + "\n" + "\n".join(to_add) + "\n", encoding="utf-8")
    else:
        _write(Path(".gitignore"), "\n".join(ignores))

    # 8. Diataxis 4-quadrant documentation
    if diataxis:
        diataxis_files = scaffold_diataxis_docs(root, project_name, agents_md_content=agents_md)
        created_files.extend(diataxis_files)

    return created_files
