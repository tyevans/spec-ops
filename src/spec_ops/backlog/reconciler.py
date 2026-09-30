"""Architectural drift reconciliation for candidate backlog tasks."""

from __future__ import annotations

import difflib
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..core.models import ADR, ProjectData, Task
from ..core.parser import FRONTMATTER_PATTERN, extract_frontmatter


@dataclass
class ReconciliationChange:
    """Record of a single reconciled specification drift."""

    change_type: str  # "superseded_adr", "stale_module_path", "bounded_context"
    target: str
    details: str


@dataclass
class ReconciliationDiff:
    """Structured diff summary of reconciliations for a task."""

    task_id: str
    changes: list[ReconciliationChange] = field(default_factory=list)

    @property
    def has_changes(self) -> bool:
        return len(self.changes) > 0

    @property
    def diff_summary(self) -> str:
        if not self.changes:
            return f"No architectural drift detected for {self.task_id}."
        lines = [f"Reconciliation Diff for {self.task_id}:"]
        for ch in self.changes:
            lines.append(f"  [{ch.change_type.upper()}] {ch.target}: {ch.details}")
        return "\n".join(lines)


@dataclass
class ReconciliationResult:
    """Result of reconciling a candidate task against repository reality."""

    task: Task
    diff: ReconciliationDiff
    modified: bool = False


class ArchitecturalReconciler:
    """Reconciles candidate task specifications against living codebase and active ADRs."""

    def __init__(self, root_dir: Path):
        self.root_dir = root_dir.resolve()
        self.docs_dir = self.root_dir / "docs" / "project"
        self.src_dir = self.root_dir / "src"

    def discover_superseded_adrs(self) -> dict[str, str]:
        """Discovers superseding ADR mapping: {superseded_adr_id: active_adr_id}."""
        superseded_map: dict[str, str] = {}
        adrs_dir = self.docs_dir / "adrs"
        if not adrs_dir.exists():
            return superseded_map

        # 1. Parse REGISTRY.md if present
        registry_file = adrs_dir / "REGISTRY.md"
        if registry_file.exists():
            for line in registry_file.read_text(encoding="utf-8").splitlines():
                # Matches: | ADR-0003 | Title | Superseded (by ADR-0015) | ...
                m = re.search(r"(ADR-\d+).*?Superseded\s*(?:\(by\s*(ADR-\d+)\))?", line, re.IGNORECASE)
                if m and m.group(2):
                    superseded_map[m.group(1).upper()] = m.group(2).upper()

        # 2. Parse individual ADR markdown files across accepted, proposed, superseded
        for p in adrs_dir.rglob("*.md"):
            if not p.is_file() or p.name in ("REGISTRY.md", "README.md"):
                continue
            try:
                content = p.read_text(encoding="utf-8")
                meta, body = extract_frontmatter(content)
                adr_id_match = re.search(r"ADR-\d+", p.stem.upper())
                curr_id = str(meta.get("id", adr_id_match.group(0) if adr_id_match else "")).upper()
                if not curr_id.startswith("ADR-") and curr_id.isdigit():
                    curr_id = f"ADR-{curr_id.zfill(4)}"

                # Check frontmatter
                superseded_by = meta.get("superseded_by")
                if superseded_by:
                    s_id = str(superseded_by).upper()
                    if not s_id.startswith("ADR-") and s_id.isdigit():
                        s_id = f"ADR-{s_id.zfill(4)}"
                    if curr_id:
                        superseded_map[curr_id] = s_id

                # Check body text
                body_match = re.search(r"Superseded\s+by\s+(?:\[`?)?(ADR-\d+)", body, re.IGNORECASE)
                if body_match and curr_id:
                    superseded_map[curr_id] = body_match.group(1).upper()
            except OSError:
                continue

        # Transitive resolution: A -> B and B -> C => A -> C
        for old_id, new_id in list(superseded_map.items()):
            visited = {old_id}
            target = new_id
            while target in superseded_map and target not in visited:
                visited.add(target)
                target = superseded_map[target]
            superseded_map[old_id] = target

        return superseded_map

    def discover_active_bounded_contexts(self) -> set[str]:
        """Discovers active bounded contexts from directory layout."""
        contexts: set[str] = set()
        if self.src_dir.exists():
            for pkg in self.src_dir.iterdir():
                if pkg.is_dir() and not pkg.name.startswith((".", "_")):
                    # Check nested subdirectories (e.g., src/spec_ops/backlog -> backlog)
                    for sub in pkg.iterdir():
                        if sub.is_dir() and not sub.name.startswith((".", "_")):
                            contexts.add(sub.name)
                    contexts.add(pkg.name)
        if not contexts:
            contexts.update(["core", "backlog", "worker", "cli", "prd", "docs", "graph", "security"])
        return contexts

    def discover_codebase_files(self) -> dict[str, Path]:
        """Returns map of relative path string to Path for all Python files."""
        files: dict[str, Path] = {}
        if self.src_dir.exists():
            for p in self.src_dir.rglob("*.py"):
                if p.is_file():
                    rel = p.relative_to(self.root_dir).as_posix()
                    files[rel] = p
        return files

    def find_module_replacement(self, stale_path: str, codebase_files: dict[str, Path]) -> str | None:
        """Finds closest active module replacement for a stale file reference."""
        stale_p = Path(stale_path)
        stale_stem = stale_p.stem
        # 1. Exact stem match across other dirs
        for rel_str, full_p in codebase_files.items():
            if full_p.stem == stale_stem:
                return rel_str

        # 2. Match without legacy/old prefixes
        clean_stem = re.sub(r"^(?:legacy_|old_|deprecated_)", "", stale_stem)
        for rel_str, full_p in codebase_files.items():
            if clean_stem == full_p.stem or (len(clean_stem) >= 4 and clean_stem in full_p.stem):
                return rel_str

        # 3. Fuzzy match stems
        best_match: str | None = None
        best_ratio = 0.0
        for rel_str, full_p in codebase_files.items():
            ratio = difflib.SequenceMatcher(None, stale_stem, full_p.stem).ratio()
            if ratio >= 0.7 and ratio > best_ratio:
                best_ratio = ratio
                best_match = rel_str

        return best_match

    def reconcile_task(self, task: Task) -> ReconciliationResult:
        """Audits and reconciles a task against living repository reality."""
        changes: list[ReconciliationChange] = []
        superseded_adrs = self.discover_superseded_adrs()
        active_bcs = self.discover_active_bounded_contexts()
        codebase_files = self.discover_codebase_files()

        updated_governing_adrs = list(task.governing_adrs)
        updated_body = task.body
        updated_bc = task.target_bc

        # 1. Reconcile Superseded ADRs
        for idx, adr_ref in enumerate(updated_governing_adrs):
            clean_ref = adr_ref.upper()
            if clean_ref in superseded_adrs:
                active_adr = superseded_adrs[clean_ref]
                updated_governing_adrs[idx] = active_adr
                changes.append(
                    ReconciliationChange(
                        change_type="superseded_adr",
                        target=f"{clean_ref} -> {active_adr}",
                        details=f"Replaced superseded citation {clean_ref} with active {active_adr}",
                    )
                )

        # Replace ADR occurrences in task body
        for old_adr, active_adr in superseded_adrs.items():
            if old_adr in updated_body:
                updated_body = re.sub(rf"\b{re.escape(old_adr)}\b", active_adr, updated_body)

        # 2. Reconcile Stale File Paths mentioned in task body
        path_matches = set(re.findall(r"src/[a-zA-Z0-9_\-/]+\.py", updated_body))
        for ref_path in path_matches:
            if ref_path not in codebase_files:
                replacement = self.find_module_replacement(ref_path, codebase_files)
                if replacement:
                    updated_body = updated_body.replace(ref_path, replacement)
                    changes.append(
                        ReconciliationChange(
                            change_type="stale_module_path",
                            target=f"{ref_path} -> {replacement}",
                            details=f"Updated stale path reference to living module {replacement}",
                        )
                    )

        # 3. Reconcile Bounded Context References
        if updated_bc and updated_bc not in active_bcs:
            # Map legacy names (e.g., 'queue' -> 'backlog')
            bc_matches = difflib.get_close_matches(updated_bc, list(active_bcs), n=1, cutoff=0.3)
            new_bc = bc_matches[0] if bc_matches else "core"
            changes.append(
                ReconciliationChange(
                    change_type="bounded_context",
                    target=f"{updated_bc} -> {new_bc}",
                    details=f"Aligned target bounded context '{updated_bc}' with active domain context '{new_bc}'",
                )
            )
            updated_bc = new_bc

        modified = len(changes) > 0
        reconciled_task = Task(
            id=task.id,
            title=task.title,
            status=task.status,
            dependencies=list(task.dependencies),
            governing_adrs=updated_governing_adrs,
            governing_prds=list(task.governing_prds),
            governing_stories=list(task.governing_stories),
            target_bc=updated_bc,
            target_release=task.target_release,
            prs=list(task.prs),
            pr_url=task.pr_url,
            claimed_by=task.claimed_by,
            branch=task.branch,
            priority_rank=task.priority_rank,
            body=updated_body,
            raw_markdown=task.raw_markdown,
            file_path=task.file_path,
            commits=list(task.commits),
        )

        return ReconciliationResult(
            task=reconciled_task,
            diff=ReconciliationDiff(task_id=task.canonical_id, changes=changes),
            modified=modified,
        )
