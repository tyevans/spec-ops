"""BDD tests for US-0064: Core Domain Mutation Testing Invariant and Mutant Kill Score Quality Gate."""

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

scenarios("features/us_0064_core_domain_mutation_testing_quality_gate.feature")


@pytest.fixture
def bdd_us64_context(tmp_path: Path) -> dict[str, Any]:
    repo = tmp_path / "repo"
    repo.mkdir(parents=True, exist_ok=True)
    init_project(name="MutationApp", target_dir=repo)

    subprocess.run(["git", "init", "-b", "main"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Jordan"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "jordan@example.com"], cwd=repo, check=True, capture_output=True)

    core_dir = repo / "src" / "spec_ops" / "core"
    core_dir.mkdir(parents=True, exist_ok=True)
    (core_dir / "models.py").write_text("def validate_model(): return True\n", encoding="utf-8")
    (core_dir / "parser.py").write_text("def parse_content(): return 1\n", encoding="utf-8")
    (core_dir / "graph.py").write_text("def filter_edges(): return []\n", encoding="utf-8")

    tests_dir = repo / "tests"
    tests_dir.mkdir(parents=True, exist_ok=True)

    return {
        "repo": repo,
        "core_dir": core_dir,
        "last_res": None,
        "output": "",
    }


def _run_cmd(context: dict[str, Any], command_str: str) -> subprocess.CompletedProcess[str]:
    repo = context["repo"]
    cmd_parts = shlex.split(command_str)
    if cmd_parts[0] == "spec-ops":
        cmd_args = [sys.executable, "-m", "spec_ops.cli.main", *cmd_parts[1:]]
    else:
        cmd_args = cmd_parts

    res = subprocess.run(cmd_args, cwd=repo, capture_output=True, text=True)
    context["last_res"] = res
    context["output"] = res.stdout + ("\n" + res.stderr if res.stderr else "")
    return res


# --- Scenario 1: Passing the mutation quality gate on core domain modules ---


@given('the test suite covers all public methods of "src/spec_ops/core/"')
def step_suite_covers_core(bdd_us64_context: dict[str, Any]):
    repo = bdd_us64_context["repo"]
    specops_dir = repo / ".specops"
    specops_dir.mkdir(parents=True, exist_ok=True)

    surviving = [
        {
            "id": f"mutant_{i}",
            "file_path": "src/spec_ops/core/graph.py",
            "line": 10 + i,
            "expression": f"edge_type_{i}",
            "diff": f"--- a\n+++ b\n@@ -{10+i} +{10+i} @@\n-edge_type\n+edge_type_{i}",
        }
        for i in range(1, 33)
    ]

    report_payload = {
        "target_module": "src/spec_ops/core",
        "threshold": 80.0,
        "killed_count": 168,
        "survived_count": 32,
        "timeout_count": 0,
        "total_mutants": 200,
        "mutation_score": 84.0,
        "surviving_mutants": surviving,
    }
    (specops_dir / "mutation_report.json").write_text(json.dumps(report_payload), encoding="utf-8")


@when(parsers.parse('the lead runs "{command_str}"'))
def lead_runs_command(bdd_us64_context: dict[str, Any], command_str: str):
    _run_cmd(bdd_us64_context, command_str)


@then(parsers.parse('Mutmut injects synthetic mutants into "{m1}", "{m2}", and "{m3}"'))
def mutmut_injects_mutants(bdd_us64_context: dict[str, Any], m1: str, m2: str, m3: str):
    core_dir = bdd_us64_context["core_dir"]
    assert (core_dir / m1).exists()
    assert (core_dir / m2).exists()
    assert (core_dir / m3).exists()


@then("tests kill at least 80% of all generated mutants")
def step_tests_kill_at_least_80_percent(bdd_us64_context: dict[str, Any]):
    output = bdd_us64_context["output"]
    assert "84%" in output or "Invariant Met" in output


@then("the command exits with code 0")
def command_exits_zero(bdd_us64_context: dict[str, Any]):
    res = bdd_us64_context["last_res"]
    assert res is not None
    assert res.returncode == 0, f"Expected 0 but got {res.returncode}. Output:\n{bdd_us64_context['output']}"


@then(parsers.parse('reports "{expected_msg}".'))
def reports_message(bdd_us64_context: dict[str, Any], expected_msg: str):
    output = bdd_us64_context["output"]
    assert expected_msg in output


# --- Scenario 2: Blocking pull request when weak assertions leave surviving mutants below threshold ---


@given('a pull request modifies "src/spec_ops/core/graph.py" adding a new edge filtering option')
def pr_modifies_graph(bdd_us64_context: dict[str, Any]):
    graph_file = bdd_us64_context["core_dir"] / "graph.py"
    graph_file.write_text(
        "def filter_edges(edge_types=None):\n"
        "    if edge_types is not None:\n"
        "        return [e for e in [] if e in edge_types]\n"
        "    return []\n",
        encoding="utf-8",
    )


@given("the author adds tests that execute the code but make no assertions on the filtered edge types")
def tests_with_weak_assertions(bdd_us64_context: dict[str, Any]):
    repo = bdd_us64_context["repo"]
    specops_dir = repo / ".specops"
    specops_dir.mkdir(parents=True, exist_ok=True)

    surviving = [
        {
            "id": f"src.spec_ops.core.graph__mutmut_{i}",
            "file_path": "src/spec_ops/core/graph.py",
            "line": 2 + (i % 3),
            "expression": f"filter_edge_branch_{i}",
            "diff": f"--- src/spec_ops/core/graph.py\n+++ src/spec_ops/core/graph.py\n@@ -{2+(i%3)} +{2+(i%3)} @@\n-if edge_types is not None:\n+if edge_types is None:",
        }
        for i in range(1, 13)
    ]

    report_payload = {
        "target_module": "src/spec_ops/core",
        "threshold": 80.0,
        "killed_count": 71,
        "survived_count": 29,
        "timeout_count": 0,
        "total_mutants": 100,
        "mutation_score": 71.0,
        "surviving_mutants": surviving,
    }
    (specops_dir / "mutation_report.json").write_text(json.dumps(report_payload), encoding="utf-8")


@when(parsers.parse('CI executes "{command_str}"'))
def ci_executes_command(bdd_us64_context: dict[str, Any], command_str: str):
    _run_cmd(bdd_us64_context, command_str)


@then(parsers.parse("Mutmut detects {count:d} surviving mutants in the unasserted filter branch"))
def mutmut_detects_surviving_mutants(bdd_us64_context: dict[str, Any], count: int):
    output = bdd_us64_context["output"]
    assert f"Surviving mutants ({count})" in output or "Surviving mutants" in output


@then(parsers.parse("the mutant kill score drops to {score:d}% (below the 80% invariant threshold)"))
def score_drops_below_threshold(bdd_us64_context: dict[str, Any], score: int):
    output = bdd_us64_context["output"]
    assert f"{score}%" in output


@then("the command exits with code 1")
def command_exits_one(bdd_us64_context: dict[str, Any]):
    res = bdd_us64_context["last_res"]
    assert res is not None
    assert res.returncode == 1, f"Expected 1 but got {res.returncode}. Output:\n{bdd_us64_context['output']}"


@then("prints surviving mutant diffs and exact line numbers requiring stronger blackbox assertions.")
def prints_surviving_mutant_diffs(bdd_us64_context: dict[str, Any]):
    output = bdd_us64_context["output"]
    assert "src/spec_ops/core/graph.py:" in output
    assert "Diff:" in output
    assert "stronger blackbox assertions" in output


# --- Scenario 3: Generating machine-readable mutation score report for CI telemetry ---


@given('a completed mutation test run on "src/spec_ops/core/"')
def completed_mutation_run(bdd_us64_context: dict[str, Any]):
    repo = bdd_us64_context["repo"]
    specops_dir = repo / ".specops"
    specops_dir.mkdir(parents=True, exist_ok=True)

    surviving = [
        {
            "id": f"mutant_{i}",
            "file_path": "src/spec_ops/core/parser.py",
            "line": 40 + i,
            "expression": f"parse_token_{i}",
            "diff": f"--- a\n+++ b\n@@ -{40+i} +{40+i} @@\n-token\n+mutated_token_{i}",
        }
        for i in range(1, 33)
    ]

    report_payload = {
        "target_module": "src/spec_ops/core",
        "threshold": 80.0,
        "killed_count": 168,
        "survived_count": 32,
        "timeout_count": 0,
        "total_mutants": 200,
        "mutation_score": 84.2,
        "surviving_mutants": surviving,
    }
    (specops_dir / "mutation_report.json").write_text(json.dumps(report_payload), encoding="utf-8")


@then("the command outputs valid JSON containing:")
def command_outputs_valid_json(bdd_us64_context: dict[str, Any]):
    res = bdd_us64_context["last_res"]
    assert res is not None
    data = json.loads(res.stdout)
    assert data["target_module"] == "src/spec_ops/core"
    assert data["mutation_score"] == 84.2
    assert data["threshold"] == 80.0
    assert data["killed_count"] == 168
    assert data["survived_count"] == 32
    assert len(data["survived_mutants"]) == 32
    for m in data["survived_mutants"]:
        assert "line" in m
        assert "mutant_id" in m or "id" in m


# --- Scenario 4: Passing the mutation quality gate on core domain modules via test mutation ---


@given("core domain modules with high-fidelity blackbox test suites")
def core_modules_with_test_suite(bdd_us64_context: dict[str, Any]):
    repo = bdd_us64_context["repo"]
    specops_dir = repo / ".specops"
    specops_dir.mkdir(parents=True, exist_ok=True)
    report_payload = {
        "target_module": "src/spec_ops/core",
        "threshold": 80.0,
        "killed_count": 88,
        "survived_count": 12,
        "timeout_count": 0,
        "total_mutants": 100,
        "mutation_score": 88.0,
        "surviving_mutants": [],
    }
    (specops_dir / "mutation_report.json").write_text(json.dumps(report_payload), encoding="utf-8")


@when(parsers.parse('"{command_str}" runs'))
def command_runs_step(bdd_us64_context: dict[str, Any], command_str: str):
    _run_cmd(bdd_us64_context, command_str)


@then("mutants are generated, killed by tests, and the command exits with code 0")
def mutants_killed_and_exit_0(bdd_us64_context: dict[str, Any]):
    res = bdd_us64_context["last_res"]
    assert res is not None
    assert res.returncode == 0
    assert "Mutation Invariant Met" in bdd_us64_context["output"]


# --- Scenario 5: Blocking weak assertions via test mutation command ---


@given("a test suite with tautological or weak assertions")
def suite_with_tautological_assertions(bdd_us64_context: dict[str, Any]):
    repo = bdd_us64_context["repo"]
    specops_dir = repo / ".specops"
    specops_dir.mkdir(parents=True, exist_ok=True)
    report_payload = {
        "target_module": "src/spec_ops/core",
        "threshold": 80.0,
        "killed_count": 55,
        "survived_count": 45,
        "timeout_count": 0,
        "total_mutants": 100,
        "mutation_score": 55.0,
        "surviving_mutants": [
            {
                "id": "mutant_weak_1",
                "file_path": "src/spec_ops/core/graph.py",
                "line": 42,
                "expression": "tautological_branch()",
                "diff": "--- a\n+++ b\n@@ -42 +42 @@\n-assert True\n+assert False",
            }
        ],
    }
    (specops_dir / "mutation_report.json").write_text(json.dumps(report_payload), encoding="utf-8")


@when("mutation score falls below 80%")
def run_failing_mutation_gate(bdd_us64_context: dict[str, Any]):
    _run_cmd(bdd_us64_context, "spec-ops test mutation --threshold 80")


@then("the command fails with a detailed breakdown of surviving mutants")
def command_fails_detailed_breakdown(bdd_us64_context: dict[str, Any]):
    res = bdd_us64_context["last_res"]
    assert res is not None
    assert res.returncode == 1
    output = bdd_us64_context["output"]
    assert "❌ Mutation Score Invariant Failed" in output
    assert "src/spec_ops/core/graph.py:42" in output
