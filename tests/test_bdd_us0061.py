"""Executable BDD step definitions for US-0061: Resilient Markdown AST Parsing."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from spec_ops.core.parser import parse_task
from spec_ops.core.spikes.cache_spike import parse_markdown_document
from spec_ops.scaffold.init import init_project

scenarios("features/us_0061_resilient_parsing.feature")


@pytest.fixture
def bdd_context(tmp_path: Path) -> dict[str, Any]:
    init_project(tmp_path, name="SpecOpsAstBDD")
    return {
        "root": tmp_path,
        "res": None,
        "last_file": None,
    }


def _run_cli(root: Path, cmd_args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "spec_ops.cli.main", *cmd_args],
        cwd=str(root),
        capture_output=True,
        text=True,
    )


@given(parsers.parse('a task file "{file_path}" containing:'))
def task_file_with_content(bdd_context: dict[str, Any], file_path: str, docstring: str):
    root: Path = bdd_context["root"]
    target = root / file_path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(docstring.strip() + "\n", encoding="utf-8")
    bdd_context["last_file"] = target


@given(parsers.parse('a task file "{file_path}" with invalid YAML indentation on line 4:'))
def task_file_with_bad_yaml(bdd_context: dict[str, Any], file_path: str, docstring: str):
    task_file_with_content(bdd_context, file_path, docstring)


@given(parsers.parse('a markdown file "{file_path}" missing the opening "---"'))
def markdown_file_missing_delim(bdd_context: dict[str, Any], file_path: str):
    root: Path = bdd_context["root"]
    target = root / file_path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("# Just Markdown\nNo frontmatter here.\n", encoding="utf-8")
    bdd_context["last_file"] = target


@when(parsers.parse('the developer executes "{command}"'))
def developer_executes_cmd(bdd_context: dict[str, Any], command: str):
    root: Path = bdd_context["root"]
    args = command.split()[1:]
    res = _run_cli(root, args)
    bdd_context["res"] = res


@then(parsers.parse('the task entity is instantiated with title "{expected_title}"'))
def entity_instantiated_with_title(bdd_context: dict[str, Any], expected_title: str):
    last_file: Path = bdd_context["last_file"]
    meta, _ = parse_markdown_document(last_file.read_text(encoding="utf-8"), file_path=last_file)
    assert meta.get("title") == expected_title
    task = parse_task(last_file)
    assert task.title == expected_title


@then("the parsed body retains the exact HTML comment, markdown table, and Python code fence verbatim without byte alteration.")
def body_retains_markdown_verbatim(bdd_context: dict[str, Any]):
    last_file: Path = bdd_context["last_file"]
    content = last_file.read_text(encoding="utf-8")
    _, body = parse_markdown_document(content, file_path=last_file)
    assert "<!-- Custom Architect Note: Do not remove -->" in body
    assert "| Step | Component |" in body
    assert "|---|---|" in body
    assert "def example():" in body
    assert "return True" in body


@then(parsers.parse("the command exits with code {expected_code:d}"))
def command_exits_with_code(bdd_context: dict[str, Any], expected_code: int):
    res: subprocess.CompletedProcess[str] = bdd_context["res"]
    assert res.returncode == expected_code


@then(parsers.parse("outputs a compiler-grade diagnostic error:"))
def outputs_compiler_grade_diagnostic(bdd_context: dict[str, Any], docstring: str):
    res: subprocess.CompletedProcess[str] = bdd_context["res"]
    combined = res.stdout + res.stderr
    for line in docstring.strip().splitlines():
        assert line.strip() in combined, f"Expected line {line!r} not found in output:\n{combined}"


@then("does not silently fallback to an empty metadata dictionary.")
def does_not_fallback_to_empty(bdd_context: dict[str, Any]):
    res: subprocess.CompletedProcess[str] = bdd_context["res"]
    assert res.returncode == 1
    last_file: Path = bdd_context["last_file"]
    with pytest.raises(Exception):
        parse_markdown_document(last_file.read_text(encoding="utf-8"), file_path=last_file)


@then(parsers.parse('reports "{expected_report}"'))
def reports_missing_frontmatter(bdd_context: dict[str, Any], expected_report: str):
    res: subprocess.CompletedProcess[str] = bdd_context["res"]
    combined = res.stdout + res.stderr
    assert expected_report in combined


@then(parsers.parse('suggests: "{expected_hint}".'))
def suggests_hint(bdd_context: dict[str, Any], expected_hint: str):
    res: subprocess.CompletedProcess[str] = bdd_context["res"]
    combined = res.stdout + res.stderr
    assert expected_hint in combined
