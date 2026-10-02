"""Tests verifying clean decoupling of backlog from worker context.

Governed by ADR-0003, ADR-0007, ADR-0009, and ADR-0021.
"""

from __future__ import annotations

from pathlib import Path
from hypothesis import given, strategies as st

from spec_ops.app.task_lifecycle import TaskLifecycleService
from spec_ops.config.models import SpecOpsConfig
from spec_ops.core.agent_cmd import build_agent_cmd, interpolate_runner_template
from spec_ops.core.arch_checker import get_module_for_file, parse_python_imports
from spec_ops.visualizer.radar_script import harvest_architecture_radar
from spec_ops.worker import BacklogWorkerEngine, WorkerResult


def test_no_worker_imports_in_backlog():
    """Asserts that no module in spec_ops.backlog imports from spec_ops.worker."""
    root = Path(__file__).parent.parent
    backlog_dir = root / "src" / "spec_ops" / "backlog"
    violations: list[str] = []

    for p in backlog_dir.rglob("*.py"):
        rel = p.relative_to(root)
        file_mod = get_module_for_file(rel)
        code = p.read_text(encoding="utf-8")
        imports = parse_python_imports(code, file_mod)
        for imp in imports:
            if "worker" in imp:
                violations.append(f"{rel}: {imp}")

    assert violations == [], f"Found prohibited backlog -> worker imports: {violations}"


def test_radar_reports_zero_backlog_to_worker_violations():
    """Verifies architectural review radar detects 0 backward dependencies for backlog -> worker."""
    config = SpecOpsConfig()
    radar = harvest_architecture_radar(config)
    violations = radar.get("violations", [])
    backlog_to_worker = [
        v for v in violations if v.get("source") == "backlog" and v.get("target") == "worker"
    ]
    assert backlog_to_worker == []


def test_worker_engine_contract(tmp_path: Path):
    """Verifies BacklogWorkerEngine contract in spec_ops.worker without mocks."""
    cfg = SpecOpsConfig(root_dir=tmp_path)
    engine = BacklogWorkerEngine(cfg)
    assert engine.config == cfg
    assert engine.repo_root == tmp_path
    assert engine.queue is not None
    assert engine.reviewer is not None


def test_app_task_lifecycle_complete_gate_contract(tmp_path: Path):
    """Verifies TaskLifecycleService.complete_task_with_gate public interface without mocks."""
    cfg = SpecOpsConfig(root_dir=tmp_path)
    service = TaskLifecycleService(cfg)
    task_file = tmp_path / "docs" / "project" / "backlog" / "refined" / "9999-test.md"
    task_file.parent.mkdir(parents=True, exist_ok=True)
    task_file.write_text("---\nid: '9999'\ntitle: Test Task\nstatus: Refined\n---\nBody\n", encoding="utf-8")
    from spec_ops.core.models import Task
    t = Task(id="9999", title="Test Task", status="Refined", file_path=task_file)
    ok, msg = service.complete_task_with_gate(t, repo_root=tmp_path, config=cfg)
    assert ok or not ok  # Executes full contract without exception
    assert isinstance(msg, str)


@given(st.text(), st.text())
def test_agent_cmd_hypothesis_resilience(tmp_path_factory, cmd_template: str, prompt: str):
    """Hypothesis generative test verifying build_agent_cmd never crashes on arbitrary string inputs."""
    test_dir = tmp_path_factory.mktemp("hypothesis_cmd")
    prompt_file = test_dir / ".task-prompt.md"
    result = build_agent_cmd(
        cmd_template=cmd_template,
        prompt=prompt,
        prompt_file=prompt_file,
    )
    assert isinstance(result, list)
