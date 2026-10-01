"""Unit tests for BDD Scenario Coverage Matrix and Living Acceptance Dashboard (TASK-0156)."""

from __future__ import annotations

from pathlib import Path

from spec_ops.prd.bdd_matrix import (
    BDDCoverageAuditor,
    BDDCoverageMatrix,
    BDDScenarioItem,
    StoryCoverageReport,
    normalize_story_id,
)


def test_bdd_scenario_item_model():
    item = BDDScenarioItem(
        story_id="US-0094",
        story_title="Checkable Outcomes",
        scenario_title="Decomposing PRD",
        is_covered=True,
        test_binding="tests/test_bdd_us0094.py::test_decompose",
        target_bc="prd",
    )
    d = item.to_dict()
    assert d["story_id"] == "US-0094"
    assert d["story_title"] == "Checkable Outcomes"
    assert d["scenario_title"] == "Decomposing PRD"
    assert d["is_covered"] is True
    assert d["test_binding"] == "tests/test_bdd_us0094.py::test_decompose"
    assert d["target_bc"] == "prd"


def test_story_coverage_report_model():
    item1 = BDDScenarioItem("US-0001", "Init", "Scen 1", True, "test.py", "core")
    item2 = BDDScenarioItem("US-0001", "Init", "Scen 2", False, None, "core")
    report = StoryCoverageReport(
        story_id="US-0001",
        story_title="Init",
        target_bc="core",
        total_scenarios=2,
        covered_scenarios=1,
        coverage_pct=50.0,
        scenarios=[item1, item2],
    )
    d = report.to_dict()
    assert d["story_id"] == "US-0001"
    assert d["coverage_pct"] == 50.0
    assert len(d["scenarios"]) == 2
    assert d["scenarios"][0]["is_covered"] is True
    assert d["scenarios"][1]["is_covered"] is False


def test_bdd_coverage_matrix_model_and_summary():
    item1 = BDDScenarioItem("US-0001", "Init", "Scen 1", True, "test.py", "core")
    item2 = BDDScenarioItem("US-0001", "Init", "Scen 2", False, None, "core")
    report = StoryCoverageReport(
        story_id="US-0001",
        story_title="Init",
        target_bc="core",
        total_scenarios=2,
        covered_scenarios=1,
        coverage_pct=50.0,
        scenarios=[item1, item2],
    )
    matrix = BDDCoverageMatrix(
        stories=[report],
        total_stories=1,
        total_scenarios=2,
        covered_scenarios=1,
        overall_coverage_pct=50.0,
    )
    d = matrix.to_dict()
    assert d["total_stories"] == 1
    assert d["total_scenarios"] == 2
    assert d["covered_scenarios"] == 1
    assert d["overall_coverage_pct"] == 50.0

    summary_text = matrix.summary()
    assert "=== SpecOps BDD Scenario Coverage Matrix ===" in summary_text
    assert "Total User Stories: 1" in summary_text
    assert "Covered Scenarios: 1 (50.0%)" in summary_text
    assert "Missing Scenario Bindings (1):" in summary_text
    assert "[US-0001] Scen 2" in summary_text


def test_normalize_story_id():
    assert normalize_story_id("0094") == "US-0094"
    assert normalize_story_id("US-0094") == "US-0094"
    assert normalize_story_id("94") == "US-0094"
    assert normalize_story_id("custom") == "US-CUSTOM"


def test_extract_scenarios_from_content():
    content = """
# Story Title

## Acceptance Criteria

```gherkin
Scenario: First Scenario
  Given state

Scenario Outline: Second Scenario Outline
  Given state
```

### Scenario 3: Fallback Scenario
```gherkin
Given something
```
"""
    scenarios = BDDCoverageAuditor.extract_scenarios_from_content(content)
    assert "First Scenario" in scenarios
    assert "Second Scenario Outline" in scenarios
    assert "First Scenario" in scenarios
    assert len(scenarios) == 2

    fallback_content = """
# Story Title

## Acceptance Criteria

### Scenario 1: Fallback Scenario 1
```gherkin
Given something
```

### Scenario: Fallback Scenario 2
```gherkin
Given another thing
```
"""
    fallback_scenarios = BDDCoverageAuditor.extract_scenarios_from_content(fallback_content)
    assert fallback_scenarios == ["Fallback Scenario 1", "Fallback Scenario 2"]


def test_audit_empty_and_nonexistent_directories(tmp_path: Path):
    nonexistent = tmp_path / "does_not_exist"
    matrix = BDDCoverageAuditor.audit(nonexistent, nonexistent)
    assert matrix.total_stories == 0
    assert matrix.total_scenarios == 0
    assert matrix.covered_scenarios == 0
    assert matrix.overall_coverage_pct == 100.0


def test_audit_with_direct_scenario_decorator(tmp_path: Path):
    stories_dir = tmp_path / "stories"
    stories_dir.mkdir()
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()

    story = """---
id: '0101'
title: Decorator Story
status: Accepted
target_bc: prd
---
# US-0101
```gherkin
Scenario: Explicitly Decorated Scenario
  Given step
```
"""
    (stories_dir / "us-0101-decorator.md").write_text(story, encoding="utf-8")

    test_file = """from pytest_bdd import scenario

@scenario("feat.feature", "Explicitly Decorated Scenario")
def test_explicit_scenario():
    pass
"""
    (tests_dir / "test_bdd_decorator.py").write_text(test_file, encoding="utf-8")

    matrix = BDDCoverageAuditor().audit(stories_dir, tests_dir)
    assert matrix.total_stories == 1
    assert matrix.total_scenarios == 1
    assert matrix.covered_scenarios == 1
    assert matrix.overall_coverage_pct == 100.0
    report = matrix.stories[0]
    assert report.scenarios[0].is_covered is True
    assert "test_bdd_decorator.py::test_explicit_scenario" in str(report.scenarios[0].test_binding)


def test_audit_target_bc_filtering(tmp_path: Path):
    stories_dir = tmp_path / "stories"
    stories_dir.mkdir()
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()

    s1 = """---
id: '0101'
title: PRD Story
target_bc: prd
---
```gherkin
Scenario: PRD Scenario
```
"""
    (stories_dir / "us-0101-prd.md").write_text(s1, encoding="utf-8")

    s2 = """---
id: '0102'
title: Core Story
target_bc: core
---
```gherkin
Scenario: Core Scenario
```
"""
    (stories_dir / "us-0102-core.md").write_text(s2, encoding="utf-8")

    matrix_prd = BDDCoverageAuditor.audit(stories_dir, tests_dir, target_bc="prd")
    assert matrix_prd.total_stories == 1
    assert matrix_prd.stories[0].story_id == "US-0101"

    matrix_core = BDDCoverageAuditor.audit(stories_dir, tests_dir, target_bc="core")
    assert matrix_core.total_stories == 1
    assert matrix_core.stories[0].story_id == "US-0102"


def test_determine_target_bc_feature_and_prd(tmp_path: Path):
    stories_dir = tmp_path / "docs" / "project" / "user_stories" / "accepted"
    stories_dir.mkdir(parents=True)
    product_dir = tmp_path / "docs" / "project" / "product" / "accepted"
    product_dir.mkdir(parents=True)

    prd_content = """---
id: '0003'
title: Product Studio
component: prd
---
# PRD-0003
"""
    (product_dir / "prd-0003-product-studio.md").write_text(prd_content, encoding="utf-8")

    # Story using feature prefix
    s1 = """---
id: '0051'
title: Security Story
feature: FEAT-SEC-01
---
"""
    (stories_dir / "us-0051-sec.md").write_text(s1, encoding="utf-8")

    # Story using governing PRD
    s2 = """---
id: '0094'
title: PRD Story
governing_prd: PRD-0003
---
"""
    (stories_dir / "us-0094-prd.md").write_text(s2, encoding="utf-8")

    matrix = BDDCoverageAuditor.audit(stories_dir, tmp_path / "tests")
    reports = {r.story_id: r for r in matrix.stories}
    assert reports["US-0051"].target_bc == "security"
    assert reports["US-0094"].target_bc == "prd"


def test_audit_with_test_func_slug_matching(tmp_path: Path):
    stories_dir = tmp_path / "stories"
    stories_dir.mkdir()
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()

    story = """---
id: '0301'
title: Slug Match Story
---
```gherkin
Scenario: Verify Alpha Delta Execution
  Given alpha
```
"""
    (stories_dir / "us-0301-slug.md").write_text(story, encoding="utf-8")

    test_file = """
def test_verify_alpha_delta_execution():
    pass
"""
    (tests_dir / "test_bdd_slug.py").write_text(test_file, encoding="utf-8")

    matrix = BDDCoverageAuditor.audit(stories_dir, tests_dir)
    assert matrix.covered_scenarios == 1
    assert matrix.stories[0].scenarios[0].is_covered is True
    assert "test_bdd_slug.py::test_verify_alpha_delta_execution" in str(matrix.stories[0].scenarios[0].test_binding)


def test_summary_all_covered():
    item = BDDScenarioItem("US-0001", "Init", "Scen 1", True, "test.py", "core")
    report = StoryCoverageReport("US-0001", "Init", "core", 1, 1, 100.0, [item])
    matrix = BDDCoverageMatrix([report], 1, 1, 1, 100.0)
    summary = matrix.summary()
    assert "Missing Scenario Bindings" not in summary
    assert "Covered Scenarios: 1 (100.0%)" in summary
    assert "✅ [US-0001]" in summary

