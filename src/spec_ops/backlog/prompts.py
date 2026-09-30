"""Prompt construction and agent command formatting utilities."""

from __future__ import annotations

import shlex
from pathlib import Path

from ..config.models import SpecOpsConfig
from ..core.models import Task


def build_task_prompt(task: Task, config: SpecOpsConfig) -> str:
    """Constructs explicit prompt contract for autonomous coding agents."""
    from ..worker.claimer import hydrate_task_prompt
    return hydrate_task_prompt(task, config)


def build_agent_cmd(
    cmd_template: str,
    prompt: str,
    prompt_file: Path,
    continue_session: bool = False,
) -> list[str]:
    """Safely builds argv list for agent command without shell quote-mangling."""
    parts = shlex.split(cmd_template)
    if parts and parts[0] == "agy":
        if "--dangerously-skip-permissions" not in parts:
            parts.insert(1, "--dangerously-skip-permissions")
        if continue_session and "-c" not in parts and "--continue" not in parts:
            parts.insert(2, "-c")

    reconstructed = " ".join(parts)
    if "{prompt_file}" in reconstructed:
        formatted = reconstructed.format(prompt_file=str(prompt_file))
        return shlex.split(formatted)
    elif "{prompt}" in reconstructed:
        placeholder = "__SPEC_OPS_PROMPT_PAYLOAD__"
        argv = shlex.split(reconstructed.replace("{prompt}", placeholder))
        return [prompt if p == placeholder else p for p in argv]
    else:
        return parts + [str(prompt_file)]
