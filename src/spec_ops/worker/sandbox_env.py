"""Zero-trust autonomous worker process sandboxing and environment scrubbing engine."""

from __future__ import annotations

import os
import re
import shlex
import subprocess
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping

from ..security.sandbox_env import (
    DEFAULT_TOOLCHAIN_ENV_VARS,
    SECRET_PATTERNS,
    SENSITIVE_KEYWORDS,
    SENSITIVE_PREFIXES,
    TOKEN_VALUE_PREFIXES,
    is_sensitive_key,
    is_sensitive_value,
    sanitize_environment,
)

APPROVED_COMMAND_PREFIXES: tuple[str, ...] = (
    "uv",
    "git",
    "python",
    "pytest",
    "spec-ops",
)


class SecurityViolationError(PermissionError):
    """Raised when an unapproved command or binary execution is rejected by sandbox guardrails."""

    def __init__(self, message: str, binary: str | None = None, details: str = ""):
        super().__init__(message)
        self.binary = binary
        self.details = details


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
