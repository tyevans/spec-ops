"""Generative property-based tests for standup digest invariants.

Governed by ADR-0001, ADR-0002, ADR-0003, ADR-0007, ADR-0009; PRD-0005; US-0077.
Asserts zero double-counting across task queues and mathematical consistency.
"""

from __future__ import annotations

import datetime
import json
import tempfile
from pathlib import Path

from hypothesis import given, settings
from hypothesis import strategies as st

from spec_ops.backlog.digest import DailyStandupDigestGenerator, parse_window_to_hours
from spec_ops.backlog.queue import write_task_file
from spec_ops.config.models import ArchitectureSettings, SpecOpsConfig
from spec_ops.core.models import BlockerInfo, Task
from spec_ops.scaffold.init import init_project


@st.composite
def task_queue_strategy(draw):
    """Generates synthetic task queues with varied statuses, completion times, and claims."""
    num_completed = draw(st.integers(min_value=0, max_value=8))
    num_refined = draw(st.integers(min_value=0, max_value=8))
    num_proposed = draw(st.integers(min_value=0, max_value=8))

    tasks_data = []
    tid = 1

    # Completed tasks
    for _ in range(num_completed):
        hrs_ago = draw(st.floats(min_value=0.5, max_value=72.0))
        tasks_data.append(
            {
                "id": f"{tid:04d}",
                "status": "Complete",
                "folder": "complete",
                "hours_ago": hrs_ago,
                "claimed_by": "",
                "is_blocked": False,
            }
        )
        tid += 1

    # Refined tasks
    for _ in range(num_refined):
        is_claimed = draw(st.booleans())
        claimant = "agent-worker" if is_claimed else ""
        claimed_hrs = draw(st.floats(min_value=1.0, max_value=60.0)) if is_claimed else 0.0
        tasks_data.append(
            {
                "id": f"{tid:04d}",
                "status": "Refined",
                "folder": "refined",
                "hours_ago": claimed_hrs,
                "claimed_by": claimant,
                "is_blocked": False,
            }
        )
        tid += 1

    # Proposed tasks
    for _ in range(num_proposed):
        is_blocked = draw(st.booleans())
        tasks_data.append(
            {
                "id": f"{tid:04d}",
                "status": "Blocked" if is_blocked else "Proposed",
                "folder": "proposed",
                "hours_ago": 0.0,
                "claimed_by": "",
                "is_blocked": is_blocked,
            }
        )
        tid += 1

    window = draw(st.sampled_from(["12h", "24h", "48h", "7d"]))
    return tasks_data, window


@given(data=task_queue_strategy())
@settings(max_examples=35)
def test_invariant_digest_metrics_zero_double_counting(data):
    """Invariant (ADR-0009): Digest metrics accurately sum task counts across statuses with zero double-counting."""
    tasks_data, window = data

    with tempfile.TemporaryDirectory() as tmp_str:
        tmp_path = Path(tmp_str)
        init_project(tmp_path, name="DigestPropertyTest")
        config = SpecOpsConfig(root_dir=tmp_path)
        backlog_dir = config.backlog_dir

        for folder in ("complete", "refined", "proposed"):
            fpath = backlog_dir / folder
            fpath.mkdir(parents=True, exist_ok=True)
            for f in fpath.glob("*.md"):
                f.unlink()

        now = datetime.datetime.now(tz=datetime.timezone.utc)


        for td in tasks_data:
            dt_str = (now - datetime.timedelta(hours=td["hours_ago"])).isoformat()
            blocker_info = None
            if td["is_blocked"]:
                blocker_info = BlockerInfo(
                    type="unknown",
                    question="Unknown dependency architecture",
                    raised_by="lead",
                    raised_at=dt_str,
                )

            task = Task(
                id=td["id"],
                title=f"Task {td['id']}",
                status=td["status"],
                claimed_by=td["claimed_by"],
                blocker=blocker_info,
                file_path=backlog_dir / td["folder"] / f"{td['id']}-task.md",
            )
            if td["status"] == "Complete":
                setattr(task, "completed_at", dt_str)
            if td["claimed_by"]:
                setattr(task, "claimed_at", dt_str)

            write_task_file(task)

        generator = DailyStandupDigestGenerator(config, now=now)
        digest = generator.generate(window=window)
        metrics = digest.metrics

        # Invariant 1: Total tasks equals exact sum of folder status counts with zero double-counting
        total_tasks = len(tasks_data)
        assert metrics["total_tasks"] == total_tasks
        assert metrics["completed_count"] + metrics["refined_count"] + metrics["proposed_count"] == total_tasks
        assert sum(metrics["status_counts"].values()) == total_tasks

        # Invariant 2: Completed throughput within window is bounded by completed count
        assert metrics["completed_in_window"] <= metrics["completed_count"]
        assert len(digest.completed_throughput) == metrics["completed_in_window"]

        # Invariant 3: Ready buffer count is bounded by refined count
        assert metrics["ready_buffer_count"] <= metrics["refined_count"]
        assert len(digest.ready_buffer.ready_tasks) == metrics["ready_buffer_count"]

        # Invariant 4: Stalled leases count is bounded by active leases count
        assert metrics["stalled_leases_count"] <= metrics["active_leases_count"]
        assert len(digest.active_worker_leases) == metrics["active_leases_count"]

        # Invariant 5: JSON serialization roundtrips and maintains all metrics
        json_str = digest.to_json()
        parsed = json.loads(json_str)
        assert parsed["metrics"]["total_tasks"] == total_tasks
        assert parsed["window"] == window
        assert len(parsed["summary_table"]) == 4

        # Invariant 6: Markdown serialization renders valid header and summary table
        md_str = digest.to_markdown()
        assert "# Daily Standup Curation Digest" in md_str
        assert "| Metric | Current State | Recommended Action |" in md_str
