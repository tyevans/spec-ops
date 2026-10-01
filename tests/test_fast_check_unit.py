"""Unit tests for sub-second IDE invariant diagnostics (TASK-0055, US-0091).

Governed by ADR-0001, ADR-0002, ADR-0003, ADR-0007, ADR-0008.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import pytest

from spec_ops.cli.main import main
from spec_ops.config.models import SpecOpsConfig
from spec_ops.rescue.fast_check import (
    DiagnosticViolation,
    FastCheckResult,
    determine_file_context,
    handle_fast_check_command,
    run_fast_check,
)


def test_clean_file_evaluation(tmp_path: Path):
    f = tmp_path / "src" / "spec_ops" / "rescue" / "helper.py"
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text("def hello():\n    return 'world'\n", encoding="utf-8")

    res = run_fast_check(f, output_format="text", root_dir=tmp_path)
    assert res.status == "clean"
    assert res.lines == 2
    assert res.exit_code == 0
    assert "Clean" in res.to_text()

    json_payload = json.loads(res.to_json())
    assert json_payload["status"] == "clean"
    assert json_payload["lines"] == 2

    sarif_payload = json.loads(res.to_sarif())
    assert len(sarif_payload["runs"][0]["results"]) == 0


def test_warning_threshold_evaluation(tmp_path: Path):
    f = tmp_path / "src" / "spec_ops" / "backlog" / "curator.py"
    f.parent.mkdir(parents=True, exist_ok=True)
    content = "\n".join(f"x_{i} = {i}" for i in range(415)) + "\n"
    f.write_text(content, encoding="utf-8")

    res = run_fast_check(f, output_format="json", root_dir=tmp_path)
    assert res.status == "warning"
    assert res.lines == 415
    assert res.exit_code == 0
    assert "Approaching file length limit (415/500 lines)" in res.message

    json_data = json.loads(res.to_json())
    assert json_data["status"] == "warning"
    assert json_data["lines"] == 415


def test_error_threshold_evaluation(tmp_path: Path):
    f = tmp_path / "src" / "spec_ops" / "core" / "graph.py"
    f.parent.mkdir(parents=True, exist_ok=True)
    content = "\n".join(f"y_{i} = {i}" for i in range(508)) + "\n"
    f.write_text(content, encoding="utf-8")

    res = run_fast_check(f, output_format="sarif", root_dir=tmp_path)
    assert res.status == "error"
    assert res.lines == 508
    assert res.exit_code == 1
    assert "Hard Invariant Violation: File exceeds 500 lines (508 lines)" in res.message

    sarif = json.loads(res.to_sarif())
    results = sarif["runs"][0]["results"]
    assert len(results) == 1
    assert results[0]["level"] == "error"
    assert results[0]["locations"][0]["physicalLocation"]["region"]["startLine"] == 501


def test_boundary_line_cases(tmp_path: Path):
    f = tmp_path / "boundary.py"

    # 399 lines -> clean
    f.write_text("\n".join(f"# {i}" for i in range(399)) + "\n", encoding="utf-8")
    assert run_fast_check(f).status == "clean"

    # 400 lines -> warning
    f.write_text("\n".join(f"# {i}" for i in range(400)) + "\n", encoding="utf-8")
    assert run_fast_check(f).status == "warning"

    # 499 lines -> warning
    f.write_text("\n".join(f"# {i}" for i in range(499)) + "\n", encoding="utf-8")
    assert run_fast_check(f).status == "warning"

    # 500 lines -> error
    f.write_text("\n".join(f"# {i}" for i in range(500)) + "\n", encoding="utf-8")
    assert run_fast_check(f).status == "error"


def test_nonexistent_file():
    res = run_fast_check("/nonexistent/file/path.py")
    assert res.status == "error"
    assert res.exit_code == 1
    assert "Target file not found" in res.message


def test_syntax_error_resilience(tmp_path: Path):
    f = tmp_path / "src" / "spec_ops" / "visualizer" / "broken.py"
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text("def broken(:\n    pass\n", encoding="utf-8")

    res = run_fast_check(f, root_dir=tmp_path)
    assert res.status == "error"
    assert res.exit_code == 1
    assert any("SyntaxError" in v.message for v in res.violations)


def test_bounded_context_import_violation_variants(tmp_path: Path):
    f = tmp_path / "src" / "spec_ops" / "visualizer" / "generator.py"
    f.parent.mkdir(parents=True, exist_ok=True)

    # Direct import
    f.write_text("import spec_ops.backlog.worker\n", encoding="utf-8")
    res1 = run_fast_check(f, root_dir=tmp_path)
    assert res1.status == "error"
    assert "Bounded Context Violation: 'visualizer' cannot directly import internal module 'backlog.worker'" in res1.message

    # From import
    f.write_text("from spec_ops.backlog.worker import run_worker\n", encoding="utf-8")
    res2 = run_fast_check(f, root_dir=tmp_path)
    assert res2.status == "error"
    assert "Bounded Context Violation: 'visualizer' cannot directly import internal module 'backlog.worker'" in res2.message

    # Submodule import
    f.write_text("from spec_ops.backlog import worker\n", encoding="utf-8")
    res3 = run_fast_check(f, root_dir=tmp_path)
    assert res3.status == "error"
    assert "Bounded Context Violation: 'visualizer' cannot directly import internal module 'backlog.worker'" in res3.message


def test_allowed_imports(tmp_path: Path):
    f = tmp_path / "src" / "spec_ops" / "visualizer" / "clean.py"
    f.parent.mkdir(parents=True, exist_ok=True)

    # Intra-context, shared kernel, and standard library
    content = (
        "import os\n"
        "import sys\n"
        "from spec_ops.core.models import Task\n"
        "from spec_ops.config.models import SpecOpsConfig\n"
        "from .radar_script import harvest_architecture_radar\n"
    )
    f.write_text(content, encoding="utf-8")

    res = run_fast_check(f, root_dir=tmp_path)
    assert res.status == "clean"
    assert res.exit_code == 0
    assert len(res.violations) == 0


def test_cli_missing_file_handling(capsys: pytest.CaptureFixture):
    parser_args = argparse.Namespace(file=None, positional_file=None, format="text")
    config = SpecOpsConfig(root_dir=Path("."))
    code = handle_fast_check_command(parser_args, config)
    assert code == 1
    captured = capsys.readouterr()
    assert "Target file required" in captured.err


def test_sub_50ms_execution_performance(tmp_path: Path):
    f = tmp_path / "src" / "spec_ops" / "rescue" / "benchmark.py"
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text("\n".join(f"val_{i} = {i}" for i in range(350)) + "\n", encoding="utf-8")

    t0 = time.perf_counter()
    res = run_fast_check(f, root_dir=tmp_path)
    dur = (time.perf_counter() - t0) * 1000

    assert res.exit_code == 0
    assert dur < 50.0, f"Expected <50ms, took {dur:.2f}ms"
