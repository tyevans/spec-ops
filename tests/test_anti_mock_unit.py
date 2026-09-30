"""Unit tests for AST anti-mock quality gate and CLI test handler."""

from __future__ import annotations

import argparse
import ast
import json
from pathlib import Path
from typing import Any

import pytest

from spec_ops.cli.test_handler import handle_test_command
from spec_ops.config.models import SpecOpsConfig
from spec_ops.core.anti_mock import (
    AntiMockAuditReport,
    AntiMockViolation,
    _extract_snippet,
    _is_private_name,
    _resolve_call_path,
    audit_test_suite,
    resolve_mutation_stats,
    scan_test_code,
    scan_test_file,
    scan_test_tree,
)


def test_is_private_name():
    assert _is_private_name("_internal") is True
    assert _is_private_name("_foo_bar") is True
    assert _is_private_name("__init__") is False
    assert _is_private_name("__future__") is False
    assert _is_private_name("public") is False
    assert _is_private_name("CamelCase") is False


def test_resolve_call_path():
    assert _resolve_call_path(ast.Name(id="patch")) == "patch"
    attr_node = ast.Attribute(value=ast.Name(id="patch"), attr="object")
    assert _resolve_call_path(attr_node) == "patch.object"
    nested_node = ast.Attribute(
        value=ast.Attribute(value=ast.Name(id="unittest"), attr="mock"),
        attr="patch",
    )
    assert _resolve_call_path(nested_node) == "unittest.mock.patch"
    assert _resolve_call_path(ast.Constant(value=42)) == ""


def test_extract_snippet():
    lines = ["first line", "second line", "third line"]
    assert _extract_snippet(lines, 1) == "first line"
    assert _extract_snippet(lines, 2) == "second line"
    assert _extract_snippet(lines, 3) == "third line"
    assert _extract_snippet(lines, 0) == ""
    assert _extract_snippet(lines, 4) == ""
    assert _extract_snippet(lines, -1) == ""


def test_anti_mock_violation_formatting():
    v_with_snippet = AntiMockViolation(
        file_path="tests/test_foo.py",
        line=10,
        column=4,
        rule="prohibited_mock_import",
        message="Import forbidden",
        snippet="import unittest.mock",
    )
    diag = v_with_snippet.format_diagnostic()
    assert "tests/test_foo.py:10:4" in diag
    assert "Line 10: import unittest.mock" in diag
    assert "Import forbidden" in diag
    assert "ADR-0003" in diag

    v_no_snippet = AntiMockViolation(
        file_path="tests/test_bar.py",
        line=5,
        column=0,
        rule="prohibited_mock_call",
        message="Call forbidden",
        snippet="",
    )
    diag_no = v_no_snippet.format_diagnostic()
    assert "tests/test_bar.py:5:0" in diag_no
    assert "Line 5:" not in diag_no


def test_audit_report_clean_and_violations():
    clean_report = AntiMockAuditReport(
        scanned_files=5,
        violations=[],
        mutation_score=85.0,
    )
    assert clean_report.is_clean is True
    out_clean = clean_report.format_output()
    assert "Frontdoor Verification Passed: 0 private backdoors detected" in out_clean
    assert "Mutation Kill Score: 85%" in out_clean

    viol_report = AntiMockAuditReport(
        scanned_files=2,
        violations=[
            AntiMockViolation(
                file_path="test_a.py",
                line=3,
                column=2,
                rule="mock",
                message="Mock detected",
            )
        ],
        mutation_score=85.0,
    )
    assert viol_report.is_clean is False
    out_viol = viol_report.format_output()
    assert "Found 1 prohibited mock backdoor violation" in out_viol
    assert "test_a.py:3:2" in out_viol


def test_audit_report_strict_mutation():
    strict_failing = AntiMockAuditReport(
        scanned_files=4,
        violations=[],
        mutation_score=68.0,
        surviving_mutants=["mutant_1", "mutant_3"],
        untyped_branches=["Branch at line 45: missing property test"],
        strict_mutation=True,
        mutation_threshold=80.0,
    )
    assert strict_failing.is_clean is False
    out_strict = strict_failing.format_output()
    assert "Mutation Score Invariant Failed: 68.0% < 80.0%" in out_strict
    assert "mutant_1" in out_strict
    assert "mutant_3" in out_strict
    assert "Branch at line 45" in out_strict

    strict_passing = AntiMockAuditReport(
        scanned_files=4,
        violations=[],
        mutation_score=82.5,
        strict_mutation=True,
        mutation_threshold=80.0,
    )
    assert strict_passing.is_clean is True
    out_pass = strict_passing.format_output()
    assert "Frontdoor Verification Passed" in out_pass
    assert "82.5%" in out_pass


def test_scan_test_code_syntax_error():
    bad_syntax = "def test_invalid(\n"
    violations = scan_test_code(bad_syntax, "tests/test_broken.py")
    assert len(violations) == 1
    assert violations[0].rule == "syntax_error"
    assert "Syntax error parsing" in violations[0].message


def test_scan_test_code_imports():
    code_mod_import = "import unittest.mock\nimport mock\nimport pytest_mock\nimport _private_mod\nimport sys\n"
    v = scan_test_code(code_mod_import)
    assert len(v) == 4
    rules = [x.rule for x in v]
    assert rules.count("prohibited_mock_import") == 3
    assert rules.count("private_symbol_import") == 1

    code_from_import = (
        "from unittest.mock import patch, MagicMock\n"
        "from unittest import mock, TestCase\n"
        "from _internal_pkg import helper\n"
        "from my_module import _hidden_fn, public_fn\n"
        "from __future__ import annotations\n"
    )
    v2 = scan_test_code(code_from_import)
    assert len(v2) >= 4


def test_scan_test_code_monkeypatching():
    code_patch = (
        "def test_tamper(monkeypatch):\n"
        "    monkeypatch.setattr(obj, '_secret', 42)\n"
        "    monkeypatch.delattr(obj, '_secret')\n"
        "    monkeypatch.setattr('pkg._internal.fn', dummy)\n"
        "    monkeypatch.setattr(obj, 'public_attr', 100)\n"
        "    monkeypatch.setattr('pkg.public_mod.fn', dummy)\n"
    )
    v = scan_test_code(code_patch)
    assert len(v) == 3
    for viol in v:
        assert viol.rule == "private_monkeypatch"


def test_scan_test_file_and_tree(tmp_path: Path):
    assert scan_test_file(tmp_path / "nonexistent.py") == []

    f_clean = tmp_path / "test_clean.py"
    f_clean.write_text("def test_ok(): assert True\n", encoding="utf-8")
    assert scan_test_file(f_clean) == []

    f_bad = tmp_path / "test_bad.py"
    f_bad.write_text("from unittest.mock import patch\n", encoding="utf-8")
    assert len(scan_test_file(f_bad)) == 1

    # Excluded directories
    venv_dir = tmp_path / ".venv"
    venv_dir.mkdir()
    f_venv = venv_dir / "test_venv.py"
    f_venv.write_text("from unittest.mock import patch\n", encoding="utf-8")

    tree_violations = scan_test_tree(tmp_path)
    assert len(tree_violations) == 1
    assert "test_bad.py" in tree_violations[0].file_path


def test_resolve_mutation_stats(tmp_path: Path):
    score, surv, untyped = resolve_mutation_stats(tmp_path)
    assert score == 85.0
    assert surv == []
    assert untyped == []

    specops_dir = tmp_path / ".specops"
    specops_dir.mkdir()
    (specops_dir / "mutation_report.json").write_text(
        json.dumps({
            "mutation_score": 75.5,
            "surviving_mutants": ["m1", "m2"],
            "untyped_branches": ["b1"],
        }),
        encoding="utf-8",
    )
    s2, surv2, un2 = resolve_mutation_stats(tmp_path)
    assert s2 == 75.5
    assert surv2 == ["m1", "m2"]
    assert un2 == ["b1"]

    # Test mutants/mutmut-cicd-stats.json
    (specops_dir / "mutation_report.json").unlink()
    mutants_dir = tmp_path / "mutants"
    mutants_dir.mkdir()
    (mutants_dir / "mutmut-cicd-stats.json").write_text(
        json.dumps({
            "total": 10,
            "killed": 8,
            "survived": 2,
        }),
        encoding="utf-8",
    )
    s3, surv3, un3 = resolve_mutation_stats(tmp_path)
    assert s3 == 80.0
    assert surv3 == ["mutant_1", "mutant_2"]


def test_audit_test_suite_runner(tmp_path: Path):
    tests = tmp_path / "tests"
    tests.mkdir()
    (tests / "test_one.py").write_text("def test_1(): pass\n", encoding="utf-8")

    rep = audit_test_suite(target_path="tests", root_dir=tmp_path)
    assert rep.is_clean is True
    assert rep.scanned_files == 1

    (tests / "test_one.py").write_text("import unittest.mock\n", encoding="utf-8")
    rep_viol = audit_test_suite(target_path="tests", root_dir=tmp_path)
    assert rep_viol.is_clean is False
    assert len(rep_viol.violations) == 1


def test_handle_test_command_cli(tmp_path: Path, capsys: pytest.CaptureFixture):
    parser = argparse.ArgumentParser()
    config = SpecOpsConfig(root_dir=tmp_path)

    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_app.py").write_text("def test_app(): assert 1 == 1\n", encoding="utf-8")

    # Missing action -> SystemExit(0) via help
    args_no_action = argparse.Namespace(test_action=None)
    with pytest.raises(SystemExit) as exc_info:
        handle_test_command(args_no_action, config, parser)
    assert exc_info.value.code == 0

    # Clean test suite
    args_clean = argparse.Namespace(
        test_action="audit-anti-mock",
        path="tests",
        opt_path=None,
        strict_mutation=False,
        threshold=80.0,
        json=False,
    )
    assert handle_test_command(args_clean, config, parser) == 0
    captured = capsys.readouterr()
    assert "Frontdoor Verification Passed" in captured.out

    # JSON output
    args_json = argparse.Namespace(
        test_action="verify-frontdoors",
        path="tests",
        opt_path=None,
        strict_mutation=False,
        threshold=80.0,
        json=True,
    )
    assert handle_test_command(args_json, config, parser) == 0
    out_json = capsys.readouterr().out
    data = json.loads(out_json)
    assert data["is_clean"] is True
    assert data["scanned_files"] == 1

    # Violating test suite
    (tests_dir / "test_app.py").write_text("import unittest.mock\n", encoding="utf-8")
    assert handle_test_command(args_clean, config, parser) == 1
    err_out = capsys.readouterr().err
    assert "Found 1 prohibited mock backdoor violation" in err_out
