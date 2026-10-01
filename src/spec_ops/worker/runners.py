"""Pluggable agent CLI runner execution engine with template interpolation."""

from __future__ import annotations

import os
import re
import shlex
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..config.models import SpecOpsConfig


def interpolate_runner_template(
    cmd_template: str,
    prompt_file: Path,
    prompt: str = "",
    worktree_dir: Path | None = None,
    continue_session: bool = False,
    env: dict[str, str] | None = None,
) -> list[str]:
    """Safely interpolates template placeholders into argv list without shell injection.

    Placeholders supported:
    - {prompt_file}: Absolute path to the generated task prompt file
    - {prompt}: Raw prompt text payload
    - {SPEC_OPS_WORKTREE}: Worktree directory path
    - {PWD}: Worktree directory path
    """
    if not cmd_template or not cmd_template.strip():
        return []

    try:
        tokens = shlex.split(cmd_template)
    except ValueError:
        tokens = cmd_template.split()
    if not tokens:
        return []

    # Handle agy command defaults
    if tokens[0] == "agy":
        if "--dangerously-skip-permissions" not in tokens:
            tokens.insert(1, "--dangerously-skip-permissions")
        if continue_session and "-c" not in tokens and "--continue" not in tokens:
            tokens.insert(2, "-c")

    # Determine paths
    if worktree_dir is not None:
        wt_path = str(worktree_dir.resolve())
        abs_prompt = str((worktree_dir / prompt_file).resolve()) if not prompt_file.is_absolute() else str(prompt_file.resolve())
    else:
        wt_path = str(prompt_file.parent.resolve())
        if prompt_file.is_absolute() or prompt_file.exists():
            abs_prompt = str(prompt_file.resolve())
        else:
            abs_prompt = str(prompt_file)

    has_prompt_file_placeholder = "{prompt_file}" in cmd_template
    has_prompt_placeholder = "{prompt}" in cmd_template

    argv: list[str] = []
    for token in tokens:
        # Interpolate variables within token
        replaced = token
        if "{prompt_file}" in replaced:
            replaced = replaced.replace("{prompt_file}", abs_prompt)
        if "{prompt}" in replaced:
            replaced = replaced.replace("{prompt}", prompt)
        if "{SPEC_OPS_WORKTREE}" in replaced:
            replaced = replaced.replace("{SPEC_OPS_WORKTREE}", wt_path)
        if "{PWD}" in replaced:
            replaced = replaced.replace("{PWD}", wt_path)

        # Handle environment variables if provided
        if env:
            for env_k, env_v in env.items():
                replaced = replaced.replace(f"{{{env_k}}}", env_v)

        argv.append(replaced)

    # If neither {prompt_file} nor {prompt} was specified, append prompt_file to argv
    if not has_prompt_file_placeholder and not has_prompt_placeholder:
        argv.append(abs_prompt)

    return argv


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
