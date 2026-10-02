"""Blackbox frontdoor verification for TASK-0243: Decouple Spike from Worker.

Governed by ADR-0001, ADR-0002, ADR-0003, ADR-0007, ADR-0021; US-0013, US-0106.
"""

from __future__ import annotations

import ast
from pathlib import Path
import subprocess

from spec_ops.config.loader import load_config
from spec_ops.core.git_worktree import (
    cleanup_worktree,
    create_worktree,
    get_worktree_branch,
    is_worktree_dirty,
)
from spec_ops.rescue.lifecycle import (
    cleanup_worktree as rescue_cleanup,
    create_worktree as rescue_create,
)
from spec_ops.visualizer.radar_script import harvest_architecture_radar
from spec_ops.worker.worktree import (
    cleanup_worktree as worker_cleanup,
    create_worktree as worker_create,
)


def test_spike_modules_have_no_worker_imports():
    """Verify that spike context modules contain zero imports of spec_ops.worker."""
    spike_files = [
        Path("src/spec_ops/spike/sandbox.py"),
        Path("src/spec_ops/spike/graduate.py"),
    ]
    for sf in spike_files:
        assert sf.is_file(), f"{sf} must exist"
        code = sf.read_text(encoding="utf-8")
        tree = ast.parse(code)
        worker_imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if "worker" in alias.name:
                        worker_imports.append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                mod = node.module or ""
                if "worker" in mod:
                    worker_imports.append(mod)

        assert not worker_imports, f"Found illegal worker imports in {sf}: {worker_imports}"


def test_spike_to_worker_boundary_violation_resolved():
    """Verify that harvest_architecture_radar reports zero violations from spike -> worker."""
    config = load_config(Path("."))
    radar = harvest_architecture_radar(config)
    violations = radar.get("violations", [])

    spike_worker_violations = [
        v for v in violations
        if v.get("source") == "spike" and v.get("target") == "worker"
    ]
    assert not spike_worker_violations, f"Active spike -> worker violations detected: {spike_worker_violations}"


def test_core_git_worktree_reexported_downward():
    """Verify worker and rescue re-export core git worktree primitives downward."""
    assert worker_create is create_worktree
    assert worker_cleanup is cleanup_worktree
    assert rescue_create is create_worktree
    assert rescue_cleanup is cleanup_worktree


def test_git_worktree_lifecycle_frontdoor(tmp_path: Path):
    """Verify worktree lifecycle create and cleanup through core frontdoor."""
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()
    subprocess.run(["git", "init"], cwd=repo_dir, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Tester"], cwd=repo_dir, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo_dir, check=True)

    init_file = repo_dir / "README.md"
    init_file.write_text("# Test Repo\n", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=repo_dir, check=True)
    subprocess.run(["git", "commit", "-m", "initial commit"], cwd=repo_dir, check=True)

    wt_dir = tmp_path / "wt_test"
    create_worktree(repo_dir, branch="feat/spike-test", worktree_dir=wt_dir)

    assert wt_dir.is_dir()
    assert (wt_dir / ".git").is_file()
    assert get_worktree_branch(wt_dir) == "feat/spike-test"
    assert is_worktree_dirty(wt_dir) is False

    cleanup_worktree(repo_dir, worktree_dir=wt_dir, branch="feat/spike-test", delete_branch=True)
    assert not wt_dir.exists()
