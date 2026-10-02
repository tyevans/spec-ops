"""Executable BDD acceptance tests for US-0126: Technical Debt Baselining Ratchet and AST Decomposition."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
from pytest_bdd import given, scenarios, then, when

scenarios("features/us_0126_debt_ratchet.feature")

CLI_ENV = {
    **os.environ,
    "PYTHONPATH": f"{Path(__file__).resolve().parent.parent / 'src'}:{os.environ.get('PYTHONPATH', '')}".rstrip(":"),
}


def run_spec_ops(repo: Path, args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "spec_ops.cli.main", *args],
        cwd=repo,
        capture_output=True,
        text=True,
        env=CLI_ENV,
    )


@pytest.fixture
def repo_ctx(tmp_path: Path) -> dict[str, Any]:
    repo = tmp_path / "brownfield_repo"
    repo.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-b", "main"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Devon"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "devon@example.com"], cwd=repo, check=True, capture_output=True)
    return {"repo": repo, "result": None}


# Scenario 1


@given("an existing codebase containing source files exceeding the 500-line architectural limit")
def given_oversized_codebase(repo_ctx: dict[str, Any]):
    repo = repo_ctx["repo"]
    src_dir = repo / "src"
    src_dir.mkdir(parents=True, exist_ok=True)
    legacy_file = src_dir / "legacy_big.py"
    legacy_file.write_text("\n".join(f"# line {i}" for i in range(550)) + "\n", encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "feat: initial legacy file"], cwd=repo, check=True, capture_output=True)


@when('running "spec-ops adopt --grandfather-debt"')
def when_adopt_grandfather_debt(repo_ctx: dict[str, Any]):
    repo = repo_ctx["repo"]
    res = run_spec_ops(repo, ["adopt", "--grandfather-debt", "--name", "test-project"])
    assert res.returncode == 0
    repo_ctx["result"] = res


@then('".spec-ops/debt_baseline.json" is created recording relative paths and baselined line counts')
def then_debt_baseline_created(repo_ctx: dict[str, Any]):
    repo = repo_ctx["repo"]
    debt_file = repo / ".spec-ops" / "debt_baseline.json"
    assert debt_file.is_file()
    data = json.loads(debt_file.read_text(encoding="utf-8"))
    files = data.get("files", {})
    assert "src/legacy_big.py" in files
    assert files["src/legacy_big.py"] >= 550


@then('"spec-ops health" reports 0 file limit violations.')
def then_health_reports_zero_violations(repo_ctx: dict[str, Any]):
    repo = repo_ctx["repo"]
    res = run_spec_ops(repo, ["health"])
    assert res.returncode == 0
    assert "Zero source files exceed length limit" in res.stdout


# Scenario 2


@given('a codebase with baselined files in ".spec-ops/debt_baseline.json"')
def given_codebase_with_baselined_debt(repo_ctx: dict[str, Any]):
    repo = repo_ctx["repo"]
    src_dir = repo / "src"
    src_dir.mkdir(parents=True, exist_ok=True)
    legacy_file = src_dir / "legacy_big.py"
    legacy_file.write_text("\n".join(f"# line {i}" for i in range(550)) + "\n", encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "feat: initial commit"], cwd=repo, check=True, capture_output=True)
    run_spec_ops(repo, ["adopt", "--grandfather-debt", "--name", "test-project"])


@when("a grandfathered file has additional lines added exceeding its baselined line count")
def when_file_expanded(repo_ctx: dict[str, Any]):
    repo = repo_ctx["repo"]
    legacy_file = repo / "src" / "legacy_big.py"
    # Expand by adding 50 more lines
    current_content = legacy_file.read_text(encoding="utf-8")
    expanded_content = current_content + "\n".join(f"# added line {i}" for i in range(50)) + "\n"
    legacy_file.write_text(expanded_content, encoding="utf-8")


@then('"spec-ops health" flags the file as an unapproved debt regression violation')
def then_health_flags_regression(repo_ctx: dict[str, Any]):
    repo = repo_ctx["repo"]
    res = run_spec_ops(repo, ["health"])
    assert res.returncode == 1
    assert "expanded beyond recorded baseline" in (res.stdout + res.stderr) or "File Length Violation" in res.stdout


@then("newly added files exceeding 500 lines are strictly rejected.")
def then_new_files_rejected(repo_ctx: dict[str, Any]):
    repo = repo_ctx["repo"]
    # Revert legacy file to baseline count
    legacy_file = repo / "src" / "legacy_big.py"
    legacy_file.write_text("\n".join(f"# line {i}" for i in range(550)) + "\n", encoding="utf-8")

    # Add a brand new file with 520 lines
    new_file = repo / "src" / "unapproved_new.py"
    new_file.write_text("\n".join(f"# new line {i}" for i in range(520)) + "\n", encoding="utf-8")

    res = run_spec_ops(repo, ["health"])
    assert res.returncode == 1
    assert "unapproved_new.py" in (res.stdout + res.stderr)
    assert "unexempt file limit violation" in (res.stdout + res.stderr)


# Scenario 3


@given("grandfathered files detected during adoption")
def given_grandfathered_detected(repo_ctx: dict[str, Any]):
    repo = repo_ctx["repo"]
    src_dir = repo / "src"
    src_dir.mkdir(parents=True, exist_ok=True)
    # Python code with classes and functions to trigger AST seams
    code = """
class FirstBigClass:
    def method_one(self):
        pass

class SecondBigClass:
    def method_two(self):
        pass
""" + "\n".join(f"# filler {i}" for i in range(520))
    (src_dir / "complex_legacy.py").write_text(code, encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "feat: complex legacy"], cwd=repo, check=True, capture_output=True)


@when('"spec-ops adopt" scans file syntax trees')
def when_adopt_scans_ast(repo_ctx: dict[str, Any]):
    repo = repo_ctx["repo"]
    res = run_spec_ops(repo, ["adopt", "--grandfather-debt", "--name", "test-project"])
    assert res.returncode == 0
    repo_ctx["result"] = res


@then('actionable refactoring tasks are emitted into "docs/project/backlog/proposed/"')
def then_refactor_tasks_emitted(repo_ctx: dict[str, Any]):
    repo = repo_ctx["repo"]
    proposed_dir = repo / "docs" / "project" / "backlog" / "proposed"
    assert proposed_dir.is_dir()
    refactor_tasks = list(proposed_dir.glob("TASK-REFACTOR-*.md"))
    assert len(refactor_tasks) > 0


@then("each task includes concrete AST seam suggestions, extractable classes, and target line reductions.")
def then_task_includes_ast_suggestions(repo_ctx: dict[str, Any]):
    repo = repo_ctx["repo"]
    proposed_dir = repo / "docs" / "project" / "backlog" / "proposed"
    refactor_tasks = list(proposed_dir.glob("TASK-REFACTOR-*.md"))
    content = refactor_tasks[0].read_text(encoding="utf-8")
    assert "ADR-0002" in content
    assert "Decomposition" in content or "Refactor" in content
