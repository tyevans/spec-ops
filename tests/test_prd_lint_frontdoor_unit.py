"""Unit tests for PRD Lint CLI frontdoor runner and handlers."""

from __future__ import annotations

import io
import json
import sys
from pathlib import Path

import pytest

from spec_ops.cli.main import main
from spec_ops.config.loader import load_config
from spec_ops.prd.lint_runner import run_prd_lint
from spec_ops.scaffold.init import init_project


@pytest.fixture
def clean_project(tmp_path: Path):
    init_project(tmp_path, name="LintCliProject")
    config = load_config(root_dir=tmp_path)
    return config, tmp_path


def test_run_prd_lint_empty_repo(clean_project):
    config, tmp_path = clean_project
    # Delete sample PRDs if any
    prd_dir = tmp_path / "docs" / "project" / "product"
    if prd_dir.exists():
        for f in prd_dir.rglob("*.md"):
            if f.name != "REGISTRY.md":
                f.unlink()

    code = run_prd_lint(config)
    assert code == 0


def test_run_prd_lint_nonexistent_target(clean_project):
    config, _ = clean_project
    code = run_prd_lint(config, target_path="nonexistent-prd.md")
    assert code == 1


def test_run_prd_lint_single_file_json(clean_project, capsys):
    config, tmp_path = clean_project
    prd_file = tmp_path / "docs" / "project" / "product" / "idea" / "prd-0080.md"
    prd_file.parent.mkdir(parents=True, exist_ok=True)
    prd_file.write_text(
        """---
id: PRD-0080
title: Test
status: Idea
target_persona: Alex
---
# PRD-0080
## Problem Statement
P
## What good looks like
G
## What this does not do
N
## Checkable Outcomes
- Fast response
""",
        encoding="utf-8",
    )

    code = run_prd_lint(config, target_path=str(prd_file), json_output=True)
    captured = capsys.readouterr().out
    assert code == 1
    data = json.loads(captured)
    assert data["total_errors"] >= 1
    assert data["unfalsifiable_count"] == 1


def test_run_prd_lint_remediate_flow(clean_project):
    config, tmp_path = clean_project
    prd_file = tmp_path / "docs" / "project" / "product" / "idea" / "prd-0081.md"
    prd_file.parent.mkdir(parents=True, exist_ok=True)
    prd_file.write_text(
        """---
id: PRD-0081
title: Remediate Flow
status: Idea
target_persona: Alex
---
# PRD-0081
## Problem Statement
P
## What good looks like
G
## What this does not do
N
## Checkable Outcomes
- The UI is intuitive and modern
""",
        encoding="utf-8",
    )

    code = run_prd_lint(config, target_path=str(prd_file), remediate=True)
    assert code == 0
    remediated_text = prd_file.read_text(encoding="utf-8")
    assert "intuitive" not in remediated_text.lower()
    assert "modern" not in remediated_text.lower()


def test_main_cli_invocation(clean_project, monkeypatch):
    config, tmp_path = clean_project
    monkeypatch.chdir(tmp_path)
    prd_file = tmp_path / "docs" / "project" / "product" / "idea" / "prd-0082.md"
    prd_file.parent.mkdir(parents=True, exist_ok=True)
    prd_file.write_text(
        """---
id: PRD-0082
title: CLI Dispatch
status: Idea
target_persona: Alex
---
# PRD-0082
## Problem Statement
P
## What good looks like
G
## What this does not do
N
## Checkable Outcomes
- Response latency under 50ms
""",
        encoding="utf-8",
    )

    code = main(["prd", "lint"])
    assert code == 0
