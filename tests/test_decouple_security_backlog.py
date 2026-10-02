"""Blackbox frontdoor verification for TASK-0239: Decouple Security from Backlog.

Governed by ADR-0001, ADR-0002, ADR-0003, ADR-0007, ADR-0021; US-0013, US-0106.
"""

from __future__ import annotations

import ast
from pathlib import Path

from spec_ops.config.loader import load_config
from spec_ops.core.models import Task
from spec_ops.security.dual_custody import (
    record_sign_off,
    register_default_task_finder,
    sign_task_review,
)
from spec_ops.visualizer.radar_script import harvest_architecture_radar


def test_dual_custody_has_no_backlog_imports():
    """Verify that src/spec_ops/security/dual_custody.py contains zero imports of spec_ops.backlog."""
    sec_file = Path("src/spec_ops/security/dual_custody.py")
    assert sec_file.is_file(), "dual_custody.py must exist"

    code = sec_file.read_text(encoding="utf-8")
    tree = ast.parse(code)
    backlog_imports = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if "backlog" in alias.name:
                    backlog_imports.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            if "backlog" in mod:
                backlog_imports.append(mod)

    assert not backlog_imports, f"Found illegal backlog imports in security/dual_custody.py: {backlog_imports}"


def test_security_to_backlog_boundary_violation_resolved():
    """Verify that harvest_architecture_radar reports zero violations from security -> backlog."""
    config = load_config(Path("."))
    radar = harvest_architecture_radar(config)
    violations = radar.get("violations", [])

    sec_backlog_violations = [
        v for v in violations
        if v.get("source") == "security" and v.get("target") == "backlog"
    ]
    assert not sec_backlog_violations, f"Active security -> backlog violations detected: {sec_backlog_violations}"


def test_record_sign_off_injected_writer(tmp_path: Path):
    """Verify record_sign_off accepts and invokes an injected task_writer."""
    task_file = tmp_path / "task.md"
    task_file.write_text("---\nid: '0001'\nstatus: Proposed\n---\nBody\n", encoding="utf-8")
    task = Task(id="0001", title="Test Task", status="Proposed", body="Body", file_path=task_file)

    written: list[Task] = []

    def custom_writer(t: Task) -> Path:
        written.append(t)
        return t.file_path

    record_sign_off(task, "Signer <signer@example.com>", timestamp="2026-01-01T00:00:00Z", task_writer=custom_writer)
    assert len(written) == 1
    assert task.signed_off_by == "Signer <signer@example.com>"
    assert task.signed_off_at == "2026-01-01T00:00:00Z"


def test_sign_task_review_injected_finder(tmp_path: Path):
    """Verify sign_task_review uses injected task_finder without static backlog dependency."""
    config = load_config(tmp_path)
    task_file = tmp_path / "task.md"
    task_file.write_text("---\nid: '0042'\nstatus: Proposed\n---\nBody\n", encoding="utf-8")
    task = Task(id="0042", title="Task 42", status="Proposed", body="Body", file_path=task_file)

    def custom_finder(task_id: str) -> Task | None:
        if task_id in ("TASK-0042", "42"):
            return task
        return None

    def custom_writer(t: Task) -> Path:
        return t.file_path

    ok, msg = sign_task_review(
        "TASK-0042",
        "Signer <signer@example.com>",
        config,
        task_finder=custom_finder,
        task_writer=custom_writer,
    )
    assert ok is True
    assert "review successfully signed" in msg
    assert task.signed_off_by == "Signer <signer@example.com>"


def test_sign_task_review_registered_finder(tmp_path: Path):
    """Verify sign_task_review utilizes registered task finder callback."""
    config = load_config(tmp_path)
    task_file = tmp_path / "task.md"
    task_file.write_text("---\nid: '0099'\nstatus: Proposed\n---\nBody\n", encoding="utf-8")
    task = Task(id="0099", title="Task 99", status="Proposed", body="Body", file_path=task_file)

    def registered_finder(task_id: str) -> Task | None:
        if task_id in ("TASK-0099", "99"):
            return task
        return None

    try:
        register_default_task_finder(registered_finder)
        ok, msg = sign_task_review("TASK-0099", "Signer <signer@example.com>", config)
        assert ok is True
        assert task.signed_off_by == "Signer <signer@example.com>"
    finally:
        register_default_task_finder(None)
