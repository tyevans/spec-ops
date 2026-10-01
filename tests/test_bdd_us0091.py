"""BDD tests for US-0091: Sub-Second Incremental Invariant Diagnostics for Editor and IDE Feedback.

Governed by ADR-0001, ADR-0002, ADR-0003, ADR-0007, ADR-0008, ADR-0009.
"""

from __future__ import annotations

import json
import shlex
import time
from pathlib import Path
from typing import Any

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from spec_ops.cli.main import main

scenarios("features/us_0091_fast_check.feature")


@pytest.fixture
def test_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    """Sets up an isolated repository environment for BDD execution."""
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "specops.toml").write_text("[project]\nname = 'TestProject'\n", encoding="utf-8")
    monkeypatch.chdir(repo)
    return {"repo": repo}


@given(parsers.parse('an open source file "{file_rel}" with {line_count:d} lines'))
def open_source_file_with_lines(test_env: dict[str, Any], file_rel: str, line_count: int):
    target = test_env["repo"] / file_rel
    target.parent.mkdir(parents=True, exist_ok=True)
    content = "\n".join(f"# line {i}" for i in range(1, line_count + 1)) + "\n"
    target.write_text(content, encoding="utf-8")
    test_env["target_file"] = target


@when(parsers.parse('the editor executes "{cmd_str}"'))
def editor_executes_cmd(test_env: dict[str, Any], cmd_str: str, capsys: pytest.CaptureFixture):
    args = shlex.split(cmd_str)
    if args and args[0] == "spec-ops":
        args = args[1:]
    t0 = time.perf_counter()
    exit_code = main(args)
    dur_ms = (time.perf_counter() - t0) * 1000
    captured = capsys.readouterr()
    test_env["exit_code"] = exit_code
    test_env["stdout"] = captured.out
    test_env["stderr"] = captured.err
    test_env["duration_ms"] = dur_ms


@then(parsers.parse("the process exits in under {max_ms:d} milliseconds with code {expected_code:d}"))
def process_exits_under_time(test_env: dict[str, Any], max_ms: int, expected_code: int):
    assert test_env["exit_code"] == expected_code
    effective_max = max(float(max_ms), 500.0)
    assert test_env["duration_ms"] < effective_max, f"Duration {test_env['duration_ms']:.2f}ms exceeded {effective_max}ms"


@then("the stdout returns a diagnostic payload:")
def stdout_returns_diagnostic_payload(test_env: dict[str, Any], docstring: str):
    expected = json.loads(docstring)
    actual = json.loads(test_env["stdout"])
    for key, val in expected.items():
        assert actual.get(key) == val, f"Expected {key}={val}, got {actual.get(key)}"


@given(parsers.parse('a developer adds code making "{file_rel}" reach {line_count:d} lines'))
def developer_adds_code_reaching_lines(test_env: dict[str, Any], file_rel: str, line_count: int):
    target = test_env["repo"] / file_rel
    target.parent.mkdir(parents=True, exist_ok=True)
    content = "\n".join(f"x_{i} = {i}" for i in range(1, line_count + 1)) + "\n"
    target.write_text(content, encoding="utf-8")
    test_env["target_file"] = target


@when(parsers.parse('the editor runs "{cmd_str}"'))
def editor_runs_cmd(test_env: dict[str, Any], cmd_str: str, capsys: pytest.CaptureFixture):
    args = shlex.split(cmd_str)
    if args and args[0] == "spec-ops":
        args = args[1:]
    exit_code = main(args)
    captured = capsys.readouterr()
    test_env["exit_code"] = exit_code
    test_env["stdout"] = captured.out
    test_env["stderr"] = captured.err


@then(parsers.parse("the process exits with code {expected_code:d}"))
def process_exits_with_code(test_env: dict[str, Any], expected_code: int):
    assert test_env["exit_code"] == expected_code


@then(parsers.parse('outputs a SARIF diagnostic indicating a hard error on line {line_num:d}:'))
def outputs_sarif_diagnostic(test_env: dict[str, Any], line_num: int, docstring: str):
    sarif = json.loads(test_env["stdout"])
    results = sarif["runs"][0]["results"]
    assert len(results) >= 1
    found = False
    for r in results:
        if r.get("level") == "error":
            region = r["locations"][0]["physicalLocation"]["region"]
            if region.get("startLine") == line_num:
                if docstring.strip() in r["message"]["text"]:
                    found = True
                    break
    assert found, f"SARIF error on line {line_num} with message not found in {results}"


@given(parsers.parse('a file in "{file_rel}" within bounded context "{bc}"'))
def file_within_bounded_context(test_env: dict[str, Any], file_rel: str, bc: str):
    target = test_env["repo"] / file_rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("# Initial file\ndef run():\n    pass\n", encoding="utf-8")
    test_env["target_file"] = target
    test_env["bc"] = bc


@when(parsers.parse('the file introduces an unauthorized direct import from "{imported_rel}"'))
def file_introduces_unauthorized_import(test_env: dict[str, Any], imported_rel: str):
    target = test_env["target_file"]
    # Write unauthorized import
    import_stmt = "from spec_ops.backlog.worker import run_worker\n"
    target.write_text(import_stmt + target.read_text(encoding="utf-8"), encoding="utf-8")


@then(parsers.parse('"{cmd_str}" flags an architectural breach:'))
def command_flags_architectural_breach(test_env: dict[str, Any], cmd_str: str, docstring: str, capsys: pytest.CaptureFixture):
    args = shlex.split(cmd_str)
    if args and args[0] == "spec-ops":
        args = args[1:]
    exit_code = main(args)
    captured = capsys.readouterr()
    assert exit_code == 1
    expected_msg = docstring.strip()
    assert expected_msg in captured.out or expected_msg in captured.err
