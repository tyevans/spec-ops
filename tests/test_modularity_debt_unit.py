"""Comprehensive unit tests for ModularityDebtEngine and related models."""

from __future__ import annotations

import tempfile
from pathlib import Path

from spec_ops.core.modularity_debt import (
    FileModularityScore,
    ModularityDebtAnalyzer,
    ModularityReport,
    count_file_imports,
    count_file_lines,
    determine_risk_level,
    get_recommended_action,
)


def test_count_file_lines():
    with tempfile.TemporaryDirectory() as tmp_str:
        tmp = Path(tmp_str)
        f_empty = tmp / "empty.py"
        f_empty.write_text("", encoding="utf-8")
        assert count_file_lines(f_empty) == 0

        f_nonempty = tmp / "sample.py"
        f_nonempty.write_text("a = 1\nb = 2\nc = 3\n", encoding="utf-8")
        assert count_file_lines(f_nonempty) == 3

        f_nonexistent = tmp / "does_not_exist.py"
        assert count_file_lines(f_nonexistent) == 0


def test_count_file_imports_python():
    with tempfile.TemporaryDirectory() as tmp_str:
        tmp = Path(tmp_str)
        f = tmp / "app.py"
        f.write_text(
            "import os\nfrom sys import path\nimport math, json\n\ndef main():\n    pass\n",
            encoding="utf-8",
        )
        assert count_file_imports(f) == 3


def test_count_file_imports_non_python_and_syntax_error():
    with tempfile.TemporaryDirectory() as tmp_str:
        tmp = Path(tmp_str)
        # Non-python
        f_ts = tmp / "service.ts"
        f_ts.write_text(
            "import { useState } from 'react';\nconst x = require('path');\nconsole.log(x);\n",
            encoding="utf-8",
        )
        assert count_file_imports(f_ts) == 2

        # Syntax error python fallback
        f_bad_py = tmp / "bad.py"
        f_bad_py.write_text(
            "import os\ndef def syntax error\nfrom collections import defaultdict\n",
            encoding="utf-8",
        )
        assert count_file_imports(f_bad_py) == 2

        # Nonexistent file
        f_missing = tmp / "missing.ts"
        assert count_file_imports(f_missing) == 0


def test_calculate_file_score_thresholds():
    # Boundary tests
    assert ModularityDebtAnalyzer.calculate_file_score(-10) == 0.0
    assert ModularityDebtAnalyzer.calculate_file_score(0) == 0.0

    score_100 = ModularityDebtAnalyzer.calculate_file_score(100)
    assert 15.0 <= score_100 <= 30.0

    score_250 = ModularityDebtAnalyzer.calculate_file_score(250)
    assert 45.0 <= score_250 <= 60.0

    score_380 = ModularityDebtAnalyzer.calculate_file_score(380)
    assert 75.0 <= score_380 <= 85.0

    score_450 = ModularityDebtAnalyzer.calculate_file_score(450)
    assert 85.0 <= score_450 <= 100.0

    score_600 = ModularityDebtAnalyzer.calculate_file_score(600)
    assert score_600 == 100.0


def test_calculate_file_score_with_imports():
    score_no_imports = ModularityDebtAnalyzer.calculate_file_score(100, imports_count=0)
    score_with_imports = ModularityDebtAnalyzer.calculate_file_score(100, imports_count=10)
    assert score_with_imports >= score_no_imports

    # Negative imports handled safely
    score_neg_imports = ModularityDebtAnalyzer.calculate_file_score(100, imports_count=-5)
    assert score_neg_imports == score_no_imports


def test_determine_risk_level():
    assert determine_risk_level(20.0, 50) == "low"
    assert determine_risk_level(50.0, 220) == "moderate"
    assert determine_risk_level(75.0, 360) == "high"
    assert determine_risk_level(90.0, 420) == "critical"
    assert determine_risk_level(86.0, 100) == "critical"


def test_get_recommended_action():
    act_crit = get_recommended_action("critical", 450)
    assert "Urgent decomposition required" in act_crit

    act_high = get_recommended_action("high", 380)
    assert "Proactive decomposition recommended" in act_high

    act_mod = get_recommended_action("moderate", 250)
    assert "Monitor file growth" in act_mod

    act_low = get_recommended_action("low", 50)
    assert "Optimal modularity" in act_low


def test_file_modularity_score_to_dict():
    score = FileModularityScore(
        file_path="src/foo.py",
        line_count=150,
        risk_score=30.0,
        risk_level="low",
        recommended_action="Optimal modularity; maintain current structure.",
    )
    d = score.to_dict()
    assert d["file_path"] == "src/foo.py"
    assert d["line_count"] == 150
    assert d["risk_score"] == 30.0
    assert d["risk_level"] == "low"
    assert "Optimal" in d["recommended_action"]


def test_modularity_report_summary_and_to_dict():
    f1 = FileModularityScore("src/a.py", 50, 10.0, "low", "Optimal")
    f2 = FileModularityScore("src/b.py", 380, 79.0, "high", "Decompose")
    rep = ModularityReport(
        files=[f1, f2],
        overall_debt_score=44.5,
        danger_zone_files=[f2],
    )

    summary_text = rep.summary()
    assert "Modularity Debt Report" in summary_text
    assert "Danger Zone Files (approaching 400 lines): 1" in summary_text
    assert "src/b.py" in summary_text
    assert "Proactive decomposition warning" in summary_text

    d = rep.to_dict()
    assert d["overall_debt_score"] == 44.5
    assert d["total_files"] == 2
    assert d["danger_zone_count"] == 1
    assert len(d["files"]) == 2
    assert len(d["danger_zone_files"]) == 1

    # Empty report summary
    empty_rep = ModularityReport()
    empty_summary = empty_rep.summary()
    assert "0 proactive warnings; codebase modularity optimal" in empty_summary


def test_analyzer_analyze_directory():
    with tempfile.TemporaryDirectory() as tmp_str:
        tmp = Path(tmp_str)
        src_dir = tmp / "src"
        src_dir.mkdir()

        # Valid source files
        (src_dir / "mod1.py").write_text("import sys\n" + "\n".join("x = 1" for _ in range(50)) + "\n")
        (src_dir / "mod2.ts").write_text("\n".join("console.log('hi');" for _ in range(360)) + "\n")

        # Excluded directory
        venv_dir = tmp / ".venv"
        venv_dir.mkdir()
        (venv_dir / "ignored.py").write_text("\n".join("pass" for _ in range(400)) + "\n")

        # Non-source file
        (src_dir / "notes.txt").write_text("\n".join("note" for _ in range(500)) + "\n")

        analyzer = ModularityDebtAnalyzer(tmp)
        report = analyzer.analyze_directory(tmp)

        assert len(report.files) == 2
        file_paths = [f.file_path for f in report.files]
        assert any("mod1.py" in p for p in file_paths)
        assert any("mod2.ts" in p for p in file_paths)
        assert not any("ignored.py" in p for p in file_paths)
        assert not any("notes.txt" in p for p in file_paths)

        assert len(report.danger_zone_files) == 1
        assert "mod2.ts" in report.danger_zone_files[0].file_path
        assert report.danger_zone_files[0].risk_level == "high"
