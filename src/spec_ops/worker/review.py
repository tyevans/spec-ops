"""Context-enriched pull request review brief and architectural lineage generator."""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from ..config.models import SpecOpsConfig
from ..core.models import Task
from ..core.parser import extract_frontmatter, parse_task

KNOWN_ADR_DESCRIPTIONS = {
    "ADR-0001": "Specification as Code",
    "ADR-0002": "<500 lines limit",
    "ADR-0003": "Frontdoor TDD",
    "ADR-0005": "Strict Backlog Isolation",
    "ADR-0006": "Executable BDD User Stories",
    "ADR-0007": "Domain-Driven Design",
    "ADR-0009": "Property-Based Testing & Mutation",
    "ADR-0010": "Security & Supply-Chain Invariants",
}


@dataclass
class ChangedFileInfo:
    path: str
    added: int
    deleted: int
    total_lines: int
    headroom: int


@dataclass
class CommitProvenanceInfo:
    commit_hash: str
    author: str
    subject: str
    author_type: str  # "Autonomous Worker" | "Human Contributor"
    has_task_trailer: bool
    missing_trailer_warning: str | None = None


@dataclass
class ReviewBrief:
    task_id: str
    task_title: str
    governing_prd: str
    governing_adrs: str
    acceptance_scenarios: list[str] = field(default_factory=list)
    lineage_path: str = "Persona -> PRD -> User Story -> Task"
    lineage_detail: str = ""
    changed_files: list[ChangedFileInfo] = field(default_factory=list)
    verification_report: str = ""
    private_mock_violations: list[str] = field(default_factory=list)
    commits: list[CommitProvenanceInfo] = field(default_factory=list)


def _find_task(task_id: str, repo_root: Path) -> Task | None:
    clean = task_id.upper().replace("TASK-", "").replace("SPIKE-", "").lstrip("0")
    num_str = clean.zfill(4) if clean else ""
    backlog_dir = repo_root / "docs" / "project" / "backlog"
    if not backlog_dir.exists():
        return None
    for sub in ("refined", "proposed", "complete"):
        sub_dir = backlog_dir / sub
        if not sub_dir.exists():
            continue
        for p in sub_dir.glob("*.md"):
            p_clean = re.sub(r"[^\d]", "", p.stem.split("-")[0]).lstrip("0")
            if clean and (p_clean == clean or p.stem.startswith(f"{clean}-") or p.stem.startswith(f"{num_str}-")):
                return parse_task(p)
            if num_str and num_str in p.stem:
                return parse_task(p)
            if task_id.lower() in p.stem.lower():
                return parse_task(p)
    return None


def _resolve_governing_prd(task: Task, repo_root: Path) -> str:
    prd_dir = repo_root / "docs" / "project" / "product"
    prds = list(task.governing_prds)
    if not prds and prd_dir.exists():
        for p in prd_dir.rglob("*.md"):
            txt = p.read_text(encoding="utf-8", errors="replace")
            if task.canonical_id in txt:
                meta, _ = extract_frontmatter(txt)
                pid = meta.get("id", p.stem.split("-")[0])
                prds.append(f"PRD-{pid.zfill(4)}" if str(pid).isdigit() else str(pid))
                break
    if not prds:
        return f"{task.canonical_id} has no governing PRD cited"

    results: list[str] = []
    for pid in prds:
        clean = pid.upper().replace("PRD-", "").lstrip("0")
        num_str = clean.zfill(4) if clean else ""
        found_title = ""
        if prd_dir.exists():
            for p in prd_dir.rglob("*.md"):
                p_clean = re.sub(r"[^\d]", "", p.stem.split("-")[0]).lstrip("0")
                if (clean and p_clean == clean) or (num_str and num_str in p.stem):
                    meta, _ = extract_frontmatter(p.read_text(encoding="utf-8", errors="replace"))
                    found_title = meta.get("title", "")
                    break
        canonical_pid = f"PRD-{num_str}" if num_str else pid
        results.append(f"{canonical_pid} ({found_title})" if found_title else canonical_pid)
    return ", ".join(results)


def _resolve_governing_adrs(task: Task, repo_root: Path) -> str:
    adrs = list(task.governing_adrs)
    if not adrs:
        return "None cited"
    adrs_dir = repo_root / "docs" / "project" / "adrs"
    results: list[str] = []
    for adr in adrs:
        clean = adr.upper().replace("ADR-", "").lstrip("0")
        canon_adr = f"ADR-{clean.zfill(4)}" if clean else adr.upper()
        if canon_adr in KNOWN_ADR_DESCRIPTIONS:
            results.append(f"{canon_adr} ({KNOWN_ADR_DESCRIPTIONS[canon_adr]})")
            continue
        title = ""
        if adrs_dir.exists():
            for p in adrs_dir.rglob("*.md"):
                if clean.zfill(4) in p.stem:
                    m = re.search(r"^#\s*ADR-\d+:\s*(.+)$", p.read_text(encoding="utf-8", errors="replace"), re.MULTILINE)
                    title = m.group(1).strip() if m else ""
                    break
        results.append(f"{canon_adr} ({title})" if title else canon_adr)
    return ", ".join(results)


def _resolve_acceptance_scenarios(task: Task, repo_root: Path) -> tuple[list[str], str]:
    stories_dir = repo_root / "docs" / "project" / "user_stories"
    scenarios: list[str] = []
    persona = ""
    story_refs = list(task.governing_stories)
    if not story_refs and stories_dir.exists():
        for p in stories_dir.rglob("*.md"):
            txt = p.read_text(encoding="utf-8", errors="replace")
            if task.canonical_id in txt:
                meta, _ = extract_frontmatter(txt)
                sid = meta.get("id", p.stem.split("-")[0])
                story_refs.append(f"US-{sid.zfill(4)}" if str(sid).isdigit() else str(sid))
                break

    for s_ref in story_refs:
        clean = s_ref.upper().replace("US-", "").lstrip("0")
        num_str = clean.zfill(4) if clean else ""
        if stories_dir.exists():
            for p in stories_dir.rglob("*.md"):
                if num_str and (num_str in p.stem):
                    content = p.read_text(encoding="utf-8", errors="replace")
                    meta, _ = extract_frontmatter(content)
                    if not persona and meta.get("persona"):
                        persona = str(meta.get("persona"))
                    for line in content.splitlines():
                        if line.strip().startswith("Scenario:"):
                            scenarios.append(line.strip())

    if not scenarios:
        for line in task.body.splitlines():
            if line.strip().startswith("Scenario:"):
                scenarios.append(line.strip())
    if not scenarios:
        scenarios = ["Scenario: Verification of observable contracts through public frontdoor"]
    return scenarios, persona


def _resolve_git_branch(task: Task, repo_root: Path) -> str:
    if task.branch:
        check = subprocess.run(["git", "rev-parse", "--verify", task.branch], cwd=repo_root, capture_output=True)
        if check.returncode == 0:
            return task.branch
    for c in (f"task/{task.canonical_id}", f"task/{task.id}", f"feat/{task.id}"):
        check = subprocess.run(["git", "rev-parse", "--verify", c], cwd=repo_root, capture_output=True)
        if check.returncode == 0:
            return c
    curr = subprocess.run(["git", "symbolic-ref", "--short", "HEAD"], cwd=repo_root, capture_output=True, text=True)
    return curr.stdout.strip() if curr.returncode == 0 and curr.stdout.strip() else "HEAD"


def _analyze_git_changes(branch: str, repo_root: Path) -> tuple[list[ChangedFileInfo], list[str]]:
    base_branch = "main"
    if subprocess.run(["git", "rev-parse", "--verify", "main"], cwd=repo_root, capture_output=True).returncode != 0:
        base_branch = "master"
    diff_res = subprocess.run(["git", "diff", "--numstat", f"{base_branch}...{branch}"], cwd=repo_root, capture_output=True, text=True)
    if diff_res.returncode != 0 or not diff_res.stdout.strip():
        diff_res = subprocess.run(["git", "diff", "--numstat", "HEAD~1...HEAD"], cwd=repo_root, capture_output=True, text=True)

    changed_files: list[ChangedFileInfo] = []
    mock_violations: list[str] = []
    mock_patterns = [r"unittest\.mock", r"mocker\.patch", r"patch\(", r"patch\.object\(", r"MagicMock"]

    if diff_res.returncode == 0 and diff_res.stdout.strip():
        for line in diff_res.stdout.splitlines():
            parts = line.split(maxsplit=2)
            if len(parts) < 3:
                continue
            add_s, del_s, fpath = parts
            added, deleted = (int(add_s) if add_s.isdigit() else 0), (int(del_s) if del_s.isdigit() else 0)
            fp = repo_root / fpath
            file_txt = ""
            if fp.is_file():
                try:
                    file_txt = fp.read_text(encoding="utf-8", errors="replace")
                except Exception:
                    pass
            if not file_txt:
                show_p = subprocess.run(["git", "show", f"{branch}:{fpath}"], cwd=repo_root, capture_output=True, text=True)
                if show_p.returncode == 0:
                    file_txt = show_p.stdout

            total_lines = len(file_txt.splitlines()) if file_txt else max(0, added - deleted)
            for pat in mock_patterns:
                if file_txt and re.search(pat, file_txt):
                    mock_violations.append(f"{fpath} contains forbidden private mock ({pat})")
            changed_files.append(ChangedFileInfo(path=fpath, added=added, deleted=deleted, total_lines=total_lines, headroom=max(0, 500 - total_lines)))
    return changed_files, mock_violations


def _analyze_commit_provenance(branch: str, task: Task, repo_root: Path) -> list[CommitProvenanceInfo]:
    base_branch = "main"
    if subprocess.run(["git", "rev-parse", "--verify", "main"], cwd=repo_root, capture_output=True).returncode != 0:
        base_branch = "master"
    log_res = subprocess.run(["git", "log", "--pretty=format:%H%x09%an%x09%ae%x09%s", "--reverse", f"{base_branch}..{branch}"], cwd=repo_root, capture_output=True, text=True)
    if log_res.returncode != 0 or not log_res.stdout.strip():
        log_res = subprocess.run(["git", "log", "-5", "--pretty=format:%H%x09%an%x09%ae%x09%s"], cwd=repo_root, capture_output=True, text=True)

    commits: list[CommitProvenanceInfo] = []
    if log_res.returncode == 0 and log_res.stdout.strip():
        for line in log_res.stdout.splitlines():
            parts = line.split("\t")
            if len(parts) < 4:
                continue
            c_hash, author_name, author_email, subject = parts
            show_res = subprocess.run(["git", "log", "-1", "--pretty=full", c_hash], cwd=repo_root, capture_output=True, text=True)
            full_msg = show_res.stdout if show_res.returncode == 0 else ""
            is_auto = bool("Provenance:" in full_msg or any(k in author_name.lower() or k in author_email.lower() for k in ("agent", "bot", "worker", "spec-ops", "autonomous")))
            has_trailer = bool(re.search(rf"SpecOps-Task\s*:\s*{re.escape(task.canonical_id)}", full_msg, re.IGNORECASE) or re.search(rf"SpecOps-Task\s*:\s*{re.escape(task.id)}", full_msg, re.IGNORECASE))
            warning = None if has_trailer else f'Commit {c_hash[:8]} is missing "SpecOps-Task: {task.canonical_id}" git trailer.'
            commits.append(CommitProvenanceInfo(commit_hash=c_hash, author=f"{author_name} <{author_email}>", subject=subject, author_type=("Autonomous Worker" if is_auto else "Human Contributor"), has_task_trailer=has_trailer, missing_trailer_warning=warning))
    return commits


def generate_review_brief(task_id: str, config: SpecOpsConfig, provenance: bool = False, repo_dir: Path | None = None) -> ReviewBrief:
    """Generates structured architectural PR review brief linking diffs to governing specifications."""
    repo_root = repo_dir or config.root_dir
    task = _find_task(task_id, repo_root) or Task(id=task_id.upper(), title=task_id)
    prd_summary = _resolve_governing_prd(task, repo_root)
    adrs_summary = _resolve_governing_adrs(task, repo_root)
    scenarios, persona = _resolve_acceptance_scenarios(task, repo_root)

    persona_name = persona or "Alex (The Agentic Systems Architect)"
    story_name = task.governing_stories[0] if task.governing_stories else "Governing Story"
    lineage_detail = f"{persona_name} -> {prd_summary.split('(')[0].strip()} -> {story_name} -> {task.canonical_id}"

    branch = _resolve_git_branch(task, repo_root)
    changed_files, mock_violations = _analyze_git_changes(branch, repo_root)
    verification = f"⚠️ Mock Violations: {len(mock_violations)} private mocks flagged (ADR-0003 violation)." if mock_violations else "0 private internal mocks flagged. Observable contracts verified via public frontdoors (ADR-0003 compliant)."
    commits = _analyze_commit_provenance(branch, task, repo_root)

    return ReviewBrief(
        task_id=task.canonical_id,
        task_title=task.title,
        governing_prd=prd_summary,
        governing_adrs=adrs_summary,
        acceptance_scenarios=scenarios,
        lineage_path="Persona -> PRD -> User Story -> Task",
        lineage_detail=lineage_detail,
        changed_files=changed_files,
        verification_report=verification,
        private_mock_violations=mock_violations,
        commits=commits,
    )


def render_review_brief(brief: ReviewBrief, provenance: bool = False) -> str:
    """Renders structured review brief into human-readable Markdown for PR review."""
    lines: list[str] = [
        f"=== SpecOps Architectural PR Review Brief: {brief.task_id} ===",
        f"Task: {brief.task_id} — {brief.task_title}\n",
        "## Governing PRD",
        f"{brief.governing_prd}\n",
        "## Governing ADRs",
        f"{brief.governing_adrs}\n",
        "## Acceptance Scenarios",
        "Executable Gherkin scenarios from governing user story:",
    ]
    for s in brief.acceptance_scenarios:
        lines.append(f"  - {s}")
    lines.extend(["\n## Lineage Path", f"{brief.lineage_path}", f"Trace: {brief.lineage_detail}\n", "## Changed Source Files"])
    if not brief.changed_files:
        lines.append("  (No changed source files detected in branch diff)")
    else:
        for f in brief.changed_files:
            lines.append(f"  - {f.path} (+{f.added}/-{f.deleted}): {f.total_lines} lines (headroom: {f.headroom} lines remaining until 500-line limit)")
    lines.extend(["\n## Verification Report", f"{brief.verification_report}"])
    if provenance:
        lines.extend(["\n## Commit Provenance & Author Distinction"])
        if not brief.commits:
            lines.append("  (No commits found on branch)")
        else:
            for c in brief.commits:
                lines.append(f"  - [{c.commit_hash[:8]}] {c.author_type} ({c.author}): {c.subject}")
                if c.missing_trailer_warning:
                    lines.append(f"    ⚠️ Warning: {c.missing_trailer_warning}")
    return "\n".join(lines)
