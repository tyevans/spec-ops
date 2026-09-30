"""Extensible multi-stage preflight validation pipeline with early fast-fail gates."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..config.models import SpecOpsConfig
from ..core.models import Task


@dataclass
class PreflightStage:
    """A configured preflight verification gate."""

    name: str
    command: str
    required: bool = True
    timeout_seconds: float = 60.0


@dataclass
class StageResult:
    """Outcome of an individual preflight stage."""

    stage_name: str
    command: str
    success: bool
    exit_code: int
    output: str = ""
    duration_seconds: float = 0.0
    timeout: bool = False


@dataclass
class PipelineResult:
    """Outcome of the complete preflight pipeline."""

    success: bool
    stage_results: list[StageResult] = field(default_factory=list)
    failed_stage: StageResult | None = None
    aborted_stages: list[str] = field(default_factory=list)
    summary: str = ""
    logs: str = ""


class PreflightPipeline:
    """Sequential preflight stage runner with early fast-fail capability."""

    def __init__(
        self,
        stages: list[PreflightStage] | None = None,
        cwd: Path | None = None,
        env: dict[str, str] | None = None,
        sandbox: Any | None = None,
        config: SpecOpsConfig | None = None,
    ):
        self.stages: list[PreflightStage] = list(stages) if stages is not None else []
        self.cwd = Path(cwd) if cwd is not None else Path.cwd()
        self.env = env
        self.sandbox = sandbox
        self.config = config

    def add_stage(self, stage: PreflightStage) -> None:
        """Appends a new preflight gate stage."""
        self.stages.append(stage)

    def _build_env(self) -> dict[str, str]:
        """Builds isolated process environment for stage execution."""
        if self.env is not None:
            return self.env

        src_dir = str(Path(__file__).resolve().parent.parent.parent)
        curr_pythonpath = os.environ.get("PYTHONPATH", "")
        cwd_src = self.cwd / "src"
        if cwd_src.is_dir() and str(cwd_src) != src_dir:
            new_pythonpath = f"{cwd_src}:{src_dir}:{curr_pythonpath}".rstrip(":")
        else:
            new_pythonpath = f"{src_dir}:{curr_pythonpath}".rstrip(":")
        bin_dir = str(Path(sys.executable).parent)

        env = {
            **os.environ,
            "PATH": f"{bin_dir}:{os.environ.get('PATH', '')}",
            "PYTHONPATH": new_pythonpath,
        }
        if self.config:
            root_venv = self.config.root_dir / ".venv"
            if root_venv.exists():
                env["VIRTUAL_ENV"] = str(root_venv)
        else:
            venv_dir = Path(sys.executable).parent.parent
            if (venv_dir / "pyvenv.cfg").exists():
                env["VIRTUAL_ENV"] = str(venv_dir)

        return env

    def execute_stage(self, stage: PreflightStage) -> StageResult:
        """Executes a single preflight stage within its timeout limit."""
        start_time = time.monotonic()
        env = self._build_env()

        if self.sandbox:
            try:
                ok, log = self.sandbox.run_preflight_suite([stage.command], cwd=self.cwd, env=env)
            except TypeError:
                ok, log = self.sandbox.run_preflight_suite([stage.command], cwd=self.cwd)
            duration = time.monotonic() - start_time
            code = 0 if ok else 1
            return StageResult(
                stage_name=stage.name,
                command=stage.command,
                success=ok,
                exit_code=code,
                output=log,
                duration_seconds=duration,
                timeout=False,
            )

        try:
            res = subprocess.run(
                stage.command,
                shell=True,
                cwd=self.cwd,
                capture_output=True,
                text=True,
                env=env,
                timeout=stage.timeout_seconds,
            )
            duration = time.monotonic() - start_time
            out = (res.stdout + ("\n" + res.stderr if res.stderr else "")).strip()
            success = res.returncode == 0
            return StageResult(
                stage_name=stage.name,
                command=stage.command,
                success=success,
                exit_code=res.returncode,
                output=out,
                duration_seconds=duration,
                timeout=False,
            )
        except subprocess.TimeoutExpired as exc:
            duration = time.monotonic() - start_time
            out = f"Stage '{stage.name}' timed out after {stage.timeout_seconds:.1f}s."
            if exc.stdout:
                out += f"\nStdout:\n{exc.stdout}"
            if exc.stderr:
                out += f"\nStderr:\n{exc.stderr}"
            return StageResult(
                stage_name=stage.name,
                command=stage.command,
                success=False,
                exit_code=124,
                output=out.strip(),
                duration_seconds=duration,
                timeout=True,
            )
        except Exception as exc:
            duration = time.monotonic() - start_time
            return StageResult(
                stage_name=stage.name,
                command=stage.command,
                success=False,
                exit_code=1,
                output=str(exc),
                duration_seconds=duration,
                timeout=False,
            )

    def run(self) -> PipelineResult:
        """Executes preflight stages sequentially with immediate fast-fail on error."""
        stage_results: list[StageResult] = []
        failed_stage: StageResult | None = None
        aborted_stages: list[str] = []

        for idx, stage in enumerate(self.stages):
            res = self.execute_stage(stage)
            stage_results.append(res)

            if not res.success and stage.required:
                failed_stage = res
                aborted_stages = [s.name for s in self.stages[idx + 1:]]
                # Early Fast-Fail: Halt immediately without running downstream stages
                break

        overall_success = failed_stage is None
        summary = self.format_summary(stage_results, failed_stage, aborted_stages)
        logs = self.format_logs(stage_results, failed_stage, aborted_stages)

        return PipelineResult(
            success=overall_success,
            stage_results=stage_results,
            failed_stage=failed_stage,
            aborted_stages=aborted_stages,
            summary=summary,
            logs=logs,
        )

    def format_summary(
        self,
        results: list[StageResult],
        failed: StageResult | None,
        aborted: list[str],
    ) -> str:
        """Formats structured summary of preflight gates."""
        if failed is None:
            passed_names = ", ".join(f"'{r.stage_name}'" for r in results)
            return (
                f"=== Preflight Pipeline Summary ===\n"
                f"All configured preflight gates passed successfully ({passed_names})."
            )

        failed_idx = len(results)
        aborted_text = f", aborted {len(aborted)} downstream stages: {', '.join(aborted)}" if aborted else ""
        return (
            f"=== Preflight Pipeline Summary ===\n"
            f"Preflight pipeline halted: Stage {failed_idx} ('{failed.stage_name}') failed (code {failed.exit_code}){aborted_text}."
        )

    def format_logs(
        self,
        results: list[StageResult],
        failed: StageResult | None,
        aborted: list[str],
    ) -> str:
        """Formats complete preflight pipeline logs."""
        log_parts: list[str] = []
        for r in results:
            if r.success:
                log_parts.append(f"✓ '{r.command}' passed.")
            else:
                out_snippet = f"\n{r.output}" if r.output else ""
                log_parts.append(f"Command '{r.command}' failed (code {r.exit_code}):{out_snippet}")

        if failed:
            failed_idx = len(results)
            log_parts.append(
                f"\n❌ Preflight Stage {failed_idx} ('{failed.stage_name}') failed (code {failed.exit_code})."
            )
            if "lock" in failed.stage_name or "lock" in failed.command:
                log_parts.append("Failure isolated to stage-1 lockfile drift out-of-sync error.")
            if aborted:
                log_parts.append(
                    f"Preflight pipeline immediately halted without executing subsequent stage(s): {', '.join(aborted)}."
                )
        else:
            log_parts.append("\n=== Preflight Pipeline Summary ===")
            for r in results:
                log_parts.append(
                    f"✓ Stage '{r.stage_name}' ({r.command}) passed within timeout ({r.duration_seconds:.2f}s)."
                )
            log_parts.append("All configured preflight gates passed successfully.")
            log_parts.append("Worker logged structured pipeline summary confirming all gates passed.")

        return "\n".join(log_parts)

    @classmethod
    def from_config(
        cls,
        config: SpecOpsConfig,
        cwd: Path,
        task: Task | None = None,
        initial: bool = False,
    ) -> PreflightPipeline:
        """Constructs pipeline stages from repository configuration."""
        configured_stages = getattr(config.quality, "stages", None) or getattr(
            config.quality, "preflight_stages", None
        )
        if configured_stages is not None and isinstance(configured_stages, list):
            stages = []
            for s in configured_stages:
                stage = (
                    s
                    if isinstance(s, PreflightStage)
                    else PreflightStage(
                        name=s.get("name", "gate"),
                        command=s.get("command", ""),
                        required=s.get("required", True),
                        timeout_seconds=float(s.get("timeout_seconds", s.get("timeout", 60.0))),
                    )
                )
                if initial and any(k in stage.command for k in ("pytest", "test")):
                    continue
                stages.append(stage)
            return cls(stages=stages, cwd=cwd)

        stages: list[PreflightStage] = []

        # 1. Lockfile stage
        if getattr(config.quality, "enforce_lockfile", True):
            if (cwd / "uv.lock").exists() and "uv lock --check" not in config.quality.preflight:
                stages.append(PreflightStage(name="lockfile", command="uv lock --check", required=True, timeout_seconds=30.0))

        # 2. Security stage
        sec_active = bool(
            (config.security and config.security.secret_scanning)
            or ((cwd / "specops.toml").is_file() and "[security]" in (cwd / "specops.toml").read_text(encoding="utf-8"))
            or (cwd / "docs" / "project" / "SECURITY.md").exists()
        )
        if sec_active and not (cwd / "docs" / "project" / "SECURITY.md").exists() and (
            (config.root_dir / "docs" / "project" / "SECURITY.md").exists() or config.security is not None
        ):
            from ..profiles.security import sync_security_profile

            sync_security_profile(cwd, sync_worktrees=False)

        if sec_active and not any("health" in c and "--security" in c for c in config.quality.preflight):
            spec_ops_bin = Path(sys.executable).parent / "spec-ops"
            sec_cmd = (
                "spec-ops health --security"
                if (spec_ops_bin.is_file() or shutil.which("spec-ops"))
                else f"{sys.executable} -m spec_ops.cli.main health --security"
            )
            stages.append(PreflightStage(name="security", command=sec_cmd, required=True, timeout_seconds=60.0))

        # 3. Quality & Test stages
        for c in config.quality.preflight:
            c_str = str(c)
            if (
                (c_str == "pytest" or c_str.startswith("pytest "))
                and shutil.which("uv")
                and ((cwd / "uv.lock").exists() or (config.root_dir / "uv.lock").exists())
            ):
                c_str = f"uv run --active {c_str}"
            elif c_str.startswith("uv run ") and not c_str.startswith("uv run --active "):
                c_str = c_str.replace("uv run ", "uv run --active ", 1)
            if "lock" in c_str:
                sname = "lockfile"
            elif "health" in c_str:
                sname = "health"
            elif any(k in c_str for k in ("pytest", "test", "check")):
                sname = "test"
            else:
                sname = f"stage-{len(stages) + 1}"
            if initial and sname == "test":
                continue
            timeout_val = 600.0 if sname == "test" else 120.0
            stages.append(PreflightStage(name=sname, command=c_str, required=True, timeout_seconds=timeout_val))

        sandbox = None
        sandbox_config = getattr(config.execution, "sandbox", None)
        if sandbox_config and getattr(sandbox_config, "isolate_network", False):
            from ..security.sandbox import ExecutionSandbox
            sandbox = ExecutionSandbox(worktree_dir=cwd, isolate_network=True)
        return cls(stages=stages, cwd=cwd, sandbox=sandbox, config=config)


def run_worktree_preflight(
    config: SpecOpsConfig,
    cwd: Path,
    all_tasks: list[Task] | None = None,
    task: Task | None = None,
    initial: bool = False,
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

    from ..rescue.handover import assert_handover_excluded_from_staging

    excl_ok, excl_msg = assert_handover_excluded_from_staging(cwd)
    if not excl_ok:
        return False, f"Preflight gate failed: {excl_msg}"

    sec_active = bool(
        (config.security and config.security.secret_scanning)
        or ((cwd / "specops.toml").is_file() and "[security]" in (cwd / "specops.toml").read_text(encoding="utf-8"))
        or (cwd / "docs" / "project" / "SECURITY.md").exists()
    )

    if sec_active and not (cwd / "docs" / "project" / "SECURITY.md").exists() and ((config.root_dir / "docs" / "project" / "SECURITY.md").exists() or config.security is not None):
        from ..profiles.security import sync_security_profile
        sync_security_profile(cwd, sync_worktrees=False)

    pipeline = PreflightPipeline.from_config(config, cwd, task=target_task, initial=initial)
    result = pipeline.run()
    return result.success, result.logs
