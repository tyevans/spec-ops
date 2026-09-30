"""Tests for dynamic pytest-bdd mark registration and test manipulation."""

import subprocess
import sys
import warnings
from pathlib import Path
from typing import Any

import pytest
from _pytest.warning_types import PytestUnknownMarkWarning

from tests.conftest import ROOT_DIR, _discover_dynamic_marks, pytest_bdd_apply_tag


def test_discover_dynamic_marks_finds_feature_tags_and_user_stories():
    """Verify dynamic discovery collects tags from .feature files and user stories."""
    marks = _discover_dynamic_marks(ROOT_DIR)

    # Core user stories and feature tags that exist in the repository
    assert "us_0106" in marks
    assert "us_0001" in marks
    assert "us_0116" in marks
    assert "visualizer" in marks
    assert "architecture" in marks
    assert "security" in marks
    assert "sandboxing" in marks
    assert "worktree" in marks
    assert "cli" in marks

    # Pre-registered range
    for i in range(1, 51):
        assert f"us_{i:04d}" in marks


def test_pytest_bdd_apply_tag_registers_unseen_tags_dynamically():
    """Verify pytest_bdd_apply_tag registers new marks dynamically on the fly."""
    new_tag = "test_dynamic_unseen_tag_xyz123"

    def dummy_test_function():
        pass

    with warnings.catch_warnings(record=True) as recorded:
        warnings.simplefilter("always")
        applied = pytest_bdd_apply_tag(new_tag, dummy_test_function)

    assert applied is True
    # Ensure no PytestUnknownMarkWarning was issued
    unknown_mark_warnings = [
        w for w in recorded if issubclass(w.category, PytestUnknownMarkWarning)
    ]
    assert unknown_mark_warnings == []

    # Verify the mark is actually applied to the function
    assert hasattr(dummy_test_function, "pytestmark")
    marker_names = [m.name for m in dummy_test_function.pytestmark]
    assert new_tag in marker_names


def test_pytest_mark_dynamic_getattr_registers_marker():
    """Verify accessing pytest.mark.<new_name> registers dynamically without warning."""
    tag_name = "us_9999_dynamic_test"

    with warnings.catch_warnings(record=True) as recorded:
        warnings.simplefilter("always")
        mark_dec = getattr(pytest.mark, tag_name)

    assert mark_dec.name == tag_name
    unknown_mark_warnings = [
        w for w in recorded if issubclass(w.category, PytestUnknownMarkWarning)
    ]
    assert unknown_mark_warnings == []


def test_pytest_run_with_strict_markers_and_custom_mark():
    """Verify running pytest with --strict-markers -m <mark> succeeds without error."""
    cmd = [
        sys.executable,
        "-m",
        "pytest",
        "--strict-markers",
        "-m",
        "us_0106",
        "tests/test_bdd_us0106_architectural_radar.py",
    ]
    result = subprocess.run(cmd, cwd=str(ROOT_DIR), capture_output=True, text=True)
    assert result.returncode == 0
    assert "3 passed" in result.stdout
    assert "PytestUnknownMarkWarning" not in result.stderr
    assert "PytestUnknownMarkWarning" not in result.stdout


def test_pytest_manipulate_selection_by_mark():
    """Verify test selection and deselection using -m flag."""
    # Positive selection
    cmd_pos = [
        sys.executable,
        "-m",
        "pytest",
        "-m",
        "us_0106 and visualizer",
        "tests/test_bdd_us0106_architectural_radar.py",
    ]
    res_pos = subprocess.run(cmd_pos, cwd=str(ROOT_DIR), capture_output=True, text=True)
    assert res_pos.returncode == 0
    assert "3 passed" in res_pos.stdout

    # Negative selection (deselection)
    cmd_neg = [
        sys.executable,
        "-m",
        "pytest",
        "-m",
        "not visualizer",
        "tests/test_bdd_us0106_architectural_radar.py",
    ]
    res_neg = subprocess.run(cmd_neg, cwd=str(ROOT_DIR), capture_output=True, text=True)
    # Pytest exits with 5 when all tests are deselected
    assert res_neg.returncode == 5
    assert "3 deselected" in res_neg.stdout
