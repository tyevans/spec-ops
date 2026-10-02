"""Tests for spec_ops.app application orchestration services.

Exercises public frontdoor contracts for TaskLifecycleService, RescueLifecycleService,
and SiteBundlerService with zero private mocks, governed by ADR-0003, ADR-0007,
ADR-0009, and ADR-0021.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from hypothesis import given, strategies as st

from spec_ops.app import (
    RescueLifecycleService,
    SiteBundlerService,
    TaskLifecycleService,
)
from spec_ops.app.rescue_lifecycle import RescueResult
from spec_ops.app.site_bundler import BundlingResult
from spec_ops.app.task_lifecycle import TaskIntegrationResult
from spec_ops.config.models import SpecOpsConfig
from spec_ops.core.arch_checker import ArchitectureChecker


def test_app_bounded_context_discovery(tmp_path: Path):
    """Verifies that ArchitectureChecker discovers app as a valid bounded context."""
    src_dir = tmp_path / "src" / "spec_ops"
    src_dir.mkdir(parents=True)
    (src_dir / "__init__.py").touch()
    (src_dir / "app").mkdir()
    (src_dir / "app" / "__init__.py").touch()
    (src_dir / "core").mkdir()
    (src_dir / "core" / "__init__.py").touch()

    checker = ArchitectureChecker(tmp_path)
    assert "app" in checker.bounded_contexts


def test_task_lifecycle_service_verify_not_found(tmp_path: Path):
    """Verifies TaskLifecycleService returns failure when task does not exist."""
    cfg = SpecOpsConfig(root_dir=tmp_path)
    (tmp_path / "docs" / "project" / "backlog").mkdir(parents=True)

    service = TaskLifecycleService(cfg)
    ok, msg, task = service.verify_ready_for_completion("TASK-9999")
    assert not ok
    assert "not found" in msg.lower()
    assert task is None


def test_task_lifecycle_service_complete_missing_task(tmp_path: Path):
    """Verifies complete_task returns a failed TaskIntegrationResult when task is missing."""
    cfg = SpecOpsConfig(root_dir=tmp_path)
    (tmp_path / "docs" / "project" / "backlog").mkdir(parents=True)

    service = TaskLifecycleService(cfg)
    result = service.complete_task("TASK-9999")
    assert result.success is False
    assert result.task_id == "TASK-9999"
    assert "not found" in result.message.lower()


def test_rescue_lifecycle_salvage_nonexistent_worktree(tmp_path: Path):
    """Verifies RescueLifecycleService handles salvage failure cleanly without mocks."""
    cfg = SpecOpsConfig(root_dir=tmp_path)
    service = RescueLifecycleService(cfg)

    res = service.complete_salvage("TASK-9999", author="Alex")
    assert res.success is False
    assert res.action == "salvage"
    assert res.task_id == "TASK-9999"


def test_site_bundler_service_basic(tmp_path: Path):
    """Verifies SiteBundlerService creates output bundle directories via public frontdoor."""
    cfg = SpecOpsConfig(root_dir=tmp_path)
    # Set up minimal docs structure
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir(parents=True)
    (docs_dir / "index.md").write_text("# Welcome\nTest documentation site.\n", encoding="utf-8")

    service = SiteBundlerService(cfg)
    target_out = tmp_path / "dist" / "site"

    result = service.bundle_documentation_suite(
        target_dir=target_out,
        include_visualizer=False,
        include_roadmap=False,
    )

    assert result.output_dir == target_out
    assert target_out.is_dir()
    assert (target_out / "index.html").is_file()


@given(
    task_id=st.text(min_size=1, max_size=20),
    success=st.booleans(),
    message=st.text(min_size=0, max_size=50),
)
def test_task_integration_result_invariants(task_id: str, success: bool, message: str):
    """Hypothesis invariant property asserting TaskIntegrationResult preserves contract fields."""
    res = TaskIntegrationResult(task_id=task_id, success=success, message=message)
    assert res.task_id == task_id
    assert res.success == success
    assert res.message == message


@given(
    task_id=st.text(min_size=1, max_size=20),
    success=st.booleans(),
    action=st.sampled_from(["salvage", "reset", "discard"]),
)
def test_rescue_result_invariants(task_id: str, success: bool, action: str):
    """Hypothesis invariant property asserting RescueResult preserves contract fields."""
    res = RescueResult(task_id=task_id, success=success, message="info", action=action)
    assert res.action in ["salvage", "reset", "discard"]
    assert res.task_id == task_id


@given(
    pages_compiled=st.integers(min_value=0, max_value=1000),
    vis_embedded=st.booleans(),
    roadmap_exported=st.booleans(),
)
def test_bundling_result_invariants(pages_compiled: int, vis_embedded: bool, roadmap_exported: bool):
    """Hypothesis invariant property asserting BundlingResult preserves contract fields."""
    res = BundlingResult(
        output_dir=Path("/tmp/dist"),
        pages_compiled=pages_compiled,
        visualizer_embedded=vis_embedded,
        roadmap_exported=roadmap_exported,
    )
    assert res.pages_compiled == pages_compiled
    assert res.visualizer_embedded == vis_embedded
    assert res.roadmap_exported == roadmap_exported
