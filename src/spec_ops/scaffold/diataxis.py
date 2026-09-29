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

Authoritative reference for the `{project_name}` command-line interface.

## Commands

- `spec-ops health`: Verify file length invariants (<500 lines) and PRIORITY.md sync.
- `spec-ops stats`: Inspect project entity metrics and buffer capacity.
- `spec-ops prd create <id>`: Scaffold a new PRD specification.
- `spec-ops prd decompose <id>`: Decompose an accepted PRD into stories and tasks.
- `spec-ops curate`: Refine backlog tasks to maintain the target buffer.
- `spec-ops worker`: Execute the next ready task in an isolated worktree.
- `spec-ops docs build`: Compile Diataxis documentation static site and embedded visualizer.
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
