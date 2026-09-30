"""Unit and mutation kill test suite for mutation gate runner and report generator (ADR-0009)."""

from __future__ import annotations

import argparse
import json
import sys
from io import StringIO
from pathlib import Path

from spec_ops.cli.test_handler import handle_mutation_command, handle_test_command
from spec_ops.config.models import SpecOpsConfig
from spec_ops.core.mutation_gate import (
    MutationReport,
    SurvivingMutant,
    calculate_mutation_score,
    execute_mutmut_run,
    load_specops_report,
    parse_diff_details,
    parse_mutmut_results,
    run_mutation_gate,
)


def test_calculate_mutation_score_edge_cases():
    assert calculate_mutation_score(0, 0) == 100.0
    assert calculate_mutation_score(0, 0, default_on_zero=0.0) == 0.0
    assert calculate_mutation_score(-5, 0) == 100.0
    assert calculate_mutation_score(0, 10) == 0.0
    assert calculate_mutation_score(-2, 10) == 0.0
    assert calculate_mutation_score(10, 10) == 100.0
    assert calculate_mutation_score(15, 10) == 100.0
    assert calculate_mutation_score(84, 100) == 84.0
    assert calculate_mutation_score(168, 200) == 84.0
    assert calculate_mutation_score(71, 100) == 71.0


def test_surviving_mutant_to_dict():
    mutant = SurvivingMutant(
        mutant_id="m1",
        file_path="src/core/calc.py",
        line=42,
        expression="a - b",
        diff="--- a\n+++ b",
    )
    d = mutant.to_dict()
    assert d["id"] == "m1"
    assert d["mutant_id"] == "m1"
    assert d["file_path"] == "src/core/calc.py"
    assert d["line"] == 42
    assert d["expression"] == "a - b"
    assert d["diff"] == "--- a\n+++ b"


def test_mutation_report_formatting_passed():
    report = MutationReport(
        target_module="src/spec_ops/core",
        threshold=80.0,
        killed_count=168,
        survived_count=32,
        timeout_count=0,
    )
    assert report.total_mutants == 200
    assert report.mutation_score == 84.0
    assert report.is_passed is True
    formatted = report.format_report()
    assert formatted == "Mutation Invariant Met: 84% mutant kill score (168 killed, 32 survived, 0 timed out)"


def test_mutation_report_formatting_failed():
    report = MutationReport(
        target_module="src/spec_ops/core",
        threshold=80.0,
        killed_count=71,
        survived_count=29,
        timeout_count=0,
        survived_mutants=[
            SurvivingMutant(
                mutant_id="mutant_1",
                file_path="src/spec_ops/core/graph.py",
                line=38,
                expression="if not edge_types:",
                diff="--- a\n+++ b\n@@ -38 +38 @@\n-if edge_types:\n+if not edge_types:",
            )
        ],
    )
    assert report.is_passed is False
    formatted = report.format_report()
    assert "❌ Mutation Score Invariant Failed: 71% < 80.0% threshold (ADR-0009 violation)." in formatted
    assert "Surviving mutants (1) requiring stronger blackbox assertions:" in formatted
    assert "src/spec_ops/core/graph.py:38 [mutant_1] - Mutated: if not edge_types:" in formatted
    assert "@@ -38 +38 @@" in formatted


def test_mutation_report_float_score_formatting():
    report = MutationReport(
        target_module="src/spec_ops/core",
        threshold=80.0,
        killed_count=842,
        survived_count=158,
        timeout_count=0,
        mutation_score=84.2,
    )
    assert report.is_passed is True
    assert "84.2%" in report.format_report()


def test_parse_diff_details():
    diff_text = """# calc.add__mutmut_1: survived
--- a/src/calc.py
+++ b/src/calc.py
@@ -14,2 +14,2 @@
-def add(x, y):
+def add(x, -y):
"""
    fpath, lno, expr = parse_diff_details(diff_text, fallback_file="default.py")
    assert fpath == "src/calc.py"
    assert lno == 14
    assert expr == "def add(x, -y):"


def test_load_specops_report_from_file(tmp_path: Path):
    report_file = tmp_path / "mutation_report.json"
    data = {
        "target_module": "src/spec_ops/core",
        "threshold": 80.0,
        "killed_count": 168,
        "survived_count": 32,
        "timeout_count": 0,
        "total_mutants": 200,
        "mutation_score": 84.0,
        "survived_mutants": [
            {
                "id": "mut_1",
                "file_path": "src/spec_ops/core/models.py",
                "line": 10,
                "expression": "x = 1",
                "diff": "diff",
            },
            "string_mutant_2",
        ],
    }
    report_file.write_text(json.dumps(data), encoding="utf-8")

    report = load_specops_report(report_file, target_module="src/spec_ops/core", threshold=80.0)
    assert report is not None
    assert report.killed_count == 168
    assert report.survived_count == 32
    assert report.mutation_score == 84.0
    assert len(report.survived_mutants) == 2
    assert report.survived_mutants[0].mutant_id == "mut_1"
    assert report.survived_mutants[1].mutant_id == "string_mutant_2"


def test_load_specops_report_missing_or_corrupt(tmp_path: Path):
    non_existent = tmp_path / "missing.json"
    assert load_specops_report(non_existent, "core", 80.0) is None

    bad_json = tmp_path / "corrupt.json"
    bad_json.write_text("{not valid json", encoding="utf-8")
    assert load_specops_report(bad_json, "core", 80.0) is None


def test_parse_mutmut_results_from_cicd_stats(tmp_path: Path):
    mutants_dir = tmp_path / "mutants"
    mutants_dir.mkdir(parents=True)
    cicd_file = mutants_dir / "mutmut-cicd-stats.json"
    cicd_file.write_text(json.dumps({
        "killed": 16,
        "survived": 4,
        "timeout": 0,
        "total": 20,
    }), encoding="utf-8")

    report = parse_mutmut_results(tmp_path, target_module="src/spec_ops/core", threshold=80.0)
    assert report is not None
    assert report.killed_count == 16
    assert report.survived_count == 4
    assert report.mutation_score == 80.0
    assert len(report.survived_mutants) == 4


def test_parse_mutmut_results_from_meta_files(tmp_path: Path):
    mutants_dir = tmp_path / "mutants"
    mutants_dir.mkdir(parents=True)
    meta_file = mutants_dir / "calc.py.meta"
    meta_file.write_text(json.dumps({
        "exit_code_by_key": {
            "calc.add__mutmut_1": 1,
            "calc.add__mutmut_2": 0,
            "calc.add__mutmut_3": 36,
        }
    }), encoding="utf-8")

    report = parse_mutmut_results(tmp_path, target_module="calc.py", threshold=80.0)
    assert report is not None
    assert report.killed_count == 1
    assert report.survived_count == 1
    assert report.timeout_count == 1
    assert report.total_mutants == 3
    assert len(report.survived_mutants) == 1
    assert report.survived_mutants[0].mutant_id == "calc.add__mutmut_2"


def test_parse_mutmut_results_extracts_diff_on_show_success(tmp_path: Path, monkeypatch):
    mutants_dir = tmp_path / "mutants"
    mutants_dir.mkdir(parents=True)
    meta_file = mutants_dir / "calc.py.meta"
    meta_file.write_text(json.dumps({
        "exit_code_by_key": {
            "calc.add__mutmut_1": 0,
        }
    }), encoding="utf-8")

    sample_diff = (
        "--- src/calc.py\n"
        "+++ src/calc.py\n"
        "@@ -15,1 +15,1 @@\n"
        "-x = 1\n"
        "+x = 2\n"
    )

    import subprocess
    def fake_subprocess_run(cmd, *args, **kwargs):
        if "show" in cmd:
            return subprocess.CompletedProcess(args=cmd, returncode=0, stdout=sample_diff, stderr="")
        return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_subprocess_run)

    report = parse_mutmut_results(tmp_path, target_module="calc.py", threshold=80.0)
    assert report is not None
    assert report.survived_count == 1
    assert len(report.survived_mutants) == 1
    m = report.survived_mutants[0]
    assert m.mutant_id == "calc.add__mutmut_1"
    assert m.file_path == "src/calc.py"
    assert m.line == 15
    assert m.expression == "x = 2"
    assert "x = 2" in m.diff


def test_execute_mutmut_run_temp_setup_cfg(tmp_path: Path):
    src_dir = tmp_path / "src"
    src_dir.mkdir(parents=True)
    (src_dir / "lib.py").write_text("def f(): pass", encoding="utf-8")

    # execute_mutmut_run will create temporary setup.cfg and remove it cleanly in finally block
    execute_mutmut_run(tmp_path, target_module="src")
    assert not (tmp_path / "setup.cfg").exists()


def test_run_mutation_gate_loads_existing_specops_report(tmp_path: Path):
    specops_dir = tmp_path / ".specops"
    specops_dir.mkdir(parents=True)
    (specops_dir / "mutation_report.json").write_text(json.dumps({
        "target_module": "src/spec_ops/core",
        "threshold": 80.0,
        "killed_count": 84,
        "survived_count": 16,
        "mutation_score": 84.0,
    }), encoding="utf-8")

    report = run_mutation_gate(root_dir=tmp_path, threshold=80.0)
    assert report.mutation_score == 84.0
    assert report.is_passed is True


def test_cli_handle_mutation_command_json_output(tmp_path: Path, monkeypatch):
    specops_dir = tmp_path / ".specops"
    specops_dir.mkdir(parents=True)
    (specops_dir / "mutation_report.json").write_text(json.dumps({
        "target_module": "src/spec_ops/core",
        "threshold": 80.0,
        "killed_count": 90,
        "survived_count": 10,
        "mutation_score": 90.0,
    }), encoding="utf-8")

    config = SpecOpsConfig(root_dir=tmp_path)
    args = argparse.Namespace(
        test_action="mutation",
        opt_path=None,
        path=None,
        target_bc="core",
        threshold=80.0,
        json=True,
        force_run=False,
    )

    out = StringIO()
    monkeypatch.setattr(sys, "stdout", out)
    code = handle_mutation_command(args, config)
    assert code == 0
    payload = json.loads(out.getvalue())
    assert payload["mutation_score"] == 90.0
    assert payload["is_passed"] is True


def test_cli_handle_mutation_command_failing_text(tmp_path: Path, monkeypatch):
    specops_dir = tmp_path / ".specops"
    specops_dir.mkdir(parents=True)
    (specops_dir / "mutation_report.json").write_text(json.dumps({
        "target_module": "src/spec_ops/core",
        "threshold": 80.0,
        "killed_count": 60,
        "survived_count": 40,
        "mutation_score": 60.0,
        "survived_mutants": [
            {"id": "mut_1", "file_path": "src/spec_ops/core/graph.py", "line": 50, "expression": "pass"}
        ],
    }), encoding="utf-8")

    config = SpecOpsConfig(root_dir=tmp_path)
    args = argparse.Namespace(
        test_action="mutation",
        opt_path=None,
        path=None,
        target_bc="core",
        threshold=80.0,
        json=False,
        force_run=False,
    )

    err = StringIO()
    monkeypatch.setattr(sys, "stderr", err)
    code = handle_mutation_command(args, config)
    assert code == 1
    assert "❌ Mutation Score Invariant Failed" in err.getvalue()


def test_cli_handle_test_command_dispatch(tmp_path: Path, monkeypatch):
    specops_dir = tmp_path / ".specops"
    specops_dir.mkdir(parents=True)
    (specops_dir / "mutation_report.json").write_text(json.dumps({
        "target_module": "src/spec_ops/core",
        "threshold": 80.0,
        "killed_count": 85,
        "survived_count": 15,
        "mutation_score": 85.0,
    }), encoding="utf-8")

    config = SpecOpsConfig(root_dir=tmp_path)
    parser = argparse.ArgumentParser()
    args = argparse.Namespace(
        test_action="mutation",
        opt_path=None,
        path=None,
        target_bc="core",
        threshold=80.0,
        json=False,
        force_run=False,
    )

    out = StringIO()
    monkeypatch.setattr(sys, "stdout", out)
    code = handle_test_command(args, config, parser)
    assert code == 0
    assert "Mutation Invariant Met: 85% mutant kill score" in out.getvalue()
