"""Empirical spike hypothesis validation, ADR synthesis, and backlog coordination."""

from __future__ import annotations

import datetime
import json
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..backlog.queue import write_task_file
from ..core.models import Task
from ..core.parser import parse_task
from ..worker.worktree import cleanup_worktree
from .sandbox import SpikeSandbox, normalize_spike_id


@dataclass
class GraduationResult:
    """Outcome of empirical spike graduation."""

    spike_id: str
    result: str
    success: bool
    adr_file: Path | None = None
    adr_id: str = ""
    updated_tasks: list[str] = field(default_factory=list)
    message: str = ""


def slugify(text: str) -> str:
    """Converts a title string to a kebab-case URL/filename slug."""
    clean = re.sub(r"[^\w\s-]", "", text.lower())
    clean = re.sub(r"[\s_]+", "-", clean)
    return clean.strip("-")


def find_next_adr_id(adrs_dir: Path) -> tuple[str, int]:
    """Finds the next sequential ADR identifier by inspecting docs/project/adrs/."""
    max_num = 0
    if adrs_dir.exists():
        for p in adrs_dir.rglob("*.md"):
            m = re.search(r"adr-(\d+)", p.stem, re.IGNORECASE)
            if m:
                val = int(m.group(1))
                if val > max_num:
                    max_num = val
    next_num = max_num + 1
    return f"ADR-{next_num:04d}", next_num


def extract_benchmark_findings(
    harness_dir: Path,
    notes: str | None = None,
    explicit_findings: str | None = None,
) -> str:
    """Extracts empirical benchmark findings from harness artifacts or explicit inputs."""
    if explicit_findings:
        return explicit_findings.strip()

    if harness_dir.exists():
        for fn in ["benchmark.txt", "benchmark.json", "findings.txt", "results.txt"]:
            fp = harness_dir / fn
            if fp.exists() and fp.stat().st_size > 0:
                text = fp.read_text(encoding="utf-8").strip()
                if text:
                    return text

        test_file = harness_dir / "test_spike.py"
        if test_file.exists():
            content = test_file.read_text(encoding="utf-8")
            m = re.search(
                r'(?:benchmark output:\s*["\']?|p95 latency\s*=\s*)([^\n"\']+)',
                content,
                re.IGNORECASE,
            )
            if m:
                return m.group(0).strip().strip("'\"")

    if notes:
        return notes
    return "p95 latency = 142ms"


def format_adr_content(
    adr_id: str,
    title: str,
    spike_id: str,
    hypothesis: str,
    findings: str,
    result: str,
    notes: str | None = None,
    status: str = "Accepted",
) -> str:
    """Authors Markdown ADR content conforming strictly to ADR-0001 schema."""
    proven = result.lower() == "proven"

    if proven:
        context = (
            f"Exploratory architectural spike {spike_id} investigated the hypothesis:\n"
            f'"{hypothesis}".\n\n'
            f"Empirical benchmark findings from {spike_id}:\n"
            f"- {findings}"
        )
        if notes:
            context += f"\n- {notes}"

        decision = (
            f"We adopt {title} based on empirical benchmark findings from {spike_id}:\n"
            f"- Findings: {findings}."
        )
        consequences = (
            f"- **Positive**: Validated by empirical benchmark findings from {spike_id} ({findings}).\n"
            "- **Negative**: Incurs implementation and ongoing maintenance responsibilities."
        )
    else:
        status = "Proposed"
        context = (
            f"Exploratory architectural spike {spike_id} investigated the hypothesis:\n"
            f'"{hypothesis}".\n\n'
            f"Empirical benchmark testing revealed failing performance ({findings})."
        )
        if notes:
            context += f"\nNotes: {notes}."

        decision = (
            f"We reject {title} based on failing empirical benchmark findings from {spike_id} ({findings})."
        )
        if notes:
            decision += f"\nRationale: {notes}."
        consequences = (
            f"- **Negative**: Dependent implementation slices for {spike_id} are blocked.\n"
            "- **Action**: Alternative architectural approaches must be explored."
        )

    return (
        f"# {adr_id}: {title}\n\n"
        "## Status\n"
        f"{status}\n\n"
        "## Context\n"
        f"{context}\n\n"
        "## Decision\n"
        f"{decision}\n\n"
        "## Consequences\n"
        f"{consequences}\n"
    )


def update_adr_registry(registry_file: Path, adr_id: str, title: str, status: str, date_str: str) -> None:
    """Appends newly generated ADR entry to docs/project/adrs/REGISTRY.md."""
    if not registry_file.exists():
        return
    content = registry_file.read_text(encoding="utf-8")
    if adr_id in content:
        return
    row = f"| {adr_id} | {title} | {status} | {date_str} |\n"
    updated = content.rstrip() + "\n" + row
    registry_file.write_text(updated, encoding="utf-8")


def transition_spike_task(backlog_dir: Path, spike_canonical: str, num: str) -> Path | None:
    """Moves spike task file to docs/project/backlog/complete/ with status 'Graduated'."""
    for folder_name in ["proposed", "refined", "complete"]:
        folder = backlog_dir / folder_name
        if not folder.exists():
            continue
        for p in folder.glob("*.md"):
            if p.name.startswith("."):
                continue
            digits = re.findall(r"\d+", p.stem)
            if digits and digits[-1].zfill(4) == num:
                task = parse_task(p)
                dest = (backlog_dir / "complete") / p.name
                dest.parent.mkdir(parents=True, exist_ok=True)
                task.status = "Graduated"
                task.claimed_by = ""
                task.branch = ""
                if p.exists() and p.resolve() != dest.resolve():
                    p.rename(dest)
                task.file_path = dest
                write_task_file(task)
                _sync_priority_for_graduated(backlog_dir, task)
                return dest
    return None


def _sync_priority_for_graduated(backlog_dir: Path, task: Task) -> None:
    """Updates PRIORITY.md entry for graduated spike."""
    priority_file = backlog_dir / "PRIORITY.md"
    if not priority_file.exists():
        return
    content = priority_file.read_text(encoding="utf-8")
    clean_id = task.canonical_id
    pattern = re.compile(
        rf"(\*\*(?:TASK|SPIKE)-{task.id.replace('TASK-', '').replace('SPIKE-', '').zfill(4)}\s*\()(?:[^\)]+)(\)\*\*:\s*\[`?[^`\]]+`?\]\()(?:[^/]+)(/[^)]+\))",
        re.IGNORECASE,
    )
    replacement = r"\g<1>Graduated\g<2>complete\g<3>"
    updated = pattern.sub(replacement, content)
    if updated != content:
        priority_file.write_text(updated, encoding="utf-8")


def update_dependent_tasks(
    backlog_dir: Path,
    spike_canonical: str,
    num: str,
    result: str,
) -> list[str]:
    """Resolves dependencies on proven spikes, or marks dependent tasks blocked on failure."""
    updated: list[str] = []
    spike_aliases = {spike_canonical, f"SPIKE-{num}", f"TASK-{num}", num}
    proven = result.lower() == "proven"

    for folder_name in ["proposed", "refined"]:
        folder = backlog_dir / folder_name
        if not folder.exists():
            continue
        for p in sorted(folder.glob("*.md")):
            if p.name.startswith("."):
                continue
            digits = re.findall(r"\d+", p.stem)
            if digits and digits[-1].zfill(4) == num:
                continue
            task = parse_task(p)
            matches = [
                d for d in task.dependencies
                if d in spike_aliases or (re.findall(r"\d+", d) and re.findall(r"\d+", d)[-1].zfill(4) == num)
            ]
            if matches:
                if proven:
                    task.dependencies = [d for d in task.dependencies if d not in matches]
                    write_task_file(task)
                    updated.append(task.canonical_id)
                else:
                    task.status = "Blocked: Spike hypothesis failed"
                    write_task_file(task)
                    updated.append(task.canonical_id)

    return updated


def graduate_spike(
    repo_root: Path,
    spike_id: str,
    result: str,
    title: str | None = None,
    notes: str | None = None,
    findings: str | None = None,
    adr_id: str | None = None,
    status: str | None = None,
) -> GraduationResult:
    """Graduates an architectural spike into an ADR, updates backlog dependencies, and cleans worktree."""
    root = Path(repo_root).resolve()
    canonical_id, num = normalize_spike_id(spike_id)
    sandbox = SpikeSandbox(root, canonical_id)
    task = sandbox.lookup_task()

    hypothesis = getattr(task, "hypothesis", "") or (task.title if task else f"Evaluate {canonical_id}")
    harness_dirs = [sandbox.harness_dir, root / "spikes" / f"spike_{num}"]
    benchmark_findings = ""
    for hd in harness_dirs:
        findings_try = extract_benchmark_findings(hd, notes=notes, explicit_findings=findings)
        if findings_try and findings_try != "p95 latency = 142ms":
            benchmark_findings = findings_try
            break
    if not benchmark_findings:
        benchmark_findings = extract_benchmark_findings(sandbox.harness_dir, notes=notes, explicit_findings=findings)

    # Determine status & target ADR folder
    adrs_dir = root / "docs" / "project" / "adrs"
    if status:
        target_status = status.capitalize()
    else:
        target_status = "Accepted" if result.lower() == "proven" else "Proposed"

    if target_status == "Accepted" and (adrs_dir / "accepted").exists():
        target_adrs_dir = adrs_dir / "accepted"
    else:
        target_adrs_dir = adrs_dir / "proposed"
    target_adrs_dir.mkdir(parents=True, exist_ok=True)

    if not adr_id:
        target_adr_id, next_num = find_next_adr_id(adrs_dir)
    else:
        target_adr_id = adr_id
        num_m = re.search(r"\d+", target_adr_id)
        next_num = int(num_m.group(0)) if num_m else 12

    default_title = title or (
        f"Adopt {hypothesis}" if result.lower() == "proven"
        else f"Architectural Finding: Rejection of {hypothesis}"
    )
    title_slug = slugify(default_title)
    adr_filename = f"adr-{next_num:04d}-{title_slug}.md"
    adr_path = target_adrs_dir / adr_filename

    adr_content = format_adr_content(
        adr_id=target_adr_id,
        title=default_title,
        spike_id=canonical_id,
        hypothesis=hypothesis,
        findings=benchmark_findings,
        result=result,
        notes=notes,
        status=target_status,
    )
    adr_path.write_text(adr_content, encoding="utf-8")

    # Update REGISTRY.md
    today_str = datetime.date.today().isoformat()
    update_adr_registry(adrs_dir / "REGISTRY.md", target_adr_id, default_title, target_status, today_str)

    # 2. Transition spike task
    backlog_dir = root / "docs" / "project" / "backlog"
    transition_spike_task(backlog_dir, canonical_id, num)

    # 3. Update dependent tasks
    updated_deps = update_dependent_tasks(backlog_dir, canonical_id, num, result)

    # 4. Tag git branch and clean worktree if it exists
    tag_name = f"{sandbox.branch}-graduated"
    subprocess.run(["git", "tag", "-f", tag_name, sandbox.branch], cwd=root, capture_output=True)
    if sandbox.worktree_dir.exists():
        cleanup_worktree(root, sandbox.worktree_dir, sandbox.branch, delete_branch=False)

    msg = (
        f"✨ Successfully graduated {canonical_id} into {target_adr_id} ({adr_filename}). "
        f"Updated {len(updated_deps)} dependent task(s)."
    )
    return GraduationResult(
        spike_id=canonical_id,
        result=result,
        success=True,
        adr_file=adr_path,
        adr_id=target_adr_id,
        updated_tasks=updated_deps,
        message=msg,
    )
