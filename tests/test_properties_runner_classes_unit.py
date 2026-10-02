"""Unit tests for test class and Hypothesis attribute discovery in properties_runner.

Governed by ADR-0001, ADR-0002, ADR-0003, ADR-0009; PRD-0003; US-0001; TASK-0180.
Target Bounded Context: core. File length strictly under 400 lines.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from hypothesis import given, strategies as st

from spec_ops.core.properties_runner import (
    discover_property_tests,
    is_hypothesis_test,
    run_property_tests,
)


def test_is_hypothesis_test_non_callable():
    assert is_hypothesis_test(123) is False
    assert is_hypothesis_test("not_a_func") is False
    assert is_hypothesis_test(None) is False


def test_is_hypothesis_test_attributes():
    def standard_func():
        pass

    assert is_hypothesis_test(standard_func) is False
    assert is_hypothesis_test(standard_func, name="test_property_foo") is True
    assert is_hypothesis_test(standard_func, name="test_something_properties") is True

    class CustomMarker:
        pass

    def dummy():
        pass

    dummy.is_hypothesis_test = True  # type: ignore[attr-defined]
    assert is_hypothesis_test(dummy) is True

    dummy2 = lambda: None
    dummy2.hypothesis = CustomMarker()  # type: ignore[attr-defined]
    assert is_hypothesis_test(dummy2) is True

    dummy3 = lambda: None
    dummy3._hypothesis_internal_use_raw_state = True  # type: ignore[attr-defined]
    assert is_hypothesis_test(dummy3) is True

    dummy4 = lambda: None
    dummy4._hypothesis_internal_use_seed = 42  # type: ignore[attr-defined]
    assert is_hypothesis_test(dummy4) is True

    dummy5 = lambda: None
    dummy5._hypothesis_internal_use_settings = {}  # type: ignore[attr-defined]
    assert is_hypothesis_test(dummy5) is True

    dummy6 = lambda: None
    dummy6._hypothesis_internal_given_arguments = ()  # type: ignore[attr-defined]
    assert is_hypothesis_test(dummy6) is True


def test_discover_test_class_methods(tmp_path: Path):
    test_file = tmp_path / "test_class_properties.py"
    test_file.write_text(
        'from hypothesis import given, strategies as st\n\n'
        'class TestClassA:\n'
        '    """Test Suite A."""\n'
        '    executed = []\n\n'
        '    @given(st.integers())\n'
        '    def test_given_method(self, x):\n'
        '        """Parser Round-Trip: Tests round trip."""\n'
        '        TestClassA.executed.append(x)\n\n'
        '    def test_property_plain(self):\n'
        '        pass\n\n'
        '    def not_a_test(self):\n'
        '        pass\n\n'
        'class HelperClass:\n'
        '    def test_ignored(self):\n'
        '        pass\n',
        encoding="utf-8",
    )

    discovered = discover_property_tests(target_path=test_file, root_dir=tmp_path)
    ids = [item[2] for item in discovered]
    assert "TestClassA::test_given_method" in ids
    assert "TestClassA::test_property_plain" in ids
    assert "HelperClass::test_ignored" not in ids

    # Ensure suite names are derived correctly
    suite_by_id = {item[2]: item[0] for item in discovered}
    assert suite_by_id["TestClassA::test_given_method"] == "Parser Round-Trip"
    assert suite_by_id["TestClassA::test_property_plain"] == "Plain"


def test_discover_test_class_filter(tmp_path: Path):
    test_file = tmp_path / "test_filter_properties.py"
    test_file.write_text(
        'class TestClassOne:\n'
        '    def test_property_alpha(self):\n'
        '        pass\n'
        '    def test_property_beta(self):\n'
        '        pass\n',
        encoding="utf-8",
    )

    discovered_alpha = discover_property_tests(
        target_path=test_file,
        root_dir=tmp_path,
        filter_expr="alpha",
    )
    assert len(discovered_alpha) == 1
    assert discovered_alpha[0][2] == "TestClassOne::test_property_alpha"


def test_discover_test_class_init_exception_fallback(tmp_path: Path):
    test_file = tmp_path / "test_init_fail_properties.py"
    test_file.write_text(
        'class TestFailingInit:\n'
        '    def __init__(self):\n'
        '        raise RuntimeError("Init failed")\n'
        '    def test_property_works(self):\n'
        '        pass\n',
        encoding="utf-8",
    )

    discovered = discover_property_tests(target_path=test_file, root_dir=tmp_path)
    assert len(discovered) == 1
    assert discovered[0][2] == "TestFailingInit::test_property_works"
    # Executing the bound method should not fail
    fn = discovered[0][1]
    fn()


def test_run_property_tests_with_test_class(tmp_path: Path):
    test_file = tmp_path / "test_run_class_properties.py"
    test_file.write_text(
        'from hypothesis import given, strategies as st\n\n'
        'class TestExecution:\n'
        '    @given(st.integers(min_value=0, max_value=10))\n'
        '    def test_bounded(self, val):\n'
        '        assert 0 <= val <= 10\n',
        encoding="utf-8",
    )

    report = run_property_tests(target_path=test_file, root_dir=tmp_path, max_examples=10)
    assert report.total_count == 1
    assert report.passed_count == 1
    assert report.failed_count == 0
    assert report.results[0].function_name == "TestExecution::test_bounded"
