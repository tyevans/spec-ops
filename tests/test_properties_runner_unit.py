"""Unit tests for properties_runner.py.

Governed by ADR-0001, ADR-0002, ADR-0003, ADR-0009.
Target Bounded Context: core. File length strictly under 400 lines.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import pytest
from hypothesis import settings

from spec_ops.config.models import SpecOpsConfig
from spec_ops.core.properties_runner import (
    PropertyRunReport,
    PropertyTestResult,
    _derive_suite_name,
    configure_hypothesis_profile,
    discover_property_tests,
    handle_properties_command,
    run_property_tests,
)


def test_derive_suite_name_keywords():
    def f_roundtrip():
        """Parser Round-Trip Invariant: Round trips."""

    def f_acyclic():
        """Graph Acyclicity: DAG test."""

    def f_boundary():
        """Boundary Classification: File limits."""

    def f_buffer():
        """Buffer Capacity: Backlog check."""

    def f_perm():
        """Graph Permutation Invariance: Order test."""

    assert _derive_suite_name(f_roundtrip) == "Parser Round-Trip"
    assert _derive_suite_name(f_acyclic) == "Graph Acyclicity"
    assert _derive_suite_name(f_boundary) == "Boundary Classification"
    assert _derive_suite_name(f_buffer) == "Buffer Capacity"
    assert _derive_suite_name(f_perm) == "Graph Permutation Invariance"


def test_derive_suite_name_fallbacks():
    def f_custom():
        """Invariant: Custom Property Test."""

    def f_colon():
        """Prefix Invariant: Does something."""

    def test_property_something_cool():
        pass

    def test_plain_function():
        pass

    def raw_identifier():
        pass

    assert _derive_suite_name(f_custom) == "Custom Property Test"
    assert _derive_suite_name(f_colon) == "Prefix Invariant"
    assert _derive_suite_name(test_property_something_cool) == "Something Cool"
    assert _derive_suite_name(test_plain_function) == "Plain Function"
    assert _derive_suite_name(raw_identifier) == "raw_identifier"


def test_configure_hypothesis_profile():
    ex1 = configure_hypothesis_profile(max_examples=50)
    assert ex1 == 50
    prof = settings.get_profile("specops_deterministic")
    assert prof.max_examples == 50
    assert prof.deadline is None

    ex2 = configure_hypothesis_profile(max_examples=None)
    assert ex2 == 100

    ex3 = configure_hypothesis_profile(max_examples=0)
    assert ex3 == 100

    ex4 = configure_hypothesis_profile(max_examples=-5)
    assert ex4 == 100


def test_discover_property_tests(tmp_path: Path):
    test_file = tmp_path / "test_sample_properties.py"
    test_file.write_text(
        'def test_property_one():\n'
        '    """Boundary Classification: Test one."""\n'
        '    pass\n\n'
        'def test_property_two():\n'
        '    """Buffer Capacity: Test two."""\n'
        '    pass\n\n'
        'def helper_not_test():\n'
        '    pass\n',
        encoding="utf-8",
    )

    discovered = discover_property_tests(target_path=test_file, root_dir=tmp_path)
    assert len(discovered) == 2
    names = [d[0] for d in discovered]
    assert "Boundary Classification" in names
    assert "Buffer Capacity" in names

    # Filter expression matching
    filtered = discover_property_tests(target_path=test_file, root_dir=tmp_path, filter_expr="boundary")
    assert len(filtered) == 1
    assert filtered[0][0] == "Boundary Classification"

    # Filter expression non-matching
    non_matching = discover_property_tests(target_path=test_file, root_dir=tmp_path, filter_expr="non_existent")
    assert len(non_matching) == 0

    # Directory discovery
    dir_discovered = discover_property_tests(target_path=tmp_path, root_dir=tmp_path)
    assert len(dir_discovered) == 2


def test_discover_property_tests_nonexistent(tmp_path: Path):
    empty_discovered = discover_property_tests(target_path=tmp_path / "missing.py", root_dir=tmp_path)
    assert len(empty_discovered) == 0


def test_run_property_tests_success(tmp_path: Path):
    test_file = tmp_path / "test_success_properties.py"
    test_file.write_text(
        'def test_property_math():\n'
        '    """Invariant: Pure Math."""\n'
        '    assert 2 + 2 == 4\n',
        encoding="utf-8",
    )

    report = run_property_tests(target_path=test_file, root_dir=tmp_path, max_examples=10)
    assert report.is_success is True
    assert report.total_count == 1
    assert report.passed_count == 1
    assert report.failed_count == 0
    assert len(report.results) == 1
    assert report.results[0].status == "passed"
    assert report.results[0].name == "Pure Math"
    assert "Invariant Verification Passed" in report.format_output()


def test_run_property_tests_failure(tmp_path: Path):
    test_file = tmp_path / "test_fail_properties.py"
    test_file.write_text(
        'def test_property_flaky():\n'
        '    """Invariant: Broken Contract."""\n'
        '    raise ValueError("Explicit test regression")\n',
        encoding="utf-8",
    )

    report = run_property_tests(target_path=test_file, root_dir=tmp_path, max_examples=5)
    assert report.is_success is False
    assert report.total_count == 1
    assert report.passed_count == 0
    assert report.failed_count == 1
    assert "ValueError: Explicit test regression" in report.results[0].error_message
    assert "Invariant Verification Failed" in report.format_output()


def test_property_run_report_empty():
    report = PropertyRunReport()
    assert report.is_success is False
    assert report.total_count == 0
    d = report.to_dict()
    assert d["is_success"] is False
    assert d["total_count"] == 0


def test_handle_properties_command_text(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    test_file = tmp_path / "test_cmd_properties.py"
    test_file.write_text(
        'def test_property_ok():\n'
        '    """Parser Round-Trip: Ok."""\n'
        '    assert True\n',
        encoding="utf-8",
    )

    cfg = SpecOpsConfig(root_dir=tmp_path)
    args = argparse.Namespace(
        path=str(test_file),
        opt_path=None,
        max_examples=10,
        json=False,
        filter_expr=None,
    )
    rc = handle_properties_command(args, cfg)
    assert rc == 0
    captured = capsys.readouterr()
    assert "Parser Round-Trip" in captured.out
    assert "Invariant Verification Passed" in captured.out


def test_handle_properties_command_json(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    test_file = tmp_path / "test_cmd_properties.py"
    test_file.write_text(
        'def test_property_ok():\n'
        '    """Parser Round-Trip: Ok."""\n'
        '    assert True\n',
        encoding="utf-8",
    )

    cfg = SpecOpsConfig(root_dir=tmp_path)
    args = argparse.Namespace(
        path=str(test_file),
        opt_path=None,
        max_examples=10,
        json=True,
        filter_expr=None,
    )
    rc = handle_properties_command(args, cfg)
    assert rc == 0
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert data["is_success"] is True
    assert data["total_count"] == 1
    assert data["passed_count"] == 1
    assert data["results"][0]["name"] == "Parser Round-Trip"


def test_handle_properties_command_failure_json(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    test_file = tmp_path / "test_cmd_properties.py"
    test_file.write_text(
        'def test_property_fail():\n'
        '    """Graph Acyclicity: Fails."""\n'
        '    assert 1 == 2\n',
        encoding="utf-8",
    )

    cfg = SpecOpsConfig(root_dir=tmp_path)
    args = argparse.Namespace(
        path=str(test_file),
        opt_path=None,
        max_examples=10,
        json=True,
        filter_expr=None,
    )
    rc = handle_properties_command(args, cfg)
    assert rc == 1
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert data["is_success"] is False
    assert data["failed_count"] == 1


def test_handle_properties_command_failure_text(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    test_file = tmp_path / "test_cmd_properties.py"
    test_file.write_text(
        'def test_property_fail():\n'
        '    """Graph Acyclicity: Fails."""\n'
        '    assert 1 == 2\n',
        encoding="utf-8",
    )

    cfg = SpecOpsConfig(root_dir=tmp_path)
    args = argparse.Namespace(
        path=str(test_file),
        opt_path=None,
        max_examples=10,
        json=False,
        filter_expr=None,
    )
    rc = handle_properties_command(args, cfg)
    assert rc == 1
    captured = capsys.readouterr()
    assert "Invariant Verification Failed" in captured.err
