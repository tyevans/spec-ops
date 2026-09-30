"""Architectural spike creation and test harness scaffolding."""

from __future__ import annotations

import re
from pathlib import Path

from ..backlog.queue import write_task_file
from ..core.models import Task
from .sandbox import normalize_spike_id


def find_next_spike_number(root_dir: Path) -> int:
    """Finds the next sequential spike number by scanning backlog tasks and spikes/."""
    max_num = 0
    backlog_dir = root_dir / "docs" / "project" / "backlog"
    if backlog_dir.exists():
        for p in backlog_dir.rglob("*.md"):
            m = re.search(r"(?:spike[-_]|task[-_])?(\d+)", p.stem, re.IGNORECASE)
            if m:
                val = int(m.group(1))
                if val > max_num:
                    max_num = val

    spikes_dir = root_dir / "spikes"
    if spikes_dir.exists():
        for p in spikes_dir.glob("spike_*"):
            m = re.search(r"spike_(\d+)", p.name, re.IGNORECASE)
            if m:
                val = int(m.group(1))
                if val > max_num:
                    max_num = val

    return max_num + 1


def create_spike(
    root_dir: Path,
    name: str,
    question: str,
    timebox: str = "2h",
    prd_id: str | None = None,
    task_id: str | None = None,
) -> tuple[Task, Path]:
    """Scaffolds an architectural spike task in backlog and test harness directory."""
    root = Path(root_dir).resolve()
    next_num = find_next_spike_number(root)
    spike_id, num_str = normalize_spike_id(f"SPIKE-{next_num:04d}")

    clean_slug = re.sub(r"[^\w\s-]", "", name.lower())
    clean_slug = re.sub(r"[\s_-]+", "-", clean_slug).strip("-")[:40]

    proposed_dir = root / "docs" / "project" / "backlog" / "proposed"
    proposed_dir.mkdir(parents=True, exist_ok=True)
    task_file = proposed_dir / f"{num_str}-spike-{clean_slug}.md"

    governing_prds = [prd_id] if prd_id else []

    title = f"Architectural Spike: {name}"
    body = f"""# {spike_id}: {title}

## Summary & Unanswered Question
{question.strip()}

## Timebox & Scope
- **Timebox**: {timebox}
- **Target Harness**: `spikes/spike_{num_str}/`
- **Governing Task**: {task_id or "None"}

## Graduation Criteria
1. Execute exploratory benchmark or prototype tests in `spikes/spike_{num_str}/`.
2. Run `spec-ops spike check` to verify write isolation and timebox compliance.
3. Run `spec-ops spike graduate {spike_id} --result proven|disproven` to synthesize the ADR.
"""

    task = Task(
        id=spike_id,
        title=title,
        status="Proposed",
        file_path=task_file,
        body=body,
        allows_dependencies=True,
        hypothesis=question.strip(),
        timebox=timebox,
        governing_prds=[p for p in governing_prds if p],
    )
    write_task_file(task)

    # Scaffold test harness in spikes/spike_XXXX/
    harness_dir = root / "spikes" / f"spike_{num_str}"
    harness_dir.mkdir(parents=True, exist_ok=True)
    (harness_dir / "__init__.py").write_text("", encoding="utf-8")

    test_spike_code = f'''"""Empirical test harness for {spike_id}: {name}."""

def test_{clean_slug.replace("-", "_")}_hypothesis():
    """Validates the empirical hypothesis for {spike_id}."""
    # Question: {question}
    # TODO: Implement empirical prototype benchmark
    assert True
'''
    (harness_dir / "test_spike.py").write_text(test_spike_code, encoding="utf-8")
    (harness_dir / "README.md").write_text(
        f"# {spike_id}: {name}\n\nQuestion: {question}\nTimebox: {timebox}\n",
        encoding="utf-8",
    )

    # Sync into PRIORITY.md
    priority_file = root / "docs" / "project" / "backlog" / "PRIORITY.md"
    if priority_file.exists():
        content = priority_file.read_text(encoding="utf-8")
        entry_line = f"- **{spike_id} (Proposed)**: [`{task_file.stem}`](proposed/{task_file.name})\n"
        if spike_id not in content:
            priority_file.write_text(
                content.rstrip() + "\n" + entry_line, encoding="utf-8"
            )

    return task, task_file
