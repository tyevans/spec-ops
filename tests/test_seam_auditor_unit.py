"""Unit and mutation kill tests for spec_ops.core.seam_auditor."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from spec_ops.config.loader import load_config
from spec_ops.core.seam_auditor import (
    ContextMetrics,
    SeamAuditor,
    SeamViolation,
    calculate_instability,
    export_coupling_heatmap,
    extract_python_imports_with_lines,
    handle_seam_audit,
)
from spec_ops.scaffold.init import init_project


def test_calculate_instability() -> None:
    assert calculate_instability(0, 0) == 0.0
    assert calculate_instability(10, 0) == 0.0
    assert calculate_instability(0, 10) == 1.0
    assert calculate_instability(5, 5) == 0.5
    assert calculate_instability(1, 3) == 0.75
    assert calculate_instability(-5, 5) == 0.0
    assert calculate_instability(5, -5) == 0.0


def test_extract_python_imports_with_lines() -> None:
    code = """
import os
import sys as system
from pathlib import Path
from ..worker import worker_engine
from .sub import helper
"""
    imps = extract_python_imports_with_lines(code, file_module="spec_ops.core.engine")
    imp_names = [m for m, _ in imps]
    assert "os" in imp_names
    assert "sys" in imp_names
    assert "pathlib" in imp_names
    assert "spec_ops.worker" in imp_names
    assert "spec_ops.core.sub" in imp_names

    # SyntaxError handling
    invalid_code = "def invalid_syntax(::"
    assert extract_python_imports_with_lines(invalid_code) == []


def test_seam_violation_formatting() -> None:
    v = SeamViolation(
        source_file="src/core/models.py",
        source_context="core",
        imported_module="visualizer._internal",
        target_context="visualizer",
        reason="Illegal direct import of private visualizer internals",
        line=42,
    )
    msg = v.format_message()
    assert "src/core/models.py:42" in msg
    assert "Illegal direct import" in msg
    d = v.to_dict()
    assert d["line"] == 42
    assert d["source_context"] == "core"


def test_context_metrics_serialization() -> None:
    cm = ContextMetrics(
        context="core",
        afferent_coupling=4,
        efferent_coupling=2,
        instability=0.333333,
        incoming_contexts=["worker", "cli"],
        outgoing_contexts=["config"],
    )
    d = cm.to_dict()
    assert d["context"] == "core"
    assert d["afferent_coupling"] == 4
    assert d["efferent_coupling"] == 2
    assert d["instability"] == 0.333
    assert d["incoming_contexts"] == ["cli", "worker"]
    assert d["outgoing_contexts"] == ["config"]


@pytest.fixture
def mock_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "mock_project"
    repo.mkdir(parents=True, exist_ok=True)
    init_project(name="MockProject", target_dir=repo)

    # Context 1: domain models
    core_dir = repo / "src" / "core"
    core_dir.mkdir(parents=True, exist_ok=True)
    (core_dir / "models.py").write_text("class Entity:\n    pass\n", encoding="utf-8")

    # Context 2: worker
    worker_dir = repo / "src" / "worker"
    worker_dir.mkdir(parents=True, exist_ok=True)
    (worker_dir / "agent.py").write_text("from core.models import Entity\nclass Worker:\n    pass\n", encoding="utf-8")

    # Context 3: visualizer
    vis_dir = repo / "src" / "visualizer"
    vis_dir.mkdir(parents=True, exist_ok=True)
    (vis_dir / "render.py").write_text("from core.models import Entity\nclass Renderer:\n    pass\n", encoding="utf-8")

    return repo


def test_seam_auditor_clean_repo(mock_repo: Path) -> None:
    auditor = SeamAuditor(mock_repo)
    report = auditor.audit()
    assert report.is_valid
    assert len(report.violations) == 0
    assert "core" in report.contexts
    assert "worker" in report.contexts
    assert "visualizer" in report.contexts

    core_m = report.metrics["core"]
    assert core_m.afferent_coupling == 2  # worker and visualizer import core
    assert core_m.efferent_coupling == 0  # core imports nothing
    assert core_m.instability == 0.0


def test_seam_auditor_detects_private_internals_violation(mock_repo: Path) -> None:
    vis_dir = mock_repo / "src" / "visualizer"
    (vis_dir / "_private.py").write_text("SECRET = 1\n", encoding="utf-8")

    worker_dir = mock_repo / "src" / "worker"
    (worker_dir / "leaky.py").write_text("from visualizer._private import SECRET\n", encoding="utf-8")

    auditor = SeamAuditor(mock_repo)
    report = auditor.audit()
    assert not report.is_valid
    assert len(report.violations) >= 1
    assert any("private visualizer internals" in v.reason for v in report.violations)


def test_seam_auditor_detects_domain_purity_violation(mock_repo: Path) -> None:
    core_dir = mock_repo / "src" / "core"
    # Pure domain model importing visualizer
    (core_dir / "models.py").write_text("from visualizer.render import Renderer\n", encoding="utf-8")

    auditor = SeamAuditor(mock_repo)
    report = auditor.audit()
    assert not report.is_valid
    assert any("Pure domain model cannot import 'visualizer'" in v.reason for v in report.violations)


def test_seam_auditor_custom_boundary_rules(mock_repo: Path) -> None:
    # Add custom rule: worker cannot import visualizer
    toml_path = mock_repo / "specops.toml"
    toml_path.write_text(
        """
[project]
name = "MockProject"

[architecture]
boundary_rules = { worker = ["visualizer.*"] }
""",
        encoding="utf-8",
    )

    worker_dir = mock_repo / "src" / "worker"
    (worker_dir / "render_call.py").write_text("from visualizer.render import Renderer\n", encoding="utf-8")

    auditor = SeamAuditor(mock_repo)
    report = auditor.audit()
    assert not report.is_valid
    assert any("forbidden from importing 'visualizer'" in v.reason for v in report.violations)


def test_seam_auditor_bounded_contexts_from_toml_list(tmp_path: Path) -> None:
    repo = tmp_path / "toml_list_repo"
    repo.mkdir(parents=True, exist_ok=True)
    (repo / "specops.toml").write_text(
        """
[project]
name = "ListRepo"
[architecture]
bounded_contexts = [
  { id = "alpha" },
  { id = "beta" }
]
""",
        encoding="utf-8",
    )
    auditor = SeamAuditor(repo)
    assert "alpha" in auditor.contexts
    assert "beta" in auditor.contexts


def test_export_coupling_heatmap(mock_repo: Path, tmp_path: Path) -> None:
    auditor = SeamAuditor(mock_repo)
    report = auditor.audit()

    # Markdown export
    md_dest = tmp_path / "heatmap.md"
    export_coupling_heatmap(report, md_dest)
    assert md_dest.is_file()
    md_text = md_dest.read_text(encoding="utf-8")
    assert "| From \\ To |" in md_text
    assert "Instability" in md_text

    # JSON export
    json_dest = tmp_path / "heatmap.json"
    export_coupling_heatmap(report, json_dest)
    assert json_dest.is_file()
    data = json.loads(json_dest.read_text(encoding="utf-8"))
    assert "is_valid" in data
    assert "coupling_matrix" in data

    # HTML export
    html_dest = tmp_path / "heatmap.html"
    export_coupling_heatmap(report, html_dest)
    assert html_dest.is_file()
    html_text = html_dest.read_text(encoding="utf-8")
    assert "<!DOCTYPE html>" in html_text
    assert "Context Coupling Heatmap" in html_text


def test_handle_seam_audit_cli(mock_repo: Path, capsys: pytest.CaptureFixture[str], tmp_path: Path) -> None:
    cfg = load_config(mock_repo)

    # Clean repo
    rc = handle_seam_audit(cfg, strict=False, json_output=False)
    assert rc == 0
    out = capsys.readouterr().out
    assert "comply with Domain-Driven Design seams" in out

    # JSON mode
    rc_json = handle_seam_audit(cfg, strict=True, json_output=True)
    assert rc_json == 0
    out_json = capsys.readouterr().out
    data = json.loads(out_json)
    assert data["is_valid"] is True

    # Heatmap export option
    hmap_dest = tmp_path / "out_heat.md"
    rc_hmap = handle_seam_audit(cfg, strict=False, json_output=False, export_heatmap=str(hmap_dest))
    assert rc_hmap == 0
    assert hmap_dest.is_file()

    # Introduce leak and test strict mode
    vis_dir = mock_repo / "src" / "visualizer"
    (vis_dir / "_leaky.py").write_text("X = 1\n", encoding="utf-8")
    (mock_repo / "src" / "core" / "bad.py").write_text("from visualizer._leaky import X\n", encoding="utf-8")

    rc_strict = handle_seam_audit(cfg, strict=True, json_output=False)
    assert rc_strict == 1
    out_err = capsys.readouterr().out
    assert "Detected" in out_err
