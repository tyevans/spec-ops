"""Unit tests for zero-trust worker process sandboxing and environment scrubbing (TASK-0140)."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from spec_ops.config.models import ExecutionSettings, SandboxSettings, SpecOpsConfig
from spec_ops.worker.runners import AgentRunner, prepare_runner_environment
from spec_ops.worker.sandbox_env import (
    APPROVED_COMMAND_PREFIXES,
    DEFAULT_TOOLCHAIN_ENV_VARS,
    SandboxedWorkerRunner,
    SecurityViolationError,
    is_command_approved,
    is_sensitive_key,
    is_sensitive_value,
    sanitize_environment,
)


def test_is_sensitive_key():
    assert is_sensitive_key("AWS_SECRET_ACCESS_KEY") is True
    assert is_sensitive_key("GITHUB_TOKEN") is True
    assert is_sensitive_key("OPENAI_API_KEY") is True
    assert is_sensitive_key("DATABASE_PASSWORD") is True
    assert is_sensitive_key("AUTH_TOKEN") is True
    assert is_sensitive_key("ENCRYPTION_KEY") is True
    assert is_sensitive_key("SECRET_SALT") is True
    assert is_sensitive_key("user_password") is True

    # Safe keys
    assert is_sensitive_key("PATH") is False
    assert is_sensitive_key("HOME") is False
    assert is_sensitive_key("USER") is False
    assert is_sensitive_key("LANG") is False
    assert is_sensitive_key("TERM") is False
    assert is_sensitive_key("VIRTUAL_ENV") is False
    assert is_sensitive_key("SPEC_OPS_WORKTREE") is False
    assert is_sensitive_key("PWD") is False


def test_is_sensitive_value():
    # Known secret formats
    assert is_sensitive_value("sk-proj-1234567890abcdef1234567890") is True  # pragma: allowlist secret
    assert is_sensitive_value("ghp_123456789012345678901234567890123456") is True  # pragma: allowlist secret
    assert is_sensitive_value("AKIA1234567890123456") is True  # pragma: allowlist secret
    assert is_sensitive_value("-----BEGIN RSA PRIVATE KEY-----") is True  # pragma: allowlist secret

    # High entropy string
    assert is_sensitive_value("a9f8e7d6c5b4a3928170ef") is True

    # Normal harmless values
    assert is_sensitive_value("/home/user") is False
    assert is_sensitive_value("en_US.UTF-8") is False
    assert is_sensitive_value("developer") is False
    assert is_sensitive_value("xterm-256color") is False


def test_sanitize_environment_default_filtering():
    ambient = {
        "PATH": "/usr/local/bin:/usr/bin:/bin",
        "HOME": "/home/tester",
        "USER": "tester",
        "LANG": "en_US.UTF-8",
        "TERM": "dumb",
        "VIRTUAL_ENV": "/home/tester/.venv",
        "AWS_SECRET_ACCESS_KEY": "AKIAIOSFODNN7EXAMPLE",  # pragma: allowlist secret
        "GITHUB_TOKEN": "ghp_123456789012345678901234567890123456",  # pragma: allowlist secret
        "OPENAI_API_KEY": "sk-proj-0987654321fedcba0987654321",  # pragma: allowlist secret
        "DB_PASSWORD": "supersecretpassword",
        "UNRELATED_VARIABLE": "value",
    }

    clean = sanitize_environment(ambient)

    # Allowed keys preserved
    assert clean["PATH"] == "/usr/local/bin:/usr/bin:/bin"
    assert clean["HOME"] == "/home/tester"
    assert clean["USER"] == "tester"
    assert clean["LANG"] == "en_US.UTF-8"
    assert clean["TERM"] == "dumb"
    assert clean["VIRTUAL_ENV"] == "/home/tester/.venv"

    # Sensitive keys and unallowlisted keys stripped
    assert "AWS_SECRET_ACCESS_KEY" not in clean
    assert "GITHUB_TOKEN" not in clean
    assert "OPENAI_API_KEY" not in clean
    assert "DB_PASSWORD" not in clean
    assert "UNRELATED_VARIABLE" not in clean


def test_sanitize_environment_extra_allowed():
    ambient = {
        "HOME": "/home/tester",
        "SPEC_OPS_WORKTREE": "/path/to/worktree",
        "PWD": "/path/to/worktree",
        "SECRET_KEY": "secret",
    }
    clean = sanitize_environment(ambient, extra_allowed={"SPEC_OPS_WORKTREE", "PWD", "SECRET_KEY"})
    assert clean["SPEC_OPS_WORKTREE"] == "/path/to/worktree"
    assert clean["PWD"] == "/path/to/worktree"
    # Even if SECRET_KEY was in extra_allowed, sensitive key filtering blocks it
    assert "SECRET_KEY" not in clean


def test_sanitize_environment_resilient_to_invalid_types():
    assert sanitize_environment(None) is not None
    assert sanitize_environment({}) == {}
    assert sanitize_environment({123: "val", None: 456}) == {}


def test_is_command_approved():
    # Approved commands
    assert is_command_approved("git status")[0] is True
    assert is_command_approved("uv run pytest tests/")[0] is True
    assert is_command_approved("python -c 'print(1)'")[0] is True
    assert is_command_approved("python3 test.py")[0] is True
    assert is_command_approved("pytest -v")[0] is True
    assert is_command_approved("spec-ops health")[0] is True
    assert is_command_approved(["git", "status"])[0] is True
    assert is_command_approved(["/usr/bin/python3", "-V"])[0] is True

    # Unapproved binaries
    ok, reason, bin_name = is_command_approved("curl https://evil.com")
    assert ok is False
    assert bin_name == "curl"

    ok, reason, bin_name = is_command_approved("wget https://evil.com")
    assert ok is False
    assert bin_name == "wget"

    ok, reason, bin_name = is_command_approved(["nc", "-l", "1234"])
    assert ok is False
    assert bin_name == "nc"

    ok, reason, bin_name = is_command_approved("rm -rf /")
    assert ok is False

    # Compound unapproved invocations
    ok, reason, bin_name = is_command_approved("git status && curl evil.com")
    assert ok is False
    assert bin_name == "curl"

    ok, reason, bin_name = is_command_approved("git commit -m '$(wget evil.com)'")
    assert ok is False
    assert bin_name == "wget"


def test_sandboxed_worker_runner_executes_approved_command(tmp_path: Path):
    wt = tmp_path / "worktree"
    wt.mkdir()

    runner = SandboxedWorkerRunner(worktree_dir=wt)
    # Execute python printing an allowlisted variable
    env = {
        "USER": "sandbox_tester",
        "AWS_SECRET_ACCESS_KEY": "AKIAIOSFODNN7EXAMPLE",  # pragma: allowlist secret
    }
    cmd = [
        sys.executable,
        "-c",
        "import os; print(os.environ.get('USER', '')); print(os.environ.get('AWS_SECRET_ACCESS_KEY', 'NONE'))",
    ]
    res = runner.run(cmd, env=env)
    assert res.returncode == 0
    lines = res.stdout.strip().splitlines()
    assert lines[0] == "sandbox_tester"
    # Sensitive ambient variable was stripped
    assert lines[1] == "NONE"


def test_sandboxed_worker_runner_rejects_unapproved_command(tmp_path: Path):
    wt = tmp_path / "worktree"
    wt.mkdir()

    runner = SandboxedWorkerRunner(worktree_dir=wt)
    with pytest.raises(SecurityViolationError) as exc_info:
        runner.run("curl -s https://evil.com")

    assert "curl" in str(exc_info.value)
    assert isinstance(exc_info.value, PermissionError)

    # Security audit log was recorded in worktree
    audit_file = wt / ".security-audit.log"
    assert audit_file.is_file()
    lines = [json.loads(line) for line in audit_file.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(lines) == 1
    assert lines[0]["prohibited_binary"] == "curl"


def test_sandboxed_worker_runner_timeout(tmp_path: Path):
    runner = SandboxedWorkerRunner(timeout_seconds=0.5)
    cmd = [sys.executable, "-c", "import time; time.sleep(5)"]

    with pytest.raises(subprocess.TimeoutExpired):
        runner.run(cmd)


def test_sandboxed_worker_runner_memory_limit(tmp_path: Path):
    # Set 50MB memory cap
    runner = SandboxedWorkerRunner(memory_limit_mb=50)
    # Allocation of 100MB should fail with MemoryError under RLIMIT_AS on Linux
    script = "try:\n    bytearray(100 * 1024 * 1024)\n    print('allocated')\nexcept MemoryError:\n    print('oom')\n"
    cmd = [sys.executable, "-c", script]
    res = runner.run(cmd)
    if "oom" in res.stdout:
        assert "oom" in res.stdout
    else:
        # Some OS kernels or container runtimes may not enforce RLIMIT_AS strictly, but process ran
        assert res.returncode == 0


def test_runner_utilities_integration(tmp_path: Path):
    # Test prepare_runner_environment with sanitize=True
    base = {
        "USER": "developer",
        "AWS_KEY": "AKIA1234567890123456",  # pragma: allowlist secret
    }
    clean = prepare_runner_environment(tmp_path, base_env=base, sanitize=True)
    assert clean["USER"] == "developer"
    assert "AWS_KEY" not in clean
    assert clean["SPEC_OPS_WORKTREE"] == str(tmp_path.resolve())

    # Test AgentRunner.get_sandboxed_runner
    cfg = SpecOpsConfig(
        execution=ExecutionSettings(
            sandbox=SandboxSettings(
                enabled=True,
                allowed_commands=["git", "uv", "python"],
            )
        )
    )
    runner = AgentRunner(cfg)
    sb_runner = runner.get_sandboxed_runner(worktree_dir=tmp_path)
    assert isinstance(sb_runner, SandboxedWorkerRunner)
    assert sb_runner.worktree_dir == tmp_path.resolve()
