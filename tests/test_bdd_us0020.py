"""BDD tests for US-0020: Blackbox Frontdoor Test Verification and Anti-Mock Quality Gate."""

from __future__ import annotations

import json
import shlex
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from spec_ops.scaffold.init import init_project

scenarios("features/us_0020_blackbox_frontdoor_test_verification_and_anti_mock_gate.feature")


@pytest.fixture
def bdd_us20_context(tmp_path: Path) -> dict[str, Any]:
    repo = tmp_path / "repo"
    repo.mkdir(parents=True, exist_ok=True)
    init_project(name="FrontdoorApp", target_dir=repo)

    # Initialize git repo
    subprocess.run(["git", "init", "-b", "main"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Jordan"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "jordan@example.com"], cwd=repo, check=True, capture_output=True)

    tests_dir = repo / "tests"
    tests_dir.mkdir(parents=True, exist_ok=True)

    return {
        "repo": repo,
        "tests_dir": tests_dir,
        "last_res": None,
        "output": "",
    }


# --- Scenario 1: Passing Clean Blackbox Test Suite with Mutation Invariants ---


@given("a Python test suite where all feature tests interact exclusively through public frontdoors")
def clean_python_test_suite(bdd_us20_context: dict[str, Any]):
    tests_dir = bdd_us20_context["tests_dir"]
    clean_test = tests_dir / "test_public_feature.py"
    clean_test.write_text(
        'def test_public_calculator():\n'
        '    result = 2 + 2\n'
        '    assert result == 4\n',
        encoding="utf-8",
    )


@given('no tests invoke "unittest.mock.patch" on internal module private methods')
def no_tests_invoke_mock_patch(bdd_us20_context: dict[str, Any]):
    tests_dir = bdd_us20_context["tests_dir"]
    another_clean_test = tests_dir / "test_another_frontdoor.py"
    another_clean_test.write_text(
        'from pathlib import Path\n'
        'def test_file_reading(tmp_path: Path):\n'
        '    f = tmp_path / "data.txt"\n'
        '    f.write_text("specops", encoding="utf-8")\n'
        '    assert f.read_text(encoding="utf-8") == "specops"\n',
        encoding="utf-8",
    )


@given("Mutmut mutation testing achieves >=80% mutant kill score on target domain modules")
def mutmut_achieves_passing_score(bdd_us20_context: dict[str, Any]):
    repo = bdd_us20_context["repo"]
    specops_dir = repo / ".specops"
    specops_dir.mkdir(parents=True, exist_ok=True)
    mutation_report = specops_dir / "mutation_report.json"
    mutation_report.write_text(
        json.dumps({
            "mutation_score": 85.0,
            "surviving_mutants": [],
            "untyped_branches": [],
        }),
        encoding="utf-8",
    )


@when(parsers.parse('the lead runs "{command_str}"'))
def lead_runs_command(bdd_us20_context: dict[str, Any], command_str: str):
    repo = bdd_us20_context["repo"]
    cmd_parts = shlex.split(command_str)
    if cmd_parts[0] == "spec-ops":
        cmd_args = [sys.executable, "-m", "spec_ops.cli.main", *cmd_parts[1:]]
    else:
        cmd_args = cmd_parts

    res = subprocess.run(cmd_args, cwd=repo, capture_output=True, text=True)
    bdd_us20_context["last_res"] = res
    bdd_us20_context["output"] = res.stdout + ("\n" + res.stderr if res.stderr else "")


@then(parsers.parse("the command exits with code {exit_code:d}"))
def verify_exit_code(bdd_us20_context: dict[str, Any], exit_code: int):
    res = bdd_us20_context["last_res"]
    assert res is not None, "Command was not executed"
    assert res.returncode == exit_code, f"Expected {exit_code}, got {res.returncode}. Output:\n{bdd_us20_context['output']}"


@then(parsers.parse('reports "{expected_msg}".'))
def verify_reported_message(bdd_us20_context: dict[str, Any], expected_msg: str):
    output = bdd_us20_context["output"]
    assert expected_msg in output, f"Expected '{expected_msg}' in output:\n{output}"


# --- Scenario 2: Blocking Tests with Prohibited Mock Backdoors and Private Method Spies ---


@given("an autonomous agent generates a test file in an active worktree")
def agent_generates_test_file(bdd_us20_context: dict[str, Any]):
    repo = bdd_us20_context["repo"]
    tests_dir = bdd_us20_context["tests_dir"]
    assert tests_dir.is_dir()


@given(parsers.parse('the test file imports private functions prefixed with "_" or uses "patch.object" on internal persistence adapters'))
def test_file_with_forbidden_mocks(bdd_us20_context: dict[str, Any]):
    tests_dir = bdd_us20_context["tests_dir"]
    bad_test = tests_dir / "test_bad_adapter.py"
    bad_test.write_text(
        'from spec_ops.core.models import _find_task\n'
        'from unittest.mock import patch\n'
        '\n'
        'def test_adapter_spy():\n'
        '    with patch.object(adapter, "_connect"):\n'
        '        pass\n',
        encoding="utf-8",
    )


@when(parsers.parse('the in-worktree preflight executes "{command_str}"'))
def preflight_executes_command(bdd_us20_context: dict[str, Any], command_str: str):
    lead_runs_command(bdd_us20_context, command_str)


@then(parsers.parse("prints a diagnostic violation citing ADR-0003 and the exact line numbers containing prohibited mocks"))
def verify_diagnostic_violation(bdd_us20_context: dict[str, Any]):
    output = bdd_us20_context["output"]
    assert "ADR-0003" in output
    assert "Line 1:" in output or ":1:" in output
    assert "Line 2:" in output or ":2:" in output


@then(parsers.parse("instructs the agent to exercise the feature exclusively through public entrypoints."))
def verify_instruction_to_agent(bdd_us20_context: dict[str, Any]):
    output = bdd_us20_context["output"]
    assert "public entrypoints" in output


# --- Scenario 3: Mutation Score Threshold Enforcement ---


@given("a test suite verifying a domain state machine through public APIs")
def test_suite_domain_state_machine(bdd_us20_context: dict[str, Any]):
    clean_python_test_suite(bdd_us20_context)


@given("Mutmut identifies surviving mutants dropping the mutation score to 68% (below the 80% invariant)")
def mutmut_identifies_surviving_mutants(bdd_us20_context: dict[str, Any]):
    repo = bdd_us20_context["repo"]
    specops_dir = repo / ".specops"
    specops_dir.mkdir(parents=True, exist_ok=True)
    mutation_report = specops_dir / "mutation_report.json"
    mutation_report.write_text(
        json.dumps({
            "mutation_score": 68.0,
            "surviving_mutants": ["mutant_12", "mutant_15"],
            "untyped_branches": ["Branch at line 45: missing boundary property test"],
        }),
        encoding="utf-8",
    )


@then("lists the surviving mutant IDs and untyped code branches requiring property or edge-case tests.")
def verify_lists_surviving_mutants(bdd_us20_context: dict[str, Any]):
    output = bdd_us20_context["output"]
    assert "mutant_12" in output
    assert "mutant_15" in output
    assert "Branch at line 45" in output


# --- Scenario 4: Scanning Test Tree with Audit Anti-Mock Command ---


@given("a test suite that exercises only public CLI and module frontdoors")
def clean_test_suite_frontdoors(bdd_us20_context: dict[str, Any]):
    clean_python_test_suite(bdd_us20_context)


@when(parsers.parse('"{command_str}" scans the test tree'))
def audit_command_scans_tree(bdd_us20_context: dict[str, Any], command_str: str):
    lead_runs_command(bdd_us20_context, command_str)


@then("zero anti-mock violations are reported.")
def verify_zero_violations(bdd_us20_context: dict[str, Any]):
    res = bdd_us20_context["last_res"]
    assert res.returncode == 0
    assert "0 private backdoors detected" in bdd_us20_context["output"]


# --- Scenario 5: Blocking Tests with Monkeypatching and Prohibited Mock Imports ---


@given("a test that monkeypatches private attributes or imports unittest.mock")
def test_monkeypatches_private_or_imports_mock(bdd_us20_context: dict[str, Any]):
    tests_dir = bdd_us20_context["tests_dir"]
    violating_test = tests_dir / "test_monkeypatch_internal.py"
    violating_test.write_text(
        'import unittest.mock\n'
        'def test_internal_patch(monkeypatch):\n'
        '    monkeypatch.setattr(obj, "_internal_state", 100)\n',
        encoding="utf-8",
    )


@when("anti-mock audit runs")
def anti_mock_audit_runs(bdd_us20_context: dict[str, Any]):
    lead_runs_command(bdd_us20_context, "spec-ops test audit-anti-mock")


@then("the test file is flagged with line numbers and commit is blocked.")
def verify_file_flagged_with_lines_and_blocked(bdd_us20_context: dict[str, Any]):
    res = bdd_us20_context["last_res"]
    assert res.returncode != 0
    output = bdd_us20_context["output"]
    assert "test_monkeypatch_internal.py" in output
    assert "Line 1:" in output or ":1:" in output
    assert "Line 3:" in output or ":3:" in output
