"""Executable BDD step definitions for US-0094 / TASK-0156: BDD Feature Scenario Coverage Matrix."""

from __future__ import annotations

from pathlib import Path
import subprocess
import sys
from typing import Any

import pytest
from pytest_bdd import given, scenarios, then, when

from spec_ops.scaffold.init import init_project

scenarios("features/us_0094_bdd_coverage.feature")


@pytest.fixture
def bdd_coverage_context(tmp_path: Path) -> dict[str, Any]:
    init_project(tmp_path, name="SpecOpsCoverageApp")
    return {
        "root": tmp_path,
        "res": None,
    }


def _run_cli(root: Path, cmd_args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "spec_ops.cli.main", *cmd_args],
        cwd=str(root),
        capture_output=True,
        text=True,
    )


@given("a set of accepted user stories with executable Gherkin scenarios")
def accepted_user_stories_with_scenarios(bdd_coverage_context: dict[str, Any]):
    root = bdd_coverage_context["root"]
    stories_dir = root / "docs" / "project" / "user_stories" / "accepted"
    stories_dir.mkdir(parents=True, exist_ok=True)

    story_content = """---
id: '0201'
title: Sample Feature Story
status: Accepted
target_bc: prd
---

# US-0201 — Sample Feature Story

## Acceptance Criteria

```gherkin
Scenario: First automated acceptance scenario
  Given system is ready
  When action occurs
  Then state is verified
```
"""
    (stories_dir / "us-0201-sample-feature-story.md").write_text(story_content, encoding="utf-8")


@given("corresponding pytest-bdd test modules in the test suite")
def corresponding_test_modules_in_test_suite(bdd_coverage_context: dict[str, Any]):
    root = bdd_coverage_context["root"]
    features_dir = root / "tests" / "features"
    features_dir.mkdir(parents=True, exist_ok=True)

    feature_content = """Feature: Sample Feature Story
  Scenario: First automated acceptance scenario
    Given system is ready
    When action occurs
    Then state is verified
"""
    (features_dir / "us_0201_sample_feature.feature").write_text(feature_content, encoding="utf-8")

    test_content = """from pytest_bdd import scenarios
scenarios("features/us_0201_sample_feature.feature")
"""
    (root / "tests" / "test_bdd_us0201.py").write_text(test_content, encoding="utf-8")


@when("the developer runs spec-ops prd coverage")
def run_prd_coverage(bdd_coverage_context: dict[str, Any]):
    root = bdd_coverage_context["root"]
    res = _run_cli(root, ["prd", "coverage"])
    bdd_coverage_context["res"] = res


@then("the scenario coverage matrix reports mapped scenarios and overall coverage percentage")
def verify_coverage_matrix_reported(bdd_coverage_context: dict[str, Any]):
    res = bdd_coverage_context["res"]
    assert res is not None
    assert "SpecOps BDD Scenario Coverage Matrix" in res.stdout
    assert "Covered Scenarios:" in res.stdout
    assert "US-0201" in res.stdout
    assert "First automated acceptance scenario" in res.stdout
    assert "test_bdd_us0201.py" in res.stdout


@then("exits with success code 0")
def verify_success_code(bdd_coverage_context: dict[str, Any]):
    res = bdd_coverage_context["res"]
    assert res.returncode == 0


@given("an accepted user story with scenarios lacking test implementations")
def story_lacking_test_implementation(bdd_coverage_context: dict[str, Any]):
    root = bdd_coverage_context["root"]
    stories_dir = root / "docs" / "project" / "user_stories" / "accepted"
    stories_dir.mkdir(parents=True, exist_ok=True)

    unimplemented_story = """---
id: '0202'
title: Unimplemented Backlog Story
status: Accepted
target_bc: prd
---

# US-0202 — Unimplemented Backlog Story

## Acceptance Criteria

```gherkin
Scenario: Missing test implementation scenario
  Given pending feature
  When executed
  Then nothing is implemented yet
```
"""
    (stories_dir / "us-0202-unimplemented-story.md").write_text(unimplemented_story, encoding="utf-8")


@when("the developer runs spec-ops prd coverage with strict mode enabled")
def run_prd_coverage_strict(bdd_coverage_context: dict[str, Any]):
    root = bdd_coverage_context["root"]
    res = _run_cli(root, ["prd", "coverage", "--strict"])
    bdd_coverage_context["res"] = res


@then("the command reports the missing scenario bindings")
def verify_missing_scenario_bindings(bdd_coverage_context: dict[str, Any]):
    res = bdd_coverage_context["res"]
    assert res is not None
    combined = res.stdout + res.stderr
    assert "Missing Scenario Bindings" in combined or "missing test binding" in combined
    assert "Missing test implementation scenario" in combined


@then("terminates with exit code 1")
def verify_strict_failure_code(bdd_coverage_context: dict[str, Any]):
    res = bdd_coverage_context["res"]
    assert res.returncode == 1
