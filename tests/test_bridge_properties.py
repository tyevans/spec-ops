"""Generative property-based tests for external issue tracker bridge (TASK-0079, ADR-0009)."""

from __future__ import annotations

import re
from pathlib import Path

from hypothesis import HealthCheck, given, settings, strategies as st
import pytest
import yaml

from spec_ops.backlog.bridge.importer import IssueImporter
from spec_ops.backlog.bridge.models import ExternalIssue
from spec_ops.core.schema_validator import validate_document
from spec_ops.scaffold.init import init_project

safe_text = st.text(
    alphabet=st.characters(blacklist_categories=("Cs", "Cc"), blacklist_characters=("\r", "\n", "\0", "\\")),
    min_size=1,
    max_size=60,
).filter(lambda s: bool(s.strip()))

key_strategy = st.from_regex(r"^[A-Z]{2,6}-[0-9]{1,4}$", fullmatch=True)


@st.composite
def issue_list_strategy(draw: st.DrawFn) -> list[ExternalIssue]:
    count = draw(st.integers(min_value=1, max_value=8))
    keys = [f"ISSUE-{i}" for i in range(1, count + 1)]
    issues: list[ExternalIssue] = []

    for i, key in enumerate(keys):
        title = draw(safe_text)
        desc = draw(st.text(min_size=0, max_size=120))
        # Pick random dependencies from preceding issues
        deps = [k for k in keys[:i] if draw(st.booleans())] if i > 0 else []
        issues.append(
            ExternalIssue(
                key=key,
                title=title,
                description=desc,
                url=f"https://tracker.example.com/browse/{key}",
                target_bc="core",
                dependencies=list(deps),
                source="test",
            )
        )
    return issues


@settings(max_examples=30, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(issues=issue_list_strategy())
def test_hypothesis_non_colliding_ids_and_schema_compliance(tmp_path_factory: pytest.TempPathFactory, issues: list[ExternalIssue]) -> None:
    repo = tmp_path_factory.mktemp("hypo_repo")
    init_project(repo, name="HypothesisRepo")
    backlog_dir = repo / "docs" / "project" / "backlog"

    importer = IssueImporter(backlog_dir=backlog_dir)
    res = importer.ingest_issues(issues, default_bc="core")

    # Property 1: All generated task IDs must be strictly unique
    assert len(res.task_ids) == len(issues)
    assert len(set(res.task_ids)) == len(issues)

    # Property 2: IDs must match canonical TASK-XXXX format
    for tid in res.task_ids:
        assert re.match(r"^TASK-\d{4}$", tid)

    # Property 3: Every generated file must pass strict schema validation
    for file_path in res.files:
        assert file_path.is_file()
        content = file_path.read_text(encoding="utf-8")
        errs = validate_document(content, file_path=file_path)
        assert len(errs) == 0, f"Schema errors in {file_path.name}: {[str(e) for e in errs]}"

        # Property 4: Frontmatter is valid YAML and includes required fields
        parts = content.split("---", 2)
        assert len(parts) >= 3
        meta = yaml.safe_load(parts[1])
        assert "id" in meta
        assert "title" in meta
        assert meta["status"] == "Proposed"
        assert meta["target_bc"] == "core"

    # Property 5: Dependencies between issues in the batch must be resolved to canonical IDs
    for idx, issue in enumerate(issues):
        file_path = res.files[idx]
        content = file_path.read_text(encoding="utf-8")
        parts = content.split("---", 2)
        meta = yaml.safe_load(parts[1])
        meta_deps = meta.get("dependencies", [])
        for orig_dep in issue.dependencies:
            mapped_expected = res.key_mapping[orig_dep]
            assert mapped_expected in meta_deps, f"Expected {mapped_expected} in {meta_deps}"
