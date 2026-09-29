"""Prompt construction and agent command formatting utilities."""

from __future__ import annotations

import shlex
from pathlib import Path

from ..config.models import SpecOpsConfig
from ..core.models import Task


def build_task_prompt(task: Task, config: SpecOpsConfig) -> str:
    """Constructs explicit prompt contract for autonomous coding agents."""
    preflight_cmds = " && ".join(config.quality.preflight)
    parts = [
        f"# Task: {task.canonical_id} — {task.title}",
        "",
        "## Architectural Context",
        f"- Target Bounded Context: {task.target_bc or 'core'}",
        f"- Governing ADRs: {', '.join(task.governing_adrs) or 'None'}",
        f"- Governing PRDs: {', '.join(task.governing_prds) or 'None'}",
        f"- Governing Stories: {', '.join(task.governing_stories) or 'None'}",
        f"- File Length Invariant: Every new or edited source file must contain fewer than {config.architecture.file_length_limit} lines.",
        "- Testing Invariant: Features must be verified blackbox style through public entry points without private backdoors.",
        "- Backlog Isolation: DO NOT edit files under docs/project/ directly on this branch.",
        "",
        "## Task Specification",
        task.body.strip(),
        "",
        "## Acceptance Criteria & Preflight",
        f"Your modifications must pass: `{preflight_cmds}`",
        "Ensure all tests pass cleanly before completing.",
    ]
    return "\n".join(parts)


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
