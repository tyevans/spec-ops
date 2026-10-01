"""Comprehensive unit tests for AST self-healing DiagnosticInjector (TASK-0151, ADR-0004)."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

import pytest

from spec_ops.cli.parser import build_parser
from spec_ops.cli.worker_handler import handle_worker_diagnose
from spec_ops.config.models import SpecOpsConfig
from spec_ops.worker.diagnostic_injector import (
    DiagnosticCard,
    DiagnosticInjector,
    find_containing_ast_node,
    resolve_source_file,
)


def test_diagnostic_card_to_dict():
    """Verify DiagnosticCard serialization."""
    card = DiagnosticCard(
        file_path="src/spec_ops/test.py",
        line_number=42,
        node_type="FunctionDef",
        node_name="test_fn",
        source_snippet="def test_fn(): assert True",
        failure_category="assertion_error",
        breached_rule="ADR-0003",
        actionable_guidance="Fix assertion failure.",
    )
    d = card.to_dict()
    assert d["file_path"] == "src/spec_ops/test.py"
    assert d["line_number"] == 42
    assert d["node_type"] == "FunctionDef"
    assert d["node_name"] == "test_fn"
    assert d["source_snippet"] == "def test_fn(): assert True"
    assert d["failure_category"] == "assertion_error"
    assert d["breached_rule"] == "ADR-0003"
    assert d["actionable_guidance"] == "Fix assertion failure."


def test_diagnose_empty_and_whitespace():
    """Verify empty and whitespace inputs return empty cards list."""
    assert DiagnosticInjector.diagnose_failure("") == []
    assert DiagnosticInjector.diagnose_failure("   \n\t  ") == []


def test_diagnose_unmapped_output():
    """Verify non-empty unmapped output returns a graceful unknown card."""
    cards = DiagnosticInjector.diagnose_failure("Some completely unrecognized error occurred")
    assert len(cards) == 1
    card = cards[0]
    assert card.file_path == "unknown"
    assert card.line_number is None
    assert card.failure_category == "unknown"
    assert card.node_type == "unknown"
    assert card.breached_rule is None


def test_find_containing_ast_node_function(tmp_path: Path):
    """Verify AST node locator identifies FunctionDef and AsyncFunctionDef."""
    code = (
        "import os\n"
        "\n"
        "def sync_func(x: int) -> int:\n"
        "    y = x + 1\n"
        "    assert y > 0\n"
        "    return y\n"
        "\n"
        "async def async_func(z: int) -> int:\n"
        "    assert z == 0\n"
        "    return z\n"
    )
    # Line 5 is 'assert y > 0' inside sync_func
    ntype, nname, snip = find_containing_ast_node(code, 5)
    assert ntype == "FunctionDef"
    assert nname == "sync_func"
    assert "def sync_func" in snip
    assert "assert y > 0" in snip

    # Line 9 is 'assert z == 0' inside async_func
    ntype, nname, snip = find_containing_ast_node(code, 9)
    assert ntype == "AsyncFunctionDef"
    assert nname == "async_func"
    assert "async def async_func" in snip


def test_find_containing_ast_node_class_and_statement(tmp_path: Path):
    """Verify AST node locator identifies ClassDef and top-level statements."""
    code = (
        "class ServiceContainer:\n"
        "    DEFAULT_TIMEOUT = 30\n"
        "    CONFIG = {}\n"
        "\n"
        "TOP_LEVEL_ASSERT = True\n"
        "assert TOP_LEVEL_ASSERT\n"
    )
    # Line 2 is inside ServiceContainer
    ntype, nname, snip = find_containing_ast_node(code, 2)
    assert ntype == "ClassDef"
    assert nname == "ServiceContainer"
    assert "class ServiceContainer" in snip

    # Line 6 is top-level assert statement
    ntype, nname, snip = find_containing_ast_node(code, 6)
    assert ntype == "Assert"
    assert nname is None
    assert "assert TOP_LEVEL_ASSERT" in snip


def test_diagnose_syntax_error(tmp_path: Path):
    """Verify Python syntax errors are extracted correctly."""
    bad_file = tmp_path / "broken.py"
    bad_file.write_text("def broken_fn(\n", encoding="utf-8")

    trace = f'  File "{bad_file}", line 1\n    def broken_fn(\n                  ^\nSyntaxError: unexpected EOF while parsing\n'
    cards = DiagnosticInjector.diagnose_failure(trace, repo_root=tmp_path)
    assert len(cards) == 1
    card = cards[0]
    assert card.line_number == 1
    assert card.failure_category == "syntax_error"
    assert "broken.py" in card.file_path
    assert "Fix Python syntax error" in card.actionable_guidance


def test_diagnose_pytest_traceback(tmp_path: Path):
    """Verify standard pytest stack trace extraction."""
    src_file = tmp_path / "app.py"
    src_file.write_text("def calculate():\n    assert 1 == 2\n", encoding="utf-8")

    trace = f"""
    Traceback (most recent call last):
      File "{src_file}", line 2, in calculate
        assert 1 == 2
    AssertionError: assert 1 == 2
    """
    cards = DiagnosticInjector.diagnose_failure(trace, repo_root=tmp_path)
    assert len(cards) >= 1
    card = cards[0]
    assert card.line_number == 2
    assert card.failure_category == "assertion_error"
    assert card.breached_rule == "ADR-0003"
    assert card.node_name == "calculate"


def test_synthesize_retry_prompt_contents():
    """Verify synthesize_retry_prompt structure and invariant rules."""
    card1 = DiagnosticCard(
        file_path="src/large.py",
        line_number=10,
        node_type="ClassDef",
        node_name="GiantClass",
        source_snippet="class GiantClass:\n    pass",
        failure_category="file_limit_violation",
        breached_rule="ADR-0002",
        actionable_guidance="Decompose module.",
    )
    card2 = DiagnosticCard(
        file_path="src/service.py",
        line_number=25,
        node_type="FunctionDef",
        node_name="process",
        source_snippet="def process(): assert False",
        failure_category="assertion_error",
        breached_rule="ADR-0003",
        actionable_guidance="Verify public frontdoors.",
    )

    prompt = DiagnosticInjector.synthesize_retry_prompt([card1, card2])
    assert "## Preflight Failure Diagnostics & AST Self-Healing Guidance" in prompt
    assert "### Issue 1: File Limit Violation" in prompt
    assert "### Issue 2: Assertion Error" in prompt
    assert "src/large.py" in prompt
    assert "src/service.py" in prompt
    assert "ADR-0002" in prompt
    assert "ADR-0003" in prompt
    assert "ADR-0005" in prompt
    assert "ADR-0020" in prompt


def test_cli_diagnose_text_flag(capsys):
    """Verify CLI 'spec-ops worker diagnose --text <trace>'."""
    args = argparse.Namespace(
        trace_text="src/spec_ops/test.py:15: AssertionError: assert 0 == 1",
        log_file=None,
        json=False,
    )
    code = handle_worker_diagnose(args, SpecOpsConfig())
    assert code == 0
    captured = capsys.readouterr()
    assert "src/spec_ops/test.py" in captured.out
    assert "ADR-0003" in captured.out


def test_cli_diagnose_json_flag(capsys):
    """Verify CLI 'spec-ops worker diagnose --text <trace> --json'."""
    args = argparse.Namespace(
        trace_text="src/spec_ops/test.py:15: AssertionError: assert 0 == 1",
        log_file=None,
        json=True,
    )
    code = handle_worker_diagnose(args, SpecOpsConfig())
    assert code == 0
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert isinstance(data, list)
    assert len(data) == 1
    assert data[0]["failure_category"] == "assertion_error"
    assert data[0]["line_number"] == 15


def test_cli_diagnose_missing_log_file(capsys):
    """Verify CLI error on non-existent log file."""
    args = argparse.Namespace(
        trace_text=None,
        log_file="non_existent_file.log",
        json=False,
    )
    code = handle_worker_diagnose(args, SpecOpsConfig())
    assert code == 1
    captured = capsys.readouterr()
    assert "Error: Log file not found" in captured.err


def test_parser_has_worker_diagnose():
    """Verify build_parser registers 'worker diagnose'."""
    parser = build_parser()
    args = parser.parse_args(["worker", "diagnose", "--text", "foo:1: AssertionError", "--json"])
    assert args.worker_action == "diagnose"
    assert args.trace_text == "foo:1: AssertionError"
    assert args.json is True


def test_diagnostic_injector_file_length_under_400():
    """Verify file length invariant (ADR-0002) for diagnostic_injector.py."""
    module_path = Path(__file__).resolve().parent.parent / "src" / "spec_ops" / "worker" / "diagnostic_injector.py"
    line_count = len(module_path.read_text(encoding="utf-8").splitlines())
    assert line_count < 400, f"diagnostic_injector.py is {line_count} lines, must be < 400 lines (ADR-0002)"
