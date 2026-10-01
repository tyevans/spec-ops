"""Autonomous failure post-mortem clustering and prompt anti-loop synthesizer (PRD-0004, US-0084, ADR-0020)."""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from .memory import parse_task_memory


@dataclass
class ClusteredFailureEntry:
    """Individual failure event extracted from task history or worktree logs."""

    task_id: str
    reason: str
    attempt_date: str = ""
    timestamp: str = ""
    worker_id: str = ""
    failed_invariants: list[str] = field(default_factory=list)
    source: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class FailureArchetype:
    """Categorical archetype defining failure detection patterns and prohibitions."""

    archetype_id: str
    name: str
    invariant_id: str
    mandate: str
    prohibition: str
    regex: re.Pattern
    keywords: list[str] = field(default_factory=list)


ARCHETYPES: list[FailureArchetype] = [
    FailureArchetype(
        archetype_id="mock_backdoors",
        name="Mock Backdoor Tampering",
        invariant_id="ADR-0003",
        mandate="You must strictly use public frontdoor entrypoints with zero mock backdoors.",
        prohibition="Strictly forbidding mocks, monkeypatching, and private backdoor tampering. All tests must exercise public interfaces.",
        regex=re.compile(r"\bADR-0003\b|mock\b|monkeypatch\b|patch\.object|unittest\.mock|pytest_mock|mocker\.patch|MagicMock|prohibited_mock|mock backdoor|internal tampering", re.I),
        keywords=["mock", "monkeypatch", "patch", "magicmock", "backdoor", "tampering"],
    ),
    FailureArchetype(
        archetype_id="line_length",
        name="Line Length / Modularity Violations",
        invariant_id="ADR-0002",
        mandate="You must decompose source files to stay strictly under 500 lines (and warn at >=400 lines) with single-responsibility modules.",
        prohibition="Strictly forbidding monolithic files exceeding file length limits; decompose into modular single-responsibility files.",
        regex=re.compile(r"\bADR-0002\b|file length|500 lines|400 lines|exceeds? (?:file )?limit|lines > limit 500|modularity", re.I),
        keywords=["file length", "line limit", "500 lines", "400 lines", "modularity"],
    ),
    FailureArchetype(
        archetype_id="credential_leaks",
        name="Credential / Secret Leaks",
        invariant_id="ADR-0019",
        mandate="You must never hardcode credentials, secrets, or high-entropy tokens.",
        prohibition="Strictly forbidding hardcoding API keys, secrets, credentials, or high-entropy tokens.",
        regex=re.compile(r"\bADR-0019\b|secret(?:s)?\b|credential(?:s)?\b|high-entropy|api[-_ ]key|token leak|exposed secrets?", re.I),
        keywords=["secret", "credential", "token", "api key", "high-entropy"],
    ),
    FailureArchetype(
        archetype_id="supply_chain",
        name="Supply-Chain / Lockfile Drift",
        invariant_id="ADR-0018",
        mandate="You must not edit lockfiles or dependencies without explicit authorization.",
        prohibition="Strictly forbidding unapproved modifications to lockfiles (uv.lock, package-lock.json) or dependencies.",
        regex=re.compile(r"\bADR-0018\b|lockfile|uv\.lock|package-lock\.json|dependency drift|lockfile mutation|supply[- ]chain", re.I),
        keywords=["lockfile", "uv.lock", "dependency drift", "supply-chain"],
    ),
    FailureArchetype(
        archetype_id="dependency_cycles",
        name="Dependency Cycles / Topological Deadlocks",
        invariant_id="ADR-0017",
        mandate="You must break DAG dependency cycles and maintain a strict acyclic task dependency graph.",
        prohibition="Strictly forbidding circular dependencies and topological deadlocks in task backlog.",
        regex=re.compile(r"\bADR-0017\b|dependency cycle|deadlock\b|circular dependency|tarjan|cycle detected|topological deadlock", re.I),
        keywords=["cycle", "deadlock", "circular dependency", "tarjan"],
    ),
]

GENERIC_ARCHETYPE = FailureArchetype(
    archetype_id="generic_churn",
    name="Generic / Operational Churn",
    invariant_id="ADR-0020",
    mandate="You must avoid repeating the described failure pattern and strictly adhere to project invariants.",
    prohibition="Strictly forbidding repetition of previously failed operational approaches.",
    regex=re.compile(r".*", re.DOTALL),
    keywords=[],
)


@dataclass
class FailureCluster:
    """Clustered grouping of recurrent failure entries sharing an archetype."""

    archetype_id: str
    name: str
    invariant_id: str
    mandate: str
    prohibition: str
    entries: list[ClusteredFailureEntry] = field(default_factory=list)

    @property
    def count(self) -> int:
        return len(self.entries)

    @property
    def task_ids(self) -> list[str]:
        seen: set[str] = set()
        result: list[str] = []
        for e in self.entries:
            if e.task_id and e.task_id not in seen:
                seen.add(e.task_id)
                result.append(e.task_id)
        return result

    def to_dict(self) -> dict[str, Any]:
        return {
            "archetype_id": self.archetype_id,
            "name": self.name,
            "invariant_id": self.invariant_id,
            "mandate": self.mandate,
            "prohibition": self.prohibition,
            "count": self.count,
            "task_ids": self.task_ids,
            "entries": [e.to_dict() for e in self.entries],
        }


def classify_failure_entry(entry: ClusteredFailureEntry) -> FailureArchetype:
    """Classifies a failure entry into an archetype deterministically."""
    inv_upper = {str(inv).upper() for inv in entry.failed_invariants}
    for arch in ARCHETYPES:
        if arch.invariant_id in inv_upper:
            return arch

    reason_text = entry.reason or ""
    for arch in ARCHETYPES:
        if arch.regex.search(reason_text):
            return arch

    reason_lower = reason_text.lower()
    for arch in ARCHETYPES:
        for kw in arch.keywords:
            if kw.lower() in reason_lower:
                return arch

    return GENERIC_ARCHETYPE


def cluster_failure_entries(
    entries: list[ClusteredFailureEntry],
    include_empty: bool = False,
) -> list[FailureCluster]:
    """Clusters failure entries into archetypes deterministically."""
    all_archetypes = list(ARCHETYPES) + [GENERIC_ARCHETYPE]
    cluster_map: dict[str, FailureCluster] = {
        arch.archetype_id: FailureCluster(
            archetype_id=arch.archetype_id,
            name=arch.name,
            invariant_id=arch.invariant_id,
            mandate=arch.mandate,
            prohibition=arch.prohibition,
            entries=[],
        )
        for arch in all_archetypes
    }

    for entry in entries:
        arch = classify_failure_entry(entry)
        cluster_map[arch.archetype_id].entries.append(entry)

    if include_empty:
        return [cluster_map[arch.archetype_id] for arch in all_archetypes]
    return [cluster_map[arch.archetype_id] for arch in all_archetypes if cluster_map[arch.archetype_id].count > 0]


def collect_backlog_failures(backlog_dir: Path, repo_root: Path | None = None) -> list[ClusteredFailureEntry]:
    """Collects failure_history entries across tasks and worktree failure logs."""
    entries: list[ClusteredFailureEntry] = []
    seen_keys: set[tuple[str, str, str]] = set()

    if backlog_dir and backlog_dir.exists():
        task_files: list[Path] = []
        for sub in ("refined", "proposed", "complete"):
            folder = backlog_dir / sub
            if folder.exists():
                task_files.extend(folder.glob("*.md"))
        if not task_files:
            task_files = list(backlog_dir.glob("*.md"))

        for path in sorted(task_files):
            try:
                content = path.read_text(encoding="utf-8")
                meta, _, history = parse_task_memory(content)
            except Exception:
                continue

            raw_id = str(meta.get("id", ""))
            clean_id = raw_id.upper().replace("TASK-", "").lstrip("0")
            tid_num = clean_id.zfill(4) if clean_id else "0000"
            canonical_id = f"TASK-{tid_num}" if raw_id else path.stem.upper()

            for item in history:
                if not isinstance(item, dict):
                    continue
                reason = str(item.get("reason", "")).strip()
                attempt_date = str(item.get("attempt_date", ""))
                timestamp = str(item.get("timestamp", ""))
                worker_id = str(item.get("worker_id", ""))
                invariants = item.get("failed_invariants", [])
                if isinstance(invariants, str):
                    invariants = [invariants]

                key = (canonical_id, reason, attempt_date or timestamp)
                if key not in seen_keys:
                    seen_keys.add(key)
                    entries.append(
                        ClusteredFailureEntry(
                            task_id=canonical_id,
                            reason=reason,
                            attempt_date=attempt_date,
                            timestamp=timestamp,
                            worker_id=worker_id,
                            failed_invariants=list(invariants),
                            source=str(path),
                        )
                    )

    if repo_root and (repo_root / ".worktrees").exists():
        wt_dir = repo_root / ".worktrees"
        for p in sorted(wt_dir.iterdir()):
            if not p.is_dir():
                continue
            m = re.search(r"task-?(\d+)", p.name, re.IGNORECASE)
            wt_tid = f"TASK-{m.group(1).zfill(4)}" if m else p.name.upper()

            for cand in [p / ".failure.log", p / ".worker.json"]:
                if not cand.is_file():
                    continue
                try:
                    text = cand.read_text(encoding="utf-8", errors="ignore").strip()
                except Exception:
                    continue
                if not text:
                    continue
                reason = text
                if cand.suffix == ".json":
                    try:
                        data = json.loads(text)
                        reason = str(data.get("failure_log") or data.get("error") or "").strip()
                    except Exception:
                        continue
                if not reason:
                    continue
                key = (wt_tid, reason[:100], "")
                if key not in seen_keys:
                    seen_keys.add(key)
                    entries.append(ClusteredFailureEntry(task_id=wt_tid, reason=reason, source=str(cand)))

    return entries


def synthesize_fleet_negative_constraints(clusters: list[FailureCluster]) -> str:
    """Synthesizes markdown negative prompt constraints section from failure clusters."""
    active_clusters = [c for c in clusters if c.count > 0]
    if not active_clusters:
        return ""

    lines: list[str] = ["## Prior Fleet Failures & Prohibitions"]
    for c in active_clusters:
        lines.append(f"- {c.name} ({c.invariant_id}): {c.mandate}")
        lines.append(f"  - Prohibition: {c.prohibition}")
        lines.append(f"  - Fleet impact: Observed {c.count} failure(s) across tasks: {', '.join(c.task_ids)}.")

    return "\n".join(lines) + "\n"


def format_fleet_failure_prompt(
    backlog_dir: Path | list[FailureCluster] | None = None,
    task: Any = None,
    repo_root: Path | None = None,
) -> str:
    """Hydrates prompt negative constraints section from fleet failure clusters."""
    if isinstance(backlog_dir, list):
        clusters = backlog_dir
    elif isinstance(backlog_dir, Path):
        entries = collect_backlog_failures(backlog_dir, repo_root=repo_root)
        clusters = cluster_failure_entries(entries, include_empty=False)
    else:
        default_dir = Path("docs/project/backlog")
        if default_dir.exists():
            entries = collect_backlog_failures(default_dir, repo_root=repo_root)
            clusters = cluster_failure_entries(entries, include_empty=False)
        else:
            return ""

    if not clusters:
        return ""

    if task and hasattr(task, "governing_adrs") and task.governing_adrs:
        task_adrs = {str(a).upper() for a in task.governing_adrs}
        clusters = sorted(clusters, key=lambda c: 0 if c.invariant_id in task_adrs else 1)

    return synthesize_fleet_negative_constraints(clusters)


def handle_cluster_cli(config: Any, args: Any) -> int:
    """CLI handler for spec-ops rescue cluster subcommand."""
    task_filter = getattr(args, "task", None)
    is_json = getattr(args, "json", False)

    backlog_dir = getattr(config, "backlog_dir", None) or Path("docs/project/backlog")
    repo_root = getattr(config, "root_dir", None)

    entries = collect_backlog_failures(backlog_dir, repo_root=repo_root)

    if task_filter:
        clean = task_filter.upper().replace("TASK-", "").lstrip("0")
        tid_num = clean.zfill(4) if clean else "0000"
        canonical_id = f"TASK-{tid_num}"
        entries = [e for e in entries if e.task_id.upper() == canonical_id or clean in e.task_id.upper()]

    clusters = cluster_failure_entries(entries, include_empty=False)
    negative_constraints = synthesize_fleet_negative_constraints(clusters)

    if is_json:
        payload: dict[str, Any] = {
            "total_failures": len(entries),
            "cluster_count": len(clusters),
            "clusters": [c.to_dict() for c in clusters],
            "negative_constraints": negative_constraints,
        }
        if task_filter:
            payload["task_id"] = task_filter
        print(json.dumps(payload, indent=2))
        return 0

    if not entries:
        msg = f"No failure history records found for {task_filter}." if task_filter else "No failure history records found across backlog."
        print(f"ℹ️  {msg}")
        return 0

    print("=== Fleet Failure Post-Mortem Clusters ===")
    print(f"Total recorded failures: {len(entries)} across {len(clusters)} cluster(s)\n")

    for c in clusters:
        tasks_str = ", ".join(c.task_ids) if c.task_ids else "None"
        print(f"🔴 {c.name} ({c.invariant_id}) — {c.count} failure(s) [Tasks: {tasks_str}]")
        print(f"   Mandate: {c.mandate}")
        if c.entries:
            print("   Sample reasons:")
            for sample in c.entries[:3]:
                print(f"     - {sample.reason}")
        print()

    if negative_constraints.strip():
        print(negative_constraints)

    return 0
