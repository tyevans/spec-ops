"""Property-based generative tests for ergonomic task authoring and frontmatter roundtripping."""

from __future__ import annotations

import tempfile
from pathlib import Path

from hypothesis import given
from hypothesis import strategies as st

from spec_ops.cli.task_handler import scaffold_task_file
from spec_ops.core.parser import SpecOpsParser, parse_task


@given(
    title=st.text(
        alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd", "Zs")),
        min_size=3,
        max_size=50,
    )
    .map(lambda s: s.strip())
    .filter(lambda s: len(s) >= 3 and not s.isdigit()),
    target_bc=st.sampled_from(["worker", "core", "visualizer", "prd", "graph", "security", "spike", "docs"]),
    stage=st.sampled_from(["proposed", "refined"]),
    prd_nums=st.lists(st.integers(min_value=1, max_value=99), min_size=1, max_size=3, unique=True),
    story_nums=st.lists(st.integers(min_value=1, max_value=99), min_size=1, max_size=3, unique=True),
    adr_nums=st.lists(st.integers(min_value=1, max_value=99), min_size=0, max_size=3, unique=True),
    dep_nums=st.lists(st.integers(min_value=1, max_value=99), min_size=0, max_size=3, unique=True),
)
def test_property_task_frontmatter_roundtrip_zero_unparsed_fields(
    title: str,
    target_bc: str,
    stage: str,
    prd_nums: list[int],
    story_nums: list[int],
    adr_nums: list[int],
    dep_nums: list[int],
):
    """Generative Invariant: scaffolded tasks always produce valid YAML frontmatter

    that round-trips through SpecOpsParser with zero data loss or unparsed fields.
    Governed by ADR-0009.
    """
    prds = [f"PRD-{n:04d}" for n in prd_nums]
    stories = [f"US-{n:04d}" for n in story_nums]
    adrs = [f"ADR-{n:04d}" for n in adr_nums]
    deps = [f"TASK-{n:04d}" for n in dep_nums]

    with tempfile.TemporaryDirectory() as tmp_dir_str:
        tmp_dir = Path(tmp_dir_str)
        docs_dir = tmp_dir / "docs" / "project"
        backlog_dir = docs_dir / "backlog"
        backlog_dir.mkdir(parents=True, exist_ok=True)
        (backlog_dir / "PRIORITY.md").write_text("# Priority\n\n", encoding="utf-8")

        cid, created_file = scaffold_task_file(
            backlog_dir=backlog_dir,
            title=title,
            target_bc=target_bc,
            governing_prds=prds,
            governing_stories=stories,
            governing_adrs=adrs,
            dependencies=deps,
            stage=stage,
        )

        assert created_file.is_file()
        assert created_file.exists()

        # Parse single task
        task = parse_task(created_file)
        assert task.canonical_id == cid
        assert task.id == cid.replace("TASK-", "")
        assert task.title == title
        assert task.target_bc == target_bc
        assert task.status == stage.capitalize()
        assert task.governing_prds == prds
        assert task.governing_stories == stories
        assert task.governing_adrs == adrs
        assert task.dependencies == deps
        assert task.body.strip() != ""

        # Parse via SpecOpsParser
        parser = SpecOpsParser(docs_dir)
        project_data = parser.parse_all()
        assert len(project_data.tasks) == 1
        p_task = project_data.tasks[0]
        assert p_task.canonical_id == cid
        assert p_task.title == title
        assert p_task.target_bc == target_bc
        assert p_task.status == stage.capitalize()
        assert p_task.governing_prds == prds
        assert p_task.governing_stories == stories
        assert p_task.governing_adrs == adrs
        assert p_task.dependencies == deps

        # Verify PRIORITY.md
        priority_content = (backlog_dir / "PRIORITY.md").read_text(encoding="utf-8")
        assert cid in priority_content
        assert created_file.name in priority_content
