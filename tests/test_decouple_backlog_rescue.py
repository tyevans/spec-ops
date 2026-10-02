"""Tests verifying clean decoupling of backlog from rescue context.

Governed by ADR-0003, ADR-0007, and ADR-0021.
"""

from __future__ import annotations

from pathlib import Path

from spec_ops.config.models import SpecOpsConfig
from spec_ops.core.arch_checker import ArchitectureChecker, get_module_for_file, parse_python_imports
from spec_ops.rescue.manager import RescueInfo, WorktreeRescueManager
from spec_ops.visualizer.radar_script import harvest_architecture_radar


def test_no_rescue_imports_in_backlog():
    """Asserts that no module in spec_ops.backlog imports from spec_ops.rescue."""
    root = Path(__file__).parent.parent
    backlog_dir = root / "src" / "spec_ops" / "backlog"
    violations: list[str] = []

    for p in backlog_dir.rglob("*.py"):
        rel = p.relative_to(root)
        file_mod = get_module_for_file(rel)
        code = p.read_text(encoding="utf-8")
        imports = parse_python_imports(code, file_mod)
        for imp in imports:
            if "rescue" in imp:
                violations.append(f"{rel}: {imp}")

    assert violations == [], f"Found prohibited backlog -> rescue imports: {violations}"


def test_radar_reports_zero_backlog_to_rescue_violations():
    """Verifies architectural review radar detects 0 backward dependencies for backlog -> rescue."""
    config = SpecOpsConfig()
    radar = harvest_architecture_radar(config)
    violations = radar.get("violations", [])
    backlog_to_rescue = [
        v for v in violations if v.get("source") == "backlog" and v.get("target") == "rescue"
    ]
    assert backlog_to_rescue == []


def test_worktree_rescue_manager_contract(tmp_path: Path):
    """Verifies WorktreeRescueManager public interface works in spec_ops.rescue without mocks."""
    cfg = SpecOpsConfig(root_dir=tmp_path)
    mgr = WorktreeRescueManager(cfg)
    assert mgr.list_active_worktrees() == []

    # Verify inspect non-existent worktree returns None
    info = mgr.inspect_task("TASK-0999")
    assert info is None
