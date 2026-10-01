"""Zero-trust autonomous worker process sandboxing and environment scrubbing engine."""

from __future__ import annotations

import os
import re
import shlex
import subprocess
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping

from ..security.secrets.entropy import is_high_entropy
from ..security.secrets.patterns import (
    AWS_ACCESS_KEY_ID_PATTERN,
    AWS_SECRET_KEY_PATTERN,
    GITHUB_TOKEN_PATTERN,
    OPENAI_KEY_PATTERN,
    PRIVATE_KEY_PATTERN,
    SLACK_TOKEN_PATTERN,
)

DEFAULT_TOOLCHAIN_ENV_VARS: frozenset[str] = frozenset({
    "PATH",
    "HOME",
    "USER",
    "LANG",
    "TERM",
    "VIRTUAL_ENV",
})

SENSITIVE_PREFIXES: tuple[str, ...] = (
    "AWS_",
    "GITHUB_",
    "OPENAI_",
)

SENSITIVE_KEYWORDS: tuple[str, ...] = (
    "TOKEN",
    "KEY",
    "SECRET",
    "PASSWORD",
)

APPROVED_COMMAND_PREFIXES: tuple[str, ...] = (
    "uv",
    "git",
    "python",
    "pytest",
    "spec-ops",
)

SECRET_PATTERNS = (
    OPENAI_KEY_PATTERN,
    AWS_ACCESS_KEY_ID_PATTERN,
    AWS_SECRET_KEY_PATTERN,
    GITHUB_TOKEN_PATTERN,
    SLACK_TOKEN_PATTERN,
    PRIVATE_KEY_PATTERN,
)


class SecurityViolationError(PermissionError):
    """Raised when an unapproved command or binary execution is rejected by sandbox guardrails."""

    def __init__(self, message: str, binary: str | None = None, details: str = ""):
        super().__init__(message)
        self.binary = binary
        self.details = details


def is_sensitive_key(key: Any) -> bool:
    """Detects if an environment variable key matches sensitive prefixes or keywords."""
    if not isinstance(key, str):
        key = str(key)
    k_upper = key.upper()
    if any(k_upper.startswith(prefix) for prefix in SENSITIVE_PREFIXES):
        return True
    if any(keyword in k_upper for keyword in SENSITIVE_KEYWORDS):
        return True
    return False


TOKEN_VALUE_PREFIXES: tuple[str, ...] = (
    "sk-",
    "ghp_",
    "gho_",
    "ghu_",
    "ghs_",
    "ghr_",
    "github_pat_",
    "AKIA",
    "xoxb-",
    "xoxa-",
    "xoxp-",
    "xoxr-",
    "xoxs-",
)


def is_sensitive_value(value: Any, is_path: bool = False) -> bool:
    """Detects if an environment variable value matches high-entropy secret patterns."""
    if not isinstance(value, str):
        value = str(value)

    # Check known secret value prefixes
    if any(value.startswith(p) for p in TOKEN_VALUE_PREFIXES):
        return True

    # Check known secret regex signatures
    if any(p.search(value) for p in SECRET_PATTERNS):
        return True

    # For PATH, check each path component individually
    if is_path:
        for component in value.split(":"):
            if component and (
                any(component.startswith(p) for p in TOKEN_VALUE_PREFIXES)
                or any(p.search(component) for p in SECRET_PATTERNS)
            ):
                return True
        return False

    # Check Shannon entropy for tokens of length >= 16
    return is_high_entropy(value, threshold=3.7, min_length=16)


def sanitize_environment(
    env: Mapping[Any, Any] | None = None,
    allowed_vars: Iterable[str] | None = None,
    extra_allowed: Iterable[str] | None = None,
) -> dict[str, str]:
    """Sanitizes an environment dictionary according to zero-trust scrubbing rules.

    - Deterministically retains exclusively allowlisted variables.
    - Strips all keys matching sensitive prefixes (AWS_, GITHUB_, OPENAI_, TOKEN, KEY, SECRET, PASSWORD).
    - Strips all values exhibiting high-entropy secret patterns or signatures.
    - Never raises exceptions on arbitrary input keys or values.
    """
    if env is None:
        source_env: Mapping[Any, Any] = os.environ
    else:
        source_env = env

    effective_allowed = set(allowed_vars if allowed_vars is not None else DEFAULT_TOOLCHAIN_ENV_VARS)
    if extra_allowed:
        effective_allowed.update(extra_allowed)

    sanitized: dict[str, str] = {}

    try:
        items = list(source_env.items())
    except Exception:
        return sanitized

    for raw_k, raw_v in items:
        try:
            k = str(raw_k)
            v = str(raw_v)
        except Exception:
            continue

        # 1. Enforce allowlist
        if k not in effective_allowed:
            continue

        # 2. Reject sensitive key patterns
        if is_sensitive_key(k):
            continue

        # 3. Reject high-entropy secret values
        is_path_var = (k == "PATH")
        if is_sensitive_value(v, is_path=is_path_var):
            continue

        sanitized[k] = v

    return sanitized


def is_binary_name_approved(bin_name: str, allowed: Iterable[str]) -> bool:
    """Validates if a single binary filename matches approved command prefixes."""
    clean_name = Path(bin_name).name
    for prefix in allowed:
        if clean_name == prefix:
            return True
        if clean_name.startswith(f"{prefix}-") or clean_name.startswith(f"{prefix}."):
            return True
        if prefix == "python" and clean_name.startswith("python"):
            return True
    return False


def is_command_approved(
    cmd: str | list[str],
    allowed_commands: Iterable[str] | None = None,
) -> tuple[bool, str, str | None]:
    """Validates if a command invocation conforms to approved process execution guardrails."""
    allowed = list(allowed_commands if allowed_commands is not None else APPROVED_COMMAND_PREFIXES)

    if isinstance(cmd, list):
        if not cmd:
            return False, "Command is empty.", None
        primary_bin = Path(cmd[0]).name
        if not is_binary_name_approved(primary_bin, allowed):
            return False, f"Binary '{primary_bin}' is not in approved prefixes {sorted(allowed)}", primary_bin
        cmd_str = shlex.join(cmd)
    else:
        cmd_str = str(cmd).strip()
        if not cmd_str:
            return False, "Command string is empty.", None

    from ..security.interceptor import extract_executables
    executables = extract_executables(cmd_str)
    if not executables:
        try:
            tokens = shlex.split(cmd_str)
        except ValueError:
            tokens = cmd_str.split()
        if tokens:
            bin_name = tokens[0]
            if not is_binary_name_approved(bin_name, allowed):
                return False, f"Binary '{bin_name}' is not in approved prefixes {sorted(allowed)}", bin_name
        return True, "Command is permissible.", None

    for bin_name, _tokens in executables:
        if not is_binary_name_approved(bin_name, allowed):
            return (
                False,
                f"Binary '{bin_name}' extracted from '{cmd_str}' is not in approved prefixes {sorted(allowed)}",
                bin_name,
            )

    return True, "Command is permissible.", None


def _build_memory_limit_preexec_fn(memory_limit_mb: int | None) -> Callable[[], None] | None:
    """Constructs a child process preexec_fn applying POSIX memory limit caps."""
    if memory_limit_mb is None or memory_limit_mb <= 0:
        return None

    def _set_limits() -> None:
        try:
            import resource
            bytes_limit = memory_limit_mb * 1024 * 1024
            resource.setrlimit(resource.RLIMIT_AS, (bytes_limit, bytes_limit))
        except (ImportError, ValueError, OSError):
            pass

    return _set_limits


class SandboxedWorkerRunner:
    """Zero-trust autonomous worker process runner enforcing environment and command guardrails."""

    def __init__(
        self,
        worktree_dir: Path | str | None = None,
        allowed_commands: Iterable[str] | None = None,
        allowed_env_vars: Iterable[str] | None = None,
        timeout_seconds: float | None = None,
        memory_limit_mb: int | None = None,
    ):
        self.worktree_dir = Path(worktree_dir).resolve() if worktree_dir else None
        self.allowed_commands = list(allowed_commands if allowed_commands is not None else APPROVED_COMMAND_PREFIXES)
        self.allowed_env_vars = set(allowed_env_vars if allowed_env_vars is not None else DEFAULT_TOOLCHAIN_ENV_VARS)
        self.timeout_seconds = timeout_seconds
        self.memory_limit_mb = memory_limit_mb

    def sanitize_environment(
        self,
        env: Mapping[Any, Any] | None = None,
        extra_allowed: Iterable[str] | None = None,
    ) -> dict[str, str]:
        """Sanitizes environment dictionary for child process execution."""
        extra = set(extra_allowed or ())
        if self.worktree_dir:
            extra.update({"PWD", "SPEC_OPS_WORKTREE"})
        return sanitize_environment(
            env,
            allowed_vars=self.allowed_env_vars,
            extra_allowed=extra,
        )

    def run(
        self,
        cmd: str | list[str],
        cwd: Path | str | None = None,
        env: Mapping[Any, Any] | None = None,
        shell: bool = False,
        capture_output: bool = True,
        text: bool = True,
        timeout: float | None = None,
        **kwargs: Any,
    ) -> subprocess.CompletedProcess[str]:
        """Executes an approved binary within the zero-trust sandbox."""
        is_ok, reason, bin_name = is_command_approved(cmd, self.allowed_commands)
        if not is_ok:
            if self.worktree_dir:
                try:
                    from ..security.interceptor import record_security_violation
                    cmd_repr = shlex.join(cmd) if isinstance(cmd, list) else str(cmd)
                    record_security_violation(
                        worktree_dir=self.worktree_dir,
                        command=cmd_repr,
                        prohibited_binary=bin_name or "unknown",
                        parent_pid=os.getpid(),
                        details=reason,
                    )
                except Exception:
                    pass
            raise SecurityViolationError(
                f"Execution rejected by zero-trust sandbox: '{bin_name}' is not an approved binary.\n{reason}",
                binary=bin_name,
                details=reason,
            )

        sanitized_env = self.sanitize_environment(env)
        if self.worktree_dir:
            wt_path = str(self.worktree_dir.resolve())
            sanitized_env["SPEC_OPS_WORKTREE"] = wt_path
            sanitized_env["PWD"] = wt_path

        exec_cwd = Path(cwd or self.worktree_dir or Path.cwd()).resolve()
        eff_timeout = timeout if timeout is not None else self.timeout_seconds
        preexec = _build_memory_limit_preexec_fn(self.memory_limit_mb)

        exec_args = shlex.split(cmd) if not shell and isinstance(cmd, str) else cmd

        return subprocess.run(
            exec_args,
            cwd=exec_cwd,
            env=sanitized_env,
            shell=shell,
            capture_output=capture_output,
            text=text,
            timeout=eff_timeout,
            preexec_fn=preexec,
            **kwargs,
        )
