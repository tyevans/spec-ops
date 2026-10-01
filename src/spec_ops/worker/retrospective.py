"""Continuous orchestration retrospective and self-healing engine (ADR-0020, US-0117)."""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

INVARIANT_PATTERNS: dict[str, dict[str, Any]] = {
    "ADR-0003": {
        "category": "Mock backdoors / private internal tampering",
        "regex": re.compile(
            r"\bADR-0003\b|mock\b|monkeypatch\b|patch\.object|unittest\.mock|pytest_mock|mocker\.patch|MagicMock|prohibited_mock|mock backdoor",
            re.I,
        ),
        "mandate": "You must strictly use public frontdoor entrypoints with zero mock backdoors.",
        "governing_adrs": ["ADR-0003", "ADR-0020"],
        "governing_prds": ["PRD-0001", "PRD-0006"],
    },
    "ADR-0002": {
        "category": "File length limit violations",
        "regex": re.compile(r"\bADR-0002\b|file length|500 lines|400 lines|exceeds? (?:file )?limit|lines > limit 500", re.I),
        "mandate": "You must decompose source files to stay strictly under 500 lines (and warn at >=400 lines) with single-responsibility modules.",
        "governing_adrs": ["ADR-0002", "ADR-0020"],
        "governing_prds": ["PRD-0001", "PRD-0006"],
    },
    "ADR-0019": {
        "category": "Diff secret / high-entropy credential scanner triggers",
        "regex": re.compile(r"\bADR-0019\b|secret(?:s)?\b|credential(?:s)?\b|high-entropy|api[-_ ]key|token leak|Exposed secrets", re.I),
        "mandate": "You must never hardcode credentials, secrets, or high-entropy tokens.",
        "governing_adrs": ["ADR-0019", "ADR-0020"],
        "governing_prds": ["PRD-0001", "PRD-0006"],
    },
    "ADR-0018": {
        "category": "Unstaged dependency lockfile drifts",
        "regex": re.compile(r"\bADR-0018\b|lockfile|uv\.lock|package-lock\.json|dependency drift|lockfile mutation", re.I),
        "mandate": "You must not edit lockfiles or dependencies without explicit authorization.",
        "governing_adrs": ["ADR-0018", "ADR-0020"],
        "governing_prds": ["PRD-0001", "PRD-0006"],
    },
    "ADR-0017": {
        "category": "DAG dependency cycle deadlocks",
        "regex": re.compile(r"\bADR-0017\b|dependency cycle|deadlock\b|circular dependency|tarjan|cycle detected", re.I),
        "mandate": "You must break DAG dependency cycles and maintain a strict acyclic task dependency graph.",
        "governing_adrs": ["ADR-0017", "ADR-0020"],
        "governing_prds": ["PRD-0001", "PRD-0006"],
    },
}

GENERIC_FALLBACK: dict[str, Any] = {
    "invariant_id": "ADR-0020",
    "category": "Generic orchestration failure",
    "mandate": "You must avoid repeating the described failure pattern and strictly adhere to project invariants.",
    "governing_adrs": ["ADR-0020"],
    "governing_prds": ["PRD-0001", "PRD-0006"],
}


@dataclass
class FailurePattern:
    invariant_id: str
    category: str
    mandate: str
    governing_adrs: list[str] = field(default_factory=list)
    governing_prds: list[str] = field(default_factory=list)
    matched_text: str = ""
    source_file: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class OrchestrationHealthSummary:
    total_attempts: int = 0
    passed_attempts: int = 0
    failed_attempts: int = 0
    pass_rate: float = 100.0
    active_worktrees: list[dict[str, Any]] = field(default_factory=list)
    stalled_worktrees: list[dict[str, Any]] = field(default_factory=list)
    unaddressed_bugs: list[dict[str, Any]] = field(default_factory=list)
    is_healthy: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def classify_failure(log_text: str) -> list[FailurePattern]:
    """Deterministically classifies error log text into detected invariant breaches or fallback."""
    text = str(log_text) if not isinstance(log_text, str) else log_text
    detected: list[FailurePattern] = []

    for inv_id, info in INVARIANT_PATTERNS.items():
        if info["regex"].search(text):
            detected.append(
                FailurePattern(
                    invariant_id=inv_id,
                    category=info["category"],
                    mandate=info["mandate"],
                    governing_adrs=list(info["governing_adrs"]),
                    governing_prds=list(info["governing_prds"]),
                    matched_text=text[:300].strip(),
                )
            )

    if not detected:
        detected.append(
            FailurePattern(
                invariant_id=GENERIC_FALLBACK["invariant_id"],
                category=GENERIC_FALLBACK["category"],
                mandate=GENERIC_FALLBACK["mandate"],
                governing_adrs=list(GENERIC_FALLBACK["governing_adrs"]),
                governing_prds=list(GENERIC_FALLBACK["governing_prds"]),
                matched_text=text[:300].strip(),
            )
        )
    return detected


def _get_next_task_number(backlog_dir: Path) -> int:
    max_id = 0
    if backlog_dir.exists():
        for p in backlog_dir.rglob("*.md"):
            m = re.match(r"^(\d+)", p.stem)
            if m:
                max_id = max(max_id, int(m.group(1)))
    p_file = backlog_dir / "PRIORITY.md"
    if p_file.is_file():
        content = p_file.read_text(encoding="utf-8", errors="ignore")
        for m in re.finditer(r"TASK-(\d+)", content):
            max_id = max(max_id, int(m.group(1)))
    return max_id + 1


def _slugify(text: str) -> str:
    cleaned = re.sub(r"[^\w\s-]", "", text.lower())
    slug = re.sub(r"[\s_]+", "-", cleaned).strip("-")
    return re.sub(r"-+", "-", slug)[:40] or "task"


def synthesize_remediation_task(
    pattern: FailurePattern,
    backlog_dir: Path,
    dry_run: bool = False,
    next_task_id: int | None = None,
) -> tuple[Path | None, dict[str, Any]]:
    """Synthesizes a PMaC proposed remediation task with losslessly hydrated ADR-0020 frontmatter."""
    num = next_task_id if next_task_id is not None else _get_next_task_number(backlog_dir)
    tid = f"{num:04d}"
    canonical_id = f"TASK-{tid}"
    title = f"Remediate {pattern.invariant_id} violation: {pattern.category}"
    slug = f"{tid}-remediate-{pattern.invariant_id.lower()}-{_slugify(pattern.category)}"
    proposed_dir = backlog_dir / "proposed"
    target_file = proposed_dir / f"{slug}.md"

    now = datetime.now(timezone.utc)
    reason = pattern.matched_text.splitlines()[0][:120] if pattern.matched_text else f"{pattern.category} in preflight"

    frontmatter_dict: dict[str, Any] = {
        "id": tid,
        "title": title,
        "status": "Proposed",
        "governing_adrs": pattern.governing_adrs,
        "governing_prds": pattern.governing_prds,
        "governing_stories": ["US-0117"],
        "target_bc": "worker",
        "failure_history": [
            {
                "attempt_date": now.strftime("%Y-%m-%d"),
                "timestamp": now.isoformat(),
                "reason": reason,
                "failed_invariants": [pattern.invariant_id],
                "negative_prompt_guidance": pattern.mandate,
            }
        ],
    }

    body = (
        f"# {canonical_id}: {title}\n\n"
        f"## Summary\n"
        f"Autonomous remediation task synthesized by retrospective engine (AGENTS.md, ADR-0020).\n\n"
        f"## Prior Attempt Failures & Anti-Patterns (DO NOT REPEAT)\n"
        f"- Previous failure: {reason}.\n"
        f"- Mandate: {pattern.mandate}\n\n"
        f"## Problem Statement & Context\n"
        f"Preflight invariant breach: {pattern.invariant_id} ({pattern.category}).\n"
        f"Source: {pattern.source_file or 'Worktree preflight'}\n\n"
        f"```text\n{pattern.matched_text}\n```\n\n"
        f"## Key Requirements & Scope\n"
        f"1. Eliminate root cause of {pattern.invariant_id} breach.\n"
        f"2. Adhere strictly to: {pattern.mandate}\n"
        f"3. Validate exclusively via blackbox frontdoors without mock backdoors.\n"
    )

    yaml_block = yaml.dump(frontmatter_dict, sort_keys=False, default_flow_style=False, allow_unicode=True).strip()
    full_content = f"---\n{yaml_block}\n---\n\n{body}"

    if not dry_run:
        proposed_dir.mkdir(parents=True, exist_ok=True)
        target_file.write_text(full_content, encoding="utf-8")

    return target_file if not dry_run else None, frontmatter_dict


def scan_failure_logs(
    target_dir: Path | None = None,
    repo_root: Path | None = None,
) -> list[FailurePattern]:
    """Scans worktree directories, failure logs, and security audit logs for invariant breaches."""
    results: list[FailurePattern] = []
    base_dirs: list[Path] = []
    if target_dir and target_dir.exists():
        base_dirs.append(target_dir)
    elif repo_root and (repo_root / ".worktrees").exists():
        base_dirs.append(repo_root / ".worktrees")

    for base in base_dirs:
        candidates = list(base.glob("*.log")) + list(base.glob("*.json"))
        for p in base.iterdir():
            if p.is_dir():
                candidates.extend([p / ".security-audit.log", p / ".failure.log", p / "HANDOVER.md", p / ".task-prompt.md", p / ".worker.json"])

        for candidate in candidates:
            if not candidate.is_file():
                continue
            text = candidate.read_text(encoding="utf-8", errors="ignore").strip()
            if not text:
                continue

            log_extract = text
            if "## Preflight Failure Feedback" in text:
                log_extract = text.split("## Preflight Failure Feedback")[-1].strip()
            elif "## Exact Failure Log" in text:
                m = re.search(r"## Exact Failure Log\s*```(?:text)?\s*(.+?)\s*```", text, re.DOTALL)
                if m:
                    log_extract = m.group(1).strip()
            elif candidate.suffix == ".json":
                try:
                    data = json.loads(text)
                    log_extract = data.get("failure_log") or data.get("error") or ""
                    if not log_extract and data.get("status") in ("Failed", "Stalled"):
                        log_extract = f"Task failed with status: {data.get('status')}"
                except Exception:
                    log_extract = ""

            if not log_extract:
                continue

            for pat in classify_failure(log_extract):
                pat.source_file = str(candidate)
                if not any(r.invariant_id == pat.invariant_id and r.source_file == pat.source_file for r in results):
                    results.append(pat)

    return results


def run_retrospective(
    backlog_dir: Path,
    log_dir: Path | None = None,
    repo_root: Path | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Runs end-to-end failure pattern detection and remediation task synthesis."""
    patterns = scan_failure_logs(target_dir=log_dir, repo_root=repo_root)
    created_tasks: list[str] = []
    task_details: list[dict[str, Any]] = []

    current_next_id = _get_next_task_number(backlog_dir)
    seen_invariants: set[str] = set()

    for pat in patterns:
        if pat.invariant_id in seen_invariants:
            continue
        seen_invariants.add(pat.invariant_id)

        task_path, meta = synthesize_remediation_task(
            pat, backlog_dir, dry_run=dry_run, next_task_id=current_next_id
        )
        current_next_id += 1
        tid = f"TASK-{meta['id']}"
        created_tasks.append(tid)
        task_details.append(
            {
                "task_id": tid,
                "invariant_id": pat.invariant_id,
                "category": pat.category,
                "mandate": pat.mandate,
                "source": pat.source_file,
                "file": str(task_path) if task_path else None,
                "dry_run": dry_run,
            }
        )

    return {
        "success": True,
        "failures_detected": [p.to_dict() for p in patterns],
        "tasks_scaffolded": created_tasks,
        "details": task_details,
        "dry_run": dry_run,
    }


def get_orchestration_health(
    repo_root: Path | None = None,
    log_dir: Path | None = None,
) -> OrchestrationHealthSummary:
    """Calculates orchestration health summary, pass/fail rates, stalled worktrees, and bugs."""
    root = repo_root or Path.cwd()
    wt_dir = log_dir if (log_dir and log_dir.is_dir()) else (root / ".worktrees")
    backlog_dir = root / "docs" / "project" / "backlog"

    active_wt: list[dict[str, Any]] = []
    stalled_wt: list[dict[str, Any]] = []
    passed = 0
    failed = 0

    if wt_dir.exists():
        for p in sorted(wt_dir.iterdir()):
            if not p.is_dir():
                continue
            name = p.name
            stalled = False
            status = "Executing"
            reason = ""

            worker_json = p / ".worker.json"
            if worker_json.exists():
                try:
                    wdata = json.loads(worker_json.read_text(encoding="utf-8"))
                    status = wdata.get("status", status)
                    stalled = bool(wdata.get("stalled", False)) or status in ("Failed", "Stalled")
                    reason = wdata.get("failure_log", "")
                except Exception:
                    pass

            prompt_file = p / ".task-prompt.md"
            if prompt_file.exists():
                text = prompt_file.read_text(encoding="utf-8", errors="ignore")
                if "## Preflight Failure Feedback" in text or "stalled" in text.lower():
                    stalled = True
                    reason = reason or "Preflight failure feedback detected"

            if (p / ".failure.log").exists() or (p / "HANDOVER.md").exists():
                stalled = True
                reason = reason or "Failure or handover artifact present"

            record = {"name": name, "path": str(p), "status": status, "reason": reason[:100]}
            if stalled:
                stalled_wt.append(record)
                failed += 1
            else:
                active_wt.append(record)
                passed += 1

    unaddressed_bugs: list[dict[str, Any]] = []
    proposed_dir = backlog_dir / "proposed"
    if proposed_dir.exists():
        for f in sorted(proposed_dir.glob("*.md")):
            content = f.read_text(encoding="utf-8", errors="ignore")
            if "failure_history" in content or "Remediate" in content:
                m_title = re.search(r"title:\s*(.+)", content)
                m_id = re.search(r"id:\s*['\"]?(\d+)['\"]?", content)
                m_inv = re.search(r"failed_invariants:\s*\n\s*-\s*(ADR-\d+)", content)
                tid = f"TASK-{m_id.group(1).zfill(4)}" if m_id else f.stem
                title = m_title.group(1).strip("'\"") if m_title else f.stem
                inv = m_inv.group(1) if m_inv else "ADR-0020"
                unaddressed_bugs.append({"task_id": tid, "title": title, "status": "Proposed", "invariant_id": inv})

    total = passed + failed
    pass_rate = round((passed / total * 100.0), 1) if total > 0 else 100.0
    is_healthy = len(stalled_wt) == 0 and len(unaddressed_bugs) == 0 and pass_rate >= 80.0

    return OrchestrationHealthSummary(
        total_attempts=total,
        passed_attempts=passed,
        failed_attempts=failed,
        pass_rate=pass_rate,
        active_worktrees=active_wt,
        stalled_worktrees=stalled_wt,
        unaddressed_bugs=unaddressed_bugs,
        is_healthy=is_healthy,
    )
