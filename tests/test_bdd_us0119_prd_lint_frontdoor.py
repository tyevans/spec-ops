"""BDD step definitions for US-0119: PRD Lint Blackbox Frontdoor Verification."""

from __future__ import annotations

import io
import json
import sys
from pathlib import Path
from typing import Any

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from spec_ops.cli.main import main
from spec_ops.scaffold.init import init_project

scenarios("features/us_0119_prd_lint_frontdoor.feature")


@pytest.fixture
def bdd_ctx(tmp_path: Path) -> dict[str, Any]:
    init_project(tmp_path, name="FrontdoorLintProject")
    return {"tmp_path": tmp_path}


@given("a repository with valid PRD specifications")
def repo_with_valid_prds(bdd_ctx: dict[str, Any]):
    tmp_path: Path = bdd_ctx["tmp_path"]
    prd_dir = tmp_path / "docs" / "project" / "product" / "idea"
    prd_dir.mkdir(parents=True, exist_ok=True)
    content = """---
id: PRD-0070
title: Valid Specification
status: Idea
target_persona: Alex
component: prd
---

# PRD-0070: Valid Specification

## Problem Statement
Verifiable problem statement.

## What good looks like
Deterministic tests.

## What this does not do
Does not introduce delays.

## Checkable Outcomes
- All endpoints respond within 150ms
"""
    (prd_dir / "prd-0070.md").write_text(content, encoding="utf-8")


@given("a repository with PRD specifications containing subjective adjectives")
def repo_with_subjective_prds(bdd_ctx: dict[str, Any]):
    tmp_path: Path = bdd_ctx["tmp_path"]
    prd_dir = tmp_path / "docs" / "project" / "product" / "idea"
    prd_dir.mkdir(parents=True, exist_ok=True)
    content = """---
id: PRD-0071
title: Subjective Specification
status: Idea
target_persona: Alex
component: prd
---

# PRD-0071: Subjective Specification

## Problem Statement
Needs improvement.

## What good looks like
Better flow.

## What this does not do
None.

## Checkable Outcomes
- The web app is ultra fast and intuitive
"""
    (prd_dir / "prd-0071.md").write_text(content, encoding="utf-8")


@given("a repository with PRD specifications needing quality remediation")
def repo_with_remediation_prds(bdd_ctx: dict[str, Any]):
    tmp_path: Path = bdd_ctx["tmp_path"]
    prd_dir = tmp_path / "docs" / "project" / "product" / "idea"
    prd_dir.mkdir(parents=True, exist_ok=True)
    content = """---
id: PRD-0072
title: Needs Remediation
status: Idea
target_persona: Alex
component: prd
---

# PRD-0072: Needs Remediation

## Problem Statement
A problem statement.

## What good looks like
Falsifiable requirements.

## What this does not do
Does not fail silently.

## Checkable Outcomes
- The CLI tool is simple and fast
"""
    (prd_dir / "prd-0072.md").write_text(content, encoding="utf-8")


@given("a repository with PRD specifications")
def repo_generic_prds(bdd_ctx: dict[str, Any]):
    tmp_path: Path = bdd_ctx["tmp_path"]
    prd_dir = tmp_path / "docs" / "project" / "product" / "idea"
    prd_dir.mkdir(parents=True, exist_ok=True)
    content = """---
id: PRD-0073
title: Generic Specification
status: Idea
target_persona: Alex
component: prd
---

# PRD-0073: Generic Specification

## Problem Statement
P
## What good looks like
G
## What this does not do
N
## Checkable Outcomes
- Deterministic output produced
"""
    (prd_dir / "prd-0073.md").write_text(content, encoding="utf-8")


@when(parsers.parse('the user runs "{command_str}"'))
def run_cli_command(command_str: str, bdd_ctx: dict[str, Any], monkeypatch: pytest.MonkeyPatch):
    tmp_path: Path = bdd_ctx["tmp_path"]
    monkeypatch.chdir(tmp_path)
    args = command_str.split()[1:]  # skip "spec-ops"

    stdout_capture = io.StringIO()
    stderr_capture = io.StringIO()
    monkeypatch.setattr(sys, "stdout", stdout_capture)
    monkeypatch.setattr(sys, "stderr", stderr_capture)

    exit_code = main(args)
    bdd_ctx["exit_code"] = exit_code
    bdd_ctx["stdout"] = stdout_capture.getvalue()
    bdd_ctx["stderr"] = stderr_capture.getvalue()


@then(parsers.parse("the process exit code is {code:d}"))
def verify_exit_code(code: int, bdd_ctx: dict[str, Any]):
    assert bdd_ctx["exit_code"] == code, f"Unexpected code {bdd_ctx['exit_code']}, output: {bdd_ctx['stdout']}"


@then("the output indicates all outcomes are falsifiable and valid")
def verify_clean_output(bdd_ctx: dict[str, Any]):
    out = bdd_ctx["stdout"]
    assert "0 errors" in out or "valid" in out.lower()
    assert "falsifiable" in out.lower()


@then("line-level diagnostics, suggested rewrites, and remediation hints are displayed")
def verify_diagnostics_output(bdd_ctx: dict[str, Any]):
    out = bdd_ctx["stdout"]
    assert "PRD-LINT-002" in out
    assert "Line" in out
    assert "Hint:" in out


@then("the files on disk have their subjective terms replaced with falsifiable criteria")
def verify_remediated_disk_file(bdd_ctx: dict[str, Any]):
    tmp_path: Path = bdd_ctx["tmp_path"]
    target_file = tmp_path / "docs" / "project" / "product" / "idea" / "prd-0072.md"
    content = target_file.read_text(encoding="utf-8")
    assert "fast" not in content.lower()


@then("the output is valid JSON containing reports and summary statistics")
def verify_json_output(bdd_ctx: dict[str, Any]):
    out = bdd_ctx["stdout"]
    data = json.loads(out)
    assert "total_files" in data
    assert "reports" in data
    assert data["total_files"] >= 1
