"""Hypothesis generative property tests for grandfathered debt baselining (ADR-0009)."""

from __future__ import annotations

from pathlib import Path

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from spec_ops.backlog.health import HealthChecker
from spec_ops.config.models import ArchitectureSettings, SpecOpsConfig
from spec_ops.core.debt_baseline import (
    evaluate_file_debt,
    load_grandfathered_debt,
    save_grandfathered_debt,
)


@st.composite
def file_debt_scenario_strategy(draw):
    num_files = draw(st.integers(min_value=2, max_value=8))
    files = {}
    for i in range(num_files):
        name = f"service_{i}.py"
        lines = draw(st.integers(min_value=100, max_value=800))
        files[name] = lines
    return files


@settings(max_examples=50, deadline=None)
@given(file_debt_scenario_strategy())
def test_hypothesis_health_accepts_unchanged_grandfathered_debt(tmp_path_factory, files_map: dict[str, int]):
    """Invariant: spec-ops health never rejects a repository if all exceeding files are registered in

    .specops/grandfathered_debt.json and unchanged.
    """
    tmp_path = tmp_path_factory.mktemp("hyp_baseline")
    src_dir = tmp_path / "src"
    src_dir.mkdir(parents=True, exist_ok=True)

    baseline_files = {}
    for fname, count in files_map.items():
        file_path = src_dir / fname
        file_path.write_text("\n".join(f"# line {i}" for i in range(count)) + "\n", encoding="utf-8")
        if count > 500:
            baseline_files[f"src/{fname}"] = count

    (tmp_path / "AGENTS.md").write_text("# Agents Constitution\n", encoding="utf-8")
    save_grandfathered_debt(tmp_path, baseline_files)

    config = SpecOpsConfig(
        root_dir=tmp_path,
        architecture=ArchitectureSettings(file_length_limit=500, file_warning_threshold=400),
    )
    checker = HealthChecker(config)
    report = checker.run_check()

    assert len(report.violations) == 0, f"Expected 0 violations, but got: {report.violations}"
    assert report.is_healthy
    assert len(report.violations) == 0
    assert len(report.grandfathered_debt) == len(baseline_files)


@settings(max_examples=50, deadline=None)
@given(
    file_debt_scenario_strategy(),
    st.integers(min_value=1, max_value=100),
)
def test_hypothesis_health_rejects_expanded_grandfathered_debt(
    tmp_path_factory, files_map: dict[str, int], additional_lines: int
):
    """Invariant: spec-ops health immediately rejects any modification that increases line count of a

    grandfathered file beyond its baseline.
    """
    oversized = {k: v for k, v in files_map.items() if v > 500}
    if not oversized:
        return

    tmp_path = tmp_path_factory.mktemp("hyp_expanded")
    src_dir = tmp_path / "src"
    src_dir.mkdir(parents=True, exist_ok=True)

    baseline_files = {}
    for fname, count in files_map.items():
        file_path = src_dir / fname
        file_path.write_text("\n".join(f"# line {i}" for i in range(count)) + "\n", encoding="utf-8")
        if count > 500:
            baseline_files[f"src/{fname}"] = count

    (tmp_path / "AGENTS.md").write_text("# Agents Constitution\n", encoding="utf-8")
    save_grandfathered_debt(tmp_path, baseline_files)

    # Pick first oversized file and expand it
    target_name = list(oversized.keys())[0]
    target_path = src_dir / target_name
    original_lines = oversized[target_name]
    new_line_count = original_lines + additional_lines
    target_path.write_text("\n".join(f"# line {i}" for i in range(new_line_count)) + "\n", encoding="utf-8")

    config = SpecOpsConfig(
        root_dir=tmp_path,
        architecture=ArchitectureSettings(file_length_limit=500, file_warning_threshold=400),
    )
    checker = HealthChecker(config)
    report = checker.run_check()

    assert not report.is_healthy
    assert len(report.violations) >= 1
    expanded_violation = next((v for v in report.violations if str(v.path).endswith(target_name)), None)
    assert expanded_violation is not None
    assert expanded_violation.is_expanded is True
    assert expanded_violation.lines == new_line_count
