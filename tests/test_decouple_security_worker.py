"""Blackbox frontdoor verification for TASK-0242: Decouple Security from Worker.

Governed by ADR-0001, ADR-0002, ADR-0003, ADR-0007, ADR-0021; US-0013, US-0106.
"""

from __future__ import annotations

import ast
from pathlib import Path

from spec_ops.config.loader import load_config
from spec_ops.security.sandbox import ExecutionSandbox
from spec_ops.security.sandbox_env import (
    DEFAULT_TOOLCHAIN_ENV_VARS,
    is_sensitive_key,
    is_sensitive_value,
    sanitize_environment,
)
from spec_ops.visualizer.radar_script import harvest_architecture_radar
from spec_ops.worker.sandbox_env import (
    sanitize_environment as worker_sanitize_environment,
)


def test_security_sandbox_has_no_worker_imports():
    """Verify that src/spec_ops/security/sandbox.py contains zero imports of spec_ops.worker."""
    sec_file = Path("src/spec_ops/security/sandbox.py")
    assert sec_file.is_file(), "sandbox.py must exist"

    code = sec_file.read_text(encoding="utf-8")
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

    assert not worker_imports, f"Found illegal worker imports in security/sandbox.py: {worker_imports}"


def test_security_to_worker_boundary_violation_resolved():
    """Verify that harvest_architecture_radar reports zero violations from security -> worker."""
    config = load_config(Path("."))
    radar = harvest_architecture_radar(config)
    violations = radar.get("violations", [])

    sec_worker_violations = [
        v for v in violations
        if v.get("source") == "security" and v.get("target") == "worker"
    ]
    assert not sec_worker_violations, f"Active security -> worker violations detected: {sec_worker_violations}"


def test_sanitize_environment_scrubs_secrets_correctly():
    """Verify sanitize_environment deterministically scrubs sensitive keys and secret values."""
    dirty_env = {
        "PATH": "/usr/bin:/bin",
        "HOME": "/home/user",
        "USER": "developer",
        "OPENAI_API_KEY": "sk-1234567890abcdef1234567890abcdef",  # pragma: allowlist secret
        "AWS_SECRET_ACCESS_KEY": "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",  # pragma: allowlist secret
        "MY_TOKEN": "secretvalue",
        "CUSTOM_VAR": "harmless",
    }
    cleaned = sanitize_environment(dirty_env)

    assert "PATH" in cleaned
    assert "HOME" in cleaned
    assert "USER" in cleaned
    assert "OPENAI_API_KEY" not in cleaned
    assert "AWS_SECRET_ACCESS_KEY" not in cleaned
    assert "MY_TOKEN" not in cleaned
    assert "CUSTOM_VAR" not in cleaned


def test_worker_sandbox_env_reexports_security_primitives():
    """Verify worker.sandbox_env consumes security downward and re-exports sanitize_environment."""
    assert worker_sanitize_environment is sanitize_environment


def test_execution_sandbox_prepares_clean_environment(tmp_path: Path):
    """Verify ExecutionSandbox prepares sanitized child environment without worker dependency."""
    sandbox = ExecutionSandbox(worktree_dir=tmp_path, scrub_environment=True)
    env = sandbox.prepare_environment({"PATH": "/bin", "GITHUB_TOKEN": "ghp_123456789012345678901234567890123456"})  # pragma: allowlist secret

    assert "GITHUB_TOKEN" not in env
    assert "PATH" in env
    assert str(tmp_path / ".specops" / "sandbox_shims") in env["PATH"]
