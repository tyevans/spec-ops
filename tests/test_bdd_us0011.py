"""Executable BDD acceptance tests for US-0011: Brownfield Codebase Adoption and Anti-Rot Invariant Baseline."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
from pytest_bdd import given, scenarios, then, when

scenarios("features/us_0011_brownfield_adoption.feature")

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
def repo_context(tmp_path: Path) -> dict[str, Any]:
    repo = tmp_path / "legacy_repo"
    repo.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-b", "main"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Alex"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "alex@example.com"], cwd=repo, check=True, capture_output=True)
    return {"repo": repo, "result": None, "files": []}


@given("an existing git repository containing source files where 3 files exceed 500 lines")
def given_repo_with_oversized_files(repo_context: dict[str, Any]):
    repo = repo_context["repo"]
    src_dir = repo / "src"
    src_dir.mkdir(parents=True, exist_ok=True)

    files = ["src/legacy_one.py", "src/legacy_two.py", "src/legacy_three.py"]
    for idx, f_path in enumerate(files, start=1):
        target = repo / f_path
        content = "\n".join([f"# Line {i} of legacy module {idx}" for i in range(520 + idx * 10)])
        target.write_text(content + "\n", encoding="utf-8")

    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "chore: legacy source import"], cwd=repo, check=True, capture_output=True)
    repo_context["files"] = files


@when('the architect runs "spec-ops adopt --profile core,bdd,ddd --name LegacyService"')
def when_run_adopt(repo_context: dict[str, Any]):
    repo = repo_context["repo"]
    result = run_spec_ops(repo, ["adopt", "--profile", "core,bdd,ddd", "--name", "LegacyService"])
    repo_context["result"] = result


@then('the directory "docs/project/" is created with adrs, product, user_stories, and backlog structures')
def then_docs_project_created(repo_context: dict[str, Any]):
    repo = repo_context["repo"]
    docs = repo / "docs" / "project"
    assert (docs / "adrs").is_dir()
    assert (docs / "product").is_dir()
    assert (docs / "user_stories").is_dir()
    assert (docs / "backlog").is_dir()


@then('And "specops.toml" is generated containing an "invariants.file_limits.grandfathered" list with the 3 violating files')
@then('"specops.toml" is generated containing an "invariants.file_limits.grandfathered" list with the 3 violating files')
def then_specops_toml_grandfathered(repo_context: dict[str, Any]):
    repo = repo_context["repo"]
    toml_path = repo / "specops.toml"
    assert toml_path.is_file()
    content = toml_path.read_text(encoding="utf-8")
    assert "[invariants.file_limits]" in content
    assert "src/legacy_one.py" in content
    assert "src/legacy_two.py" in content
    assert "src/legacy_three.py" in content


@then('And an "AGENTS.md" constitution is generated at the repository root')
@then('an "AGENTS.md" constitution is generated at the repository root')
def then_agents_md_generated(repo_context: dict[str, Any]):
    repo = repo_context["repo"]
    agents_md = repo / "AGENTS.md"
    assert agents_md.is_file()
    assert "LegacyService" in agents_md.read_text(encoding="utf-8")


@then('And the command exits with code 0 reporting "Adoption complete: 3 legacy files grandfathered into technical debt baseline"')
@then('the command exits with code 0 reporting "Adoption complete: 3 legacy files grandfathered into technical debt baseline"')
def then_adopt_exits_0(repo_context: dict[str, Any]):
    res: subprocess.CompletedProcess[str] = repo_context["result"]
    assert res.returncode == 0
    assert "Adoption complete: 3 legacy files grandfathered into technical debt baseline" in res.stdout


# Scenario 2
@given('a repository initialized via "spec-ops adopt" with 3 grandfathered legacy files')
def given_initialized_via_adopt(repo_context: dict[str, Any]):
    given_repo_with_oversized_files(repo_context)
    when_run_adopt(repo_context)
    then_adopt_exits_0(repo_context)


@when('a developer adds a new file "src/new_service.py" containing 520 lines')
def when_add_new_oversized_file(repo_context: dict[str, Any]):
    repo = repo_context["repo"]
    new_file = repo / "src" / "new_service.py"
    content = "\n".join([f"# Line {i} of new service" for i in range(520)])
    new_file.write_text(content + "\n", encoding="utf-8")


@when('runs "spec-ops health"')
@when('runs "spec-ops health"')
def when_runs_health(repo_context: dict[str, Any]):
    repo = repo_context["repo"]
    result = run_spec_ops(repo, ["health"])
    repo_context["result"] = result


@then("the command exits with code 1")
def then_exits_code_1(repo_context: dict[str, Any]):
    res: subprocess.CompletedProcess[str] = repo_context["result"]
    assert res.returncode == 1


@then('And lists "src/new_service.py" as an unexempt file limit violation (>500 lines)')
@then('lists "src/new_service.py" as an unexempt file limit violation (>500 lines)')
def then_lists_unexempt(repo_context: dict[str, Any]):
    res: subprocess.CompletedProcess[str] = repo_context["result"]
    out = res.stdout + res.stderr
    assert "src/new_service.py" in out
    assert "unexempt file limit violation (>500 lines)" in out


@then("And indicates that the 3 grandfathered files remain tracked debt items")
@then("indicates that the 3 grandfathered files remain tracked debt items")
def then_indicates_tracked_debt(repo_context: dict[str, Any]):
    res: subprocess.CompletedProcess[str] = repo_context["result"]
    out = res.stdout + res.stderr
    assert "3 grandfathered files remain tracked debt items" in out or "3 grandfathered file(s) remain tracked debt items" in out


# Scenario 3
@given('a repository initialized via "spec-ops adopt" with grandfathered files')
def given_repo_with_grandfathered_files(repo_context: dict[str, Any]):
    given_repo_with_oversized_files(repo_context)
    when_run_adopt(repo_context)


@when('the architect inspects "docs/project/backlog/proposed/"')
def when_inspect_proposed(repo_context: dict[str, Any]):
    repo = repo_context["repo"]
    proposed_dir = repo / "docs" / "project" / "backlog" / "proposed"
    repo_context["proposed_dir"] = proposed_dir


@then('proposed tasks prefixed with "TASK-REFACTOR-" are generated for each grandfathered file')
@then('Then proposed tasks prefixed with "TASK-REFACTOR-" are generated for each grandfathered file')
def then_proposed_tasks_generated(repo_context: dict[str, Any]):
    proposed_dir: Path = repo_context["proposed_dir"]
    refactor_files = list(proposed_dir.glob("TASK-REFACTOR-*.md"))
    assert len(refactor_files) == 3


@then("And each task cites ADR-0002 and identifies the target submodule decomposition path")
@then("each task cites ADR-0002 and identifies the target submodule decomposition path")
def then_tasks_cite_adr0002(repo_context: dict[str, Any]):
    proposed_dir: Path = repo_context["proposed_dir"]
    refactor_files = list(proposed_dir.glob("TASK-REFACTOR-*.md"))
    for rf in refactor_files:
        content = rf.read_text(encoding="utf-8")
        assert "ADR-0002" in content
        assert "Target Submodule Decomposition Path" in content or "target submodule decomposition path" in content.lower()
