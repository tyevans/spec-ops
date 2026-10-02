"""Blackbox frontdoor verification for TASK-0246: Decouple PRD from Visualizer.

Governed by ADR-0001, ADR-0002, ADR-0003, ADR-0007, ADR-0021; US-0013, US-0106.
"""

from __future__ import annotations

import ast
from pathlib import Path

from spec_ops.config.loader import load_config
from spec_ops.prd.studio_runner import (
    launch_prd_studio,
    register_default_server_launcher,
)
from spec_ops.visualizer.radar_script import harvest_architecture_radar


def test_prd_studio_runner_has_no_visualizer_imports():
    """Verify that src/spec_ops/prd/studio_runner.py contains zero imports of spec_ops.visualizer."""
    runner_file = Path("src/spec_ops/prd/studio_runner.py")
    assert runner_file.is_file(), "studio_runner.py must exist"

    code = runner_file.read_text(encoding="utf-8")
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

    assert not visualizer_imports, f"Found illegal visualizer imports in prd/studio_runner.py: {visualizer_imports}"


def test_prd_to_visualizer_boundary_violation_resolved():
    """Verify that harvest_architecture_radar reports zero violations from prd -> visualizer."""
    config = load_config(Path("."))
    radar = harvest_architecture_radar(config)
    violations = radar.get("violations", [])

    prd_vis_violations = [
        v for v in violations
        if v.get("source") == "prd" and v.get("target") == "visualizer"
    ]
    assert not prd_vis_violations, f"Active prd -> visualizer violations detected: {prd_vis_violations}"


def test_custom_server_launcher_registration(tmp_path: Path):
    """Verify register_default_server_launcher delegates server execution through registered callback."""
    config = load_config(tmp_path)
    recorded_calls: list[dict[str, object]] = []

    def sample_launcher(cfg: object, host: str = "", port: int = 0, default_view: str = "") -> None:
        recorded_calls.append({"host": host, "port": port, "view": default_view})

    register_default_server_launcher(sample_launcher)
    try:
        ret = launch_prd_studio(config, host="127.0.0.1", port=9999, open_browser=False, block=True)
        assert ret == 0
        assert len(recorded_calls) == 1
        assert recorded_calls[0] == {"host": "127.0.0.1", "port": 9999, "view": "studio"}
    finally:
        register_default_server_launcher(None)  # reset
