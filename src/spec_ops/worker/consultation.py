"""Active specification consultation and peer review coordination for multi-agent workers."""

from __future__ import annotations

import re
import subprocess
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from ..config.models import SpecOpsConfig
from ..core.models import Task
from ..core.parser import extract_frontmatter


@dataclass
class ConsultedAdr:
    id: str
    title: str
    status: str
    invariants: list[str] = field(default_factory=list)
    path: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ConsultedPrd:
    id: str
    title: str
    stage: str
    checkable_outcomes: list[str] = field(default_factory=list)
    path: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ConsultedStory:
    id: str
    title: str
    scenarios: list[str] = field(default_factory=list)
    path: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class SpecConsultationReport:
    task_id: str
    task_title: str
    target_bc: str
    adrs: list[ConsultedAdr] = field(default_factory=list)
    prds: list[ConsultedPrd] = field(default_factory=list)
    stories: list[ConsultedStory] = field(default_factory=list)
    brief: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class PeerConsultationReview:
    approved: bool
    seam_violations: list[str] = field(default_factory=list)
    adr_violations: list[str] = field(default_factory=list)
    feedback: list[str] = field(default_factory=list)
    summary: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class OrchestrationAttempt:
    attempt: int
    preflight_success: bool
    peer_review_approved: bool
    feedback: str = ""
    logs: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class WorkerOrchestrationReport:
    task_id: str
    success: bool
    attempts: int
    max_attempts: int
    preflight_passed: bool
    peer_review_passed: bool
    specs_consulted: SpecConsultationReport | None = None
    commit_hash: str = ""
    trailers: dict[str, str] = field(default_factory=dict)
    message: str = ""
    attempt_history: list[OrchestrationAttempt] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _extract_digits(identifier: str) -> str:
    digits = re.sub(r"[^\d]", "", identifier)
    return digits.lstrip("0") if digits else ""


def _find_spec_file(dir_path: Path, num: str, prefix: str) -> Path | None:
    if not dir_path.exists() or not num:
        return None
    for p in dir_path.rglob("*.md"):
        if p.name.startswith("REGISTRY"):
            continue
        m = re.search(rf"(?:{prefix})?[-_]?(\d+)", p.stem, re.IGNORECASE)
        if m and _extract_digits(m.group(1)) == num:
            return p
    return None


def consult_specifications(task: Task, repo_root: Path) -> SpecConsultationReport:
    """Actively consults governing ADRs, PRDs, and user stories for a task."""
    adrs_consulted: list[ConsultedAdr] = []
    adrs_dir = repo_root / "docs" / "project" / "adrs"
    for raw in task.governing_adrs:
        num = _extract_digits(raw)
        found = _find_spec_file(adrs_dir, num, "adr")
        cid = f"ADR-{num.zfill(4)}" if num else raw
        if found and found.exists():
            meta, body = extract_frontmatter(found.read_text(encoding="utf-8", errors="replace"))
            invs = [
                ln.strip().lstrip("-* ").strip() for ln in body.splitlines()
                if (ln.strip().startswith("- ") or ln.strip().startswith("* "))
                and any(k in ln.lower() for k in ("limit", "invariant", "must", "strictly", "mock", "tdd"))
            ]
            adrs_consulted.append(ConsultedAdr(cid, meta.get("title") or found.stem, meta.get("status", "Accepted"), invs[:5], str(found.relative_to(repo_root))))
        else:
            adrs_consulted.append(ConsultedAdr(cid, raw, "Accepted", [], ""))

    prds_consulted: list[ConsultedPrd] = []
    prd_dir = repo_root / "docs" / "project" / "product"
    for raw in task.governing_prds:
        num = _extract_digits(raw)
        found = _find_spec_file(prd_dir, num, "prd")
        cid = f"PRD-{num.zfill(4)}" if num else raw
        if found and found.exists():
            meta, body = extract_frontmatter(found.read_text(encoding="utf-8", errors="replace"))
            outcomes = [
                ln.strip().lstrip("-* ").strip() for ln in body.splitlines()
                if (ln.strip().startswith("-") or ln.strip().startswith("*")) and "outcome" in body[:body.find(ln)].lower()[-200:]
            ]
            prds_consulted.append(ConsultedPrd(cid, meta.get("title") or found.stem, meta.get("stage", "accepted"), outcomes[:6], str(found.relative_to(repo_root))))
        else:
            prds_consulted.append(ConsultedPrd(cid, raw, "accepted", [], ""))

    stories_consulted: list[ConsultedStory] = []
    story_dir = repo_root / "docs" / "project" / "user_stories"
    for raw in task.governing_stories:
        num = _extract_digits(raw)
        found = _find_spec_file(story_dir, num, "us")
        cid = f"US-{num.zfill(4)}" if num else raw
        if found and found.exists():
            meta, body = extract_frontmatter(found.read_text(encoding="utf-8", errors="replace"))
            scenarios = [m.group(1).strip() for m in re.finditer(r"Scenario:\s*(.+)", body)]
            stories_consulted.append(ConsultedStory(cid, meta.get("title") or found.stem, scenarios, str(found.relative_to(repo_root))))
        else:
            stories_consulted.append(ConsultedStory(cid, raw, [], ""))

    brief_lines = [
        f"# Specification Consultation Brief for {task.canonical_id}",
        f"**Task Title**: {task.title} | **Target BC**: {task.target_bc or 'core'}",
        "\n## Governing ADR Invariants",
    ]
    for a in adrs_consulted:
        brief_lines.append(f"- **{a.id}**: {a.title} ({a.status})")
        brief_lines.extend(f"  - Invariant: {inv}" for inv in a.invariants)
    brief_lines.append("\n## Checkable PRD Outcomes")
    for p in prds_consulted:
        brief_lines.append(f"- **{p.id}**: {p.title}")
        brief_lines.extend(f"  - Outcome: {o}" for o in p.checkable_outcomes)
    brief_lines.append("\n## Executable Acceptance Scenarios")
    for s in stories_consulted:
        brief_lines.append(f"- **{s.id}**: {s.title}")
        brief_lines.extend(f"  - Scenario: {sc}" for sc in s.scenarios)

    return SpecConsultationReport(
        task_id=task.canonical_id,
        task_title=task.title,
        target_bc=task.target_bc or "core",
        adrs=adrs_consulted,
        prds=prds_consulted,
        stories=stories_consulted,
        brief="\n".join(brief_lines),
    )


def conduct_peer_consultation(
    task: Task,
    worktree_dir: Path,
    repo_root: Path,
    check_git: bool = True,
    changed_files: list[str] | None = None,
) -> PeerConsultationReview:
    """Performs peer review on bounded context seams and active ADR compliance."""
    seams: list[str] = []
    adrs: list[str] = []
    feedback: list[str] = []

    files = list(changed_files) if changed_files is not None else []
    if not files and check_git and (worktree_dir / ".git").exists():
        try:
            res = subprocess.run(["git", "status", "--porcelain"], cwd=worktree_dir, capture_output=True, text=True, check=False)
            files.extend(line.strip().split(maxsplit=1)[1].strip() for line in res.stdout.splitlines() if len(line.strip().split(maxsplit=1)) == 2)
        except Exception:
            pass

    target_bc = (task.target_bc or "core").strip().lower()

    for rel in files:
        rel_norm = rel.replace("\\", "/")
        full_path = worktree_dir / rel_norm
        if rel_norm.startswith("docs/project/backlog/"):
            adrs.append(f"ADR-0005: Forbidden backlog modification on feature branch: {rel_norm}")
            feedback.append(f"Discard changes to {rel_norm}. Backlog files must not be touched on task branches.")
        if rel_norm.startswith("src/spec_ops/"):
            parts = rel_norm[len("src/spec_ops/"):].split("/")
            if parts and parts[0] not in ("core", "config", "cli", target_bc, "__init__.py"):
                seams.append(f"Boundary seam crossing: file '{rel_norm}' belongs to '{parts[0]}' BC while task targets '{target_bc}'")
                feedback.append(f"Review interface contract between '{target_bc}' and '{parts[0]}'.")
        if full_path.is_file() and full_path.suffix == ".py":
            try:
                cnt = full_path.read_text(encoding="utf-8", errors="ignore")
                lines = len(cnt.splitlines())
                if lines >= 500:
                    adrs.append(f"ADR-0002: File length violation: {rel_norm} has {lines} lines (limit: 500)")
                    feedback.append(f"Decompose {rel_norm} (<500 lines).")
                elif lines >= 400:
                    feedback.append(f"Warning: {rel_norm} has {lines} lines (>=400 lines threshold).")
                if "test" in rel_norm:
                    if any(m in cnt for m in ("unittest.mock", "from unittest import mock", "MagicMock")):
                        adrs.append(f"ADR-0003: Mock backdoor in {rel_norm}")
                        feedback.append(f"Replace mocks in {rel_norm} with blackbox frontdoors.")
                    if re.search(r"\._[a-zA-Z0-9_]+(?:\(|$)", cnt):
                        adrs.append(f"ADR-0003: Private internal access in {rel_norm}")
                        feedback.append(f"Exercise public contracts in {rel_norm}.")
                if re.search(r"(?:api_key|secret_key|private_key|token|password)\s*=\s*['\"][A-Za-z0-9_\-]{16,}['\"]", cnt, re.IGNORECASE):
                    adrs.append(f"ADR-0010: Hardcoded secret in {rel_norm}")
                    feedback.append(f"Remove hardcoded secrets from {rel_norm}.")
            except Exception:
                pass

    approved = (len(seams) == 0 and len(adrs) == 0)
    summary = "Peer review approved." if approved else f"Peer review detected {len(seams)} seam issues and {len(adrs)} ADR violations."
    return PeerConsultationReview(approved=approved, seam_violations=seams, adr_violations=adrs, feedback=feedback, summary=summary)


class WorkerOrchestrator:
    """Drives multi-agent in-worktree execution loop with active spec consultation, peer review, and AST healing."""

    def __init__(self, config: SpecOpsConfig, max_attempts: int = 3, peer_review: bool = True, dry_run: bool = False):
        self.config = config
        self.repo_root = config.root_dir
        self.max_attempts = max(1, max_attempts)
        self.peer_review = peer_review
        self.dry_run = dry_run

    def resolve_target_task(self, task_id: str | None = None) -> Task | None:
        from ..backlog.queue import BacklogQueue
        queue = BacklogQueue(self.config.backlog_dir)
        all_tasks = queue.list_all_tasks()
        if task_id:
            raw = task_id.upper().strip()
            num = _extract_digits(raw)
            for t in all_tasks:
                if t.canonical_id == raw or (num and _extract_digits(t.canonical_id) == num):
                    return t
            return None
        ready = queue.get_ready_unblocked_tasks()
        return ready[0] if ready else None

    def orchestrate(self, task_id: str | None = None, worktree_dir: Path | None = None) -> WorkerOrchestrationReport:
        task = self.resolve_target_task(task_id)
        if not task:
            return WorkerOrchestrationReport(
                task_id=task_id or "UNKNOWN",
                success=False,
                attempts=0,
                max_attempts=self.max_attempts,
                preflight_passed=False,
                peer_review_passed=False,
                message=f"Task {task_id or 'next ready'} not found in backlog queue.",
            )

        wt_dir = worktree_dir or (self.repo_root / ".worktrees" / f"task-{_extract_digits(task.canonical_id).zfill(4)}")
        if not wt_dir.exists() and (self.repo_root / "src").exists():
            wt_dir = self.repo_root

        consultation = consult_specifications(task, self.repo_root)
        try:
            (wt_dir / ".spec-consultation.md").write_text(consultation.brief, encoding="utf-8")
        except Exception:
            pass

        from .commits import build_commit_trailers
        trailers = build_commit_trailers(task)

        if self.dry_run:
            return WorkerOrchestrationReport(
                task_id=task.canonical_id,
                success=True,
                attempts=1,
                max_attempts=self.max_attempts,
                preflight_passed=True,
                peer_review_passed=True,
                specs_consulted=consultation,
                trailers=trailers,
                message=f"Dry-run: Orchestration simulated for {task.canonical_id}. Specs consulted and trailers verified.",
            )

        from .ast_analyzer import format_preflight_ast_feedback
        from .preflight import run_worktree_preflight
        from ..backlog.worker import BacklogWorkerEngine

        engine = BacklogWorkerEngine(self.config)
        attempts_history: list[OrchestrationAttempt] = []
        preflight_ok, peer_ok = False, False
        commit_hash = ""

        for attempt in range(1, self.max_attempts + 1):
            peer_res = conduct_peer_consultation(task, wt_dir, self.repo_root) if self.peer_review else PeerConsultationReview(approved=True, summary="Peer review disabled.")
            peer_ok = peer_res.approved
            preflight_ok, preflight_log = run_worktree_preflight(self.config, wt_dir, task=task)

            attempt_feedback: list[str] = []
            if not preflight_ok:
                attempt_feedback.append(format_preflight_ast_feedback(preflight_log, attempt, wt_dir))
            if not peer_ok:
                attempt_feedback.extend(peer_res.feedback)

            full_feedback = "\n\n".join(attempt_feedback)
            attempts_history.append(OrchestrationAttempt(attempt, preflight_ok, peer_ok, full_feedback, preflight_log))

            if preflight_ok and peer_ok:
                c_ok, _ = engine.prepare_commit(wt_dir, task=task)
                if c_ok:
                    try:
                        h_res = subprocess.run(["git", "rev-parse", "HEAD"], cwd=wt_dir, capture_output=True, text=True, check=False)
                        commit_hash = h_res.stdout.strip()
                    except Exception:
                        commit_hash = "HEAD"
                return WorkerOrchestrationReport(
                    task_id=task.canonical_id,
                    success=True,
                    attempts=attempt,
                    max_attempts=self.max_attempts,
                    preflight_passed=True,
                    peer_review_passed=True,
                    specs_consulted=consultation,
                    commit_hash=commit_hash,
                    trailers=trailers,
                    message=f"Task {task.canonical_id} orchestrated successfully on attempt {attempt}.",
                    attempt_history=attempts_history,
                )

        return WorkerOrchestrationReport(
            task_id=task.canonical_id,
            success=False,
            attempts=self.max_attempts,
            max_attempts=self.max_attempts,
            preflight_passed=preflight_ok,
            peer_review_passed=peer_ok,
            specs_consulted=consultation,
            trailers=trailers,
            message=f"Task {task.canonical_id} failed after {self.max_attempts} attempts.",
            attempt_history=attempts_history,
        )
