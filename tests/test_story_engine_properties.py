"""Hypothesis generative property tests for story engine and domain invariants.

Governed by ADR-0001, ADR-0002, ADR-0003, ADR-0006, ADR-0009; PRD-0006; US-0117.
"""

from __future__ import annotations

from pathlib import Path
import re

from hypothesis import given, settings
from hypothesis import strategies as st

from spec_ops.core.parser import extract_frontmatter
from spec_ops.core.schema_validator import UserStoryFrontmatter
from spec_ops.core.story_engine import StoryEngine
from spec_ops.core.story_models import (
    normalize_story_id,
    slugify_story_title,
)
from spec_ops.scaffold.init import init_project


@given(st.text())
def test_slugify_story_title_invariants(raw_title: str):
    """Property: Slug is always non-empty, lowercase alphanumerics & dashes, max len 50."""
    slug = slugify_story_title(raw_title)
    assert len(slug) >= 1
    assert len(slug) <= 50
    assert re.match(r"^[a-z0-9]+(?:-[a-z0-9]+)*$", slug) is not None


@given(
    prefix=st.sampled_from(["US", "PRD", "TASK", "ADR"]),
    number=st.integers(min_value=0, max_value=99999),
)
def test_normalize_story_id_with_digits(prefix: str, number: int):
    """Property: Any raw string containing digits normalizes to prefix-4digit format."""
    raw = f"some-{prefix.lower()}-{number}-text"
    norm = normalize_story_id(raw, prefix)
    assert norm == f"{prefix}-{number:04d}"


@given(st.lists(st.integers(min_value=1, max_value=500), min_size=0, max_size=20, unique=True))
@settings(max_examples=30)
def test_next_story_number_monotonic(tmp_path_factory, numbers: list[int]):
    """Property: get_next_story_number is always strictly greater than max existing number."""
    tmp = tmp_path_factory.mktemp("story_mono")
    init_project(tmp, name="MonoRepo")
    stories_dir = tmp / "docs" / "project" / "user_stories" / "accepted"
    stories_dir.mkdir(parents=True, exist_ok=True)

    for n in numbers:
        (stories_dir / f"us-{n:04d}-story.md").write_text(f"# US-{n:04d}\n", encoding="utf-8")

    engine = StoryEngine(tmp)
    next_num = engine.get_next_story_number()

    if numbers:
        assert next_num == max(numbers) + 1
        assert all(next_num > n for n in numbers)
    else:
        assert next_num >= 1


@given(
    entries=st.lists(
        st.tuples(
            st.integers(min_value=1, max_value=300),
            st.text(alphabet=st.characters(categories=["L", "N", "Zs"]), min_size=1, max_size=30),
            st.sampled_from(["Alex", "Jordan", "Morgan", "Riley", "Taylor", "Sasha"]),
            st.sampled_from(["core", "worker", "backlog", "security"]),
            st.integers(min_value=1, max_value=20),
        ),
        min_size=1,
        max_size=15,
        unique_by=lambda x: x[0],
    )
)
@settings(max_examples=25)
def test_registry_atomic_sorting_and_uniqueness(tmp_path_factory, entries):
    """Property: update_registry preserves unique sorted rows without ID collisions."""
    tmp = tmp_path_factory.mktemp("reg_sort")
    init_project(tmp, name="RegSortRepo")
    engine = StoryEngine(tmp)

    for num, title, persona, bc, prd_num in entries:
        cid = f"US-{num:04d}"
        feat = f"FEAT-{bc.upper()[:4]}-{num % 100:02d}"
        prd_cid = f"PRD-{prd_num:04d}"
        clean_title = title.strip() or "Untitled Story"
        engine.update_registry(
            cid=cid,
            title=clean_title,
            status="Accepted",
            persona=persona,
            feature=feat,
            governing_prd=prd_cid,
        )

    reg_file = tmp / "docs" / "project" / "user_stories" / "REGISTRY.md"
    assert reg_file.is_file()

    rows = [line for line in reg_file.read_text(encoding="utf-8").splitlines() if line.startswith("| `US-")]
    extracted_nums = [int(re.search(r"US-(\d+)", r).group(1)) for r in rows]

    # Invariant 1: Strictly sorted
    assert extracted_nums == sorted(extracted_nums)
    # Invariant 2: No duplicates
    assert len(extracted_nums) == len(set(extracted_nums))
    # Invariant 3: All inserted IDs are present
    expected_nums = sorted(e[0] for e in entries)
    assert extracted_nums == expected_nums


@given(
    title=st.text(alphabet=st.characters(categories=["L", "N", "Zs"]), min_size=3, max_size=40),
    persona=st.sampled_from([
        "Alex (The Agentic Systems Architect)",
        "Jordan (The AI-Native Engineering Lead)",
        "Morgan (The Autonomous Coding Agent)",
    ]),
    bc=st.sampled_from(["core", "worker", "backlog", "security", "visualizer"]),
    prd_num=st.integers(min_value=1, max_value=50),
    scenarios=st.lists(
        st.text(alphabet=st.characters(categories=["L", "N", "Zs"]), min_size=3, max_size=30),
        min_size=1,
        max_size=4,
    ),
)
@settings(max_examples=25)
def test_create_story_schema_conformance(tmp_path_factory, title, persona, bc, prd_num, scenarios):
    """Property: create_story produces frontmatter and content conforming to schema v2.0."""
    tmp = tmp_path_factory.mktemp("story_schema")
    init_project(tmp, name="StorySchemaRepo")
    engine = StoryEngine(tmp)

    clean_title = title.strip() or "Valid Story Title"
    clean_scenarios = [s.strip() or "Default Scenario" for s in scenarios]
    prd_cid = f"PRD-{prd_num:04d}"

    res = engine.create_story(
        title=clean_title,
        prd=prd_cid,
        persona=persona,
        bc=bc,
        scenarios=clean_scenarios,
        dry_run=False,
    )

    assert res.file_path.is_file()
    content = res.file_path.read_text(encoding="utf-8")
    meta, _ = extract_frontmatter(content)

    # Validate against Pydantic schema model
    validated = UserStoryFrontmatter(**meta)
    assert validated.title == clean_title
    assert validated.status == "Accepted"
    assert validated.persona == persona
    assert validated.target_bc == bc
    assert validated.governing_prd == prd_cid
    assert validated.scenarios == clean_scenarios
