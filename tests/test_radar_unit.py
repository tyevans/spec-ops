"""Unit and mutation kill tests for living architectural radar (US-0106)."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from spec_ops.config.loader import load_config
from spec_ops.core.models import ProjectData, Task, UserStory, PRD
from spec_ops.scaffold.init import init_project
from spec_ops.visualizer.radar_script import (
    is_stdlib_module,
    _matches_pattern,
    partition_acyclic_layers,
    detect_boundary_violations,
    BoundaryViolation,
    harvest_architecture_radar,
    export_specification_drift_report,
    RADAR_JS,
)


def test_is_stdlib_module():
    assert is_stdlib_module("") is False
    assert is_stdlib_module("   ") is False
    assert is_stdlib_module("os") is True
    assert is_stdlib_module("os.path") is True
    assert is_stdlib_module("sys") is True
    assert is_stdlib_module("json") is True
    assert is_stdlib_module("math") is True
    assert is_stdlib_module("pathlib") is True
    assert is_stdlib_module("typing") is True
    assert is_stdlib_module("core") is False
    assert is_stdlib_module("visualizer") is False
    assert is_stdlib_module("my_custom_package") is False


def test_matches_pattern():
    assert _matches_pattern("core", "core.*") is True
    assert _matches_pattern("core.models", "core.*") is True
    assert _matches_pattern("core_extra", "core.*") is False
    assert _matches_pattern("core", "core") is True
    assert _matches_pattern("core", "visualizer") is False
    assert _matches_pattern("core.foo.bar", "core.*.bar") is True


def test_partition_acyclic_layers_empty_and_stdlib():
    assert partition_acyclic_layers({}) == []
    assert partition_acyclic_layers({"os": ["sys"], "json": ["math"]}) == []
    assert partition_acyclic_layers({"": [""]}) == []


def test_partition_acyclic_layers_dag():
    graph = {
        "visualizer": ["core"],
        "reporting": ["core"],
        "cli": ["visualizer", "reporting"],
        "core": [],
    }
    layers = partition_acyclic_layers(graph)
    assert len(layers) == 3
    assert layers[0] == ["core"]
    assert layers[1] == ["reporting", "visualizer"]
    assert layers[2] == ["cli"]


def test_partition_acyclic_layers_with_cycles():
    graph = {
        "a": ["b"],
        "b": ["a"],
    }
    layers = partition_acyclic_layers(graph)
    assert len(layers) == 1
    assert sorted(layers[0]) == ["a", "b"]


def test_boundary_violation_to_dict():
    bv = BoundaryViolation(
        source="core",
        target="visualizer",
        violation_type="forbidden_import",
        message="Illegal import",
        file_path="src/core/foo.py",
    )
    d = bv.to_dict()
    assert d["source"] == "core"
    assert d["target"] == "visualizer"
    assert d["type"] == "forbidden_import"
    assert d["message"] == "Illegal import"
    assert d["file_path"] == "src/core/foo.py"


def test_detect_boundary_violations_forbidden_rules():
    deps = {"core": ["visualizer", "reporting"]}
    rules = {"core": ["visualizer.*"]}
    file_paths = {("core", "visualizer"): "src/core/view.py"}

    v = detect_boundary_violations(deps, forbidden_rules=rules, file_paths=file_paths)
    assert len(v) == 1
    assert v[0].source == "core"
    assert v[0].target == "visualizer"
    assert v[0].violation_type == "forbidden_import"
    assert "cannot import forbidden" in v[0].message
    assert v[0].file_path == "src/core/view.py"


def test_detect_boundary_violations_permissible_rules():
    deps = {"core": ["visualizer", "helpers"]}
    permissible = {"core": ["helpers"]}

    v = detect_boundary_violations(deps, permissible_rules=permissible)
    assert len(v) == 1
    assert v[0].source == "core"
    assert v[0].target == "visualizer"
    assert v[0].violation_type == "unauthorized_import"
    assert "not permitted to import" in v[0].message


def test_detect_boundary_violations_domain_leak():
    deps = {
        "order.domain": ["order.infrastructure"],
        "user/domain": ["user/infrastructure"],
    }
    v = detect_boundary_violations(deps)
    assert len(v) == 2
    for item in v:
        assert item.violation_type == "domain_leak"
        assert "Domain layer leak" in item.message


def test_detect_boundary_violations_backward_dependency():
    # layer 0: core
    # layer 1: visualizer
    layers = [["core"], ["visualizer"]]
    # core (layer 0) depends on visualizer (layer 1) -> backward dependency!
    deps = {"core": ["visualizer"]}
    v = detect_boundary_violations(deps, layers=layers)
    assert len(v) == 1
    assert v[0].source == "core"
    assert v[0].target == "visualizer"
    assert v[0].violation_type == "backward_dependency"
    assert "Illegal backward dependency violating ADR-0007" in v[0].message


def test_detect_boundary_violations_valid_forward_dependency():
    # layer 0: core
    # layer 1: visualizer
    layers = [["core"], ["visualizer"]]
    # visualizer (layer 1) depends on core (layer 0) -> legal forward dependency!
    deps = {"visualizer": ["core"]}
    v = detect_boundary_violations(deps, layers=layers)
    assert len(v) == 0


def test_detect_boundary_violations_skips_self_and_stdlib():
    deps = {
        "core": ["core", "os", "sys"],
        "os": ["core"],
    }
    v = detect_boundary_violations(deps)
    assert len(v) == 0


def test_harvest_architecture_radar_and_drift_audit(tmp_path: Path):
    init_project(tmp_path, name="RadarHarvestTest")
    config = load_config(root_dir=tmp_path)

    # Populate project with orphaned items to test drift audit
    data = ProjectData()
    t_orphan = Task(
        id="TASK-0999",
        title="Orphan Task",
        status="Proposed",
        file_path=tmp_path / "docs/project/backlog/proposed/0999-orphan.md",
    )
    t_linked = Task(
        id="TASK-0998",
        title="Linked Task",
        status="Refined",
        governing_prds=["PRD-0001"],
        file_path=tmp_path / "docs/project/backlog/refined/0998-linked.md",
    )
    data.tasks = [t_orphan, t_linked]

    s_orphan = UserStory(
        id="US-0999",
        title="Orphan Story",
        file_path=tmp_path / "docs/project/user_stories/accepted/0999-orphan.md",
    )
    data.stories = [s_orphan]

    p_orphan = PRD(
        id="PRD-0999",
        title="Orphan PRD",
        file_path=tmp_path / "docs/project/product/accepted/0999-orphan.md",
    )
    data.prds = [p_orphan]

    radar = harvest_architecture_radar(config, data)
    assert "bounded_contexts" in radar
    assert "layers" in radar
    assert "coupling_matrix" in radar
    assert "violations" in radar
    assert "drift_audit" in radar

    audit = radar["drift_audit"]
    assert audit["total_orphans"] == 3
    assert any(t["id"] == "TASK-0999" for t in audit["orphaned_tasks"])
    assert any(s["id"] == "US-0999" for s in audit["orphaned_stories"])
    assert any(p["id"] == "PRD-0999" for p in audit["orphaned_prds"])


def test_export_specification_drift_report(tmp_path: Path):
    init_project(tmp_path, name="ReportExportTest")
    config = load_config(root_dir=tmp_path)

    out_file = tmp_path / "dist" / "drift-audit.json"
    exported = export_specification_drift_report(config, output_path=out_file)
    assert exported.exists()
    content = json.loads(exported.read_text(encoding="utf-8"))
    assert "total_orphans" in content
    assert "timestamp" in content


def test_radar_js_present():
    assert len(RADAR_JS) > 0
    assert "renderArchitectureRadarView" in RADAR_JS
    assert "openDriftAuditModal" in RADAR_JS
