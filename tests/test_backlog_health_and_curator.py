"""Tests for backlog health, invariant checking, queue transitions, and JIT curator."""

from pathlib import Path

from spec_ops.backlog.curator import BacklogCurator
from spec_ops.backlog.health import HealthChecker
from spec_ops.backlog.queue import BacklogQueue
from spec_ops.config.loader import load_config
from spec_ops.prd.decomposer import PRDDecomposer
from spec_ops.prd.manager import PRDManager
from spec_ops.scaffold.init import init_project


def test_health_check_file_length_limits(tmp_path: Path):
    init_project(tmp_path, name="HealthTest")
    config = load_config(root_dir=tmp_path)

    checker = HealthChecker(config)
    report = checker.run_check()
    assert report.is_healthy
    assert len(report.violations) == 0

    # Create an oversized file exceeding 500 lines
    oversized = tmp_path / "src" / "bloated.py"
    oversized.parent.mkdir(parents=True, exist_ok=True)
    oversized.write_text("\n".join(f"# line {i}" for i in range(550)), encoding="utf-8")

    report2 = checker.run_check()
    assert not report2.is_healthy
    assert len(report2.violations) == 1
    assert report2.violations[0].lines == 550


def test_backlog_curator_jit_refinement(tmp_path: Path):
    init_project(tmp_path, name="CuratorTest")
    config = load_config(root_dir=tmp_path)

    # Decompose a PRD to create proposed tasks
    mgr = PRDManager(config)
    mgr.create_prd(title="Search Engine", persona="User", component="core")
    decomposer = PRDDecomposer(config)
    decomposer.decompose("PRD-0001", include_spike=True)

    # Check queue
    queue = BacklogQueue(config.backlog_dir)
    all_tasks = queue.list_all_tasks()
    assert any(t.status == "Proposed" for t in all_tasks)

    # Run curator
    curator = BacklogCurator(config)
    res = curator.curate()
    assert len(res.tasks_refined) > 0

    refined_after = [t for t in queue.list_all_tasks() if t.status == "Refined"]
    assert len(refined_after) > 1


def test_worker_preflight_lockfile_check(tmp_path: Path):
    from spec_ops.backlog.worker import BacklogWorkerEngine
    init_project(tmp_path, name="PreflightTest")
    config = load_config(root_dir=tmp_path)
    config.quality.preflight = ["python3 -c 'print(\"ok\")'"]
    worker = BacklogWorkerEngine(config)

    # Without uv.lock
    ok, log = worker.run_preflight(tmp_path)
    assert ok
    assert "✓ 'python3 -c 'print(\"ok\")'' passed" in log

    # With dummy uv.lock but uv lock fails because dummy lockfile is invalid
    (tmp_path / "uv.lock").write_text("invalid lockfile content", encoding="utf-8")
    ok2, log2 = worker.run_preflight(tmp_path)
    assert not ok2
    assert "uv lock --check" in log2
