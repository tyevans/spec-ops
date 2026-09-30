"""Fast incremental in-worktree preflight runner with targeted step isolation (US-0093)."""

from __future__ import annotations

import json
import logging
import re
import subprocess
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from ..config.models import SpecOpsConfig
from ..worker.preflight import PipelineResult, PreflightPipeline, PreflightStage

logger = logging.getLogger(__name__)

STEP_DEPENDENCY_PATTERNS: dict[str, list[str]] = {
    "lock": ["uv.lock", "pyproject.toml"],
    "health": ["src/", "docs/", "pyproject.toml", "specops.toml", "PRIORITY.md"],
    "lint": ["src/", "tests/", "pyproject.toml", ".ruff.toml", "ruff.toml"],
    "test": ["src/", "tests/", "pyproject.toml"],
}


@dataclass
class StepRecord:
    name: str
    command: str
    passed: bool
    exit_code: int = 0
    output: str = ""
    duration_seconds: float = 0.0
    timestamp: float = 0.0
    dependencies: list[str] = field(default_factory=list)


@dataclass
class StepCacheData:
    version: int = 1
    steps: dict[str, StepRecord] = field(default_factory=dict)


def get_cache_path(worktree_dir: Path) -> Path:
    return worktree_dir / ".specops" / "step_cache.json"


def load_step_cache(worktree_dir: Path) -> StepCacheData:
    cache_file = get_cache_path(worktree_dir)
    if not cache_file.exists():
        return StepCacheData()
    try:
        raw = json.loads(cache_file.read_text(encoding="utf-8"))
        steps_dict = {
            k: StepRecord(
                name=v.get("name", k),
                command=v.get("command", ""),
                passed=bool(v.get("passed", False)),
                exit_code=int(v.get("exit_code", 0)),
                output=v.get("output", ""),
                duration_seconds=float(v.get("duration_seconds", 0.0)),
                timestamp=float(v.get("timestamp", 0.0)),
                dependencies=list(v.get("dependencies", [])),
            )
            for k, v in raw.get("steps", {}).items()
        }
        return StepCacheData(version=raw.get("version", 1), steps=steps_dict)
    except Exception as exc:
        logger.warning("Failed to load step cache: %s", exc)
        return StepCacheData()


def save_step_cache(worktree_dir: Path, cache: StepCacheData) -> None:
    cache_file = get_cache_path(worktree_dir)
    cache_file.parent.mkdir(parents=True, exist_ok=True)
    payload = {"version": cache.version, "steps": {k: asdict(v) for k, v in cache.steps.items()}}
    cache_file.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def clear_step_cache(worktree_dir: Path) -> bool:
    cache_file = get_cache_path(worktree_dir)
    if cache_file.exists():
        try:
            cache_file.unlink()
            return True
        except Exception:
            return False
    return False


def get_step_dependencies(step_name: str, command: str) -> list[str]:
    combined = f"{step_name} {command}".lower()
    for key, patterns in STEP_DEPENDENCY_PATTERNS.items():
        if key in combined:
            return list(patterns)
    return ["src/", "tests/"]


def file_matches_dependency(file_path: str, dep_pattern: str) -> bool:
    clean_p = file_path.strip().lstrip("./")
    clean_dep = dep_pattern.strip().lstrip("./")
    if clean_dep.endswith("/"):
        return clean_p.startswith(clean_dep)
    return clean_p == clean_dep or clean_p.endswith("/" + clean_dep)


def is_step_cache_valid(step: StepRecord, dirty_files: list[str] | set[str]) -> bool:
    if not step.passed:
        return False
    deps = step.dependencies or get_step_dependencies(step.name, step.command)
    return not any(file_matches_dependency(f, d) for f in dirty_files for d in deps)


def invalidate_dirty_step_caches(
    cache: StepCacheData,
    dirty_files: list[str] | set[str],
    isolated_step: str | None = None,
) -> list[str]:
    invalidated: list[str] = []
    iso = isolated_step.lower().strip() if isolated_step else None
    for name, step in list(cache.steps.items()):
        if not step.passed:
            continue
        if iso and (iso in name.lower() or iso in step.command.lower()):
            continue
        if not is_step_cache_valid(step, dirty_files):
            invalidated.append(name)
            step.passed = False
    return invalidated



def get_dirty_files(worktree_dir: Path) -> list[str]:
    try:
        res = subprocess.run(["git", "status", "--porcelain"], cwd=worktree_dir, capture_output=True, text=True)
        if res.returncode != 0:
            return []
        dirty: list[str] = []
        for line in res.stdout.splitlines():
            line = line.strip()
            if line:
                rel = line[2:].strip().split(" -> ")[-1].strip()
                if rel and not rel.startswith(".specops"):
                    dirty.append(rel)
        return dirty
    except Exception:
        return []


def parse_prior_failures_from_prompt(worktree_dir: Path) -> StepCacheData | None:
    prompt_file = worktree_dir / ".task-prompt.md"
    if not prompt_file.exists():
        return None
    try:
        content = prompt_file.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return None

    steps: dict[str, StepRecord] = {}
    for line in content.splitlines():
        line = line.strip()
        m_pass = re.search(r"✓\s*['\"]?([^'\"]+)['\"]?\s*passed", line)
        if m_pass:
            cmd = m_pass.group(1).strip()
            name = _infer_name(cmd)
            steps[name] = StepRecord(name=name, command=cmd, passed=True, dependencies=get_step_dependencies(name, cmd))
        m_fail = re.search(r"Command\s*['\"]?([^'\"]+)['\"]?\s*failed", line)
        if m_fail:
            cmd = m_fail.group(1).strip()
            name = _infer_name(cmd)
            steps[name] = StepRecord(name=name, command=cmd, passed=False, exit_code=1, dependencies=get_step_dependencies(name, cmd))
        elif line.startswith("FAILED ") or "failed with" in line:
            target = line.removeprefix("FAILED ").split("::")[0].strip()
            cmd = f"uv run pytest {target}" if target.endswith(".py") else "uv run pytest"
            steps["test"] = StepRecord(name="test", command=cmd, passed=False, exit_code=1, dependencies=get_step_dependencies("test", cmd))

    return StepCacheData(version=1, steps=steps) if steps else None


def _infer_name(cmd: str) -> str:
    c = cmd.lower()
    if "lock" in c:
        return "lockfile"
    if "health" in c:
        return "health"
    if any(k in c for k in ("ruff", "lint", "flake8")):
        return "lint"
    if any(k in c for k in ("pytest", "test")):
        return "test"
    return "stage"


def record_pipeline_result(worktree_dir: Path, result: PipelineResult) -> None:
    cache = load_step_cache(worktree_dir)
    for res in result.stage_results:
        cache.steps[res.stage_name] = StepRecord(
            name=res.stage_name,
            command=res.command,
            passed=res.success,
            exit_code=res.exit_code,
            output=res.output,
            duration_seconds=res.duration_seconds,
            timestamp=time.time(),
            dependencies=get_step_dependencies(res.stage_name, res.command),
        )
    save_step_cache(worktree_dir, cache)


def match_stage(stages: list[PreflightStage], step_query: str) -> PreflightStage | None:
    q = step_query.strip().lower()
    for s in stages:
        if s.name.lower() == q or q in s.name.lower() or q in s.command.lower():
            return s
    alias_map = {
        "lock": ["lock"],
        "lockfile": ["lock"],
        "lint": ["ruff", "lint", "flake8"],
        "pytest": ["pytest", "test"],
        "test": ["pytest", "test"],
        "health": ["health"],
    }
    for a in alias_map.get(q, []):
        for s in stages:
            if a in s.name.lower() or a in s.command.lower():
                return s
    return None


def execute_single_stage(stage: PreflightStage, worktree_dir: Path, config: SpecOpsConfig) -> StepRecord:
    t0 = time.monotonic()
    pipeline = PreflightPipeline(stages=[stage], cwd=worktree_dir, config=config)
    res = pipeline.execute_stage(stage)
    duration = time.monotonic() - t0
    return StepRecord(
        name=stage.name,
        command=stage.command,
        passed=res.success,
        exit_code=res.exit_code,
        output=res.output,
        duration_seconds=duration,
        timestamp=time.time(),
        dependencies=get_step_dependencies(stage.name, stage.command),
    )


def resolve_worktree_dir(config: SpecOpsConfig, task_id: str | None = None) -> Path:
    if task_id:
        clean = task_id.upper().replace("TASK-", "").lstrip("0")
        cand = config.root_dir / ".worktrees" / f"task-{clean.zfill(4)}"
        if cand.exists():
            return cand
    cwd = Path.cwd().resolve()
    try:
        cwd.relative_to(config.root_dir)
        curr = cwd
        while curr != config.root_dir and curr != curr.parent:
            if curr.parent.name == ".worktrees" or (curr / ".task-prompt.md").exists():
                return curr
            curr = curr.parent
    except ValueError:
        pass
    wt_parent = config.root_dir / ".worktrees"
    if wt_parent.exists():
        cand_list = [p for p in wt_parent.iterdir() if p.is_dir() and p.name.startswith("task-")]
        if len(cand_list) == 1:
            return cand_list[0]
    return cwd



def run_incremental_rescue_test(
    config: SpecOpsConfig,
    task_id: str | None = None,
    step: str | None = None,
    only_failed: bool = False,
    worktree_dir: Path | None = None,
) -> int:
    wt = worktree_dir or resolve_worktree_dir(config, task_id)
    if not wt or not wt.exists():
        print(f"❌ Target worktree directory not found for task '{task_id}'.")
        return 1

    cache = load_step_cache(wt)
    if not cache.steps:
        prompt_cache = parse_prior_failures_from_prompt(wt)
        if prompt_cache:
            cache = prompt_cache
            save_step_cache(wt, cache)

    dirty_files = get_dirty_files(wt)
    if dirty_files and invalidate_dirty_step_caches(cache, dirty_files, isolated_step=step):
        save_step_cache(wt, cache)

    pipeline = PreflightPipeline.from_config(config, wt)
    stages = pipeline.stages or [
        PreflightStage(name="lockfile", command="uv lock --check"),
        PreflightStage(name="health", command="spec-ops health"),
        PreflightStage(name="lint", command="ruff check && ruff format --check"),
        PreflightStage(name="test", command="uv run pytest"),
    ]

    if step:
        matched = match_stage(stages, step)
        if not matched:
            print(f"❌ No preflight step matches '{step}'.")
            return 1
        print(f"▶ Executing isolated step '{matched.name}' ({matched.command})...")
        rec = execute_single_stage(matched, wt, config)
        cache.steps[matched.name] = rec
        save_step_cache(wt, cache)
        if rec.passed:
            print(f"✅ PASSED: Step '{matched.name}' succeeded in {rec.duration_seconds:.2f}s.")
            return 0
        print(f"❌ FAILED: Step '{matched.name}' failed (code {rec.exit_code}) in {rec.duration_seconds:.2f}s.")
        if rec.output:
            print(rec.output)
        return 1

    if only_failed:
        failed_recs = [s for s in cache.steps.values() if not s.passed]
        passed_recs = [s for s in cache.steps.values() if s.passed]
        if not failed_recs:
            print("No previously failed preflight steps found in cache.")
            return 0
        for p in passed_recs:
            print(f"✓ Skipping cached step '{p.command}' (previously passed)")
        all_ok = True
        for f in failed_recs:
            matched = match_stage(stages, f.name) or PreflightStage(name=f.name, command=f.command)
            print(f"▶ Re-executing failed step: {matched.command}")
            rec = execute_single_stage(matched, wt, config)
            cache.steps[f.name] = rec
            save_step_cache(wt, cache)
            if rec.passed:
                print(f"✅ PASSED: Step '{matched.name}' passed in {rec.duration_seconds:.2f}s.")
            else:
                print(f"❌ FAILED: Step '{matched.name}' failed (code {rec.exit_code}).")
                if rec.output:
                    print(rec.output)
                all_ok = False
        return 0 if all_ok else 1

    all_ok = True
    for s in stages:
        c_entry = cache.steps.get(s.name)
        if c_entry and is_step_cache_valid(c_entry, dirty_files) and c_entry.passed:
            print(f"✓ Skipping cached step '{s.name}' ({s.command})")
            continue
        print(f"▶ Executing step '{s.name}' ({s.command})...")
        rec = execute_single_stage(s, wt, config)
        cache.steps[s.name] = rec
        save_step_cache(wt, cache)
        if not rec.passed:
            print(f"❌ FAILED: Step '{s.name}' failed (code {rec.exit_code}).")
            if rec.output:
                print(rec.output)
            all_ok = False
            if s.required:
                break
        else:
            print(f"✅ PASSED: Step '{s.name}' passed in {rec.duration_seconds:.2f}s.")
    return 0 if all_ok else 1
