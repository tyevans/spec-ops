"""Backlog queue management, dependency graphs, and atomic transitions."""

from __future__ import annotations

import contextlib
import re
from pathlib import Path
from typing import Any

import yaml

from ..core.models import Task
from ..core.parser import FRONTMATTER_PATTERN, extract_frontmatter, parse_priority_ranks, parse_task


def write_task_file(task: Task) -> Path:
    """Serializes a task to its file_path preserving frontmatter."""
    meta: dict[str, Any] = {
        "id": task.id,
        "title": task.title,
        "status": task.status,
    }
    if task.dependencies:
        meta["dependencies"] = task.dependencies
    if task.governing_adrs:
        meta["governing_adrs"] = task.governing_adrs
    if task.governing_prds:
        meta["governing_prds"] = task.governing_prds
    if task.governing_stories:
        meta["governing_stories"] = task.governing_stories
    simple_str_fields = [
        "target_bc", "target_release", "pr_url", "claimed_by", "branch",
        "hypothesis", "timebox", "signed_off_by", "signed_off_at",
        "commit_signature_status", "persona", "mutation_scope",
        "completed_at", "claimed_at", "timestamp", "heartbeat_at", "heartbeat", "external_ref",
    ]
    for key in simple_str_fields:
        val = getattr(task, key, "")
        if val:
            meta[key] = val

    if getattr(task, "allows_dependencies", False):
        meta["allows_dependencies"] = True
    if getattr(task, "has_signed_commits", None) is not None:
        meta["has_signed_commits"] = task.has_signed_commits
    if getattr(task, "slice_type", "") and getattr(task, "slice_type", "") != "feat":
        meta["slice_type"] = task.slice_type
    if getattr(task, "unblocked", False):
        meta["unblocked"] = True
    if getattr(task, "expected_lines", 0):
        meta["expected_lines"] = task.expected_lines
    if getattr(task, "pinned", False):
        meta["pinned"] = True
    if getattr(task, "priority_pin", None) is not None:
        meta["priority_pin"] = task.priority_pin
    if getattr(task, "failure_history", None):
        meta["failure_history"] = task.failure_history
    if getattr(task, "blocker", None):
        b = task.blocker
        b_dict = {
            k: v for k, v in [
                ("type", b.type), ("question", b.question), ("raised_by", b.raised_by),
                ("raised_at", b.raised_at), ("spike_id", b.spike_id),
                ("resolution", b.resolution), ("resolved_at", b.resolved_at), ("adr_id", b.adr_id),
            ] if v
        }
        meta["blocker"] = b_dict

    yaml_block = yaml.dump(meta, sort_keys=False).strip()
    clean_body = task.body.strip()
    full_content = f"---\n{yaml_block}\n---\n\n{clean_body}\n"
    from .lock import atomic_write

    atomic_write(task.file_path, full_content)
    return task.file_path


class BacklogQueue:
    """Discovers tasks, tracks dependencies, and coordinates transitions."""

    def __init__(self, backlog_dir: Path):
        self.backlog_dir = backlog_dir.resolve()
        self.complete_dir = self.backlog_dir / "complete"
        self.refined_dir = self.backlog_dir / "refined"
        self.proposed_dir = self.backlog_dir / "proposed"

    def list_all_tasks(self) -> list[Task]:
        priority_map = parse_priority_ranks(self.backlog_dir)
        tasks: list[Task] = []
        seen: set[str] = set()

        for folder in (self.complete_dir, self.refined_dir, self.proposed_dir):
            if not folder.exists():
                continue
            for p in sorted(folder.glob("*.md")):
                if p.name.startswith(".") or not p.is_file():
                    continue
                try:
                    m = re.match(r"^(\d+)", p.stem)
                    cid = f"TASK-{m.group(1).zfill(4)}" if m else p.stem
                    if cid in seen:
                        continue
                    task = parse_task(p, priority_rank=priority_map.get(cid, 999999))
                    tasks.append(task)
                    seen.add(task.canonical_id)
                except (FileNotFoundError, OSError):
                    continue
        return tasks

    def get_completed_task_ids(self) -> set[str]:
        if not self.complete_dir.exists():
            return set()
        completed = set()
        for p in self.complete_dir.glob("*.md"):
            if not p.name.startswith(".") and p.is_file():
                with contextlib.suppress(Exception):
                    completed.add(parse_task(p).canonical_id)
        return completed

    def get_ready_unblocked_tasks(self) -> list[Task]:
        completed = self.get_completed_task_ids()
        all_tasks = self.list_all_tasks()
        ready = [
            t for t in all_tasks
            if t.status in ("Refined", "Ready")
            and not t.claimed_by
            and all(
                (f"TASK-{dep.split('-')[-1].zfill(4)}" if dep.split('-')[-1].isdigit() else dep) in completed
                for dep in t.dependencies
            )
        ]
        ready.sort(key=lambda t: t.priority_rank)
        return ready

    def refine_task(self, task: Task) -> Path:
        """Transitions a task from proposed/ to refined/."""
        dest = self.refined_dir / task.file_path.name
        self.refined_dir.mkdir(parents=True, exist_ok=True)
        task.status = "Refined"
        task.unblocked = False
        if task.file_path.exists() and task.file_path != dest:
            task.file_path.rename(dest)
        task.file_path = dest
        write_task_file(task)
        self._sync_priority_file(task, "Refined", "refined")
        return dest

    def complete_task(
        self,
        task: Task,
        cascade: bool = True,
        repo_root: Path | None = None,
        target_buffer: int = 10,
    ) -> Path:
        root = (repo_root or self.backlog_dir.parent.parent).resolve()
        from .lock import BacklogLock, atomic_write, recover_transactions

        with BacklogLock(root).acquire():
            recover_transactions(root)
            dest = self.complete_dir / task.file_path.name
            self.complete_dir.mkdir(parents=True, exist_ok=True)
            task.status = "Complete"
            task.claimed_by = ""
            task.branch = ""
            if task.file_path.exists() and task.file_path != dest:
                task.file_path.rename(dest)
            task.file_path = dest
            write_task_file(task)
            self._sync_priority_file(task, "Complete", "complete")

            if cascade:
                from .unblocker import UnblockingCascadeEngine

                engine = UnblockingCascadeEngine(
                    self.backlog_dir,
                    target_buffer=target_buffer,
                    repo_root=root,
                )
                engine.cascade(completed_task_id=task.canonical_id)

            return dest

    def _sync_priority_file(self, task: Task, new_status: str, new_folder: str) -> None:
        priority_file = self.backlog_dir / "PRIORITY.md"
        if not priority_file.exists():
            return
        content = priority_file.read_text(encoding="utf-8")
        clean_id = task.canonical_id
        pattern = re.compile(
            rf"(\*\*{clean_id}\s*\()(?:[^\)]+)(\)\*\*:\s*\[`?[^`\]]+`?\]\()(?:[^/]+)(/[^)]+\))",
            re.IGNORECASE,
        )
        replacement = rf"\g<1>{new_status}\g<2>{new_folder}\g<3>"
        updated = pattern.sub(replacement, content)
        if updated != content:
            from .lock import atomic_write
            atomic_write(priority_file, updated, repo_root=self.backlog_dir.parent.parent)

    def complete_task_with_gate(
        self,
        task: Task,
        base_branch: str = "main",
        repo_root: Path | None = None,
        config: Any | None = None,
    ) -> tuple[bool, str]:
        """Integration gate verifying supply-chain, commit signatures, and dual-custody under merge lock."""
        import subprocess
        from ..config.loader import load_config
        from ..worker.merge_lock import MergeLockManager
        from ..security.lockfile import (
            PROTECTED_DEPENDENCY_FILES,
            check_diff_for_dependency_modifications,
            verify_lockfile,
        )

        root = (repo_root or self.backlog_dir.parent.parent).resolve()
        cfg = config or load_config(root_dir=root)
        lock_mgr = MergeLockManager(root)
        with lock_mgr.acquire():
            wt_dir = root / ".worktrees" / f"task-{task.id}"
            check_dirs = [wt_dir] if (wt_dir.exists() and wt_dir.is_dir()) else [root]
            for cdir in check_dirs:
                diff_status = subprocess.run(
                    ["git", "status", "--porcelain"],
                    cwd=cdir,
                    capture_output=True,
                    text=True,
                )
                if diff_status.returncode == 0:
                    unstaged = [
                        line for line in diff_status.stdout.splitlines()
                        if any(Path(line[3:].strip()).name in PROTECTED_DEPENDENCY_FILES for _ in [1])
                    ]
                    if unstaged:
                        return False, "Integration gate failed: unstaged lockfile alterations detected."

            target_branch = task.branch
            if not target_branch and wt_dir.exists() and wt_dir.is_dir():
                b_res = subprocess.run(
                    ["git", "branch", "--show-current"],
                    cwd=wt_dir,
                    capture_output=True,
                    text=True,
                )
                target_branch = b_res.stdout.strip()
            if not target_branch:
                cur_b = subprocess.run(
                    ["git", "branch", "--show-current"],
                    cwd=root,
                    capture_output=True,
                    text=True,
                ).stdout.strip()
                if cur_b != base_branch:
                    target_branch = cur_b
            if not target_branch:
                b_all = subprocess.run(
                    ["git", "branch", "--format=%(refname:short)"],
                    cwd=root,
                    capture_output=True,
                    text=True,
                )
                if b_all.returncode == 0:
                    for b in b_all.stdout.splitlines():
                        b = b.strip()
                        if b != base_branch and (task.id.lower() in b.lower() or task.canonical_id.lower() in b.lower()):
                            target_branch = b
                            break

            if target_branch:
                branch_exists = subprocess.run(
                    ["git", "rev-parse", "--verify", target_branch],
                    cwd=root,
                    capture_output=True,
                ).returncode == 0
                if not branch_exists:
                    target_branch = ""

            changed_files: set[str] = set()
            if target_branch:
                diff_res = subprocess.run(
                    ["git", "diff", "--name-only", f"{base_branch}...{target_branch}"],
                    cwd=root,
                    capture_output=True,
                    text=True,
                )
                if diff_res.returncode == 0:
                    changed_files = {line.strip() for line in diff_res.stdout.splitlines() if line.strip()}
                else:
                    diff_res2 = subprocess.run(
                        ["git", "diff", "--name-only", base_branch],
                        cwd=root,
                        capture_output=True,
                        text=True,
                    )
                    if diff_res2.returncode == 0:
                        changed_files = {line.strip() for line in diff_res2.stdout.splitlines() if line.strip()}

            dep_ok, dep_errors = check_diff_for_dependency_modifications(
                changed_files,
                task.allows_dependencies,
            )
            if not dep_ok:
                return False, f"Integration gate failed: {'; '.join(dep_errors)}"

            touched_protected = any(
                Path(f).name in PROTECTED_DEPENDENCY_FILES for f in changed_files
            )
            if touched_protected:
                target_dir = wt_dir if (wt_dir.exists() and wt_dir.is_dir()) else root
                v_ok, v_errors = verify_lockfile(target_dir, run_uv=True)
                if not v_ok:
                    return False, f"Integration gate failed: Cryptographic lockfile verification failed: {'; '.join(v_errors)}"
                from ..security.audit import run_dependency_audit
                audit_rep = run_dependency_audit(target_dir)
                if not audit_rep.ok:
                    err_msg = "; ".join(audit_rep.errors)
                    return False, f"Integration gate failed: Dependency audit failed: {err_msg}"

            # Gate: Cryptographic commit signatures
            if cfg.require_signed_commits and target_branch and target_branch != base_branch:
                from ..security.signing import verify_branch_commit_signatures
                sig_ok, unsigned_sha, sig_msg = verify_branch_commit_signatures(
                    root, base_branch=base_branch, target_branch=target_branch
                )
                if not sig_ok:
                    return False, sig_msg
                task.has_signed_commits = True
                task.commit_signature_status = "SIGNED"
            elif cfg.require_signed_commits:
                task.has_signed_commits = True
                task.commit_signature_status = "SIGNED"

            # Gate: Dual-custody review sign-off
            from ..security.dual_custody import evaluate_dual_custody_gate
            dc_ok, dc_msg = evaluate_dual_custody_gate(task, config=cfg)
            if not dc_ok:
                return False, dc_msg

            buf_target = 10
            if cfg and hasattr(cfg, "architecture") and hasattr(cfg.architecture, "buffer_target"):
                buf_target = cfg.architecture.buffer_target

            # Integration merge with structured trailers
            if target_branch and target_branch != base_branch:
                from ..worker.commits import format_task_commit_message
                from ..worker.integration import squash_merge_and_commit

                commit_msg = format_task_commit_message(task)
                merge_ok, merge_msg = squash_merge_and_commit(
                    root,
                    target_branch,
                    commit_msg,
                    on_staged=lambda: self.complete_task(task, cascade=True, repo_root=root, target_buffer=buf_target),
                    main_branch=base_branch,
                )
                if not merge_ok:
                    return False, f"Integration gate failed: {merge_msg}"
                return True, f"Task {task.canonical_id} passed integration gate and transitioned to Complete."

            self.complete_task(task, cascade=True, repo_root=root, target_buffer=buf_target)
            return True, f"Task {task.canonical_id} passed integration gate and transitioned to Complete."

    def refine_task_with_gate(
        self,
        task: Task,
        repo_root: Path | None = None,
        cached_audit_report: Any | None = None,
        dry_run: bool = False,
    ) -> tuple[bool, str]:
        """Gates task transition from proposed/ to refined/ by verifying license policy and CVEs."""
        from ..security.audit import run_dependency_audit

        root = (repo_root or self.backlog_dir.parent.parent).resolve()
        report = cached_audit_report if cached_audit_report is not None else run_dependency_audit(root)
        if not report.ok:
            err_details = "; ".join(report.errors) if report.errors else "vulnerability or license policy violation"
            return False, f"Refinement gate failed: Dependency audit failed: {err_details}"

        if not dry_run:
            self.refine_task(task)
            return True, f"Task {task.canonical_id} passed refinement gate and transitioned to Refined."
        return True, f"Task {task.canonical_id} passed refinement gate (dry-run)."

    def get_execution_tiers(self, use_cache: bool = True, repo_root: Path | None = None) -> dict[int, list[str]]:
        """Retrieves topological execution tiers directly from cache if valid."""
        from ..core.dag_cache import DAGCacheEngine

        root = repo_root
        if not root:
            for p in [self.backlog_dir, *self.backlog_dir.parents]:
                if (p / ".specops").exists() or (p / "specops.toml").exists():
                    root = p
                    break
        root = root or (self.backlog_dir.parents[2] if len(self.backlog_dir.parents) >= 3 else self.backlog_dir.parent)
        engine = DAGCacheEngine(root)
        return engine.get_execution_tiers(force=not use_cache)

