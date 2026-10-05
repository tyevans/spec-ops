"""Integration and direct graduation tests for spike lifecycle and ADR synthesis."""

from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path

import pytest

from spec_ops.backlog.queue import write_task_file
from spec_ops.core.models import Task
from spec_ops.core.parser import parse_task
from spec_ops.scaffold.init import init_project
from spec_ops.spike.graduate import graduate_spike
from spec_ops.spike.sandbox import start_spike


def test_graduate_spike_proven_direct(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    init_project(name="DirectApp", target_dir=repo)

    subprocess.run(["git", "init", "-b", "main"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Alex"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "alex@specops.dev"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=repo, check=True, capture_output=True)

    proposed = repo / "docs" / "project" / "backlog" / "proposed"
    proposed.mkdir(parents=True, exist_ok=True)
    spike_f = proposed / "0002-duckdb.md"
    task = Task(id="SPIKE-0002", title="DuckDB Spike", hypothesis="Faster than SQLite", file_path=spike_f)
    write_task_file(task)

    dep_f = proposed / "0050-dep.md"
    dep_t = Task(id="0050", title="Dep Task", dependencies=["SPIKE-0002"], file_path=dep_f)
    write_task_file(dep_t)

    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "propose"], cwd=repo, check=True, capture_output=True)

    sandbox = start_spike(repo, "SPIKE-0002", hypothesis="Faster than SQLite", timebox="2h")
    assert sandbox.worktree_dir.exists()

    # Record benchmark finding
    bench_txt = sandbox.harness_dir / "benchmark.txt"
    bench_txt.write_text("p95 latency = 142ms", encoding="utf-8")

    # Pass title=None to exercise default title generation from hypothesis
    res = graduate_spike(
        repo_root=repo,
        spike_id="SPIKE-0002",
        result="proven",
        notes="High throughput confirmed",
    )
    assert res.success is True
    assert res.adr_file is not None
    assert res.adr_file == repo / "docs" / "project" / "adrs" / "proposed" / "adr-0008-adopt-faster-than-sqlite.md"
    assert res.adr_file.exists()
    assert res.adr_id == "ADR-0008"
    assert not sandbox.worktree_dir.exists()
    assert parse_task(dep_f).dependencies == []
    assert parse_task((repo / "docs" / "project" / "backlog" / "complete") / spike_f.name).status == "Graduated"

    # Verify ADR content
    adr_text = res.adr_file.read_text(encoding="utf-8")
    assert "# ADR-0008: Adopt Faster than SQLite" in adr_text
    assert "p95 latency = 142ms" in adr_text
    assert "High throughput confirmed" in adr_text

    # Verify REGISTRY.md
    reg_text = (repo / "docs" / "project" / "adrs" / "REGISTRY.md").read_text(encoding="utf-8")
    assert "| ADR-0008 | Adopt Faster than SQLite | Proposed |" in reg_text

    # Verify git tag and branch persistence
    tags = subprocess.check_output(["git", "tag", "-l"], cwd=repo, text=True)
    assert "spike/SPIKE-0002-graduated" in tags
    branches = subprocess.check_output(["git", "branch", "-l"], cwd=repo, text=True)
    assert "spike/SPIKE-0002" in branches

    # Verify pre-commit hooks and spike metadata cleanup
    chk_hooks = subprocess.run(["git", "config", "--get", "core.hooksPath"], cwd=repo, capture_output=True, text=True)
    assert chk_hooks.returncode != 0 or chk_hooks.stdout.strip() != ".specops/hooks"
    assert not (repo / ".specops" / "hooks" / "pre-commit").exists()
    assert not (repo / ".specops" / "spike.json").exists()

    # Verify message
    expected_msg = "✨ Successfully graduated SPIKE-0002 into ADR-0008 (adr-0008-adopt-faster-than-sqlite.md). Updated 1 dependent task(s)."
    assert res.message == expected_msg


def test_graduate_spike_disproven_direct(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    init_project(name="DirectApp2", target_dir=repo)

    subprocess.run(["git", "init", "-b", "main"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Alex"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "alex@specops.dev"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=repo, check=True, capture_output=True)

    proposed = repo / "docs" / "project" / "backlog" / "proposed"
    proposed.mkdir(parents=True, exist_ok=True)
    spike_f = proposed / "0003-sqlite.md"
    task = Task(id="SPIKE-0003", title="SQLite Spike", hypothesis="Sync req", file_path=spike_f)
    write_task_file(task)

    dep_f = proposed / "0051-dep.md"
    dep_t = Task(id="0051", title="Dep Task", dependencies=["SPIKE-0003"], file_path=dep_f)
    write_task_file(dep_t)

    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "propose"], cwd=repo, check=True, capture_output=True)

    sandbox = start_spike(repo, "SPIKE-0003", hypothesis="Sync req", timebox="1h")
    assert sandbox.worktree_dir.exists()

    res = graduate_spike(
        repo_root=repo,
        spike_id="SPIKE-0003",
        result="disproven",
        title="Reject SQLite Sync",
        adr_id="ADR-0042",
        notes="High contention",
        findings="p95 latency is 85ms",
    )
    assert res.success is True
    assert res.adr_file is not None
    assert res.adr_file == repo / "docs" / "project" / "adrs" / "proposed" / "adr-0042-reject-sqlite-sync.md"
    assert res.adr_file.exists()
    assert res.adr_id == "ADR-0042"
    assert parse_task(dep_f).status == "Blocked: Spike hypothesis failed"

    # Verify ADR content
    adr_text = res.adr_file.read_text(encoding="utf-8")
    assert "# ADR-0042: Reject SQLite Sync" in adr_text
    assert "Rationale: High contention." in adr_text
    assert "p95 latency is 85ms" in adr_text

    # Verify git tag
    tags = subprocess.check_output(["git", "tag", "-l"], cwd=repo, text=True)
    assert "spike/SPIKE-0003-graduated" in tags

    expected_msg = "✨ Successfully graduated SPIKE-0003 into ADR-0042 (adr-0042-reject-sqlite-sync.md). Updated 1 dependent task(s)."
    assert res.message == expected_msg


def test_graduate_spike_no_task_file(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    init_project(name="NoTaskApp", target_dir=repo)

    subprocess.run(["git", "init", "-b", "main"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Alex"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "alex@specops.dev"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=repo, check=True, capture_output=True)

    # Spike with no task in docs/project/backlog
    sandbox = start_spike(repo, "SPIKE-0009", hypothesis="", timebox="1h")
    assert sandbox.worktree_dir.exists()

    res = graduate_spike(
        repo_root=repo,
        spike_id="SPIKE-0009",
        result="disproven",
    )
    assert res.success is True
    assert "adr-0008-architectural-finding-rejection-of-evaluate-spike-0009.md" in res.adr_file.name


def test_graduate_spike_restores_preexisting_hooks_and_cleans_metadata(tmp_path: Path):
    repo = tmp_path / "repo_custom"
    repo.mkdir()
    init_project(name="CustomApp", target_dir=repo)

    subprocess.run(["git", "init", "-b", "main"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Alex"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "alex@specops.dev"], cwd=repo, check=True, capture_output=True)
    # Configure a custom pre-existing core.hooksPath
    subprocess.run(["git", "config", "core.hooksPath", ".custom-hooks"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=repo, check=True, capture_output=True)

    proposed = repo / "docs" / "project" / "backlog" / "proposed"
    proposed.mkdir(parents=True, exist_ok=True)
    spike_f = proposed / "0005-bench.md"
    task = Task(id="SPIKE-0005", title="Custom Hook Spike", hypothesis="Validate hooks", file_path=spike_f)
    write_task_file(task)

    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "propose"], cwd=repo, check=True, capture_output=True)

    sandbox = start_spike(repo, "SPIKE-0005", hypothesis="Validate hooks", timebox="1h")
    assert sandbox.worktree_dir.exists()
    assert (sandbox.worktree_dir / ".specops" / "spike.json").exists()

    bench_txt = sandbox.harness_dir / "benchmark.txt"
    bench_txt.write_text("p95 latency = 10ms", encoding="utf-8")

    res = graduate_spike(
        repo_root=repo,
        spike_id="SPIKE-0005",
        result="proven",
    )
    assert res.success is True
    assert not sandbox.worktree_dir.exists()

    # Pre-existing core.hooksPath must be restored
    chk_hooks = subprocess.run(["git", "config", "--get", "core.hooksPath"], cwd=repo, capture_output=True, text=True)
    assert chk_hooks.stdout.strip() == ".custom-hooks"

    # Metadata and transient hook files must be removed
    assert not (repo / ".specops" / "hooks" / "pre-commit").exists()
    assert not (repo / ".specops" / "spike.json").exists()

