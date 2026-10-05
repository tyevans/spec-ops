"""Backlog queue management, dependency graphs, and atomic transitions."""

from __future__ import annotations

import contextlib
import re
from pathlib import Path
from typing import Any

import yaml

from ..core.models import Task
from ..core.parser import FRONTMATTER_PATTERN, extract_frontmatter, parse_priority_ranks, parse_task


from .task_serializer import write_task_file



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
        acquire_lock: bool = True,
    ) -> Path:
        root = (repo_root or self.backlog_dir.parent.parent).resolve()
        from .lock import BacklogLock, atomic_write, recover_transactions

        def _execute() -> Path:
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

        if acquire_lock:
            with BacklogLock(root).acquire():
                return _execute()
        return _execute()

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
        integration_runner: Any | None = None,
    ) -> tuple[bool, str]:
        """Integration gate verifying supply-chain, commit signatures, and dual-custody under advisory lock."""
        import subprocess
        from ..config.loader import load_config
        from .lock import BacklogLock
        from ..security.lockfile import (
            PROTECTED_DEPENDENCY_FILES,
            check_diff_for_dependency_modifications,
            verify_lockfile,
        )

        root = (repo_root or self.backlog_dir.parent.parent).resolve()
        cfg = config or load_config(root_dir=root)
        lock_mgr = BacklogLock(repo_root=root)
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

            target_branch = ""
            if wt_dir.exists() and wt_dir.is_dir():
                b_res = subprocess.run(["git", "branch", "--show-current"], cwd=wt_dir, capture_output=True, text=True)
                active_b = b_res.stdout.strip()
                if active_b and active_b != base_branch:
                    target_branch = active_b
            if not target_branch:
                target_branch = task.branch
            if not target_branch:
                cur_b = subprocess.run(["git", "branch", "--show-current"], cwd=root, capture_output=True, text=True).stdout.strip()
                if cur_b != base_branch:
                    target_branch = cur_b
            if not target_branch:
                b_all = subprocess.run(["git", "branch", "--format=%(refname:short)"], cwd=root, capture_output=True, text=True)
                for b in (b_all.stdout.splitlines() if b_all.returncode == 0 else []):
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

            # Integration merge with structured trailers via injected integration runner
            if target_branch and target_branch != base_branch:
                if integration_runner is not None:
                    merge_ok, merge_msg = integration_runner(
                        root,
                        target_branch,
                        base_branch,
                        task,
                        buf_target,
                        lambda: self.complete_task(
                            task,
                            cascade=True,
                            repo_root=root,
                            target_buffer=buf_target,
                            acquire_lock=False,
                        ),
                    )
                    if not merge_ok:
                        return False, f"Integration gate failed: {merge_msg}"
                    return True, f"Task {task.canonical_id} passed integration gate and transitioned to Complete."

            self.complete_task(
                task,
                cascade=True,
                repo_root=root,
                target_buffer=buf_target,
                acquire_lock=False,
            )
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

