"""Tests verifying clean decoupling of backlog from visualizer context.

Governed by ADR-0003, ADR-0007, ADR-0009, and ADR-0021.
"""

from __future__ import annotations

from pathlib import Path
from hypothesis import given, strategies as st

from spec_ops.config.models import SpecOpsConfig
from spec_ops.core.arch_checker import get_module_for_file, parse_python_imports
from spec_ops.core.roadmap import parse_roadmap_milestones
from spec_ops.visualizer.radar_script import harvest_architecture_radar


def test_no_visualizer_imports_in_backlog():
    """Asserts that no module in spec_ops.backlog imports from spec_ops.visualizer."""
    root = Path(__file__).parent.parent
    backlog_dir = root / "src" / "spec_ops" / "backlog"
    violations: list[str] = []

    for p in backlog_dir.rglob("*.py"):
        rel = p.relative_to(root)
        file_mod = get_module_for_file(rel)
        code = p.read_text(encoding="utf-8")
        imports = parse_python_imports(code, file_mod)
        for imp in imports:
            if "visualizer" in imp:
                violations.append(f"{rel}: {imp}")

    assert violations == [], f"Found prohibited backlog -> visualizer imports: {violations}"


def test_radar_reports_zero_backlog_to_visualizer_violations():
    """Verifies architectural review radar detects 0 backward dependencies for backlog -> visualizer."""
    config = SpecOpsConfig()
    radar = harvest_architecture_radar(config)
    violations = radar.get("violations", [])
    backlog_to_visualizer = [
        v for v in violations if v.get("source") == "backlog" and v.get("target") == "visualizer"
    ]
    assert backlog_to_visualizer == []


def test_parse_roadmap_milestones_core_contract(tmp_path: Path):
    """Verifies parse_roadmap_milestones public interface works in spec_ops.core.roadmap without mocks."""
    roadmap_file = tmp_path / "ROADMAP.md"
    content = """# Roadmap

## Milestone M1: Core Foundation (Active)
- Target Horizon: 2026-11-01
- `TASK-0010` Setup engine
- `TASK-0020` Event store

## Milestone M2: Visualizer (Planning)
- Completion Date: 2026-12-01
- `TASK-0030` Graph view
"""
    roadmap_file.write_text(content, encoding="utf-8")
    milestones = parse_roadmap_milestones(roadmap_file)
    assert len(milestones) == 2
    assert milestones[0]["id"] == "M1"
    assert milestones[0]["title"] == "Core Foundation"
    assert milestones[0]["status"] == "Active"
    assert milestones[0]["tasks"] == ["TASK-0010", "TASK-0020"]
    assert milestones[0]["horizon"] == "2026-11-01"

    assert milestones[1]["id"] == "M2"
    assert milestones[1]["title"] == "Visualizer"
    assert milestones[1]["status"] == "Planning"
    assert milestones[1]["tasks"] == ["TASK-0030"]
    assert milestones[1]["horizon"] == "2026-12-01"


@given(st.text())
def test_parse_roadmap_milestones_hypothesis_resilience(tmp_path_factory, text: str):
    """Hypothesis generative test verifying parse_roadmap_milestones never crashes on arbitrary text."""
    test_dir = tmp_path_factory.mktemp("hypothesis_roadmap")
    test_file = test_dir / "ROADMAP.md"
    test_file.write_text(text, encoding="utf-8")
    result = parse_roadmap_milestones(test_file)
    assert isinstance(result, list)
