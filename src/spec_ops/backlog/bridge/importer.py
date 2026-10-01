"""External issue tracker ingestion bridge for GitHub, Jira, and Linear (ADR-0001, ADR-0002, ADR-0003)."""

from __future__ import annotations

import json
from pathlib import Path
import re
from typing import Any

import yaml

from ...config.loader import load_config
from ...config.models import SpecOpsConfig
from .models import ExternalIssue, IngestionResult
from .parsers import (
    detect_json_source,
    fetch_github_remote,
    parse_csv_content,
    parse_github_items,
    parse_jira_items,
    parse_linear_items,
)


def slugify(text: str) -> str:
    """Creates a filesystem-safe slug from a title."""
    cleaned = re.sub(r"[^\w\s-]", "", text.lower())
    slug = re.sub(r"[\s_]+", "-", cleaned).strip("-")
    slug = re.sub(r"-+", "-", slug)
    return slug[:50] or "task"


class IssueImporter:
    """Parses issues from external trackers and writes validated proposed task files."""

    def __init__(self, backlog_dir: Path, config: SpecOpsConfig | None = None) -> None:
        self.backlog_dir = backlog_dir.resolve()
        self.config = config or load_config(root_dir=self.backlog_dir.parent.parent)
        self.proposed_dir = self.backlog_dir / "proposed"

    def import_from_source(
        self,
        source: str = "auto",
        file_path: Path | None = None,
        repo: str | None = None,
        label: str | None = None,
        default_bc: str = "core",
    ) -> IngestionResult:
        """Main frontdoor method for ingesting issues from file or remote API."""
        if file_path:
            issues = self.parse_file(file_path, source=source)
        elif repo:
            issues = self.fetch_github_issues(repo, label=label)
        else:
            raise ValueError("Either file_path (--file) or repo (--repo) must be provided for import.")

        return self.ingest_issues(issues, default_bc=default_bc)

    def parse_file(self, file_path: Path, source: str = "auto") -> list[ExternalIssue]:
        """Parses a local JSON or CSV issue export file."""
        if not file_path.exists():
            raise FileNotFoundError(f"Issue export file not found: {file_path}")

        content = file_path.read_text(encoding="utf-8")
        if file_path.suffix.lower() == ".csv":
            return parse_csv_content(content, source=source)

        data = json.loads(content)
        detected = source if source != "auto" else detect_json_source(data)
        if detected == "jira":
            return parse_jira_items(data)
        elif detected == "linear":
            return parse_linear_items(data)
        return parse_github_items(data)

    def fetch_github_issues(self, repo: str, label: str | None = None) -> list[ExternalIssue]:
        """Fetches open issues directly from the GitHub API."""
        return fetch_github_remote(repo, label=label)

    def _get_max_task_number(self) -> int:
        max_id = 0
        if self.backlog_dir.exists():
            for p in self.backlog_dir.rglob("*.md"):
                m = re.match(r"^(\d+)", p.stem)
                if m:
                    max_id = max(max_id, int(m.group(1)))
        p_file = self.backlog_dir / "PRIORITY.md"
        if p_file.is_file():
            content = p_file.read_text(encoding="utf-8")
            for m in re.finditer(r"TASK-(\d+)", content):
                max_id = max(max_id, int(m.group(1)))
        return max_id

    def _build_existing_key_map(self) -> dict[str, str]:
        key_map: dict[str, str] = {}
        if not self.backlog_dir.exists():
            return key_map
        for p in self.backlog_dir.rglob("*.md"):
            if not p.is_file() or p.name.startswith("."):
                continue
            try:
                content = p.read_text(encoding="utf-8")
                m_cid = re.search(r"TASK-(\d+)", p.name, re.I) or re.match(r"^(\d+)", p.stem)
                if not m_cid:
                    continue
                cid = f"TASK-{int(m_cid.group(1)):04d}"
                m_ref = re.search(r"external_ref:\s*['\"]?([^'\"\n]+)['\"]?", content)
                if m_ref:
                    ref_val = m_ref.group(1).strip()
                    key_map[ref_val] = cid
                    key_map[ref_val.lower()] = cid
            except OSError:
                continue
        return key_map

    def ingest_issues(
        self, issues: list[ExternalIssue], default_bc: str = "core"
    ) -> IngestionResult:
        """Assigns sequential task IDs, maps dependencies, and writes proposed tasks."""
        self.proposed_dir.mkdir(parents=True, exist_ok=True)
        key_map = self._build_existing_key_map()
        start_num = self._get_max_task_number()

        # Phase 1: Allocate non-colliding sequential IDs and register key mapping
        allocations: list[tuple[ExternalIssue, int, str]] = []
        for idx, issue in enumerate(issues, start=1):
            next_num = start_num + idx
            num_str = f"{next_num:04d}"
            cid = f"TASK-{num_str}"
            allocations.append((issue, next_num, cid))
            if issue.key:
                clean_k = issue.key.strip()
                key_map[clean_k] = cid
                key_map[clean_k.lower()] = cid
                if clean_k.startswith("#"):
                    key_map[clean_k.lstrip("#")] = cid
                digits = re.search(r"\d+", clean_k)
                if digits:
                    key_map[digits.group(0)] = cid
            if issue.url:
                key_map[issue.url.strip()] = cid

        # Phase 2: Synthesize Markdown files and audit Definition of Ready
        from ..dor_gate import audit_task_health

        created_files: list[Path] = []
        created_task_ids: list[str] = []
        ready_count = 0
        dor_incomplete_count = 0

        for issue, num, cid in allocations:
            num_str = f"{num:04d}"
            slug = slugify(issue.title)
            filename = f"{num_str}-{slug}.md"
            dest_file = self.proposed_dir / filename

            # Map dependencies to canonical SpecOps IDs
            mapped_deps: list[str] = []
            for dep in issue.dependencies:
                dep_clean = dep.strip()
                if dep_clean in key_map:
                    mapped_deps.append(key_map[dep_clean])
                elif dep_clean.lower() in key_map:
                    mapped_deps.append(key_map[dep_clean.lower()])
                elif re.match(r"^TASK-\d+$", dep_clean, re.I):
                    m_d = re.match(r"^TASK-(\d+)$", dep_clean, re.I)
                    mapped_deps.append(f"TASK-{int(m_d.group(1)):04d}")
                else:
                    mapped_deps.append(dep_clean)
            mapped_deps = sorted(set(mapped_deps))

            bc = issue.target_bc or default_bc
            file_content = self._render_task_file(issue, num_str, cid, bc, mapped_deps)
            dest_file.write_text(file_content, encoding="utf-8")
            created_files.append(dest_file)
            created_task_ids.append(cid)

            # Definition of Ready audit
            from ...core.parser import parse_task

            task_obj = parse_task(dest_file)
            report = audit_task_health(task_obj, self.config)
            if report.is_ready:
                ready_count += 1
            else:
                dor_incomplete_count += 1

            self._append_to_priority(cid, filename)

        return IngestionResult(
            imported_count=len(allocations),
            ready_count=ready_count,
            dor_incomplete_count=dor_incomplete_count,
            task_ids=created_task_ids,
            files=created_files,
            key_mapping=key_map,
        )

    def _render_task_file(
        self,
        issue: ExternalIssue,
        num_str: str,
        canonical_id: str,
        bc: str,
        mapped_deps: list[str],
    ) -> str:
        meta: dict[str, Any] = {
            "id": num_str,
            "title": issue.title,
            "status": "Proposed",
            "target_bc": bc,
        }
        if mapped_deps:
            meta["dependencies"] = mapped_deps
        if issue.url:
            meta["external_ref"] = issue.url
        elif issue.key:
            meta["external_ref"] = issue.key

        adrs = re.findall(r"ADR-\d+", issue.description, re.IGNORECASE)
        prds = re.findall(r"PRD-\d+", issue.description, re.IGNORECASE)
        stories = re.findall(r"US-\d+", issue.description, re.IGNORECASE)
        if adrs:
            meta["governing_adrs"] = sorted(set(a.upper() for a in adrs))
        if prds:
            meta["governing_prds"] = sorted(set(p.upper() for p in prds))
        if stories:
            meta["governing_stories"] = sorted(set(s.upper() for s in stories))
        m_mut = re.search(r"mutation\s+(?:testing\s+)?scope:\s*([^\n]+)", issue.description, re.IGNORECASE)
        if m_mut:
            meta["mutation_scope"] = m_mut.group(1).strip()
        m_per = re.search(r"persona:\s*([^\n]+)", issue.description, re.IGNORECASE)
        if m_per:
            meta["persona"] = m_per.group(1).strip()

        clean_title = re.sub(r"[\r\n]+", " ", issue.title).strip() or "Untitled Task"
        meta["title"] = clean_title
        yaml_block = yaml.dump(meta, sort_keys=False, width=1000, allow_unicode=True).strip()
        body = f"""# {canonical_id}: {clean_title}

## Summary
{issue.title}

## Problem Statement & Context
{issue.description.strip() or f"Task imported from {issue.source or 'external issue tracker'} ({issue.key or issue.url})."}

## External Reference
- Key: {issue.key or 'N/A'}
- URL: {issue.url or 'N/A'}
- Source: {issue.source or 'external'}

## Definition of Done (Blackbox Frontdoor TDD)
1. Public interfaces or standard domain contracts implemented.
2. Verified via automated blackbox tests without private backdoor manipulation.
3. All new source files strictly under 500 lines.
"""
        return f"---\n{yaml_block}\n---\n\n{body}\n"

    def _append_to_priority(self, canonical_id: str, filename: str) -> None:
        priority_file = self.backlog_dir / "PRIORITY.md"
        if not priority_file.exists():
            return
        content = priority_file.read_text(encoding="utf-8")
        if canonical_id in content:
            return
        stem = Path(filename).stem
        entry = f"- **{canonical_id} (Proposed)**: [`{stem}`](proposed/{filename})"
        lines = content.splitlines()
        lines.append(entry)
        priority_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
