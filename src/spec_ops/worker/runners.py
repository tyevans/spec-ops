"""Pluggable agent CLI runner execution engine with template interpolation."""

from __future__ import annotations

import os
import re
import shlex
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..config.models import SpecOpsConfig


from ..core.agent_cmd import build_agent_cmd, interpolate_runner_template


def prepare_runner_environment(
    worktree_dir: Path,
    base_env: dict[str, str] | None = None,
    sanitize: bool = False,
) -> dict[str, str]:
    """Constructs environment mapping setting SPEC_OPS_WORKTREE and PWD."""
    env = dict(base_env if base_env is not None else os.environ)
    if sanitize:
        from .sandbox_env import sanitize_environment
        env = sanitize_environment(env, extra_allowed={"SPEC_OPS_WORKTREE", "PWD"})
    resolved_wt = str(worktree_dir.resolve())
    env["SPEC_OPS_WORKTREE"] = resolved_wt
    env["PWD"] = resolved_wt
    return env


class AgentRunner:
    """Configurable runner managing agent command interpolation and execution setup."""

    def __init__(self, config: SpecOpsConfig):
        self.config = config

    def build_command(
        self,
        prompt_file: Path,
        prompt: str = "",
        worktree_dir: Path | None = None,
        continue_session: bool = False,
    ) -> list[str]:
        """Builds interpolated argv list using configured execution.agent_command."""
        cmd_template = self.config.execution.agent_command
        return interpolate_runner_template(
            cmd_template,
            prompt_file=prompt_file,
            prompt=prompt,
            worktree_dir=worktree_dir,
            continue_session=continue_session,
        )

    def prepare_environment(
        self,
        worktree_dir: Path,
        base_env: dict[str, str] | None = None,
        sanitize: bool = False,
    ) -> dict[str, str]:
        """Prepares worker execution environment with SPEC_OPS_WORKTREE and PWD."""
        return prepare_runner_environment(worktree_dir, base_env=base_env, sanitize=sanitize)

    def get_sandboxed_runner(
        self,
        worktree_dir: Path | None = None,
        timeout_seconds: float | None = None,
        memory_limit_mb: int | None = None,
    ) -> Any:
        """Returns a configured SandboxedWorkerRunner for zero-trust worker execution."""
        from .sandbox_env import SandboxedWorkerRunner
        sandbox_config = getattr(self.config.execution, "sandbox", None)
        allowed_cmds = sandbox_config.allowed_commands if sandbox_config else None
        return SandboxedWorkerRunner(
            worktree_dir=worktree_dir,
            allowed_commands=allowed_cmds,
            timeout_seconds=timeout_seconds,
            memory_limit_mb=memory_limit_mb,
        )


def build_agent_cmd(
    cmd_template: str,
    prompt: str,
    prompt_file: Path,
    continue_session: bool = False,
    worktree_dir: Path | None = None,
) -> list[str]:
    """Public helper for building agent argv lists (backwards compatible)."""
    return interpolate_runner_template(
        cmd_template=cmd_template,
        prompt_file=prompt_file,
        prompt=prompt,
        worktree_dir=worktree_dir,
        continue_session=continue_session,
    )
