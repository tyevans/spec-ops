"""Comprehensive unit tests for commits module to ensure >=80% mutation kill score."""

from __future__ import annotations

import re
from spec_ops.core.models import Task
from spec_ops.worker.commits import (
    VALID_CONVENTIONAL_TYPES,
    _normalize_task_id,
    build_commit_subject,
    build_commit_trailers,
    derive_conventional_type,
    format_task_commit_message,
    parse_commit_trailers,
)


def test_derive_conventional_type_direct():
    assert derive_conventional_type({"slice_type": "spike"}) == "spike"
    assert derive_conventional_type({"slice_type": "refactor"}) == "refactor"
    assert derive_conventional_type({"slice_type": "fix"}) == "fix"
    assert derive_conventional_type({"slice_type": "feat"}) == "feat"
    assert derive_conventional_type({"slice": "chore"}) == "chore"
    assert derive_conventional_type({"type": "docs"}) == "docs"
    assert derive_conventional_type({"slice_type": "TEST"}) == "test"
    assert derive_conventional_type({"slice_type": " perf "}) == "perf"
    assert derive_conventional_type({"slice_type": "style"}) == "style"
    assert derive_conventional_type({"slice_type": "ci"}) == "ci"


def test_derive_conventional_type_synonyms():
    assert derive_conventional_type({"slice_type": "feature"}) == "feat"
    assert derive_conventional_type({"slice_type": "refactoring"}) == "refactor"
    assert derive_conventional_type({"slice_type": "bug"}) == "fix"
    assert derive_conventional_type({"slice_type": "bugfix"}) == "fix"
    assert derive_conventional_type({"slice_type": "spike_task"}) == "spike"


def test_derive_conventional_type_task_object():
    t1 = Task(id="0001", title="feat task", slice_type="spike")
    assert derive_conventional_type(t1) == "spike"
    t2 = Task(id="0002", title="refactor task", slice_type="refactor")
    assert derive_conventional_type(t2) == "refactor"


def test_derive_conventional_type_from_id_or_title():
    assert derive_conventional_type({"id": "SPIKE-0042", "title": "investigate"}) == "spike"
    assert derive_conventional_type({"canonical_id": "SPIKE-0042", "title": "investigate"}) == "spike"
    assert derive_conventional_type({"id": "0001", "title": "spike: prototype cache"}) == "spike"
    assert derive_conventional_type({"id": "0001", "title": "[spike] prototype cache"}) == "spike"
    assert derive_conventional_type({"id": "0001", "title": "refactor: clean models"}) == "refactor"
    assert derive_conventional_type({"id": "0001", "title": "[refactor] clean models"}) == "refactor"
    assert derive_conventional_type({"id": "0001", "title": "fix: resolve crash"}) == "fix"
    assert derive_conventional_type({"id": "0001", "title": "[fix] resolve crash"}) == "fix"
    assert derive_conventional_type({"id": "0001", "title": "bug: memory leak"}) == "fix"
    assert derive_conventional_type({"id": "0001", "title": "normal title"}) == "feat"
    assert derive_conventional_type({}) == "feat"


def test_normalize_task_id():
    assert _normalize_task_id({"id": "TASK-0018"}, upper=False) == "task-0018"
    assert _normalize_task_id({"id": "TASK-0018"}, upper=True) == "TASK-0018"
    assert _normalize_task_id({"id": "18"}, upper=False) == "task-0018"
    assert _normalize_task_id({"id": "18"}, upper=True) == "TASK-0018"
    assert _normalize_task_id({"id": "SPIKE-0005"}, upper=False) == "spike-0005"
    assert _normalize_task_id({"id": "SPIKE-0005"}, upper=True) == "SPIKE-0005"
    assert _normalize_task_id({"id": "abc"}, upper=False) == "abc"
    assert _normalize_task_id({"id": "abc"}, upper=True) == "ABC"
    assert _normalize_task_id({}, upper=False) == "task-0000"
    assert _normalize_task_id({}, upper=True) == "TASK-0000"


def test_build_commit_subject():
    assert build_commit_subject({"id": "TASK-0018", "title": "Evaluate mutmut", "slice_type": "spike"}) == "spike(task-0018): Evaluate mutmut"
    assert build_commit_subject({"id": "TASK-0021", "title": "Decompose worker module", "slice_type": "refactor"}) == "refactor(task-0021): Decompose worker module"
    assert build_commit_subject({"id": "TASK-0001", "title": "fix: bug in parser", "slice_type": "fix"}) == "fix(task-0001): bug in parser"
    assert build_commit_subject({"id": "TASK-0001", "title": "feat: new feature"}) == "feat(task-0001): new feature"
    assert build_commit_subject({"id": "TASK-0001", "title": ""}) == "feat(task-0001): update"
    assert build_commit_subject({"id": "TASK-0001", "title": "Custom"}, slice_type="docs") == "docs(task-0001): Custom"


def test_build_commit_trailers_all_fields():
    meta = {
        "id": "TASK-0018",
        "slice_type": "spike",
        "governing_prds": ["PRD-0001"],
        "governing_adrs": ["ADR-0007", "ADR-0009"],
        "signed_off_by": "Riley <riley@example.com>",
    }
    trailers = build_commit_trailers(meta, provenance="custom-agent")
    assert trailers["SpecOps-Task"] == "TASK-0018"
    assert trailers["SpecOps-Slice"] == "spike"
    assert trailers["SpecOps-PRD"] == "PRD-0001"
    assert trailers["SpecOps-ADR"] == "ADR-0007, ADR-0009"
    assert trailers["Provenance"] == "custom-agent"
    assert trailers["SpecOps-Signed-By"] == "Riley <riley@example.com>"


def test_build_commit_trailers_singular_string_prd_adr():
    meta = {
        "id": "TASK-0001",
        "governing_prd": "PRD-0002",
        "governing_adr": "ADR-0003",
    }
    trailers = build_commit_trailers(meta)
    assert trailers["SpecOps-PRD"] == "PRD-0002"
    assert trailers["SpecOps-ADR"] == "ADR-0003"
    assert trailers["Provenance"] == "spec-ops-worker (autonomous)"
    assert "SpecOps-Signed-By" not in trailers


def test_build_commit_trailers_minimal():
    trailers = build_commit_trailers({})
    assert trailers["SpecOps-Task"] == "TASK-0000"
    assert trailers["SpecOps-Slice"] == "feat"
    assert "SpecOps-PRD" not in trailers
    assert "SpecOps-ADR" not in trailers
    assert trailers["Provenance"] == "spec-ops-worker (autonomous)"


def test_format_task_commit_message():
    meta = {
        "id": "TASK-0018",
        "title": "Evaluate mutmut",
        "slice_type": "spike",
        "governing_prds": ["PRD-0001"],
        "governing_adrs": ["ADR-0007", "ADR-0009"],
    }
    msg_no_body = format_task_commit_message(meta)
    assert msg_no_body.startswith("spike(task-0018): Evaluate mutmut\n\nSpecOps-Task: TASK-0018\n")
    assert msg_no_body.endswith("\n")
    assert "SpecOps-ADR: ADR-0007, ADR-0009" in msg_no_body

    msg_with_body = format_task_commit_message(meta, body="Detailed description of spike.\nMultiple lines.")
    assert "Detailed description of spike.\nMultiple lines.\n\nSpecOps-Task: TASK-0018" in msg_with_body


def test_parse_commit_trailers():
    raw_log = """commit abcdef123456
Author: Agent <agent@specops.dev>
Date:   Mon Sep 29 12:00:00 2026

    spike(task-0018): Evaluate mutmut

    SpecOps-Task: TASK-0018
    SpecOps-Slice: spike
    SpecOps-PRD: PRD-0001
    SpecOps-ADR: ADR-0007, ADR-0009
    Provenance: spec-ops-worker (autonomous)
"""
    trailers = parse_commit_trailers(raw_log)
    assert trailers["SpecOps-Task"] == "TASK-0018"
    assert trailers["SpecOps-Slice"] == "spike"
    assert trailers["SpecOps-PRD"] == "PRD-0001"
    assert trailers["SpecOps-ADR"] == "ADR-0007, ADR-0009"
    assert trailers["Provenance"] == "spec-ops-worker (autonomous)"
