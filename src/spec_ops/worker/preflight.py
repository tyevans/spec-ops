"""Preflight verification suite for autonomous workers."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

from ..config.models import SpecOpsConfig
from ..core.models import Task


def run_worktree_preflight(
    config: SpecOpsConfig,
    cwd: Path,
    all_tasks: list[Task] | None = None,
    task: Task | None = None,
) -> tuple[bool, str]:
    """Runs configured preflight verification commands with supply-chain lockfile checks."""
    from ..security.lockfile import check_worktree_dependency_integrity

    target_task = task
    if target_task is None and all_tasks:
        m = re.search(r"task-(\d+)", cwd.name, re.IGNORECASE)
        if m:
            cid = f"TASK-{m.group(1).zfill(4)}"
            for t in all_tasks:
                if t.canonical_id == cid:
                    target_task = t
                    break

    allows_dep = getattr(target_task, "allows_dependencies", False) if target_task else False
    dep_ok, dep_errs = check_worktree_dependency_integrity(cwd, allows_dependencies=allows_dep)
    if not dep_ok:
        return False, f"Unauthorized Dependency Modification: {'; '.join(dep_errs)}"

    commands = list(config.quality.preflight)

    if getattr(config.quality, "enforce_lockfile", True):
        if (cwd / "uv.lock").exists() and "uv lock --check" not in commands:
            commands.insert(0, "uv lock --check")

    sec_active = bool(
        (config.security and config.security.secret_scanning)
        or ((cwd / "specops.toml").is_file() and "[security]" in (cwd / "specops.toml").read_text(encoding="utf-8"))
        or (cwd / "docs" / "project" / "SECURITY.md").exists()
    )

    if sec_active and not any("health" in c and "--security" in c for c in commands):
        spec_ops_bin = Path(sys.executable).parent / "spec-ops"
        sec_cmd = (
            "spec-ops health --security"
            if (spec_ops_bin.is_file() or shutil.which("spec-ops"))
            else f"{sys.executable} -m spec_ops.cli.main health --security"
        )
        commands.insert(0, sec_cmd)

    sandbox_config = getattr(config.execution, "sandbox", None)
    if sandbox_config and getattr(sandbox_config, "isolate_network", False):
        from ..security.sandbox import ExecutionSandbox

        sandbox = ExecutionSandbox(worktree_dir=cwd, isolate_network=True)
        return sandbox.run_preflight_suite(commands, cwd=cwd)

    src_dir = str(Path(__file__).resolve().parent.parent.parent)
    curr_pythonpath = os.environ.get("PYTHONPATH", "")
    new_pythonpath = f"{src_dir}:{curr_pythonpath}".rstrip(":")

    env = {
        **os.environ,
        "PATH": f"{Path(sys.executable).parent}:{os.environ.get('PATH', '')}",
        "PYTHONPATH": new_pythonpath,
    }

    logs: list[str] = []
    for cmd in commands:
        res = subprocess.run(cmd, shell=True, cwd=cwd, capture_output=True, text=True, env=env)
        if res.returncode != 0:
            combined_output = (res.stdout + ("\n" + res.stderr if res.stderr else "")).strip()
            logs.append(f"Command '{cmd}' failed (code {res.returncode}):\n{combined_output}")
            return False, "\n".join(logs)
        logs.append(f"✓ '{cmd}' passed.")
    return True, "\n".join(logs)
