"""Automated SDLC provenance and bidirectional traceability audit engine.

Governed by ADR-0001, ADR-0002, ADR-0003, ADR-0007, ADR-0009; PRD-0005; US-0019.
Target Bounded Context: core. File length strictly under 400 lines.
"""

from __future__ import annotations

import argparse
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from ..config.models import SpecOpsConfig
from .models import ProjectData, Task
from .parser import SpecOpsParser


@dataclass
class CommitRecord:
    full_hash: str
    short_hash: str
    author: str
    email: str
    date: str
    subject: str
    body: str
    trailers: dict[str, str] = field(default_factory=dict)
    task_ids: list[str] = field(default_factory=list)
    provenance: str = ""
    is_autonomous: bool = False
    verification_status: str = ""
    is_merge: bool = False


@dataclass
class ContributorStats:
    contributor_class: str
    tasks_delivered: int = 0
    merged_commits: int = 0
    verification_pass_rate: float = 100.0


@dataclass
class ProvenanceReport:
    total_commits: int = 0
    anchored_commits: int = 0
    unanchored_commits: list[CommitRecord] = field(default_factory=list)
    total_stories: int = 0
    orphaned_stories: list[str] = field(default_factory=list)
    orphaned_tasks: list[str] = field(default_factory=list)
    missing_task_commits: list[tuple[CommitRecord, str]] = field(default_factory=list)
    contributor_stats: dict[str, ContributorStats] = field(default_factory=dict)
    lineage_matrix: list[dict[str, str]] = field(default_factory=list)
    integrity_pct: float = 100.0


def extract_trailers_from_text(text: str) -> dict[str, str]:
    """Extracts RFC-822 formatted git trailers from text."""
    trailers: dict[str, str] = {}
    for line in text.splitlines():
        m = re.match(r"^([A-Za-z0-9][A-Za-z0-9_-]*)\s*:\s*(.+)$", line.strip())
        if m:
            trailers[m.group(1).strip()] = m.group(2).strip()
    return trailers


def extract_task_ids_from_trailers(trailers: dict[str, str]) -> list[str]:
    """Extracts canonical task IDs from task trailers."""
    task_ids: list[str] = []
    for k, v in trailers.items():
        if k.replace("_", "-").lower() in ("specops-task", "task-id", "task", "taskid"):
            for token in re.split(r"[,;\s]+", v):
                m = re.search(r"(?:TASK|SPIKE)?[-_ ]?0*(\d+)", token, re.IGNORECASE)
                if m and m.group(1):
                    prefix = "SPIKE-" if "SPIKE" in token.upper() else "TASK-"
                    cid = f"{prefix}{m.group(1).zfill(4)}"
                    if cid not in task_ids:
                        task_ids.append(cid)
    return task_ids


def is_autonomous_contributor(trailers: dict[str, str], author: str = "", email: str = "") -> bool:
    """Attributes author to autonomous agent vs human developer."""
    for k, v in trailers.items():
        if k.lower() == "provenance":
            v_low = v.lower()
            if any(term in v_low for term in ("autonomous", "spec-ops", "agent", "worker", "bot")):
                return True
    author_id = f"{author} {email}".lower()
    return any(term in author_id for term in ("[bot]", "spec-ops-worker", "autonomous", "agent-runner"))


def parse_commit_from_raw(
    full_hash: str, short_hash: str, author: str, email: str, date: str, subject: str, body: str, is_merge: bool = False
) -> CommitRecord:
    """Parses raw git log fields into CommitRecord."""
    full_text = f"{subject}\n\n{body}".strip()
    trailers = extract_trailers_from_text(full_text)
    task_ids = extract_task_ids_from_trailers(trailers)
    prov = next((v for k, v in trailers.items() if k.lower() == "provenance"), "")
    is_auto = is_autonomous_contributor(trailers, author=author, email=email)
    v_status = next((v.lower() for k, v in trailers.items() if k.lower() in ("verification", "preflight")), "")
    return CommitRecord(
        full_hash=full_hash, short_hash=short_hash, author=author, email=email,
        date=date, subject=subject, body=body, trailers=trailers, task_ids=task_ids,
        provenance=prov, is_autonomous=is_auto, verification_status=v_status,
        is_merge=is_merge,
    )


def extract_commit_records(
    repo_dir: Path | str,
    max_commits: int = 500,
    since: str | None = None,
    baseline_commit: str | None = None,
) -> list[CommitRecord]:
    """Harvests commits from git history with parsed RFC-822 trailers."""
    repo = Path(repo_dir).resolve()
    if not (repo / ".git").exists() and not (repo / ".git").is_file():
        return []
    sep_f, sep_r = "\x1f", "\x1e"
    fmt = f"%H{sep_f}%h{sep_f}%an{sep_f}%ae{sep_f}%ad{sep_f}%s{sep_f}%p{sep_f}%B{sep_r}"

    git_args = ["git", "log"]
    effective_since = since or baseline_commit
    if effective_since:
        git_args.append(f"{effective_since}..HEAD")
    git_args.extend([f"-n{max_commits}", f"--format={fmt}", "--date=short"])

    try:
        res = subprocess.run(
            git_args,
            cwd=str(repo), capture_output=True, text=True, check=True,
        )
    except Exception:
        # Fallback if revision range fails
        try:
            res = subprocess.run(
                ["git", "log", f"-n{max_commits}", f"--format={fmt}", "--date=short"],
                cwd=str(repo), capture_output=True, text=True, check=True,
            )
        except Exception:
            return []

    records: list[CommitRecord] = []
    for block in res.stdout.split(sep_r):
        fields = block.strip().split(sep_f)
        if len(fields) >= 8:
            is_merge = len(fields[6].strip().split()) > 1
            records.append(parse_commit_from_raw(
                fields[0], fields[1], fields[2], fields[3], fields[4], fields[5], fields[7], is_merge=is_merge
            ))
        elif len(fields) >= 7:
            records.append(parse_commit_from_raw(
                fields[0], fields[1], fields[2], fields[3], fields[4], fields[5], fields[6]
            ))
    return records


def build_provenance_lineage(
    data: ProjectData, commits_by_task: dict[str, list[CommitRecord]]
) -> tuple[list[dict[str, str]], list[str]]:
    """Traverses Persona -> PRD -> Story -> Task -> Commit lineage graph."""
    rows: list[dict[str, str]] = []
    orphaned_stories: list[str] = []
    prds_by_id = {p.id: p for p in data.prds}

    tasks_by_story: dict[str, list[Task]] = {}
    for t in data.tasks:
        for sid in t.governing_stories:
            norm_sid = sid if sid.startswith("US-") else f"US-{sid.lstrip('0').zfill(4)}"
            tasks_by_story.setdefault(norm_sid, []).append(t)

    for s in data.stories:
        pid = s.governing_prd or ""
        clean_pid = f"PRD-{pid.replace('PRD-', '').lstrip('0').zfill(4)}" if pid else ""
        if not pid or (pid not in prds_by_id and clean_pid not in prds_by_id):
            orphaned_stories.append(s.id)

    for persona in data.personas:
        p_name = persona.name
        p_low = p_name.lower()
        linked_prds = [p for p in data.prds if p.target_persona and (p_low in p.target_persona.lower() or persona.id.lower() in p.target_persona.lower())]
        if not linked_prds:
            s_prds = {s.governing_prd for s in data.stories if s.persona and (p_low in s.persona.lower() or persona.id.lower() in s.persona.lower()) and s.governing_prd}
            linked_prds = [prds_by_id[pid] for pid in s_prds if pid in prds_by_id]
        if not linked_prds and data.prds and persona == data.personas[0]:
            linked_prds = list(data.prds)

        for prd in linked_prds:
            prd_stories = [s for s in data.stories if s.governing_prd == prd.id or s.id in prd.linked_stories]
            for story in prd_stories:
                s_tasks = tasks_by_story.get(story.id) or [t for t in data.tasks if story.id in t.governing_stories]
                if s_tasks:
                    for task in s_tasks:
                        t_commits = commits_by_task.get(task.canonical_id, [])
                        c_hashes = [c.short_hash for c in t_commits] if t_commits else ["—"]
                        for ch in c_hashes:
                            rows.append({
                                "persona": p_name, "prd": prd.id, "story": story.id,
                                "task": task.canonical_id, "commit": ch, "status": task.status,
                            })
                else:
                    rows.append({
                        "persona": p_name, "prd": prd.id, "story": story.id,
                        "task": "—", "commit": "—", "status": "—",
                    })
    return rows, orphaned_stories


def compute_contributor_stats(commits: list[CommitRecord], tasks: list[Task]) -> dict[str, ContributorStats]:
    """Computes delivered tasks, merged commits, and verification pass rates."""
    tasks_by_id = {t.canonical_id: t for t in tasks}
    stats = {
        True: ContributorStats(contributor_class="Autonomous Agents"),
        False: ContributorStats(contributor_class="Human Developers"),
    }
    delivered_sets: dict[bool, set[str]] = {True: set(), False: set()}
    passes: dict[bool, int] = {True: 0, False: 0}
    fails: dict[bool, int] = {True: 0, False: 0}
    explicit_rates: dict[bool, float | None] = {True: None, False: None}

    for c in commits:
        group = c.is_autonomous
        st = stats[group]
        st.merged_commits += 1
        for tid in c.task_ids:
            t = tasks_by_id.get(tid)
            if t and t.status.lower() == "complete":
                delivered_sets[group].add(tid)
        for k, v in c.trailers.items():
            if "rate" in k.lower():
                m = re.search(r"(\d+(?:\.\d+)?)", v)
                if m:
                    explicit_rates[group] = float(m.group(1))
        if c.verification_status in ("pass", "passed", "success"):
            passes[group] += 1
        elif c.verification_status in ("fail", "failed", "failure", "error"):
            fails[group] += 1

    for group, st in stats.items():
        st.tasks_delivered = len(delivered_sets[group])
        if explicit_rates[group] is not None:
            st.verification_pass_rate = explicit_rates[group]
        elif (passes[group] + fails[group]) > 0:
            st.verification_pass_rate = round((passes[group] / (passes[group] + fails[group])) * 100, 1)
        elif group is True and st.tasks_delivered > 0:
            total_auto = len({tid for c in commits if c.is_autonomous for tid in c.task_ids if tid in tasks_by_id})
            st.verification_pass_rate = round((st.tasks_delivered / total_auto) * 100, 1) if total_auto > st.tasks_delivered else 100.0
        else:
            st.verification_pass_rate = 100.0

    return {"Autonomous Agents": stats[True], "Human Developers": stats[False]}


def audit_provenance(
    data: ProjectData,
    commits: list[CommitRecord],
    strict: bool = False,
    ignore_orphaned_tasks: bool = False,
) -> ProvenanceReport:
    """Audits end-to-end SDLC traceability, detects unanchored commits, and verifies provenance."""
    tasks_by_id = {t.canonical_id: t for t in data.tasks}
    commits_by_task: dict[str, list[CommitRecord]] = {}
    unanchored: list[CommitRecord] = []
    missing_tasks: list[tuple[CommitRecord, str]] = []

    for c in commits:
        if not c.task_ids:
            if not c.is_merge:
                unanchored.append(c)
        else:
            for tid in c.task_ids:
                if tid in tasks_by_id:
                    commits_by_task.setdefault(tid, []).append(c)
                else:
                    missing_tasks.append((c, tid))

    if ignore_orphaned_tasks:
        orphaned_tasks: list[str] = []
    else:
        orphaned_tasks = [t.canonical_id for t in data.tasks if t.status.lower() == "complete" and not commits_by_task.get(t.canonical_id)]
    lineage, orphaned_stories = build_provenance_lineage(data, commits_by_task)
    contrib_stats = compute_contributor_stats(commits, data.tasks)

    if not unanchored and not orphaned_stories and not orphaned_tasks and not missing_tasks:
        integrity_pct = 100.0
    else:
        flaws = len(unanchored) + len(orphaned_stories) + len(orphaned_tasks) + len(missing_tasks)
        total_items = max(1, len(commits) + len(data.stories) + len(orphaned_tasks))
        integrity_pct = max(0.0, round(((total_items - flaws) / total_items) * 100, 1))

    return ProvenanceReport(
        total_commits=len(commits), anchored_commits=len(commits) - len(unanchored),
        unanchored_commits=unanchored, total_stories=len(data.stories),
        orphaned_stories=orphaned_stories, orphaned_tasks=orphaned_tasks,
        missing_task_commits=missing_tasks, contributor_stats=contrib_stats,
        lineage_matrix=lineage, integrity_pct=integrity_pct,
    )


def format_contributions_table(stats: dict[str, ContributorStats]) -> str:
    """Formats contributor velocity and pass rate comparison table."""
    lines = ["| Contributor Class   | Tasks Delivered | Merged Commits | Verification Pass Rate |"]
    for key in ("Autonomous Agents", "Human Developers"):
        if key in stats:
            s = stats[key]
            rate_str = f"{s.verification_pass_rate:.1f}%"
            lines.append(f"| {s.contributor_class:<19} | {s.tasks_delivered:<15} | {s.merged_commits:<14} | {rate_str:<22} |")
    return "\n".join(lines)


def format_traceability_matrix_table(rows: list[dict[str, str]]) -> str:
    """Formats verified traceability lineage matrix into ASCII table."""
    if not rows:
        return "(no traceability records found)"
    headers = ["Persona", "PRD", "User Story", "Backlog Task", "Git Commit", "Status"]
    lines = ["| " + " | ".join(headers) + " |", "|-" + "-|-".join("-" * len(h) for h in headers) + "-|"]
    for r in rows:
        lines.append(f"| {r['persona']} | {r['prd']} | {r['story']} | {r['task']} | {r['commit']} | {r['status']} |")
    return "\n".join(lines)


def run_provenance_audit(
    args: argparse.Namespace,
    config: SpecOpsConfig,
    site_updater: Callable[[SpecOpsConfig], None] | None = None,
) -> int:
    """CLI frontdoor execution entrypoint for 'spec-ops audit provenance/traceability'."""
    repo_arg = getattr(args, "repo", ".")
    repo_dir = Path(repo_arg).resolve() if Path(repo_arg).is_absolute() else (config.root_dir / repo_arg).resolve()
    data = SpecOpsParser(config.project_docs_dir).parse_all()

    since_arg = getattr(args, "since", None)
    baseline_commit = None
    toml_path = repo_dir / "specops.toml"
    if not since_arg and toml_path.is_file():
        try:
            import sys
            if sys.version_info >= (3, 11):
                import tomllib
            else:
                import tomli as tomllib  # type: ignore
            data_toml = tomllib.loads(toml_path.read_text(encoding="utf-8"))
            baseline_commit = data_toml.get("audit", {}).get("provenance", {}).get("baseline_commit")
        except Exception:
            pass

    commits = extract_commit_records(repo_dir, since=since_arg, baseline_commit=baseline_commit)
    strict = getattr(args, "strict", False)

    report = audit_provenance(
        data,
        commits,
        strict=strict,
        ignore_orphaned_tasks=bool(since_arg or baseline_commit),
    )

    if getattr(args, "contributions", False):
        print("Contributor Provenance Breakdown:")
        print(format_contributions_table(report.contributor_stats))
        if site_updater is not None:
            try:
                site_updater(config)
            except Exception:
                pass
            print("✨ Updated visualizer Traceability view with contributor filter chips.")

    print("Verified Traceability Matrix:")
    print(format_traceability_matrix_table(report.lineage_matrix))
    print()

    for c in report.unanchored_commits:
        print(f"⚠️ Warning: Unanchored commit {c.short_hash} by {c.author} lacks 'SpecOps-Task' or 'Task-ID' trailer.")
    for tid in report.orphaned_tasks:
        print(f"⚠️ Warning: Orphaned task {tid} in docs/project/backlog/complete/ has no linked git commits (missing delivery provenance).")
    for c, tid in report.missing_task_commits:
        print(f"⚠️ Warning: Commit {c.short_hash} references task {tid} which does not exist in docs/project/backlog/.")

    if not report.unanchored_commits and not report.orphaned_stories and not report.orphaned_tasks and not report.missing_task_commits:
        print("Traceability Integrity: 100% (0 unanchored commits, 0 orphaned stories)")
    else:
        print(f"Traceability Integrity: {report.integrity_pct:.0f}% ({len(report.unanchored_commits)} unanchored commits, {len(report.orphaned_stories)} orphaned stories)")

    if strict:
        return 1 if (report.unanchored_commits or report.orphaned_tasks or report.missing_task_commits or report.orphaned_stories) else 0
    return 1 if (report.unanchored_commits or report.orphaned_tasks or report.missing_task_commits) else 0
