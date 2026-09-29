"""Executable BDD scenarios using pytest-bdd for SpecOps user stories."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

scenarios("features/us_0001_project_init.feature", "features/us_0002_health_check.feature")


@pytest.fixture
def bdd_context(tmp_path: Path) -> dict[str, Any]:
    """Shared state container for BDD scenarios."""
    return {"dir": tmp_path, "res": None}


# --- US-0001 Steps ---


@given("a blank project directory")
def blank_project_directory(bdd_context: dict[str, Any]):
    # tmp_path is already empty
    assert len(list(bdd_context["dir"].iterdir())) == 0


@when('the engineer executes "spec-ops init --name TestApp --profile core,bdd,ddd"')
def execute_init_command(bdd_context: dict[str, Any]):
    target_dir = bdd_context["dir"]
    res = subprocess.run(
        [
            sys.executable,
            "-m",
            "spec_ops.cli.main",
            "init",
            "--name",
            "TestApp",
            "--dir",
            str(target_dir),
            "--profile",
            "core,bdd,ddd",
        ],
        capture_output=True,
        text=True,
    )
    bdd_context["res"] = res
    assert res.returncode == 0


@then('the directory structure "docs/project/" is created with adrs, product, user_stories, and backlog')
def verify_directory_structure(bdd_context: dict[str, Any]):
    root = bdd_context["dir"]
    docs_proj = root / "docs" / "project"
    assert (docs_proj / "adrs" / "accepted").is_dir()
    assert (docs_proj / "product" / "accepted").is_dir()
    assert (docs_proj / "user_stories" / "accepted").is_dir()
    assert (docs_proj / "backlog" / "refined").is_dir()


@then('7 baseline ADRs are installed into "docs/project/adrs/accepted/"')
def verify_baseline_adrs(bdd_context: dict[str, Any]):
    root = bdd_context["dir"]
    adrs = list((root / "docs" / "project" / "adrs" / "accepted").glob("*.md"))
    assert len(adrs) == 7


@then('"specops.toml" is generated with matching project settings')
def verify_specops_toml(bdd_context: dict[str, Any]):
    root = bdd_context["dir"]
    toml_path = root / "specops.toml"
    assert toml_path.is_file()
    content = toml_path.read_text(encoding="utf-8")
    assert 'name = "TestApp"' in content


# --- US-0002 Steps ---


@given("a repository where all source files contain fewer than 500 lines")
def clean_repository_under_limit(bdd_context: dict[str, Any]):
    target_dir = bdd_context["dir"]
    res = subprocess.run(
        [sys.executable, "-m", "spec_ops.cli.main", "init", "--name", "HealthApp", "--dir", str(target_dir)],
        capture_output=True,
        text=True,
    )
    assert res.returncode == 0
    # Add a normal compliant source file
    src_dir = target_dir / "src"
    src_dir.mkdir(parents=True, exist_ok=True)
    (src_dir / "app.py").write_text("# clean small module\n" * 50, encoding="utf-8")


@given("PRIORITY.md accurately indexes all tasks across complete, refined, and proposed directories")
def priority_md_accurately_indexed(bdd_context: dict[str, Any]):
    priority_file = bdd_context["dir"] / "docs" / "project" / "backlog" / "PRIORITY.md"
    assert priority_file.is_file()


@when('the developer runs "spec-ops health"')
def run_spec_ops_health(bdd_context: dict[str, Any]):
    target_dir = bdd_context["dir"]
    res = subprocess.run(
        [sys.executable, "-m", "spec_ops.cli.main", "health"],
        cwd=str(target_dir),
        capture_output=True,
        text=True,
    )
    bdd_context["res"] = res


@then("the command exits with code 0")
def verify_exit_code_zero(bdd_context: dict[str, Any]):
    assert bdd_context["res"].returncode == 0


@then('reports "Invariant Met: Zero source files exceed length limit"')
def verify_health_invariant_met(bdd_context: dict[str, Any]):
    assert "Invariant Met: Zero source files exceed length limit" in bdd_context["res"].stdout


@given("a source file that expands beyond 500 lines")
def monolithic_source_file_beyond_limit(bdd_context: dict[str, Any]):
    target_dir = bdd_context["dir"]
    subprocess.run(
        [sys.executable, "-m", "spec_ops.cli.main", "init", "--name", "MonolithApp", "--dir", str(target_dir)],
        capture_output=True,
        text=True,
        check=True,
    )
    src_dir = target_dir / "src"
    src_dir.mkdir(parents=True, exist_ok=True)
    violating_file = src_dir / "monolith.py"
    violating_file.write_text("# line\n" * 550, encoding="utf-8")
    bdd_context["violating_file"] = violating_file


@when('the preflight command runs "spec-ops health"')
def run_preflight_health_command(bdd_context: dict[str, Any]):
    target_dir = bdd_context["dir"]
    res = subprocess.run(
        [sys.executable, "-m", "spec_ops.cli.main", "health"],
        cwd=str(target_dir),
        capture_output=True,
        text=True,
    )
    bdd_context["res"] = res


@then("the command exits with code 1")
def verify_exit_code_one(bdd_context: dict[str, Any]):
    assert bdd_context["res"].returncode == 1


@then("lists the violating file path, exact line count, and configured limit")
def verify_violation_diagnostics(bdd_context: dict[str, Any]):
    stdout = bdd_context["res"].stdout
    assert "monolith.py" in stdout
    assert "550 lines" in stdout
    assert "limit: 500" in stdout
