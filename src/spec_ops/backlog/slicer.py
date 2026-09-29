"""Autonomous task slicer for decomposing oversized monolithic tasks into vertical slices and spikes."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..config.models import SpecOpsConfig
from ..core.models import PRD, Task
from ..core.parser import parse_prd


@dataclass
class TaskSliceResult:
    """Outcome of slicing an oversized task into thin vertical slices."""

    parent_id: str
    spike_task: Task | None
    child_slices: list[Task] = field(default_factory=list)
    promoted_task: Task | None = None
    all_outcomes: list[str] = field(default_factory=list)

    @property
    def total_child_tasks(self) -> int:
        count = len(self.child_slices)
        if self.spike_task:
            count += 1
        return count


class AutonomousTaskSlicer:
    """Decomposes oversized tasks (>500 lines or multi-BC) into INVEST-compliant thin slices."""

    def __init__(self, config: SpecOpsConfig):
        self.config = config
        self.backlog_dir = config.backlog_dir
        self.proposed_dir = self.backlog_dir / "proposed"
        self.refined_dir = self.backlog_dir / "refined"
        self.docs_dir = config.docs_dir

    def estimate_task_lines(self, task: Task) -> int:
        """Estimates line scope of a task based on explicit markers, content, or context."""
        # Check explicit markers
        m = re.search(r"estimated_lines:\s*(\d+)", task.body, re.IGNORECASE)
        if m:
            return int(m.group(1))

        # Check explicit mentions of >500 lines
        if re.search(r"(?:exceed[s]?|over|>)\s*(?:the\s*)?500\s*(?:-line|lines)", task.body, re.IGNORECASE):
            return 600

        # Count outcomes or requirements
        outcomes = self.extract_task_outcomes(task)
        if len(outcomes) > 4:
            return 120 * len(outcomes)

        # Check multi-BC indicator
        if "," in task.target_bc or len(task.target_bc.split()) > 1:
            return 550

        # Fallback to body line estimation
        body_lines = len(task.body.strip().splitlines())
        if body_lines > 50:
            return 450
        return 250

    def touches_multiple_bounded_contexts(self, task: Task) -> bool:
        """Determines if task touches multiple bounded contexts."""
        if "," in task.target_bc or len(task.target_bc.split()) > 1:
            return True
        bc_match = re.search(r"(?:touches|across|multiple)\s+bounded\s+contexts", task.body, re.IGNORECASE)
        if bc_match:
            return True
        return False

    def needs_slicing(self, task: Task) -> bool:
        """Audits whether a task exceeds modular boundaries or touches multiple contexts."""
        estimated = self.estimate_task_lines(task)
        multi_bc = self.touches_multiple_bounded_contexts(task)
        return estimated >= 400 or multi_bc

    def extract_task_outcomes(self, task: Task) -> list[str]:
        """Extracts checkable outcomes from governing PRD or task body."""
        outcomes: list[str] = []

        # 1. From governing PRDs
        if task.governing_prds and self.docs_dir.exists():
            for prd_id in task.governing_prds:
                clean = prd_id.replace("PRD-", "").lstrip("0")
                target_pat = re.compile(rf"prd-0*{clean}-", re.IGNORECASE)
                prd_dir = self.docs_dir / "product"
                if prd_dir.exists():
                    for p in prd_dir.rglob("*.md"):
                        if target_pat.search(p.name):
                            prd = parse_prd(p)
                            if prd.outcomes:
                                outcomes.extend(prd.outcomes)

        # 2. From task body specifically under Checkable Outcomes
        if not outcomes:
            m_sec = re.search(r"##\s*Checkable\s+Outcomes\s*\n(.*?)(?=\n##|\Z)", task.body, re.DOTALL | re.IGNORECASE)
            if m_sec:
                matches = re.findall(r"(?:^\s*[-*]|\d+\.)\s+(.+)$", m_sec.group(1), re.MULTILINE)
                clean_matches = [m.strip() for m in matches if len(m.strip()) > 5]
                if clean_matches:
                    outcomes.extend(clean_matches)

        # 3. Fallback to bullet matches in body
        if not outcomes:
            matches = re.findall(r"(?:^\s*[-*]|\d+\.)\s+(.+)$", task.body, re.MULTILINE)
            clean_matches = [m.strip() for m in matches if len(m.strip()) > 10 and not m.strip().startswith("TASK-")]
            if clean_matches:
                outcomes.extend(clean_matches)

        # 4. Default fallback outcome
        if not outcomes:
            outcomes = [
                f"Verify core domain logic for {task.title}",
                f"Verify public frontdoors and CLI integration for {task.title}",
                f"Verify blackbox acceptance and health invariants for {task.title}",
            ]

        # Preserve uniqueness while maintaining order
        return list(dict.fromkeys(outcomes))

    def get_max_task_number(self) -> int:
        """Finds highest existing task number across all backlog folders."""
        max_id = 0
        if self.backlog_dir.exists():
            for p in self.backlog_dir.rglob("*.md"):
                m = re.match(r"^(\d+)", p.stem)
                if m:
                    max_id = max(max_id, int(m.group(1)))
        return max_id

    def slice_task(
        self,
        task: Task,
        include_spike: bool = True,
        next_task_num: int | None = None,
    ) -> TaskSliceResult:
        """Decomposes an oversized task into discrete thin vertical slices and an architectural spike."""
        all_outcomes = self.extract_task_outcomes(task)
        curr_num = (next_task_num if next_task_num is not None else self.get_max_task_number())

        spike_task: Task | None = None
        child_slices: list[Task] = []

        # 1. Synthesize Architectural Spike if requested
        if include_spike:
            curr_num += 1
            spike_id = f"TASK-{curr_num:04d}"
            spike_title = f"Architectural Spike: {task.title}"
            spike_slug = "".join(c if c.isalnum() else "-" for c in spike_title.lower()).strip("-")[:40]
            spike_path = self.proposed_dir / f"{curr_num:04d}-{spike_slug}.md"

            spike_body = f"""## Summary
Investigate architectural boundaries, evaluate interface trade-offs, and prototype foundational contracts for {task.title}.

## Problem Statement
Mitigate architectural uncertainty and validate thin vertical slice decomposition before executing implementation slices.

estimated_lines: 150

## Checkable Outcomes
- Validate domain interfaces and data schemas across target bounded contexts.
- Benchmark and verify public frontdoor integration boundaries.
- Ensure all downstream slices remain strictly under 400 lines (ADR-0002).

## Definition of Done (Blackbox Frontdoor TDD)
1. Architectural investigation and prototype verification complete.
2. Verified through public frontdoor tests with 0 backdoor mocks (ADR-0003).
"""
            spike_task = Task(
                id=f"{curr_num:04d}",
                title=spike_title,
                status="Proposed",
                dependencies=list(task.dependencies),
                governing_adrs=list(task.governing_adrs),
                governing_prds=list(task.governing_prds),
                governing_stories=list(task.governing_stories),
                target_bc=task.target_bc.split(",")[0].strip() or "core",
                body=spike_body,
                file_path=spike_path,
            )

        # 2. Decompose outcomes across discrete vertical slices (<400 lines each)
        # Partition outcomes into chunks of at most 2 outcomes per slice
        chunk_size = max(1, min(2, (len(all_outcomes) + 1) // 2))
        outcome_chunks: list[list[str]] = []
        for i in range(0, len(all_outcomes), chunk_size):
            outcome_chunks.append(all_outcomes[i : i + chunk_size])

        if not outcome_chunks:
            outcome_chunks = [[f"Implement {task.title} contracts"]]

        slice_themes = [
            ("Domain Substrate & Core Invariants", "core"),
            ("Frontdoor API & Workflow Execution", "cli"),
            ("Verification Harness & Acceptance Guardrails", "backlog"),
        ]

        prev_id = spike_task.canonical_id if spike_task else (task.dependencies[0] if task.dependencies else "")

        for idx, chunk in enumerate(outcome_chunks):
            curr_num += 1
            tid = f"TASK-{curr_num:04d}"
            theme_title, theme_bc = slice_themes[idx % len(slice_themes)]
            s_title = f"{task.title} — {theme_title}"
            s_slug = "".join(c if c.isalnum() else "-" for c in s_title.lower()).strip("-")[:40]
            s_path = self.proposed_dir / f"{curr_num:04d}-{s_slug}.md"

            chunk_outcomes_str = "\n".join(f"- {o}" for o in chunk)
            s_body = f"""## Summary
Implement vertical slice {idx + 1}: {theme_title} for {task.title}.

## Problem Statement
Deliver focused vertical slice satisfying INVEST criteria and Hard Invariant (<500 lines).

estimated_lines: 200

## Checkable Outcomes
{chunk_outcomes_str}

## Definition of Done (Blackbox Frontdoor TDD)
1. Observable contracts exercised through public frontdoors without backdoor tampering.
2. Generative property tests verify domain invariants across randomized inputs.
3. Source file length strictly beneath modular boundaries (<400 lines).
"""
            deps = [prev_id] if prev_id else []
            child_slice = Task(
                id=f"{curr_num:04d}",
                title=s_title,
                status="Proposed",
                dependencies=deps,
                governing_adrs=list(task.governing_adrs),
                governing_prds=list(task.governing_prds),
                governing_stories=list(task.governing_stories),
                target_bc=task.target_bc.split(",")[0].strip() or theme_bc,
                body=s_body,
                file_path=s_path,
            )
            child_slices.append(child_slice)
            prev_id = tid

        # Initial thin slice or spike to promote
        promoted = spike_task if spike_task else (child_slices[0] if child_slices else None)

        return TaskSliceResult(
            parent_id=task.canonical_id,
            spike_task=spike_task,
            child_slices=child_slices,
            promoted_task=promoted,
            all_outcomes=all_outcomes,
        )

    def write_sliced_tasks(self, slice_result: TaskSliceResult, original_task: Task) -> list[Path]:
        """Scaffolds child tasks to proposed/ and updates PRIORITY.md, replacing original task."""
        from .queue import write_task_file

        self.proposed_dir.mkdir(parents=True, exist_ok=True)
        created_paths: list[Path] = []
        all_child_tasks: list[Task] = []

        if slice_result.spike_task:
            all_child_tasks.append(slice_result.spike_task)
        all_child_tasks.extend(slice_result.child_slices)

        for child in all_child_tasks:
            p = write_task_file(child)
            created_paths.append(p)

        # Update PRIORITY.md: Replace original parent task entry with sequential child tasks
        priority_file = self.backlog_dir / "PRIORITY.md"
        if priority_file.exists():
            content = priority_file.read_text(encoding="utf-8")
            replacement_entries: list[str] = []
            for child in all_child_tasks:
                rel = f"proposed/{child.file_path.name}"
                replacement_entries.append(f"- **{child.canonical_id} (Proposed)**: [`{child.slug}`]({rel})")

            parent_id = original_task.canonical_id
            pattern = re.compile(rf"- \*\*{parent_id}[^\n]+\n?", re.IGNORECASE)
            if pattern.search(content):
                updated = pattern.sub("\n".join(replacement_entries) + "\n", content)
                priority_file.write_text(updated, encoding="utf-8")
            else:
                # Append if parent not found in priority
                priority_file.write_text(content.strip() + "\n" + "\n".join(replacement_entries) + "\n", encoding="utf-8")

        # Remove or supersede parent proposed file
        if original_task.file_path.exists():
            try:
                original_task.file_path.unlink()
            except OSError:
                pass

        return created_paths
