"""Blackbox frontdoor verification for TASK-0233: Decouple Core from Visualizer.

Governed by ADR-0001, ADR-0002, ADR-0003, ADR-0007, ADR-0021; US-0013, US-0106.
"""

from __future__ import annotations

import argparse
import ast
from pathlib import Path

from spec_ops.config.loader import load_config
from spec_ops.config.models import SpecOpsConfig
from spec_ops.core.provenance import run_provenance_audit
from spec_ops.visualizer.radar_script import harvest_architecture_radar


def test_core_provenance_has_no_visualizer_imports():
    """Verify that src/spec_ops/core/provenance.py contains zero imports of spec_ops.visualizer."""
    prov_file = Path("src/spec_ops/core/provenance.py")
    assert prov_file.is_file(), "provenance.py must exist"

    code = prov_file.read_text(encoding="utf-8")
    tree = ast.parse(code)
    visualizer_imports = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if "visualizer" in alias.name:
                    visualizer_imports.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            if "visualizer" in mod:
                visualizer_imports.append(mod)

    assert not visualizer_imports, f"Found illegal visualizer imports in core/provenance.py: {visualizer_imports}"


def test_core_to_visualizer_boundary_violation_resolved():
    """Verify that harvest_architecture_radar reports zero violations from core -> visualizer."""
    config = load_config(Path("."))
    radar = harvest_architecture_radar(config)
    violations = radar.get("violations", [])

    core_vis_violations = [
        v for v in violations
        if v.get("source") == "core" and v.get("target") == "visualizer"
    ]
    assert not core_vis_violations, f"Active core -> visualizer violations detected: {core_vis_violations}"


def test_run_provenance_audit_with_injected_updater(tmp_path: Path):
    """Verify run_provenance_audit accepts and executes injected site_updater callback without errors."""
    (tmp_path / "docs" / "project" / "user_stories" / "accepted").mkdir(parents=True, exist_ok=True)
    (tmp_path / "docs" / "project" / "product" / "accepted").mkdir(parents=True, exist_ok=True)
    (tmp_path / "docs" / "project" / "backlog" / "complete").mkdir(parents=True, exist_ok=True)

    cfg = SpecOpsConfig(root_dir=tmp_path)
    called = []

    def recording_updater(c: SpecOpsConfig):
        called.append(c)

    args = argparse.Namespace(repo=str(tmp_path), strict=False, contributions=True)
    ret = run_provenance_audit(args, cfg, site_updater=recording_updater)
    assert ret == 0
    assert len(called) == 1
    assert called[0] == cfg
