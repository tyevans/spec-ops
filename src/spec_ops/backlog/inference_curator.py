"""Inference-driven backlog curation and cognitive refinement engine."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..config.models import SpecOpsConfig
from ..core.models import Task
from ..core.parser import parse_prd
from .queue import BacklogQueue, write_task_file
from .reconciler import ArchitecturalReconciler
from .slicer import AutonomousTaskSlicer, TaskSliceResult


@dataclass
class InferenceCurationResult:
    """Outcome of an inference-driven backlog curation pass."""

    initial_refined_count: int
    target_buffer: int
    tasks_refined: list[str] = field(default_factory=list)
    tasks_sliced: list[str] = field(default_factory=list)
    tasks_reconciled: list[str] = field(default_factory=list)
    audit_trail: list[str] = field(default_factory=list)
    diff_output: str = ""
    dry_run: bool = False
    message: str = ""


class InferenceCurator:
    """Evaluates proposed tasks against codebase reality, reconciles drift, slices scope, and synthesizes DoR."""

    def __init__(self, config: SpecOpsConfig, model: str | None = None):
        self.config = config
        self.model = model or getattr(config.execution, "default_model", "gemini-1.5-flash")
        self.queue = BacklogQueue(config.backlog_dir)
        self.reconciler = ArchitecturalReconciler(config.root_dir)
        self.slicer = AutonomousTaskSlicer(config)
        self.target_buffer = config.architecture.buffer_target
        self.docs_dir = config.docs_dir

    def synthesize_dor_criteria(self, task: Task) -> tuple[str, bool]:
        """Synthesizes executable Gherkin scenarios and Hypothesis invariants if missing."""
        body = task.body
        modified = False
        additions: list[str] = []

        # 1. Gherkin Scenarios
        has_gherkin = bool(re.search(r"```gherkin[\s\S]*?(Given\s+[\s\S]*?When\s+[\s\S]*?Then\s+[\s\S]*?)```", body, re.IGNORECASE))
        if not has_gherkin:
            outcomes = self.slicer.extract_task_outcomes(task)
            scenarios: list[str] = []
            for idx, outcome in enumerate(outcomes[:3], start=1):
                clean_outcome = outcome.rstrip(".")
                scenarios.append(
                    f"### Scenario {idx}: {clean_outcome}\n"
                    f"```gherkin\n"
                    f"Given the system is initialized and ready\n"
                    f"When the user executes the workflow for \"{task.title}\"\n"
                    f"Then {clean_outcome}\n"
                    f"And observable outputs satisfy public contracts without backdoor tampering.\n"
                    f"```"
                )
            if not scenarios:
                scenarios.append(
                    f"### Scenario 1: Primary User Journey\n"
                    f"```gherkin\n"
                    f"Given the public frontdoor is initialized\n"
                    f"When the user executes \"{task.title}\"\n"
                    f"Then observable contracts are verified through public entry points.\n"
                    f"```"
                )
            additions.append("## Acceptance Criteria\n\n" + "\n\n".join(scenarios))
            modified = True

        # 2. Hypothesis Invariants
        has_hypothesis = bool(re.search(r"(?:@given|Hypothesis\s+Invariant)", body, re.IGNORECASE))
        if not has_hypothesis:
            additions.append(
                "## Hypothesis Invariant Properties\n\n"
                "- `@given(...)`: Generative invariant verification asserting that valid domain operations "
                "preserve state consistency across randomized inputs without shrinking failures."
            )
            modified = True

        if modified:
            new_body = body.rstrip() + "\n\n" + "\n\n".join(additions) + "\n"
            return new_body, True

        return body, False

    def curate(self, dry_run: bool = False) -> InferenceCurationResult:
        """Executes cognitive curation sweep."""
        all_tasks = self.queue.list_all_tasks()
        refined_tasks = [t for t in all_tasks if t.status in ("Refined", "Ready")]
        proposed_tasks = [t for t in all_tasks if t.status == "Proposed"]
        completed_ids = self.queue.get_completed_task_ids()

        needed = max(0, self.target_buffer - len(refined_tasks))
        proposed_tasks.sort(key=lambda t: t.priority_rank)

        tasks_refined: list[str] = []
        tasks_sliced: list[str] = []
        tasks_reconciled: list[str] = []
        audit_trail: list[str] = []
        diff_lines: list[str] = []

        diff_lines.append(f"=== SpecOps Inference Curation Audit {'(DRY RUN)' if dry_run else ''} ===")
        diff_lines.append(f"Target Buffer: {self.target_buffer} | Current Refined: {len(refined_tasks)} | Proposed Candidates: {len(proposed_tasks)}\n")

        for task in proposed_tasks:
            # Check dependencies
            deps_satisfied = all(
                (f"TASK-{d.split('-')[-1].zfill(4)}" if d.split('-')[-1].isdigit() else d) in completed_ids
                for d in task.dependencies
            )

            # A. Scope Violation Audit & Slicing
            if self.slicer.needs_slicing(task):
                slice_res = self.slicer.slice_task(task, include_spike=True)
                child_count = slice_res.total_child_tasks
                child_ids = [c.canonical_id for c in ([slice_res.spike_task] if slice_res.spike_task else []) + slice_res.child_slices]
                msg = f"Task {task.canonical_id} exceeds modular limits (>500 lines or multi-BC). Decomposed into {child_count} thin slices: {', '.join(child_ids)}."
                diff_lines.append(f"[SCOPE SLICING] {msg}")

                if not dry_run:
                    self.slicer.write_sliced_tasks(slice_res, task)
                    tasks_sliced.append(task.canonical_id)
                    audit_trail.append(msg)

                    # Promote the initial thin slice or spike to refined if needed
                    if needed > 0 and slice_res.promoted_task and deps_satisfied:
                        promoted_dest = self.queue.refine_task(slice_res.promoted_task)
                        tasks_refined.append(slice_res.promoted_task.canonical_id)
                        needed -= 1
                        audit_trail.append(f"Promoted initial thin slice {slice_res.promoted_task.canonical_id} to refined/.")
                else:
                    if slice_res.promoted_task:
                        diff_lines.append(f"  -> Would promote initial slice {slice_res.promoted_task.canonical_id} to refined/ buffer.")
                continue

            # B. Architectural Drift Reconciliation
            rec_result = self.reconciler.reconcile_task(task)
            current_task = rec_result.task

            if rec_result.modified:
                diff_lines.append(f"[ARCHITECTURAL DRIFT] {task.canonical_id}:")
                for ch in rec_result.diff.changes:
                    diff_lines.append(f"  ✓ {ch.change_type.upper()}: {ch.target} — {ch.details}")
                if not dry_run:
                    write_task_file(current_task)
                    tasks_reconciled.append(task.canonical_id)
                    audit_trail.append(f"Reconciled {task.canonical_id}: {len(rec_result.diff.changes)} architectural changes updated.")

            # C. Definition of Ready (DoR) Synthesis
            new_body, dor_synthesized = self.synthesize_dor_criteria(current_task)
            if dor_synthesized:
                diff_lines.append(f"[DoR SYNTHESIS] {task.canonical_id}: Missing executable Gherkin scenarios or Hypothesis invariants synthesized.")
                if not dry_run:
                    current_task.body = new_body
                    write_task_file(current_task)
                    audit_trail.append(f"Synthesized DoR executable Gherkin scenarios & Hypothesis invariants for {task.canonical_id}.")

            # D. Buffer Promotion
            if needed > 0 and deps_satisfied:
                if not dry_run:
                    self.queue.refine_task(current_task)
                    tasks_refined.append(current_task.canonical_id)
                    needed -= 1
                    audit_trail.append(f"Promoted unblocked task {current_task.canonical_id} to refined/ buffer.")
                else:
                    diff_lines.append(f"[BUFFER PROMOTION] Candidate {task.canonical_id} ready for promotion to refined/ buffer.")

        diff_summary = "\n".join(diff_lines)
        if dry_run:
            msg = f"Inference curation dry-run complete. {len(proposed_tasks)} candidates inspected."
        else:
            msg = (
                f"Inference curation complete. Refined: {len(tasks_refined)}, "
                f"Sliced: {len(tasks_sliced)}, Reconciled: {len(tasks_reconciled)}."
            )

        return InferenceCurationResult(
            initial_refined_count=len(refined_tasks),
            target_buffer=self.target_buffer,
            tasks_refined=tasks_refined,
            tasks_sliced=tasks_sliced,
            tasks_reconciled=tasks_reconciled,
            audit_trail=audit_trail,
            diff_output=diff_summary,
            dry_run=dry_run,
            message=msg,
        )
