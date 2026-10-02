"""Execution sandbox coordinator managing subshell interception and process isolation."""

from __future__ import annotations

import os
import shlex
import subprocess
from pathlib import Path
from typing import Any

from .interceptor import (
    FORBIDDEN_UTILITIES,
    create_interceptor_shims,
    record_security_violation,
    resolve_audit_log_path,
    validate_command,
)
from .network_guard import generate_network_isolation_sitecustomize


class ExecutionSandbox:
    """Zero-trust execution sandbox for autonomous worker commands and preflight runs."""

    def __init__(
        self,
        worktree_dir: Path,
        allowed_commands: list[str] | None = None,
        isolate_network: bool = False,
        prohibited_commands: list[str] | None = None,
        scrub_environment: bool = True,
    ):
        self.worktree_dir = Path(worktree_dir).resolve()
        self.allowed_commands = list(allowed_commands) if allowed_commands is not None else None
        self.isolate_network = isolate_network
        self.prohibited_commands = list(prohibited_commands or FORBIDDEN_UTILITIES)
        self.scrub_environment = scrub_environment
        self.audit_log_path = resolve_audit_log_path(self.worktree_dir)

    def prepare_environment(self, base_env: dict[str, str] | None = None) -> dict[str, str]:
        """Configures PATH shims and PYTHONPATH network isolation in the child execution environment."""
        env = dict(base_env or os.environ).copy()
        if self.scrub_environment:
            from .sandbox_env import sanitize_environment
            env = sanitize_environment(
                env,
                extra_allowed={"PYTHONPATH", "PYTEST_CURRENT_TEST", "SPEC_OPS_WORKTREE", "PWD"},
            )

        # 1. Setup PATH interceptor shims
        shims_dir = self.worktree_dir / ".specops" / "sandbox_shims"
        create_interceptor_shims(shims_dir, self.audit_log_path, self.prohibited_commands)
        env["PATH"] = f"{shims_dir}:{env.get('PATH', '')}".rstrip(":")

        # 2. Setup socket network isolation via sitecustomize if requested
        if self.isolate_network:
            net_dir = self.worktree_dir / ".specops" / "network_shims"
            generate_network_isolation_sitecustomize(net_dir)
            env["PYTHONPATH"] = f"{net_dir}:{env.get('PYTHONPATH', '')}".rstrip(":")

        return env

    def run(
        self,
        cmd: str | list[str],
        cwd: Path | None = None,
        env: dict[str, str] | None = None,
        shell: bool = False,
        capture_output: bool = True,
        text: bool = True,
        **kwargs: Any,
    ) -> subprocess.CompletedProcess[str]:
        """Executes a command within the hardened sandbox, enforcing allowlists and isolation."""
        exec_cwd = Path(cwd or self.worktree_dir).resolve()

        # Frontdoor validation
        is_ok, reason, prohibited_bin = validate_command(
            cmd,
            allowed_commands=self.allowed_commands,
            prohibited_commands=self.prohibited_commands,
        )

        cmd_repr = " ".join(cmd) if isinstance(cmd, list) else str(cmd)

        if not is_ok:
            # Command prohibited: record audit log and terminate with exit code 126
            record_security_violation(
                worktree_dir=self.worktree_dir,
                command=cmd_repr,
                prohibited_binary=prohibited_bin or "unknown",
                parent_pid=os.getpid(),
                details=reason,
            )
            err_msg = (
                f"Command Prohibited: execution of '{prohibited_bin or cmd_repr}' is forbidden "
                f"by sandbox policy (exit code 126)\n{reason}\n"
            )
            return subprocess.CompletedProcess(
                args=cmd,
                returncode=126,
                stdout="",
                stderr=err_msg,
            )

        # Build hardened execution environment
        hardened_env = self.prepare_environment(env)

        exec_args = shlex.split(cmd) if not shell and isinstance(cmd, str) else cmd

        # Execute child process
        res = subprocess.run(
            exec_args,
            cwd=exec_cwd,
            env=hardened_env,
            shell=shell,
            capture_output=capture_output,
            text=text,
            **kwargs,
        )
        return res

    def run_preflight_suite(
        self,
        commands: list[str],
        cwd: Path | None = None,
        env: dict[str, str] | None = None,
    ) -> tuple[bool, str]:
        """Executes preflight verification commands with socket-level egress isolation."""
        exec_cwd = Path(cwd or self.worktree_dir).resolve()
        logs: list[str] = []

        for cmd in commands:
            res = self.run(cmd, cwd=exec_cwd, env=env, shell=True)
            if res.returncode != 0:
                err = res.stderr.strip() or res.stdout.strip()
                logs.append(f"Command '{cmd}' failed (code {res.returncode}):\n{err}")
                return False, "\n".join(logs)
            logs.append(f"✓ '{cmd}' passed.")

        return True, "\n".join(logs)
