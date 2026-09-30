"""Architectural spike: Anti-loop worktree failure memory schema and negative prompt synthesis (US-0089)."""

from __future__ import annotations

import re
import shutil
import subprocess
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from .lifecycle import cleanup_worktree, get_worktree_branch

INVARIANT_MANDATES: dict[str, str] = {
    "ADR-0001": "You must maintain specification as code in docs/project/ with YAML frontmatter.",
    "ADR-0002": "You must decompose source files to stay strictly under 500 lines (and warn at >=400 lines) with single-responsibility modules.",
    "ADR-0003": "You must strictly use public frontdoor entrypoints with zero mock backdoors.",
    "ADR-0004": "You must ensure preflight verification passes without skipping checks.",
    "ADR-0005": "You must never modify shared backlog files on feature branches.",
    "ADR-0006": "You must provide executable BDD Gherkin scenarios verified through public interfaces.",
    "ADR-0007": "You must isolate domain models from infrastructure within explicit bounded contexts.",
    "ADR-0008": "You must follow the Agent Constitution and maintain Diataxis documentation standards.",
    "ADR-0009": "You must maintain generative property tests and >=80% mutation kill score under mutmut.",
    "ADR-0010": "You must preserve event-sourced core substrate invariants.",
    "ADR-0011": "You must adhere to knowledge graph relational structures.",
    "ADR-0012": "You must execute worker commands only within sandboxed environments.",
    "ADR-0018": "You must not edit lockfiles or dependencies without explicit authorization.",
    "ADR-0019": "You must never hardcode credentials, secrets, or high-entropy tokens.",
}

DEFAULT_MANDATE = "You must avoid repeating the described failure pattern and strictly adhere to project invariants."


@dataclass
class FailureHistoryEntry:
    attempt_date: str
    reason: str
    failed_invariants: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "attempt_date": self.attempt_date,
            "reason": self.reason,
            "failed_invariants": list(self.failed_invariants),
        }


def extract_failed_invariants(reason: str) -> list[str]:
    """Extracts ADR invariant identifiers mentioned in a failure reason string."""
    found = re.findall(r"\bADR-\d{4}\b", reason, re.IGNORECASE)
    seen: set[str] = set()
    result: list[str] = []
    for inv in found:
        upper = inv.upper()
        if upper not in seen:
            seen.add(upper)
            result.append(upper)
    return result


def parse_task_memory(content: str) -> tuple[dict[str, Any], str, list[dict[str, Any]]]:
    """Extracts frontmatter metadata dict, markdown body verbatim, and failure_history entries."""
    if not content.startswith("---"):
        return {}, content, []

    first_newline = content.find("\n")
    if first_newline == -1:
        return {}, content, []

    m = re.search(r"(\r?\n)---[ \t]*(\r?\n|\Z)", content[first_newline:])
    if not m:
        return {}, content, []

    closing_start = first_newline + m.start()
    closing_end = first_newline + m.end()

    raw_yaml = content[first_newline + 1 : closing_start]
    body = content[closing_end:]

    try:
        data = yaml.safe_load(raw_yaml) or {}
    except yaml.YAMLError:
        return {}, content, []

    if not isinstance(data, dict):
        return {}, content, []

    raw_history = data.get("failure_history", [])
    history: list[dict[str, Any]] = []
    if isinstance(raw_history, list):
        for item in raw_history:
            if isinstance(item, dict):
                history.append(dict(item))

    return data, body, history


def serialize_task_with_memory(meta: dict[str, Any], body: str) -> str:
    """Serializes frontmatter dictionary and appends markdown body verbatim."""
    yaml_block = yaml.dump(
        meta,
        sort_keys=False,
        default_flow_style=False,
        allow_unicode=True,
    ).strip()
    return f"---\n{yaml_block}\n---\n{body}"


def append_failure_record(
    task_file: Path,
    reason: str,
    failed_invariants: list[str] | None = None,
    attempt_date: str | None = None,
) -> Path:
    """Appends a new failure post-mortem record to the task frontmatter losslessly."""
    content = task_file.read_bytes().decode("utf-8")
    meta, body, history = parse_task_memory(content)

    if not meta:
        meta = {"title": task_file.stem, "status": "Refined"}

    invariants = (
        list(failed_invariants)
        if failed_invariants is not None
        else extract_failed_invariants(reason)
    )
    date_str = attempt_date or datetime.now(timezone.utc).strftime("%Y-%m-%d")

    entry = FailureHistoryEntry(
        attempt_date=date_str,
        reason=reason.strip(),
        failed_invariants=invariants,
    )

    history.append(entry.to_dict())
    meta["failure_history"] = history

    new_content = serialize_task_with_memory(meta, body)
    task_file.write_bytes(new_content.encode("utf-8"))
    return task_file


def demote_task_to_proposed(
    backlog_dir: Path,
    canonical_id: str,
) -> tuple[bool, str, Path | None]:
    """Atomically moves task from refined/ to proposed/ and updates PRIORITY.md."""
    clean = canonical_id.upper().replace("TASK-", "").lstrip("0")
    tid_num = clean.zfill(4) if clean else "0000"
    target_cid = f"TASK-{tid_num}"

    refined_dir = backlog_dir / "refined"
    proposed_dir = backlog_dir / "proposed"
    proposed_dir.mkdir(parents=True, exist_ok=True)

    target_file: Path | None = None
    if refined_dir.exists():
        for p in refined_dir.glob("*.md"):
            digits = re.findall(r"\d+", p.stem)
            if digits and digits[0].zfill(4) == tid_num:
                target_file = p
                break

    if not target_file:
        return False, f"Task {target_cid} not found in {refined_dir}.", None

    dest_file = proposed_dir / target_file.name

    # Update frontmatter status to Proposed
    content = target_file.read_bytes().decode("utf-8")
    meta, body, _ = parse_task_memory(content)
    meta["status"] = "Proposed"
    new_content = serialize_task_with_memory(meta, body)

    dest_file.write_bytes(new_content.encode("utf-8"))
    target_file.unlink()

    # Update PRIORITY.md
    priority_file = backlog_dir / "PRIORITY.md"
    if priority_file.exists():
        p_content = priority_file.read_text(encoding="utf-8")
        pattern = re.compile(
            rf"(\*\*(?:TASK|SPIKE)-{tid_num}\s*\()(?:[^\)]+)(\)\*\*:\s*\[`?[^`\]]+`?\]\()(?:[^/]+)(/[^)]+\))",
            re.IGNORECASE,
        )
        updated = pattern.sub(r"\g<1>Proposed\g<2>proposed\g<3>", p_content)
        if updated != p_content:
            priority_file.write_text(updated, encoding="utf-8")

    return True, f"Demoted {target_cid} from refined/ to proposed/.", dest_file


def synthesize_negative_constraints(
    failure_history: list[dict[str, Any]] | list[FailureHistoryEntry],
) -> str:
    """Synthesizes markdown negative prompt constraints section from failure history."""
    if not failure_history:
        return ""

    lines: list[str] = ["## Prior Attempt Failures & Anti-Patterns (DO NOT REPEAT)"]

    for item in failure_history:
        entry = item.to_dict() if isinstance(item, FailureHistoryEntry) else item
        reason = str(entry.get("reason", "")).strip()
        if reason and not reason.endswith((".", "!", "?")):
            reason += "."
        lines.append(f"- Previous failure: {reason}")

        invariants = entry.get("failed_invariants") or []
        if isinstance(invariants, str):
            invariants = [invariants]
        if not invariants:
            invariants = extract_failed_invariants(reason)

        mandates: list[str] = []
        for inv in invariants:
            upper = inv.upper()
            if upper in INVARIANT_MANDATES and INVARIANT_MANDATES[upper] not in mandates:
                mandates.append(INVARIANT_MANDATES[upper])

        if not mandates:
            for k, v in INVARIANT_MANDATES.items():
                if k in reason.upper() and v not in mandates:
                    mandates.append(v)

        if not mandates:
            mandates.append(DEFAULT_MANDATE)

        for m in mandates:
            lines.append(f"- Mandate: {m}")

    return "\n".join(lines) + "\n"


def reset_worktree_with_memory(
    repo_root: Path,
    backlog_dir: Path,
    task_id_input: str,
    reason: str = "",
    demote: bool = False,
    failed_invariants: list[str] | None = None,
    attempt_date: str | None = None,
) -> tuple[bool, str]:
    """Resets worktree, purges branch, records failure memory, and optionally demotes task."""
    clean = task_id_input.upper().replace("TASK-", "").lstrip("0")
    tid_num = clean.zfill(4) if clean else "0000"
    canonical_id = f"TASK-{tid_num}"

    worktree_parent = repo_root / ".worktrees"
    worktree_dir = worktree_parent / f"task-{tid_num}"
    if not worktree_dir.exists():
        alt_wt = worktree_parent / f"task-{clean.lower()}"
        if alt_wt.exists():
            worktree_dir = alt_wt

    branch = ""
    if worktree_dir.exists():
        branch = get_worktree_branch(worktree_dir)

    candidate_branches = [
        branch,
        f"feat/{canonical_id}",
        f"task/{canonical_id}",
        f"feat/TASK-{tid_num}",
        f"task/TASK-{tid_num}",
        f"feat/task-{tid_num}",
        f"task/task-{tid_num}",
    ]

    # Teardown worktree if present
    if worktree_dir.exists():
        try:
            cleanup_worktree(repo_root, worktree_dir, branch=branch, delete_branch=True)
        except Exception:
            shutil.rmtree(worktree_dir, ignore_errors=True)

    # Clean up candidate branches from repo_root
    for b in candidate_branches:
        if b:
            subprocess.run(["git", "branch", "-D", b], cwd=repo_root, capture_output=True)

    # Locate task specification file in backlog
    target_file: Path | None = None
    for folder_name in ["refined", "proposed"]:
        folder = backlog_dir / folder_name
        if not folder.exists():
            continue
        for p in folder.glob("*.md"):
            digits = re.findall(r"\d+", p.stem)
            if digits and digits[0].zfill(4) == tid_num:
                target_file = p
                break
        if target_file:
            break

    if not target_file:
        return False, f"Task {canonical_id} specification not found in {backlog_dir}."

    actual_reason = reason.strip() or f"Reset requested for {canonical_id}."
    append_failure_record(
        target_file,
        reason=actual_reason,
        failed_invariants=failed_invariants,
        attempt_date=attempt_date,
    )

    if demote and target_file.parent.name == "refined":
        demote_ok, demote_msg, _ = demote_task_to_proposed(backlog_dir, canonical_id)
        if not demote_ok:
            return False, demote_msg

    return True, f"Safely reset worktree for {canonical_id} and recorded failure memory."


def benchmark_frontmatter_update(task_file: Path, iterations: int = 50) -> float:
    """Benchmarks frontmatter update round-trip execution latency in milliseconds."""
    start = time.perf_counter()
    for i in range(iterations):
        append_failure_record(
            task_file,
            reason=f"Benchmark failure iteration {i} violating ADR-0003",
            attempt_date="2026-09-30",
        )
    elapsed = time.perf_counter() - start
    return (elapsed / iterations) * 1000.0
