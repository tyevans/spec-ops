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
    assert len(report.warnings) == 0

    # Create a file approaching the limit (420 lines)
    warning_file = tmp_path / "src" / "approaching.py"
    warning_file.parent.mkdir(parents=True, exist_ok=True)
    warning_file.write_text("\n".join(f"# line {i}" for i in range(420)), encoding="utf-8")

    report_warn = checker.run_check()
    assert report_warn.is_healthy  # Still healthy! Not a hard violation
    assert len(report_warn.violations) == 0
    assert len(report_warn.warnings) == 1
    assert report_warn.warnings[0].lines == 420
    assert report_warn.warnings[0].threshold == 400

    # Create an oversized file exceeding 500 lines
    oversized = tmp_path / "src" / "bloated.py"
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


def test_backlog_curator_dry_run(tmp_path: Path):
    init_project(tmp_path, name="CuratorDryRunTest")
    config = load_config(root_dir=tmp_path)

    mgr = PRDManager(config)
    mgr.create_prd(title="Search Engine", persona="User", component="core")
    decomposer = PRDDecomposer(config)
    decomposer.decompose("PRD-0001", include_spike=True)

    queue = BacklogQueue(config.backlog_dir)
    refined_before = len([t for t in queue.list_all_tasks() if t.status == "Refined"])

    curator = BacklogCurator(config)
    res_dry = curator.curate(dry_run=True)
    assert len(res_dry.tasks_refined) > 0

    # Ensure disk state was NOT modified
    refined_after_dry = len([t for t in queue.list_all_tasks() if t.status == "Refined"])
    assert refined_after_dry == refined_before

    # Now execute actual curation
    res_real = curator.curate(dry_run=False)
    assert len(res_real.tasks_refined) > 0
    refined_after_real = len([t for t in queue.list_all_tasks() if t.status == "Refined"])
    assert refined_after_real > refined_before


def test_worker_preflight_lockfile_check(tmp_path: Path):
    from spec_ops.worker import BacklogWorkerEngine
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


def test_check_priority_sync_detects_unindexed_tasks(tmp_path: Path):
    init_project(tmp_path, name="SyncTest")
    config = load_config(root_dir=tmp_path)
    checker = HealthChecker(config)

    ok, errs = checker.check_priority_sync()
    assert ok
    assert len(errs) == 0

    refined_dir = tmp_path / "docs" / "project" / "backlog" / "refined"
    refined_dir.mkdir(parents=True, exist_ok=True)
    unindexed = refined_dir / "0099-unindexed-task.md"
    unindexed.write_text("---\nid: TASK-0099\ntitle: Unindexed\nstatus: Refined\n---\n", encoding="utf-8")

    ok2, errs2 = checker.check_priority_sync()
    assert not ok2
    assert len(errs2) == 1
    assert "TASK-0099" in errs2[0]
    assert "unindexed in PRIORITY.md" in errs2[0]

    report = checker.run_check()
    assert not report.is_healthy
    assert not report.priority_sync_ok
    assert any("TASK-0099" in e for e in report.sync_errors)


def test_check_priority_sync_resolves_when_indexed(tmp_path: Path):
    init_project(tmp_path, name="SyncResolveTest")
    config = load_config(root_dir=tmp_path)
    checker = HealthChecker(config)

    refined_dir = tmp_path / "docs" / "project" / "backlog" / "refined"
    refined_dir.mkdir(parents=True, exist_ok=True)
    task_file = refined_dir / "0099-indexed-task.md"
    task_file.write_text("---\nid: TASK-0099\ntitle: Indexed\nstatus: Refined\n---\n", encoding="utf-8")

    priority_file = tmp_path / "docs" / "project" / "backlog" / "PRIORITY.md"
    current = priority_file.read_text(encoding="utf-8")
    priority_file.write_text(
        current + "\n- **TASK-0099 (Refined)**: [`0099-indexed-task`](refined/0099-indexed-task.md)\n",
        encoding="utf-8",
    )

    ok, errs = checker.check_priority_sync()
    assert ok
    assert len(errs) == 0
    report = checker.run_check()
    assert report.is_healthy
    assert report.priority_sync_ok
