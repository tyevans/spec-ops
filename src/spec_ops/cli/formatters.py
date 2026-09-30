"""Structured machine-readable JSON formatters for SpecOps CLI inspection commands."""

from __future__ import annotations

import json
import re
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..backlog.health import HealthCheckReport
    from ..config.models import SpecOpsConfig
    from ..core.models import Task


def format_task_json(task: Task | None, config: SpecOpsConfig | None = None) -> str:
    """Formats a task into a structured JSON payload conforming to the domain Task schema."""
    if task is None:
        return json.dumps(
            {
                "status": "empty",
                "message": "No ready unblocked tasks found in backlog.",
                "task": None,
            },
            indent=2,
        )

    clean_id = task.canonical_id.lower().replace("task-", "").replace("spike-", "")
    prefix = config.execution.git_branch_prefix if config else "feat/"
    branch = task.branch or f"{prefix}task-{clean_id}"

    prompt_meta: dict[str, Any] = {
        "governing_adrs": list(task.governing_adrs),
        "governing_prds": list(task.governing_prds),
        "governing_stories": list(task.governing_stories),
        "preflight": list(config.quality.preflight) if config else ["pytest"],
        "allows_dependencies": bool(task.allows_dependencies),
        "file_length_limit": config.architecture.file_length_limit if config else 500,
        "testing_style": config.quality.testing_style if config else "blackbox-frontdoor",
    }

    payload = {
        "id": task.id,
        "canonical_id": task.canonical_id,
        "title": task.title,
        "status": task.status,
        "target_bc": task.target_bc,
        "target_release": task.target_release,
        "branch_name": branch,
        "branch": branch,
        "dependencies": list(task.dependencies),
        "governing_adrs": list(task.governing_adrs),
        "governing_prds": list(task.governing_prds),
        "governing_stories": list(task.governing_stories),
        "priority_rank": task.priority_rank,
        "prompt_metadata": prompt_meta,
    }
    return json.dumps(payload, indent=2)


def format_health_json(report: HealthCheckReport, config: SpecOpsConfig | None = None) -> str:
    """Formats repository invariant health check report as structured JSON."""
    mismatched_tasks: list[str] = []
    for err in report.sync_errors:
        found = re.findall(r"(?:TASK|SPIKE)-\d+", err, re.IGNORECASE)
        for tid in found:
            cid = tid.upper()
            if cid not in mismatched_tasks:
                mismatched_tasks.append(cid)

    violations_data = [
        {
            "path": str(v.path),
            "file": str(v.path),
            "lines": v.lines,
            "line_count": v.lines,
            "limit": v.limit,
            "rule": "ADR-0002",
        }
        for v in report.violations
    ]

    warnings_data = [
        {
            "path": str(w.path),
            "file": str(w.path),
            "lines": w.lines,
            "line_count": w.lines,
            "threshold": w.threshold,
            "limit": w.limit,
            "rule": "ADR-0002",
        }
        for w in report.warnings
    ]

    status = "ok" if report.is_healthy else "error"

    payload = {
        "status": status,
        "healthy": report.is_healthy,
        "violations": violations_data,
        "violation_count": len(violations_data),
        "warnings": warnings_data,
        "warning_count": len(warnings_data),
        "priority_sync": {
            "ok": report.priority_sync_ok,
            "errors": list(report.sync_errors),
            "mismatched_tasks": mismatched_tasks,
        },
        "constitution_warnings": list(report.constitution_drift_warnings),
        "backlog": {
            "completed_tasks": report.completed_tasks,
            "refined_tasks": report.refined_tasks,
            "proposed_tasks": report.proposed_tasks,
            "buffer_status": report.buffer_status,
        },
    }
    return json.dumps(payload, indent=2)


def format_profiles_info_json(config: SpecOpsConfig) -> str:
    """Formats active architectural profiles, rules, and preflight criteria as JSON."""
    active_profiles = ["core"]
    if config.quality.require_bdd:
        active_profiles.append("bdd")
    active_profiles.append("ddd")
    if config.security is not None or (config.root_dir / "docs" / "project" / "SECURITY.md").exists():
        active_profiles.append("security")

    invariants = [
        {
            "name": "file_length_limit",
            "rule": "ADR-0002",
            "limit": config.architecture.file_length_limit,
            "warning_threshold": config.architecture.file_warning_threshold,
            "description": "Source files must contain fewer than 500 lines.",
        },
        {
            "name": "blackbox_verification",
            "rule": "ADR-0003",
            "style": config.quality.testing_style,
            "description": "Blackbox frontdoor verification rules with zero private mocks.",
        },
        {
            "name": "backlog_isolation",
            "rule": "ADR-0005",
            "description": "Files under docs/project/backlog/ must not be modified on feature branches.",
        },
        {
            "name": "diataxis_documentation",
            "rule": "ADR-0008",
            "description": "Mandatory Diataxis documentation integrity requirements.",
        },
        {
            "name": "property_mutation_testing",
            "rule": "ADR-0009",
            "description": "Generative property tests (Hypothesis) and >=80% mutation kill score (Mutmut).",
        },
        {
            "name": "dependency_immutability",
            "rule": "ADR-0011",
            "description": "pyproject.toml and uv.lock are immutable unless allows_dependencies: true is explicitly declared.",
        },
    ]

    preflight_cmds = list(config.quality.preflight) or ["pytest"]
    preflight_chain = " && ".join(
        [f"uv run {cmd}" if not cmd.startswith("uv") else cmd for cmd in preflight_cmds]
    )

    payload = {
        "project": config.project.name,
        "active_profiles": active_profiles,
        "profiles": active_profiles,
        "invariants": invariants,
        "rules": {inv["name"]: inv for inv in invariants},
        "preflight": {
            "commands": preflight_cmds,
            "chain": preflight_chain,
        },
        "preflight_commands": preflight_cmds,
        "cli_entrypoints": {
            "queue_next": "spec-ops queue next --json",
            "worker_dry_run": "spec-ops worker --task TASK-XXXX --dry-run",
            "health_check": "spec-ops health --json",
            "profiles_info": "spec-ops profiles info --json",
            "rescue": "spec-ops rescue [task-id]",
        },
        "verification_criteria": [
            "Source files under 500 lines limit (ADR-0002)",
            "Public frontdoor blackbox testing with zero private mocks (ADR-0003)",
            "Lockfile immutability without prior frontmatter authorization (ADR-0011)",
            "Passing preflight command chain before completion",
        ],
    }
    return json.dumps(payload, indent=2)
