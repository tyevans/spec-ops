"""Autonomous worktree auto-rebase and optimistic merge conflict resolver."""

from __future__ import annotations

import re
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..config.models import SpecOpsConfig
from .guardrails import sanitize_backlog_modifications
from .integration import is_rebase_in_progress


@dataclass
class AutoRebaseResult:
    """Structured result of an autonomous worktree auto-rebase operation."""

    success: bool
    task_id: str | None = None
    status: str = "clean"  # "clean", "conflict_aborted", "dry_run", "up_to_date", "error"
    message: str = ""
    conflicted_files: list[str] = field(default_factory=list)
    handover_path: str | None = None
    pre_rebase_sha: str = ""
    current_head: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Converts result to a JSON-serializable dictionary."""
        return {
            "success": self.success,
            "task_id": self.task_id,
            "status": self.status,
            "message": self.message,
            "conflicted_files": self.conflicted_files,
            "handover_path": self.handover_path,
            "pre_rebase_sha": self.pre_rebase_sha,
            "current_head": self.current_head,
        }


def get_git_dir(worktree_dir: Path) -> Path | None:
    """Resolves the absolute git directory for the given worktree."""
    res = subprocess.run(["git", "rev-parse", "--git-dir"], cwd=worktree_dir, capture_output=True, text=True)
    if res.returncode != 0:
        return None
    p = Path(res.stdout.strip())
    return p if p.is_absolute() else (worktree_dir / p).resolve()


def cleanup_git_locks(worktree_dir: Path) -> None:
    """Removes stale git lock files and lingering rebase directories."""
    git_dir = get_git_dir(worktree_dir)
    if not git_dir or not git_dir.exists():
        return
    for base in [git_dir, worktree_dir, git_dir / "refs"]:
        if not base.exists():
            continue
        for lk in ["index.lock", "HEAD.lock", "rebase-merge.lock", "MERGE_HEAD"]:
            target = base / lk
            if target.is_file():
                try:
                    target.unlink()
                except OSError:
                    pass
    for reb_name in ["rebase-merge", "rebase-apply"]:
        reb_dir = git_dir / reb_name
        if reb_dir.exists():
            shutil.rmtree(reb_dir, ignore_errors=True)


def canonicalize_task_id(task_id: str | None) -> str | None:
    """Normalizes task ID to canonical format (e.g. TASK-0147)."""
    if not task_id:
        return None
    m = re.search(r"(\d+)", task_id.strip())
    return f"TASK-{m.group(1).zfill(4)}" if m else task_id.strip().upper()


def resolve_target_worktree(
    task_id: str | None = None,
    worktree_dir: Path | str | None = None,
) -> tuple[Path, str | None]:
    """Resolves worktree directory and canonical task ID from arguments or environment."""
    canon_id = canonicalize_task_id(task_id)
    if worktree_dir is not None:
        wt_path = Path(worktree_dir).resolve()
        return wt_path, canon_id or _infer_task_id(wt_path)

    cwd = Path.cwd().resolve()
    if canon_id:
        c_num = canon_id.replace("TASK-", "").lstrip("0")
        for cand in [
            cwd / ".worktrees" / f"task-{canon_id.lower()}",
            cwd / ".worktrees" / f"task-{c_num}",
            cwd / ".worktrees" / canon_id.lower(),
            cwd.parent / f"task-{canon_id.lower()}",
        ]:
            if cand.is_dir():
                return cand.resolve(), canon_id

    return cwd, canon_id or _infer_task_id(cwd)


def _infer_task_id(path: Path) -> str | None:
    """Infers canonical task ID from directory name or git branch."""
    m_dir = re.search(r"task-?(\d+)", path.name, re.IGNORECASE)
    if m_dir:
        return f"TASK-{m_dir.group(1).zfill(4)}"
    res = subprocess.run(["git", "symbolic-ref", "--short", "HEAD"], cwd=path, capture_output=True, text=True)
    if res.returncode == 0:
        m_branch = re.search(r"(?:feat|task)/TASK-(\d+)", res.stdout.strip(), re.IGNORECASE)
        if m_branch:
            return f"TASK-{m_branch.group(1).zfill(4)}"
    return None


def extract_conflict_diagnostics(worktree_dir: Path) -> tuple[list[str], str]:
    """Extracts conflicted files and conflict markers diagnostic context."""
    conflicted: list[str] = []
    res_diff = subprocess.run(["git", "diff", "--name-only", "--diff-filter=U"], cwd=worktree_dir, capture_output=True, text=True)
    if res_diff.returncode == 0:
        conflicted.extend([f.strip() for f in res_diff.stdout.splitlines() if f.strip()])
    res_stat = subprocess.run(["git", "status", "--porcelain"], cwd=worktree_dir, capture_output=True, text=True)
    if res_stat.returncode == 0:
        for line in res_stat.stdout.splitlines():
            if line[:2] in ("UU", "AA", "DD", "AU", "UA", "UD", "DU"):
                f = line[3:].strip()
                if f not in conflicted:
                    conflicted.append(f)
    diags: list[str] = []
    for f in conflicted:
        fp = worktree_dir / f
        if fp.is_file():
            try:
                txt = fp.read_text(encoding="utf-8", errors="replace")
                if "<<<<<<<" in txt:
                    diags.append(f"--- Conflict in {f} ---\n{txt[:1200]}")
            except OSError:
                pass
    return conflicted, "\n\n".join(diags)


def generate_conflict_handover(
    worktree_dir: Path,
    task_id: str,
    conflicted_files: list[str],
    failure_log: str,
    base_branch: str,
    config: SpecOpsConfig | None = None,
) -> Path:
    """Generates structured HANDOVER.md documenting merge conflict diagnostics."""
    handover_path = worktree_dir / "HANDOVER.md"
    flist = "\n".join(f"- `{f}`" for f in conflicted_files) if conflicted_files else "- (Unknown conflicts)"
    body = (
        f"# AI-to-Human Handover Brief: {task_id}\n\n"
        f"## Task Header\n"
        f"- **Canonical ID**: {task_id}\n"
        f"- **Title**: Autonomous Worktree Auto-Rebase Conflict\n"
        f"- **Target Bounded Context**: worker\n"
        f"- **Status**: Conflict Aborted\n\n"
        f"## Conflict Diagnostic Summary\n"
        f"Autonomous rebase onto '{base_branch}' encountered merge conflicts in:\n"
        f"{flist}\n\n"
        f"The rebase was safely aborted (`git rebase --abort`) and pre-rebase branch state restored.\n\n"
        f"### Conflicted Files\n{flist}\n\n"
        f"## Exact Failure Log\n```text\n{failure_log.strip()}\n```\n\n"
        f"## Governing Context\n"
        f"- **Governing PRD**: [PRD-0004](docs/project/product/accepted/prd-0004-autonomous-multi-worker-fleet-and-worktree-rescue-engine.md)\n"
        f"- **Governing User Story**: [US-0080](docs/project/user_stories/accepted/us-0080-pluggable-agent-runner-templates-and-worktree-simulation.md)\n"
        f"- **Baseline ADRs**: [ADR-0001](docs/project/adrs/accepted/adr-0001-specification-as-code-pmac.md), "
        f"[ADR-0002](docs/project/adrs/accepted/adr-0002-bounded-context-file-size-limits.md), "
        f"[ADR-0005](docs/project/adrs/accepted/adr-0005-worktree-concurrency-and-backlog-isolation.md)\n\n"
        f"## Reproduction Command\n```bash\nspec-ops worker rebase {task_id}\n```\n\n"
        f"## Completion Command\n```bash\nspec-ops queue complete {task_id}\n```\n"
    )
    handover_path.write_text(body, encoding="utf-8")
    return handover_path


def auto_rebase_worktree(
    worktree_dir: Path | str | None = None,
    task_id: str | None = None,
    target_branch: str = "main",
    abort_on_conflict: bool = True,
    dry_run: bool = False,
    config: SpecOpsConfig | None = None,
) -> AutoRebaseResult:
    """Executes in-worktree autonomous rebase against latest target branch."""
    wt_path, canon_id = resolve_target_worktree(task_id=task_id, worktree_dir=worktree_dir)
    is_repo = subprocess.run(["git", "rev-parse", "--is-inside-work-tree"], cwd=wt_path, capture_output=True, text=True)
    if is_repo.returncode != 0:
        return AutoRebaseResult(success=False, task_id=canon_id, status="error", message=f"'{wt_path}' not a git worktree.")

    sanitize_backlog_modifications(wt_path)
    pre_sha = subprocess.run(["git", "rev-parse", "HEAD"], cwd=wt_path, capture_output=True, text=True).stdout.strip()
    branch = subprocess.run(["git", "symbolic-ref", "--short", "HEAD"], cwd=wt_path, capture_output=True, text=True).stdout.strip()

    # Resolve target branch commit
    if subprocess.run(["git", "rev-parse", "--verify", target_branch], cwd=wt_path, capture_output=True).returncode != 0:
        if subprocess.run(["git", "rev-parse", "--verify", f"origin/{target_branch}"], cwd=wt_path, capture_output=True).returncode == 0:
            target_branch = f"origin/{target_branch}"
        else:
            return AutoRebaseResult(success=False, task_id=canon_id, status="error", message=f"Branch '{target_branch}' not found.", pre_rebase_sha=pre_sha, current_head=pre_sha)

    target_sha = subprocess.run(["git", "rev-parse", target_branch], cwd=wt_path, capture_output=True, text=True).stdout.strip()
    mb = subprocess.run(["git", "merge-base", "HEAD", target_branch], cwd=wt_path, capture_output=True, text=True).stdout.strip()

    if mb == target_sha:
        return AutoRebaseResult(success=True, task_id=canon_id, status="up_to_date", message=f"Branch '{branch or 'HEAD'}' is up to date with '{target_branch}'.", pre_rebase_sha=pre_sha, current_head=pre_sha)

    if dry_run:
        mt = subprocess.run(["git", "merge-tree", mb, "HEAD", target_branch], cwd=wt_path, capture_output=True, text=True)
        has_conf = mt.returncode != 0 or "<<<<<<<" in mt.stdout
        msg = f"Dry-run: rebase onto '{target_branch}' would {'encounter conflicts' if has_conf else 'apply cleanly'}."
        return AutoRebaseResult(success=not has_conf, task_id=canon_id, status="dry_run", message=msg, pre_rebase_sha=pre_sha, current_head=pre_sha)

    # Run rebase
    reb = subprocess.run(["git", "rebase", target_branch], cwd=wt_path, capture_output=True, text=True)
    if reb.returncode == 0 and not is_rebase_in_progress(wt_path):
        sanitize_backlog_modifications(wt_path)
        cur_head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=wt_path, capture_output=True, text=True).stdout.strip()
        return AutoRebaseResult(success=True, task_id=canon_id, status="clean", message=f"Rebased cleanly onto '{target_branch}'.", pre_rebase_sha=pre_sha, current_head=cur_head)

    conf_files, diag = extract_conflict_diagnostics(wt_path)
    raw_err = reb.stderr.strip() or reb.stdout.strip()
    fail_log = f"{raw_err}\n\n{diag}" if diag else raw_err

    if abort_on_conflict:
        subprocess.run(["git", "rebase", "--abort"], cwd=wt_path, capture_output=True)
        cleanup_git_locks(wt_path)
        cur_ref = subprocess.run(["git", "symbolic-ref", "--short", "HEAD"], cwd=wt_path, capture_output=True, text=True)
        if branch and (cur_ref.returncode != 0 or cur_ref.stdout.strip() != branch):
            subprocess.run(["git", "checkout", branch], cwd=wt_path, capture_output=True)
        if pre_sha:
            subprocess.run(["git", "reset", "--hard", pre_sha], cwd=wt_path, capture_output=True)

        eff_id = canon_id or branch or "TASK-UNKNOWN"
        handover = generate_conflict_handover(wt_path, eff_id, conf_files, fail_log, target_branch, config)
        sanitize_backlog_modifications(wt_path)

        return AutoRebaseResult(
            success=False,
            task_id=canon_id,
            status="conflict_aborted",
            message=f"Rebase encountered conflicts in {len(conf_files)} file(s). Aborted safely and generated HANDOVER.md.",
            conflicted_files=conf_files,
            handover_path=str(handover),
            pre_rebase_sha=pre_sha,
            current_head=pre_sha,
        )

    return AutoRebaseResult(
        success=False,
        task_id=canon_id,
        status="conflict",
        message=f"Rebase paused with conflicts in {len(conf_files)} file(s).",
        conflicted_files=conf_files,
        pre_rebase_sha=pre_sha,
        current_head=pre_sha,
    )
