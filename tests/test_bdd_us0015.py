"""Executable BDD acceptance tests for US-0015: Proactive File Decomposition Suggestions and AST Seam Extraction."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
from pytest_bdd import given, scenarios, then, when

from spec_ops.scaffold.init import init_project

scenarios("features/us_0015_proactive_file_decomposition.feature")

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
    repo = tmp_path / "decomp_repo"
    repo.mkdir(parents=True, exist_ok=True)
    init_project(repo, name="DecompDemoApp")

    subprocess.run(["git", "init", "-b", "main"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Alex"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "alex@example.com"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "chore: init"], cwd=repo, check=True, capture_output=True)

    return {"repo": repo, "result": None}


# Scenario 1: Generating decomposition suggestions for files in the warning threshold (400-500 lines)
@given('a source file "src/spec_ops/core/parser.py" with 440 lines')
def given_parser_with_440_lines(repo_context: dict[str, Any]):
    repo = repo_context["repo"]
    target = repo / "src" / "spec_ops" / "core" / "parser.py"
    target.parent.mkdir(parents=True, exist_ok=True)

    code_lines = [
        "class MarkdownParser:",
        "    def parse_markdown(self, text: str) -> str:",
        "        return text",
        "",
        "def parse_markdown_blocks(text: str) -> list[str]:",
        "    return text.splitlines()",
        "",
        "class FrontmatterParser:",
        "    def parse_frontmatter(self, text: str) -> dict:",
        "        return {}",
        "",
        "def parse_frontmatter_yaml(text: str) -> dict:",
        "    return {}",
        "",
    ]
    # Pad to 440 lines
    while len(code_lines) < 440:
        code_lines.append(f"# line {len(code_lines) + 1} padding")
    target.write_text("\n".join(code_lines) + "\n", encoding="utf-8")


@when('the architect runs "spec-ops health --suggest-splits"')
def when_run_suggest_splits(repo_context: dict[str, Any]):
    repo = repo_context["repo"]
    result = run_spec_ops(repo, ["health", "--suggest-splits"])
    repo_context["result"] = result


@then("the scanner reports a proactive anti-rot warning (440 lines >= 400 lines threshold)")
def then_reports_anti_rot_warning(repo_context: dict[str, Any]):
    res: subprocess.CompletedProcess[str] = repo_context["result"]
    out = res.stdout + res.stderr
    assert "440 lines >= 400 lines threshold" in out


@then('analyzes the AST to suggest cohesive module splits (e.g. "parser_markdown.py" and "parser_frontmatter.py")')
@then('And analyzes the AST to suggest cohesive module splits (e.g. "parser_markdown.py" and "parser_frontmatter.py")')
def then_suggests_cohesive_splits(repo_context: dict[str, Any]):
    res: subprocess.CompletedProcess[str] = repo_context["result"]
    out = res.stdout + res.stderr
    assert "parser_markdown.py" in out
    assert "parser_frontmatter.py" in out


@then('outputs the suggested exports for a barrel "__init__.py" file')
@then('And outputs the suggested exports for a barrel "__init__.py" file')
def then_outputs_barrel_exports(repo_context: dict[str, Any]):
    res: subprocess.CompletedProcess[str] = repo_context["result"]
    out = res.stdout + res.stderr
    assert "Suggested barrel exports:" in out
    assert "__all__" in out


# Scenario 2: Emitting a proposed refactoring task into the backlog
@given('a source file "src/orders/service.py" reaches 460 lines')
def given_orders_service_reaches_460(repo_context: dict[str, Any]):
    repo = repo_context["repo"]
    target = repo / "src" / "orders" / "service.py"
    target.parent.mkdir(parents=True, exist_ok=True)

    code_lines = [
        "class OrderService:",
        "    def create_order(self): pass",
        "",
        "class PaymentService:",
        "    def process_payment(self): pass",
        "",
    ]
    while len(code_lines) < 460:
        code_lines.append(f"# line {len(code_lines) + 1} padding")
    target.write_text("\n".join(code_lines) + "\n", encoding="utf-8")


@when('the architect runs "spec-ops health --suggest-splits --emit-task"')
def when_run_suggest_splits_emit_task(repo_context: dict[str, Any]):
    repo = repo_context["repo"]
    result = run_spec_ops(repo, ["health", "--suggest-splits", "--emit-task"])
    repo_context["result"] = result


@then('a new task file is written to "docs/project/backlog/proposed/TASK-SPLIT-orders-service.md"')
def then_task_file_written(repo_context: dict[str, Any]):
    repo = repo_context["repo"]
    task_file = repo / "docs" / "project" / "backlog" / "proposed" / "TASK-SPLIT-orders-service.md"
    assert task_file.is_file(), f"Expected {task_file} to exist. Backlog contents: {list((repo / 'docs' / 'project' / 'backlog' / 'proposed').glob('*'))}"
    repo_context["task_file"] = task_file


@then("the task contains the AST decomposition blueprint, suggested submodule boundaries, and INVEST criteria")
@then("And the task contains the AST decomposition blueprint, suggested submodule boundaries, and INVEST criteria")
def then_task_contains_blueprint_and_invest(repo_context: dict[str, Any]):
    task_file: Path = repo_context["task_file"]
    content = task_file.read_text(encoding="utf-8")
    assert "AST Decomposition Blueprint" in content
    assert "Suggested Submodule Boundaries" in content
    assert "INVEST Criteria" in content
    assert "ADR-0002" in content


# Scenario 3: Preserving clean status when all files remain under 400 lines
@given("all source files in the repository contain fewer than 400 lines")
def given_all_files_clean(repo_context: dict[str, Any]):
    repo = repo_context["repo"]
    # All files from init_project are small (<200 lines)
    pass


@then('the command exits with code 0 and reports "0 proactive warnings; codebase modularity optimal"')
def then_clean_exits_0(repo_context: dict[str, Any]):
    res: subprocess.CompletedProcess[str] = repo_context["result"]
    assert res.returncode == 0
    assert "0 proactive warnings; codebase modularity optimal" in res.stdout
