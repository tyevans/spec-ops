"""Autonomous Failure Memory Strategy Indexer and Healing Playbook Generator (ADR-0020, ADR-0004, PRD-0004, PRD-0006)."""

from __future__ import annotations

import argparse
import datetime
import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from ..config.models import SpecOpsConfig
from .memory import extract_failed_invariants, parse_task_memory


@dataclass
class HealingStrategy:
    """A prioritized remediation strategy for a recurring failure pattern."""

    strategy_id: str
    category: str
    failure_signature: str
    ranking_score: float
    summary: str
    actionable_remedy: str
    code_snippet: str = ""
    prompt_instruction: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class HealingPlaybook:
    """Categorized collection of healing strategies with ranked resolutions."""

    version: str = "1.0"
    indexed_at: str = field(default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat())
    strategies: list[HealingStrategy] = field(default_factory=list)

    @property
    def total_strategies(self) -> int:
        return len(self.strategies)

    def search(self, query: str | None = None) -> list[HealingStrategy]:
        """Filters strategies by query matching failure signatures, categories, or text."""
        if not query:
            return sorted(self.strategies, key=lambda s: (-s.ranking_score, s.strategy_id))

        q = query.strip().lower()
        matched = []
        for s in self.strategies:
            matchable = (
                f"{s.strategy_id} {s.category} {s.failure_signature} {s.summary} "
                f"{s.actionable_remedy} {s.prompt_instruction}"
            ).lower()
            if q in matchable:
                matched.append(s)
        return sorted(matched, key=lambda s: (-s.ranking_score, s.strategy_id))

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "indexed_at": self.indexed_at,
            "total_strategies": self.total_strategies,
            "strategies": [s.to_dict() for s in sorted(self.strategies, key=lambda x: (-x.ranking_score, x.strategy_id))],
        }

    def format_text(self, query: str | None = None) -> str:
        results = self.search(query)
        lines = [
            "=== Autonomous Failure Healing Playbook ===",
            f"Indexed Strategies: {len(results)} (Total Indexed: {self.total_strategies})",
        ]
        if query:
            lines.append(f"Query Filter: '{query}'")
        lines.append("")

        if not results:
            lines.append("ℹ️ No matching healing strategies found for given query.")
            return "\n".join(lines)

        for idx, s in enumerate(results, start=1):
            lines.append(f"{idx}. [{s.strategy_id}] {s.failure_signature} (Rank: {s.ranking_score:.1f})")
            lines.append(f"   Category: {s.category}")
            lines.append(f"   Summary:  {s.summary}")
            lines.append(f"   Remedy:   {s.actionable_remedy}")
            if s.prompt_instruction:
                lines.append(f"   Prompt:   \"{s.prompt_instruction}\"")
            if s.code_snippet:
                lines.append(f"   Example:  {s.code_snippet.strip()}")
            lines.append("")

        return "\n".join(lines)


BASELINE_STRATEGIES: list[HealingStrategy] = [
    HealingStrategy(
        strategy_id="strat-adr0002-file-length",
        category="file_length",
        failure_signature="ADR-0002: File length limit violation (>500 lines)",
        ranking_score=10.0,
        summary="Decompose monolithic module into single-responsibility submodules.",
        actionable_remedy="Run 'spec-ops decompose --suggest <file>' to analyze AST seams and extract cohesive logic.",
        code_snippet="uv run spec-ops decompose --suggest src/spec_ops/monolith.py",
        prompt_instruction="Keep all source files strictly under 400 lines by decomposing into focused helper modules.",
    ),
    HealingStrategy(
        strategy_id="strat-adr0003-mock-backdoors",
        category="mock_backdoor",
        failure_signature="ADR-0003: Prohibited mock backdoor or private internal monkeypatching",
        ranking_score=10.0,
        summary="Replace private internal mocks with public frontdoor CLI or model entrypoints.",
        actionable_remedy="Test observable outcomes through public interfaces without private mock backdoors.",
        code_snippet="result = subprocess.run([sys.executable, '-m', 'spec_ops.cli.main', '...'])",
        prompt_instruction="Never use unittest.mock or monkeypatch. Verify contracts solely through public interfaces.",
    ),
    HealingStrategy(
        strategy_id="strat-adr0005-backlog-isolation",
        category="backlog_isolation",
        failure_signature="ADR-0005: Modifying shared backlog files directly on feature branch",
        ranking_score=9.0,
        summary="Maintain strict backlog isolation; never modify docs/project/backlog on task branch.",
        actionable_remedy="Revert backlog edits in worktree. Run 'spec-ops queue complete <task-id>' on main to synchronize.",
        code_snippet="git checkout origin/main -- docs/project/backlog/",
        prompt_instruction="Do not touch docs/project/backlog/ on feature branches; backlog state transitions happen upon integration.",
    ),
    HealingStrategy(
        strategy_id="strat-adr0007-bounded-contexts",
        category="bounded_contexts",
        failure_signature="ADR-0007: Illegal cross-context private import or domain impurity",
        ranking_score=8.5,
        summary="Isolate pure domain models from presentation and infrastructure layers.",
        actionable_remedy="Run 'spec-ops architecture seams' to audit cross-context dependencies and eliminate private imports.",
        code_snippet="uv run spec-ops architecture seams --strict",
        prompt_instruction="Decouple domain models from visualizer and CLI layers. Never import private context internals.",
    ),
    HealingStrategy(
        strategy_id="strat-adr0009-mutation-testing",
        category="mutation_testing",
        failure_signature="ADR-0009: Mutation kill score below 80% threshold under mutmut",
        ranking_score=8.0,
        summary="Add boundary assertions and generative Hypothesis property tests for surviving mutants.",
        actionable_remedy="Run 'spec-ops test mutation <module>' and inspect surviving mutants to add missing assertions.",
        code_snippet="uv run spec-ops test mutation src/spec_ops/core/module.py",
        prompt_instruction="Assert boundary conditions, None handling, and operator inversions to ensure 100% mutant kill rate.",
    ),
    HealingStrategy(
        strategy_id="strat-adr0016-dual-custody",
        category="dual_custody",
        failure_signature="ADR-0016: Missing cryptographic commit signature or authorized review sign-off",
        ranking_score=8.0,
        summary="Sign commits cryptographically and record authorized human review sign-off before completion.",
        actionable_remedy="Run 'spec-ops review sign <task-id> --identity <email>' before running 'spec-ops queue complete'.",
        code_snippet="uv run spec-ops review sign <task-id> --identity 'Ty Evans <tyevans@gmail.com>'",
        prompt_instruction="Ensure git commit signing is active (commit.gpgsign=true) and obtain verified review sign-off.",
    ),
    HealingStrategy(
        strategy_id="strat-adr0018-lockfile-drift",
        category="lockfile_drift",
        failure_signature="ADR-0018: Lockfile immutability violation or unstaged dependency drift",
        ranking_score=7.5,
        summary="Discard unauthorized lockfile modifications and verify dependency lockfile integrity.",
        actionable_remedy="Run 'git checkout origin/main -- uv.lock' and verify with 'uv lock --check'.",
        code_snippet="uv lock --check",
        prompt_instruction="Never modify lockfiles without explicit human authorization. Revert lockfile changes.",
    ),
]


class StrategyIndexer:
    """Indexes historical failure post-mortems and synthesizes ranked healing strategies."""

    def __init__(self, root_dir: Path | str):
        self.root_dir = Path(root_dir).resolve()
        self.failures_dir = self.root_dir / ".specops" / "failures"

    def harvest_failure_entries(self) -> list[dict[str, Any]]:
        """Extracts failure records from .specops/failures/ and task files."""
        entries: list[dict[str, Any]] = []

        # 1. Check .specops/failures/ directory
        if self.failures_dir.is_dir():
            for f in self.failures_dir.glob("*.json"):
                try:
                    data = json.loads(f.read_text(encoding="utf-8"))
                    if isinstance(data, list):
                        entries.extend([item for item in data if isinstance(item, dict)])
                    elif isinstance(data, dict):
                        entries.append(data)
                except Exception:
                    continue

        # 2. Check task failure histories in backlog
        backlog_dir = self.root_dir / "docs" / "project" / "backlog"
        if backlog_dir.is_dir():
            for sub in ("complete", "refined", "proposed"):
                sub_p = backlog_dir / sub
                if not sub_p.is_dir():
                    continue
                for task_file in sub_p.glob("*.md"):
                    try:
                        content = task_file.read_text(encoding="utf-8")
                        _, _, histories = parse_task_memory(content)
                        for h in histories:
                            h["source_task"] = task_file.stem
                            entries.append(h)
                    except Exception:
                        continue

        return entries

    def compile_playbook(self) -> HealingPlaybook:
        """Compiles baseline and learned failure strategies into a prioritized playbook."""
        strategies_map = {s.strategy_id: HealingStrategy(**asdict(s)) for s in BASELINE_STRATEGIES}
        entries = self.harvest_failure_entries()

        # Score boosts from actual failures
        for entry in entries:
            reason = str(entry.get("reason", "") or entry.get("message", ""))
            invariants = list(entry.get("failed_invariants", [])) + extract_failed_invariants(reason)
            matched_any = False

            for s in strategies_map.values():
                if any(inv.lower() in s.strategy_id.lower() or inv.lower() in s.failure_signature.lower() for inv in invariants):
                    s.ranking_score += 1.0
                    matched_any = True
                elif s.category.lower() in reason.lower():
                    s.ranking_score += 0.5
                    matched_any = True

            # If unmapped custom failure signature, generate dynamic strategy
            if not matched_any and reason and len(reason) > 5:
                words = re.findall(r"[a-zA-Z0-9_-]+", reason)
                slug = "-".join(words[:4]).lower()
                strat_id = f"strat-custom-{slug}"
                if strat_id not in strategies_map:
                    strategies_map[strat_id] = HealingStrategy(
                        strategy_id=strat_id,
                        category="learned_failure",
                        failure_signature=reason[:80],
                        ranking_score=1.0,
                        summary=f"Remediation strategy for: {reason[:60]}...",
                        actionable_remedy=f"Inspect error trace and apply localized fix avoiding repeating: {reason[:100]}",
                        prompt_instruction=f"Avoid recurring error pattern: {reason[:120]}",
                    )
                else:
                    strategies_map[strat_id].ranking_score += 1.0

        return HealingPlaybook(
            indexed_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
            strategies=list(strategies_map.values()),
        )


def export_playbook(playbook: HealingPlaybook, out_path: Path | str) -> Path:
    """Exports compiled playbook to destination file as JSON or Markdown."""
    dest = Path(out_path).resolve()
    dest.parent.mkdir(parents=True, exist_ok=True)

    if dest.suffix.lower() == ".json":
        dest.write_text(json.dumps(playbook.to_dict(), indent=2) + "\n", encoding="utf-8")
        return dest

    # Markdown export
    lines = [
        "# SpecOps Autonomous Failure Healing Playbook",
        "",
        f"**Indexed at**: `{playbook.indexed_at}`  ",
        f"**Total Strategies**: `{playbook.total_strategies}`",
        "",
        "## Remediation Strategies",
        "",
    ]
    for idx, s in enumerate(sorted(playbook.strategies, key=lambda x: (-x.ranking_score, x.strategy_id)), start=1):
        lines.append(f"### {idx}. {s.failure_signature} (`{s.strategy_id}`)")
        lines.append(f"- **Category**: `{s.category}`")
        lines.append(f"- **Ranking Score**: `{s.ranking_score:.1f}`")
        lines.append(f"- **Summary**: {s.summary}")
        lines.append(f"- **Actionable Remedy**: {s.actionable_remedy}")
        if s.prompt_instruction:
            lines.append(f"- **Prompt Directive**: *\"{s.prompt_instruction}\"*")
        if s.code_snippet:
            lines.append("```bash")
            lines.append(s.code_snippet.strip())
            lines.append("```")
        lines.append("")

    dest.write_text("\n".join(lines), encoding="utf-8")
    return dest


def handle_playbooks_command(args: argparse.Namespace, config: SpecOpsConfig) -> int:
    """CLI dispatcher for 'spec-ops rescue playbooks [--query <pattern>] [--json] [--export <path>]'."""
    indexer = StrategyIndexer(config.root_dir)
    playbook = indexer.compile_playbook()

    query = getattr(args, "query", None)
    json_output = getattr(args, "json", False)
    export_dest = getattr(args, "export", None)

    if export_dest:
        dest_p = export_playbook(playbook, export_dest)
        print(f"✅ Exported autonomous healing playbook to {dest_p}")

    if json_output:
        if query:
            filtered = playbook.search(query)
            payload = {
                "version": playbook.version,
                "query": query,
                "total_matched": len(filtered),
                "strategies": [s.to_dict() for s in filtered],
            }
            print(json.dumps(payload, indent=2))
        else:
            print(json.dumps(playbook.to_dict(), indent=2))
        return 0

    print(playbook.format_text(query=query))
    return 0
