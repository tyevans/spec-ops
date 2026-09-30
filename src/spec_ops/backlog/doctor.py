"""Proactive backlog health diagnostics, dangling dependency auditing, and self-healing repair."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from ..core.models import Task
from ..core.parser import extract_frontmatter, parse_task
from .tree import normalize_task_id

PRIORITY_ENTRY_REGEX = re.compile(
    r"^\s*-\s*\*\*([A-Za-z0-9_-]+)\s*(?:\(([^)]+)\))?\*\*\s*:\s*\[`?([^`\]]+)`?\]\(([^)]+)\)",
    re.MULTILINE,
)


@dataclass
class BacklogDefect:
    """Represents a structural defect or synchronization drift in the backlog."""

    defect_type: str  # dangling_dependency, ghost_index_entry, unindexed_task, sync_drift, broken_link
    task_id: str
    message: str
    file_path: Path
    line_number: int = 1
    target_ref: str = ""
    details: str = ""
    suggestion: str = ""


@dataclass
class BacklogDoctorReport:
    """Comprehensive diagnostic and remediation report for backlog health."""

    defects: list[BacklogDefect] = field(default_factory=list)
    remediations: list[str] = field(default_factory=list)
    remediated_count: int = 0

    @property
    def is_healthy(self) -> bool:
        return len(self.defects) == 0

    @property
    def dangling_dependencies(self) -> list[BacklogDefect]:
        return [d for d in self.defects if d.defect_type == "dangling_dependency"]

    @property
    def ghost_entries(self) -> list[BacklogDefect]:
        return [d for d in self.defects if d.defect_type == "ghost_index_entry"]

    @property
    def unindexed_tasks(self) -> list[BacklogDefect]:
        return [d for d in self.defects if d.defect_type == "unindexed_task"]

    @property
    def sync_drifts(self) -> list[BacklogDefect]:
        return [d for d in self.defects if d.defect_type == "sync_drift"]

    @property
    def broken_links(self) -> list[BacklogDefect]:
        return [d for d in self.defects if d.defect_type == "broken_link"]

    def to_dict(self) -> dict[str, Any]:
        return {
            "is_healthy": self.is_healthy,
            "issues_count": len(self.defects),
            "remediated_count": self.remediated_count,
            "remediations": list(self.remediations),
            "defects": [
                {
                    "defect_type": d.defect_type,
                    "task_id": d.task_id,
                    "message": d.message,
                    "file_path": str(d.file_path),
                    "line_number": d.line_number,
                    "target_ref": d.target_ref,
                    "suggestion": d.suggestion,
                }
                for d in self.defects
            ],
        }


def find_dependency_line(content: str, dep: str) -> int:
    """Finds the 1-indexed line number where a dependency reference is declared."""
    lines = content.splitlines()
    raw = dep.strip()
    digits = re.search(r"\d+", raw)
    d_str = digits.group(0) if digits else ""
    for idx, line in enumerate(lines, start=1):
        if raw in line or (d_str and d_str in line and ("dependencies" in line or line.strip().startswith("-"))):
            return idx
    return 1


class BacklogDoctor:
    """Audits backlog integrity, identifies dangling dependencies, and performs self-healing repair."""

    def __init__(self, backlog_dir: Path):
        self.backlog_dir = Path(backlog_dir).resolve()
        self.priority_file = self.backlog_dir / "PRIORITY.md"

    def discover_disk_tasks(self) -> dict[str, tuple[Task, Path, str]]:
        """Scans disk folders returning {canonical_id: (Task, Path, folder)}."""
        tasks: dict[str, tuple[Task, Path, str]] = {}
        for folder_name in ("complete", "refined", "proposed"):
            folder_path = self.backlog_dir / folder_name
            if not folder_path.exists():
                continue
            for p in sorted(folder_path.glob("*.md")):
                if not p.name.startswith(".") and p.is_file():
                    try:
                        task = parse_task(p)
                        tasks[task.canonical_id] = (task, p, folder_name)
                    except Exception:
                        continue
        return tasks

    def audit(self) -> BacklogDoctorReport:
        """Audits tasks, dependency pointers, index references, and link integrity."""
        defects: list[BacklogDefect] = []
        disk_tasks = self.discover_disk_tasks()
        valid_ids = set(disk_tasks.keys())

        # 1. Audit task dependencies for broken or dangling pointers
        for cid, (task, fpath, _) in disk_tasks.items():
            content = fpath.read_text(encoding="utf-8")
            for dep in task.dependencies:
                if normalize_task_id(dep) not in valid_ids:
                    line_no = find_dependency_line(content, dep)
                    defects.append(
                        BacklogDefect(
                            defect_type="dangling_dependency",
                            task_id=cid,
                            target_ref=dep,
                            message=f"Backlog Defect: {cid} references non-existent dependency '{dep}'",
                            file_path=fpath,
                            line_number=line_no,
                            details=f"Task {cid} at {fpath.name}:{line_no} lists missing dependency '{dep}'.",
                            suggestion="Suggest removing the dangling reference or authoring the missing task specification.",
                        )
                    )

        # 2. Audit PRIORITY.md for ghost entries, drift, and unindexed files
        indexed_ids, indexed_files = set(), set()
        if self.priority_file.exists():
            for idx, line in enumerate(self.priority_file.read_text(encoding="utf-8").splitlines(), start=1):
                m = PRIORITY_ENTRY_REGEX.match(line)
                if not m:
                    continue
                raw_id, raw_status, _, raw_target = m.groups()
                cid = normalize_task_id(raw_id)
                indexed_ids.add(cid)
                target_p = self.backlog_dir / raw_target
                indexed_files.add(target_p.name)

                if cid not in disk_tasks and not target_p.exists():
                    defects.append(
                        BacklogDefect(
                            defect_type="ghost_index_entry",
                            task_id=cid,
                            target_ref=raw_target,
                            message=f"Backlog Defect: PRIORITY.md lists a reference to '{cid}' whose file has been deleted from disk",
                            file_path=self.priority_file,
                            line_number=idx,
                            details=f"Ghost reference '{cid}' pointing to deleted file '{raw_target}'.",
                            suggestion="Remove ghost index reference from PRIORITY.md.",
                        )
                    )
                elif cid in disk_tasks:
                    _, actual_p, actual_folder = disk_tasks[cid]
                    target_folder = raw_target.split("/")[0] if "/" in raw_target else ""
                    st = (raw_status or "").strip()
                    if target_folder != actual_folder and not (actual_folder == "refined" and st in ("In-Progress", "Review")):
                        defects.append(
                            BacklogDefect(
                                defect_type="sync_drift",
                                task_id=cid,
                                target_ref=raw_target,
                                message=f"Backlog Defect: {cid} is in {actual_folder}/ on disk but referenced as {target_folder}/ in PRIORITY.md",
                                file_path=self.priority_file,
                                line_number=idx,
                                details=f"Folder mismatch: disk={actual_folder}, priority={target_folder}",
                                suggestion=f"Update PRIORITY.md reference to {actual_folder}/{actual_p.name}",
                            )
                        )

        # 3. Audit unindexed task files on disk
        for cid, (task, fpath, folder) in disk_tasks.items():
            if cid not in indexed_ids and fpath.name not in indexed_files:
                defects.append(
                    BacklogDefect(
                        defect_type="unindexed_task",
                        task_id=cid,
                        target_ref=fpath.name,
                        message=f"Backlog Defect: Task file '{fpath.name}' exists in '{folder}/' but is missing from PRIORITY.md",
                        file_path=fpath,
                        details=f"Unindexed file {folder}/{fpath.name} ({cid}) missing from PRIORITY.md",
                        suggestion=f"Append {cid} to PRIORITY.md under {folder} status.",
                    )
                )

        # 4. Audit broken markdown links across backlog files
        link_pat = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
        for cid, (_, fpath, _) in disk_tasks.items():
            for idx, line in enumerate(fpath.read_text(encoding="utf-8").splitlines(), start=1):
                for match in link_pat.finditer(line):
                    t = match.group(2).split("#")[0].strip()
                    if t and t.endswith(".md") and not t.startswith(("http://", "https://", "mailto:", "#")):
                        resolved = (fpath.parent / t).resolve()
                        try:
                            resolved.relative_to(self.backlog_dir)
                            if not resolved.exists():
                                defects.append(
                                    BacklogDefect(
                                        defect_type="broken_link",
                                        task_id=cid,
                                        target_ref=t,
                                        message=f"Backlog Defect: Broken link '{t}' in {fpath.name}",
                                        file_path=fpath,
                                        line_number=idx,
                                        suggestion="Fix or remove broken link target.",
                                    )
                                )
                        except ValueError:
                            pass

        return BacklogDoctorReport(defects=defects)

    def fix(self) -> BacklogDoctorReport:
        """Applies automated in-place self-healing repair across task files and PRIORITY.md."""
        report = self.audit()
        if report.is_healthy:
            return BacklogDoctorReport(defects=[], remediations=[], remediated_count=0)

        remediations: list[str] = []
        disk_tasks = self.discover_disk_tasks()

        # 1. Clean dangling dependencies in task files
        tasks_with_dangling: dict[str, list[BacklogDefect]] = {}
        for d in report.dangling_dependencies:
            tasks_with_dangling.setdefault(d.task_id, []).append(d)

        for cid, d_list in tasks_with_dangling.items():
            if cid not in disk_tasks:
                continue
            task, fpath, _ = disk_tasks[cid]
            meta, body = extract_frontmatter(fpath.read_text(encoding="utf-8"))
            current_deps = meta.get("dependencies", [])
            dangling_targets = {normalize_task_id(d.target_ref) for d in d_list}
            updated_deps = [dep for dep in current_deps if normalize_task_id(str(dep)) not in dangling_targets]

            if len(updated_deps) != len(current_deps):
                meta["dependencies"] = updated_deps
                yaml_block = yaml.dump(meta, sort_keys=False, default_flow_style=False).strip()
                clean_b = body.strip()
                new_content = f"---\n{yaml_block}\n---\n" if not clean_b else f"---\n{yaml_block}\n---\n\n{clean_b}\n"
                fpath.write_text(new_content, encoding="utf-8")
                for d in d_list:
                    remediations.append(f"Cleaned dangling dependency '{d.target_ref}' from {cid}")

        # 2. Reconcile PRIORITY.md: remove ghost entries, fix drift, append unindexed files
        ghost_targets = {d.target_ref for d in report.ghost_entries}
        ghost_ids = {d.task_id for d in report.ghost_entries}
        existing_lines = (
            self.priority_file.read_text(encoding="utf-8").splitlines()
            if self.priority_file.exists()
            else ["# Backlog Priority Index", "", "Strict sequential order of execution for engineering tasks.", ""]
        )

        disk_tasks = self.discover_disk_tasks()
        lines: list[str] = []

        for line in existing_lines:
            m = PRIORITY_ENTRY_REGEX.match(line)
            if not m:
                lines.append(line)
                continue
            raw_id, raw_status, _, raw_target = m.groups()
            cid = normalize_task_id(raw_id)
            if cid in ghost_ids or raw_target in ghost_targets:
                remediations.append(f"Cleaned ghost reference to '{cid}' from PRIORITY.md")
                continue

            if cid in disk_tasks:
                _, actual_path, actual_folder = disk_tasks[cid]
                target_folder = raw_target.split("/")[0] if "/" in raw_target else ""
                st = (raw_status or "").strip()
                if target_folder != actual_folder and not (actual_folder == "refined" and st in ("In-Progress", "Review")):
                    lines.append(f"- **{cid} ({actual_folder.capitalize()})**: [`{actual_path.stem}`]({actual_folder}/{actual_path.name})")
                    remediations.append(f"Updated PRIORITY.md reference for {cid} to {actual_folder}/")
                    continue
            lines.append(line)

        # 3. Deterministically append unindexed task files sorted by task integer
        def sort_key(d: BacklogDefect) -> int:
            num = re.search(r"\d+", d.task_id)
            return int(num.group(0)) if num else 999999

        for d in sorted(report.unindexed_tasks, key=sort_key):
            if d.task_id in disk_tasks:
                task, fpath, folder = disk_tasks[d.task_id]
                lines.append(f"- **{task.canonical_id} ({folder.capitalize()})**: [`{fpath.stem}`]({folder}/{fpath.name})")
                remediations.append(f"Appended unindexed task '{fpath.name}' to PRIORITY.md under {folder} status")

        self.priority_file.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
        post_audit = self.audit()
        post_audit.remediations = remediations
        post_audit.remediated_count = len(remediations)
        return post_audit


def run_backlog_doctor(backlog_dir: Path, fix: bool = False, as_json: bool = False) -> int:
    """CLI runner function for backlog doctor inspection and repair."""
    doctor = BacklogDoctor(backlog_dir)
    report = doctor.fix() if fix else doctor.audit()

    if as_json:
        print(json.dumps(report.to_dict(), indent=2))
        return 0 if (report.is_healthy or fix) else 1

    if fix:
        print(f"Backlog self-healing complete: {report.remediated_count} issues remediated.")
        for rem in report.remediations:
            print(f"  • {rem}")
        return 0 if report.is_healthy else 1

    if report.is_healthy:
        print("Backlog is healthy: 0 defects detected.")
        return 0

    u_cnt, g_cnt = len(report.unindexed_tasks), len(report.ghost_entries)
    print(f"Backlog Defect Audit: {len(report.defects)} defects found.\n")

    for d in report.dangling_dependencies:
        print(f"Backlog Defect: {d.task_id} references non-existent dependency '{d.target_ref}' (at line {d.line_number})")
        if d.suggestion:
            print("  -> Suggest removing the dangling reference or authoring the missing task specification.")

    for d in report.unindexed_tasks:
        print(f"Backlog Defect: Task file '{d.target_ref}' exists in backlog but is missing from PRIORITY.md (unindexed task file)")

    for d in report.ghost_entries:
        print(f"Backlog Defect: PRIORITY.md lists reference to '{d.task_id}' whose file has been deleted from disk (ghost index reference)")

    for d in report.sync_drifts:
        print(d.message)

    for d in report.broken_links:
        print(d.message)

    print(f"\nDiagnostic report highlights {u_cnt} unindexed task file{'s' if u_cnt != 1 else ''} and {g_cnt} ghost index reference{'s' if g_cnt != 1 else ''}.")
    print("Warning: backlog synchronization drift detected.")
    print("Run 'spec-ops queue doctor --fix' (or 'spec-ops backlog doctor --repair') to automatically repair.")
    return 1
