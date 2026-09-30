"""Executable BDD scenarios using pytest-bdd for SpecOps user stories."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Any

SRC_DIR = str(Path(__file__).resolve().parent.parent / "src")
CLI_ENV = {**os.environ, "PYTHONPATH": f"{SRC_DIR}:{os.environ.get('PYTHONPATH', '')}".rstrip(":")}

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

scenarios(
    "features/us_0001_project_init.feature",
    "features/us_0002_health_check.feature",
    "features/us_0007_multi_agent_adapters.feature",
    "features/us_0008_diataxis_audit.feature",
)




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


# --- US-0007 Steps ---


@when('the engineer executes "spec-ops init --name PlatformApp --agent antigravity,claude,cursor"')
def execute_init_platform_command(bdd_context: dict[str, Any]):
    target_dir = bdd_context["dir"]
    res = subprocess.run(
        [
            sys.executable,
            "-m",
            "spec_ops.cli.main",
            "init",
            "--name",
            "PlatformApp",
            "--dir",
            str(target_dir),
            "--agent",
            "antigravity,claude,cursor",
        ],
        capture_output=True,
        text=True,
        env=CLI_ENV,
    )
    bdd_context["res"] = res
    assert res.returncode == 0


@then('"CLAUDE.md" is generated for Claude Code')
def verify_claude_md(bdd_context: dict[str, Any]):
    root = bdd_context["dir"]
    claude_file = root / "CLAUDE.md"
    assert claude_file.is_file()
    content = claude_file.read_text(encoding="utf-8")
    assert "Claude Code Operating Guidelines" in content


@then('".cursorrules" is generated for Cursor')
def verify_cursorrules(bdd_context: dict[str, Any]):
    root = bdd_context["dir"]
    cursor_file = root / ".cursorrules"
    assert cursor_file.is_file()
    content = cursor_file.read_text(encoding="utf-8")
    assert "Cursor Rules" in content


@then('"GEMINI.md" and slash command skills are generated for Antigravity')
def verify_antigravity(bdd_context: dict[str, Any]):
    root = bdd_context["dir"]
    gemini_file = root / "GEMINI.md"
    assert gemini_file.is_file()
    content = gemini_file.read_text(encoding="utf-8")
    assert "Antigravity Operating Rules" in content

    skills_dir = root / ".agents" / "skills"
    assert (skills_dir / "curate" / "SKILL.md").is_file()
    assert (skills_dir / "health" / "SKILL.md").is_file()
    assert (skills_dir / "worker" / "SKILL.md").is_file()
    assert (skills_dir / "spec-ops" / "SKILL.md").is_file()


@then("all generated files contain the hard invariant file limit under 500 lines")
def verify_hard_invariants(bdd_context: dict[str, Any]):
    root = bdd_context["dir"]
    for path in [root / "CLAUDE.md", root / ".cursorrules", root / "GEMINI.md"]:
        content = path.read_text(encoding="utf-8")
        assert "500 lines" in content


# --- US-0008 Steps ---


@given("a project initialized with SpecOps and Diataxis documentation")
def project_init_diataxis(bdd_context: dict[str, Any]):
    target_dir = bdd_context["dir"]
    res = subprocess.run(
        [
            sys.executable,
            "-m",
            "spec_ops.cli.main",
            "init",
            "--name",
            "DocAuditApp",
            "--dir",
            str(target_dir),
            "--diataxis",
        ],
        capture_output=True,
        text=True,
        env=CLI_ENV,
    )
    assert res.returncode == 0


@given('an unapproved documentation file is added to "docs/misc/random.md"')
def add_unapproved_doc(bdd_context: dict[str, Any]):
    target_dir = bdd_context["dir"]
    unapproved_file = target_dir / "docs" / "misc" / "random.md"
    unapproved_file.parent.mkdir(parents=True, exist_ok=True)
    unapproved_file.write_text("# Random Unapproved Doc\n", encoding="utf-8")


@when('the developer executes "spec-ops docs audit"')
def execute_docs_audit(bdd_context: dict[str, Any]):
    target_dir = bdd_context["dir"]
    res = subprocess.run(
        [sys.executable, "-m", "spec_ops.cli.main", "docs", "audit"],
        cwd=str(target_dir),
        capture_output=True,
        text=True,
        env=CLI_ENV,
    )
    bdd_context["res"] = res


@then("the audit command exits with code 0")
def audit_exit_code_zero(bdd_context: dict[str, Any]):
    assert bdd_context["res"].returncode == 0


@then("reports that all 5 approved quadrants are verified")
def audit_verified_quadrants(bdd_context: dict[str, Any]):
    assert "All 5 approved quadrants verified" in bdd_context["res"].stdout


@then("reports status CLEAN with 0 errors")
def audit_status_clean(bdd_context: dict[str, Any]):
    assert "Status: ✅ CLEAN" in bdd_context["res"].stdout


@then("the audit command exits with code 1")
def audit_exit_code_one(bdd_context: dict[str, Any]):
    assert bdd_context["res"].returncode == 1


@then("reports status DRIFT DETECTED")
def audit_status_drift(bdd_context: dict[str, Any]):
    assert "Status: ❌ DRIFT DETECTED" in bdd_context["res"].stdout


@then('identifies the unapproved quadrant "misc"')
def audit_identifies_unapproved(bdd_context: dict[str, Any]):
    assert "misc" in bdd_context["res"].stdout

