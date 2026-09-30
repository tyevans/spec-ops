"""Property-based generative tests for governed spike lifecycle and empirical ADR synthesis."""

from __future__ import annotations

import re
import subprocess
import tempfile
from pathlib import Path

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from spec_ops.backlog.queue import write_task_file
from spec_ops.core.models import Task
from spec_ops.core.parser import parse_adr, parse_task
from spec_ops.scaffold.init import init_project
from spec_ops.spike.graduate import format_adr_content, graduate_spike
from spec_ops.spike.sandbox import normalize_spike_id, parse_timebox_duration, start_spike


@settings(max_examples=25, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(
    hypothesis=st.text(alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd", "Zs")), min_size=5, max_size=80),
    timebox_val=st.integers(min_value=1, max_value=72),
    timebox_unit=st.sampled_from(["h", "m", "d"]),
    result=st.sampled_from(["proven", "disproven"]),
    dep_count=st.integers(min_value=0, max_value=3),
)
def test_spike_graduation_property_invariants(
    hypothesis: str,
    timebox_val: int,
    timebox_unit: str,
    result: str,
    dep_count: int,
):
    """Generative property test verifying ADR schema conformity, deterministic task state transitions,

    and zero orphan git worktree references upon spike graduation (ADR-0009).
    """
    timebox = f"{timebox_val}{timebox_unit}"
    tb_seconds = parse_timebox_duration(timebox)
    assert tb_seconds > 0

    with tempfile.TemporaryDirectory() as tmp_dir_str:
        repo = Path(tmp_dir_str)
        init_project(name="SpikePropApp", target_dir=repo)

        # Baseline git repo setup
        subprocess.run(["git", "init", "-b", "main"], cwd=repo, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.name", "Alex"], cwd=repo, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.email", "alex@specops.dev"], cwd=repo, check=True, capture_output=True)
        subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
        subprocess.run(["git", "commit", "-m", "chore: initial commit"], cwd=repo, check=True, capture_output=True)

        spike_id = "SPIKE-0042"
        canonical_id, num = normalize_spike_id(spike_id)
        assert canonical_id == "SPIKE-0042"
        assert num == "0042"

        # Create proposed spike task
        proposed_dir = repo / "docs" / "project" / "backlog" / "proposed"
        proposed_dir.mkdir(parents=True, exist_ok=True)
        spike_file = proposed_dir / "0042-prop-spike.md"
        spike_task = Task(
            id=canonical_id,
            title="Generative Architecture Spike",
            status="Proposed",
            hypothesis=hypothesis.strip(),
            timebox=timebox,
            file_path=spike_file,
        )
        write_task_file(spike_task)

        # Create dependent downstream tasks
        dep_files: list[Path] = []
        for i in range(dep_count):
            dep_id = f"TASK-{100 + i:04d}"
            df = proposed_dir / f"{100 + i:04d}-downstream-slice.md"
            dt = Task(
                id=dep_id,
                title=f"Downstream Slice {i}",
                status="Proposed",
                dependencies=[canonical_id],
                file_path=df,
            )
            write_task_file(dt)
            dep_files.append(df)

        subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
        subprocess.run(["git", "commit", "-m", "docs: propose spike & deps"], cwd=repo, check=True, capture_output=True)

        # 1. Start spike
        sandbox = start_spike(repo, canonical_id, hypothesis=hypothesis.strip(), timebox=timebox)
        assert sandbox.worktree_dir.exists()
        assert (sandbox.worktree_dir / "spikes" / f"spike_{num}" / "test_spike.py").exists()

        # 2. Graduate spike
        grad_res = graduate_spike(
            repo_root=repo,
            spike_id=canonical_id,
            result=result,
            title="Empirical Evaluation Decision",
            findings="p95 latency = 110ms",
        )
        assert grad_res.success is True
        assert grad_res.adr_file is not None
        assert grad_res.adr_file.exists()

        # Invariant 1: ADR schema conformity (ADR-0001)
        adr_content = grad_res.adr_file.read_text(encoding="utf-8")
        parsed_adr = parse_adr(grad_res.adr_file)
        assert parsed_adr.id.startswith("ADR-")
        assert "## Status" in adr_content
        assert "## Context" in adr_content
        assert "## Decision" in adr_content
        assert "## Consequences" in adr_content
        assert "110ms" in parsed_adr.context or "110ms" in adr_content
        assert "110ms" in parsed_adr.decision or "110ms" in adr_content

        # Invariant 2: Spike task moved to complete/ with status Graduated
        complete_dir = repo / "docs" / "project" / "backlog" / "complete"
        assert (complete_dir / spike_file.name).exists()
        graduated_task = parse_task(complete_dir / spike_file.name)
        assert graduated_task.status == "Graduated"

        # Invariant 3: Deterministic transition of dependent tasks
        for df in dep_files:
            assert df.exists()
            t = parse_task(df)
            if result == "proven":
                assert canonical_id not in t.dependencies
            else:
                assert t.status == "Blocked: Spike hypothesis failed"

        # Invariant 4: Zero orphan git worktrees and branch tagged
        assert not sandbox.worktree_dir.exists()
        wt_list = subprocess.run(["git", "worktree", "list"], cwd=repo, capture_output=True, text=True)
        assert str(sandbox.worktree_dir) not in wt_list.stdout

        tag_chk = subprocess.run(
            ["git", "tag", "--list", f"{sandbox.branch}-graduated"],
            cwd=repo,
            capture_output=True,
            text=True,
        )
        assert f"{sandbox.branch}-graduated" in tag_chk.stdout
