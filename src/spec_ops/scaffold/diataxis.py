"""Diataxis documentation scaffolding for SpecOps."""

from __future__ import annotations

import re
from pathlib import Path

DEFAULT_INDEX_MD = """# {project_name} Documentation

Welcome to **{project_name}**, managed via **SpecOps**—the autonomous Project Management as Code (PMaC) engine.

This documentation follows the 4-quadrant **Diataxis framework**:

- **Tutorials**: Step-by-step onboarding walkthroughs.
- **How-To Guides**: Practical recipes solving everyday operational challenges.
- **Technical Reference**: Authoritative documentation of CLI interfaces and architecture.
- **Explanation**: In-depth design philosophy, domain boundaries, and hard invariants.

---

## Interactive 2D Graph Visualizer

Explore our living project dependency graph in real time:

👉 **[Launch Interactive 2D Graph Visualizer](visualizer/)**
"""

DEFAULT_TUTORIAL_GETTING_STARTED = """# Getting Started with {project_name}

Welcome to {project_name}! This tutorial guides you through setting up your environment and running your first autonomous feature cycle.

## Prerequisites
- Python 3.11+
- UV package manager (`curl -LsSf https://astral.sh/uv/install.sh | sh`)
- Git

## Step 1: Install Dependencies
```bash
uv sync
```

## Step 2: Verify System Health
Run the SpecOps invariant scanner:
```bash
uv run spec-ops health
```
"""

DEFAULT_HOWTO_BOOTSTRAP = """# How-To: Bootstrap a SpecOps Project

This recipe walks you through bootstrapping a new project with opinionated PMaC invariants and Diataxis documentation.

## Running Init
```bash
uv run spec-ops init --name "MySystem" --diataxis
```
"""

DEFAULT_REFERENCE_CLI = """# CLI Reference

SpecOps provides a unified command-line interface (`spec-ops`).

---

## Subcommands

| Command | Arguments | Description |
|---|---|---|
| `spec-ops init` | `[--dir PATH] [--name NAME] [--profile PROFILES] [--agent AGENTS] [--diataxis/--no-diataxis] [--github-pages/--no-github-pages] [--pre-commit/--no-pre-commit]` | Bootstrap a new PMaC project with profile ADRs and multi-agent platform adapters |
| `spec-ops profiles list` | None | List available architectural profiles |
| `spec-ops profiles apply` | `<PROFILE_NAME>` | Apply architectural profile to current repository |
| `spec-ops profiles sync` | `<PROFILE_NAME>` | Synchronize or restore architectural profile artifacts |
| `spec-ops scaffold agents` | None | Regenerate AGENTS.md constitution from installed profiles |
| `spec-ops health` | `[--security]` | Verify file length limits and PRIORITY sync |
| `spec-ops stats` | `[--cache]` | Report project statistics and entity counts |
| `spec-ops parse` | `PATH` | Parse specification file with resilient AST diagnostics |
| `spec-ops graph compile` | `[--incremental] [--json] [--force-cold]` | Compile repository relational knowledge graph backed by content-addressed cache |
| `spec-ops prd create` | `[--title TITLE] [--persona PERSONA] [--component COMPONENT] [--summary SUMMARY] [--stage STAGE]` | Scaffold a new PRD specification |
| `spec-ops prd new` | `[--title TITLE] [--persona PERSONA] [--component COMPONENT] [--friction FRICTION] [--good GOOD] [--anti-goals ANTI_GOALS] [--outcomes OUTCOMES] [--non-interactive]` | Interactively scaffold a new PRD specification in idea stage |
| `spec-ops prd lint` | `[PATH]` | Lint PRD markdown files for mandatory sections and falsifiable outcomes |
| `spec-ops prd promote` | `<PRD_ID> --stage STAGE` | Advance PRD through lifecycle stage gates |
| `spec-ops prd ship` | `<PRD_ID>` | Transition accepted PRD to shipped upon backlog completion |
| `spec-ops prd audit` | None | Audit PRD lifecycle statuses |
| `spec-ops prd decompose` | `<PRD_ID> [--no-spike] [--by-outcomes] [--diff]` | Decompose PRD into vertical slices |
| `spec-ops curate` | `[--infer] [--dry-run] [--model MODEL]` | Perform JIT backlog refinement, cognitive drift reconciliation, and scope slicing |
| `spec-ops visualizer` | `[--serve] [--build OUT] [--port PORT]` | Interactive 2D graph visualizer |
| `spec-ops worker` | `[ACTION] [TASK_ID] [--task TASK_ID] [--auto] [--drain] [--max-concurrency N] [--max-tasks M] [--dry-run] [--no-merge] [--no-review] [--skip-review]` | Execute backlog task in isolated worktree with concurrent review |
| `spec-ops cycle` | `[--max-tasks N] [--max-concurrency N] [--drain] [--dry-run] [--no-merge] [--build-docs] [--no-review] [--skip-review]` | Run end-to-end autonomous development cycle |
| `spec-ops rescue` | `[TASK_ID] [--list] [--complete] [--discard] [--prune]` | Inspect and recover stalled or failed autonomous worktrees |
| `spec-ops spike create` | `--name NAME --question QUESTION [--timebox TIMEBOX] [--task TASK_ID] [--prd PRD_ID]` | Author a new architectural spike task and isolated test harness |
| `spec-ops spike start` | `<SPIKE_ID> [--hypothesis HYPOTHESIS] [--timebox TIMEBOX]` | Instantiate disposable sandboxed spike worktree |
| `spec-ops spike check` | `[SPIKE_ID] [--elapsed ELAPSED]` | Check spike timebox and write isolation |
| `spec-ops spike preflight` | `[SPIKE_ID]` | Enforce in-worktree write isolation preflight hook |
| `spec-ops spike graduate` | `<SPIKE_ID> --result {{proven,disproven}} [--title TITLE] [--notes NOTES] [--findings FINDINGS] [--status STATUS]` | Graduate empirical spike findings into an Architectural Decision Record |
| `spec-ops tui` | `[--once] [--view {{overview,backlog,tree,health}}]` | Launch interactive Terminal UI (TUI) dashboard |
| `spec-ops queue complete` | `<TASK_ID> [--base BASE]` | Gate and complete task integration under merge lock |
| `spec-ops queue tree` | `[--task TASK] [--direction {{blocks,blocked-by}}] [--reverse] [--waves] [--all] [--json]` | Display task dependency tree, execution waves, and blockers |
| `spec-ops queue block` | `<TASK_ID> --question QUESTION [--type {{unknown,spike_needed,external,dependency}}] [--spike] [--timebox TIMEBOX] [--raised-by RAISED_BY]` | Mark a task as blocked by an unknown question or impediment |
| `spec-ops queue unblock` | `<TASK_ID> --resolution RESOLUTION [--adr ADR]` | Resolve an unknown/blocker and restore ready/proposed state |
| `spec-ops queue blockers` | `[--json]` | List all currently blocked tasks, open questions, and linked spikes |
| `spec-ops security verify-lock` | `[--path PATH]` | Verify supply-chain lockfile cryptographic hashes and pinning |
| `spec-ops audit dependencies` | `[--path PATH] [--offline]` | Scan direct and transitive dependencies for High/Critical CVEs and enforce license allowlists |
| `spec-ops review sign` | `<TASK_ID> --identity IDENTITY` | Cryptographically verify reviewer identity against keyring and record dual-custody review sign-off |
| `spec-ops docs build` | `[--out OUT_DIR] [--base-url BASE_URL]` | Compile Diataxis documentation static site and embedded 2D visualizer |
| `spec-ops docs audit` | `[--dir DIR] [--strict]` | Audit Diataxis quadrant structure, CLI drift, and documentation code snippets |
"""

DEFAULT_EXPLANATION_PMAC = """# Project Management as Code (PMaC)

{project_name} uses SpecOps to version-lock all project specifications directly in git.

## Why Specification as Code?
1. **Zero Context Drift**: Specifications, user stories, and tasks live in the exact same git commit history as implementation code.
2. **Thin Vertical Slicing**: Features are built through single-pass vertical slices rather than speculative horizontal layers.
3. **Hard Invariants**: Source files remain strictly under 500 lines to prevent monolithic file rot.
"""

DEFAULT_CONTRIBUTING_MD = """# Contributing to {project_name} Documentation

We adhere strictly to the **Diataxis documentation framework**:

1. **Tutorials (`docs/tutorials/`)**: Learning-oriented lessons for beginners.
2. **How-To Guides (`docs/how-to/`)**: Task-oriented recipes to solve real-world problems.
3. **Reference (`docs/reference/`)**: Information-oriented technical descriptions.
4. **Explanation (`docs/explanation/`)**: Understanding-oriented discussions of architecture and decisions.

## Invariants
- Keep all documentation synchronized with running code.
- Run `uv run spec-ops docs build` to verify that all pages compile cleanly.
"""


def scaffold_diataxis_docs(root_dir: Path, project_name: str, agents_md_content: str | None = None) -> list[Path]:
    """Scaffolds the 4-quadrant Diataxis documentation tree and starter files."""
    docs_dir = root_dir / "docs"
    created: list[Path] = []

    def _write_doc(rel_path: Path, content: str) -> None:
        full_path = docs_dir / rel_path
        full_path.parent.mkdir(parents=True, exist_ok=True)
        if not full_path.exists():
            full_path.write_text(content.strip() + "\n", encoding="utf-8")
            created.append(full_path)

    # 1. Directories
    for d in ["tutorials", "how-to", "reference", "explanation"]:
        (docs_dir / d).mkdir(parents=True, exist_ok=True)

    # 2. Starter files
    _write_doc(Path("index.md"), DEFAULT_INDEX_MD.format(project_name=project_name))
    _write_doc(Path("tutorials") / "01-getting-started.md", DEFAULT_TUTORIAL_GETTING_STARTED.format(project_name=project_name))
    _write_doc(Path("how-to") / "bootstrap-project.md", DEFAULT_HOWTO_BOOTSTRAP.format(project_name=project_name))
    _write_doc(Path("reference") / "cli.md", DEFAULT_REFERENCE_CLI.format(project_name=project_name))
    _write_doc(Path("explanation") / "project-management-as-code.md", DEFAULT_EXPLANATION_PMAC.format(project_name=project_name))
    _write_doc(Path("contributing.md"), DEFAULT_CONTRIBUTING_MD.format(project_name=project_name))

    # 3. Synchronize operating-manual.md from AGENTS.md
    manual_path = docs_dir / "operating-manual.md"
    if not manual_path.exists():
        if agents_md_content:
            clean_content = re.sub(r"\]\(docs/", "](", agents_md_content)
            manual_path.write_text(clean_content.strip() + "\n", encoding="utf-8")
            created.append(manual_path)
        elif (root_dir / "AGENTS.md").exists():
            clean_content = re.sub(r"\]\(docs/", "](", (root_dir / "AGENTS.md").read_text(encoding="utf-8"))
            manual_path.write_text(clean_content.strip() + "\n", encoding="utf-8")
            created.append(manual_path)

    return created
