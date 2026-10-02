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


@settings(max_examples=30, deadline=None)
@given(
    st.sampled_from([".claude", ".cursor", ".vscode", ".idea", ".superpowers", ".custom_tool"]),
    st.text(alphabet=st.characters(whitelist_categories=("Ll",)), min_size=3, max_size=10),
    st.integers(min_value=510, max_value=800),
)
def test_hypothesis_hidden_directories_never_baselined(
    tmp_path_factory, hidden_dir_name: str, sub_path: str, line_count: int
):
    """Invariant: Files inside hidden dot-directories are never baselined into grandfathered debt."""
    from spec_ops.core.debt_baseline import scan_and_record_grandfathered_debt

    tmp_path = tmp_path_factory.mktemp("hyp_hidden")
    hidden_dir = tmp_path / hidden_dir_name / sub_path
    hidden_dir.mkdir(parents=True)
    file_path = hidden_dir / "oversized.py"
    file_path.write_text("\n".join(f"# line {i}" for i in range(line_count)) + "\n", encoding="utf-8")
    oversized = scan_and_record_grandfathered_debt(tmp_path, limit=500)
    assert len(oversized) == 0


@settings(max_examples=30, deadline=None)
@given(
    st.lists(
        st.tuples(
            st.text(alphabet=st.characters(whitelist_categories=("Ll",)), min_size=3, max_size=10),
            st.integers(min_value=501, max_value=999),
        ),
        min_size=1,
        max_size=8,
        unique_by=lambda x: x[0],
    ),
    st.sampled_from([
        (".specops", "grandfathered_debt.json"),
        (".spec-ops", "debt-baseline.json"),
    ]),
)
def test_hypothesis_legacy_alias_equivalency(tmp_path_factory, files_list, location):
    """Invariant: Both canonical and legacy alias debt baseline files load identically."""
    import json
    dir_name, file_name = location
    tmp_path = tmp_path_factory.mktemp("hyp_alias")
    debt_dir = tmp_path / dir_name
    debt_dir.mkdir(parents=True)
    baseline_dict = {f"src/{name}.py": count for name, count in files_list}
    (debt_dir / file_name).write_text(json.dumps(baseline_dict), encoding="utf-8")

    loaded = load_grandfathered_debt(tmp_path)
    assert loaded == baseline_dict


@settings(max_examples=40, deadline=None)
@given(
    st.lists(
        st.sampled_from([
            ".worktrees/",
            ".specops",
            ".specops/",
            "/.specops/",
            ".specops/*",
            "!.specops/grandfathered_debt.json",
            "dist/",
            "site/",
            "__pycache__/",
            "*.pyc",
            "# some comment",
            "",
            "custom_dir/",
        ]),
        max_size=10,
    )
)
def test_hypothesis_ensure_debt_baseline_unignored_invariant(tmp_path_factory, initial_rules: list[str]):
    """Invariant: ensure_debt_baseline_unignored always yields an unignored debt baseline and is idempotent."""
    from spec_ops.core.debt_baseline import ensure_debt_baseline_unignored

    tmp_path = tmp_path_factory.mktemp("hyp_unignore")
    gi = tmp_path / ".gitignore"
    gi.write_text("\n".join(initial_rules) + "\n", encoding="utf-8")

    ensure_debt_baseline_unignored(tmp_path)
    content = gi.read_text(encoding="utf-8")
    lines = [line.strip() for line in content.splitlines()]

    # Invariants
    assert ".specops/*" in lines
    assert "!.specops/grandfathered_debt.json" in lines
    blanket_rules = {".specops", ".specops/", "/.specops", "/.specops/"}
    for b in blanket_rules:
        assert b not in lines

    # Idempotence: second call must not modify and return False
    second_modified = ensure_debt_baseline_unignored(tmp_path)
    assert second_modified is False
    assert gi.read_text(encoding="utf-8") == content



