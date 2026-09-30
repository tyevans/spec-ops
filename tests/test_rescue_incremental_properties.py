"""Generative property-based tests for incremental preflight runner invariants using Hypothesis (ADR-0009)."""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Optional

from hypothesis import given, strategies as st

from spec_ops.rescue.incremental_runner import (
    StepCacheData,
    StepRecord,
    clear_step_cache,
    file_matches_dependency,
    get_step_dependencies,
    invalidate_dirty_step_caches,
    is_step_cache_valid,
    load_step_cache,
    save_step_cache,
)

# Common strategies
step_names = st.sampled_from(["lockfile", "health", "lint", "test", "custom_step"])
commands = st.sampled_from([
    "uv lock --check",
    "spec-ops health",
    "ruff check && ruff format --check",
    "uv run pytest tests/",
    "echo custom",
])
file_paths = st.sampled_from([
    "uv.lock",
    "pyproject.toml",
    "specops.toml",
    "PRIORITY.md",
    "src/spec_ops/rescue/incremental_runner.py",
    "src/spec_ops/core/models.py",
    "tests/test_visualizer.py",
    "tests/test_bdd_us0093.py",
    "docs/project/product/accepted/prd-0001.md",
    "docs/how-to/deploy.md",
    "README.md",
    "unrelated/data.json",
    ".ruff.toml",
])


@st.composite
def step_records(draw):
    name = draw(step_names)
    cmd = draw(commands)
    passed = draw(st.booleans())
    exit_code = 0 if passed else draw(st.integers(min_value=1, max_value=127))
    deps = get_step_dependencies(name, cmd)
    return StepRecord(
        name=name,
        command=cmd,
        passed=passed,
        exit_code=exit_code,
        output=draw(st.text(max_size=50)),
        dependencies=deps,
    )


@given(
    dirty_files=st.lists(file_paths, min_size=0, max_size=10),
    isolated_step=st.one_of(st.none(), step_names),
)
def test_dirty_modification_invalidation_invariant(
    dirty_files: list[str],
    isolated_step: Optional[str],
):
    """Property: Any dirty file modifications outside the isolated step invalidate step caches deterministically (ADR-0009)."""
    # Create fixed fleet of steps
    steps = {
        "lockfile": StepRecord(name="lockfile", command="uv lock --check", passed=True, dependencies=get_step_dependencies("lockfile", "uv lock --check")),
        "health": StepRecord(name="health", command="spec-ops health", passed=True, dependencies=get_step_dependencies("health", "spec-ops health")),
        "lint": StepRecord(name="lint", command="ruff check && ruff format --check", passed=True, dependencies=get_step_dependencies("lint", "ruff check")),
        "test": StepRecord(name="test", command="uv run pytest tests/", passed=True, dependencies=get_step_dependencies("test", "pytest")),
    }
    cache1 = StepCacheData(version=1, steps=copy.deepcopy(steps))
    cache2 = StepCacheData(version=1, steps=copy.deepcopy(steps))

    # 1. Determinism
    inv1 = invalidate_dirty_step_caches(cache1, dirty_files, isolated_step=isolated_step)
    inv2 = invalidate_dirty_step_caches(cache2, dirty_files, isolated_step=isolated_step)
    assert inv1 == inv2, "Cache invalidation must be strictly deterministic across identical inputs"
    assert {k: v.passed for k, v in cache1.steps.items()} == {k: v.passed for k, v in cache2.steps.items()}

    # 2. Isolated step immunity
    if isolated_step:
        iso_norm = isolated_step.lower().strip()
        for name, step in cache1.steps.items():
            if iso_norm in name.lower() or iso_norm in step.command.lower():
                assert name not in inv1, f"Isolated step '{name}' must never be invalidated by external dirty files"
                assert step.passed is True

    # 3. Deterministic Dependency Invalidation Invariant
    for name, step in cache1.steps.items():
        if isolated_step and (isolated_step.lower() in name.lower() or isolated_step.lower() in step.command.lower()):
            continue

        has_dirty_match = any(
            file_matches_dependency(f, dep)
            for f in dirty_files
            for dep in step.dependencies
        )

        if has_dirty_match:
            assert not step.passed, f"Step '{name}' was not invalidated despite dirty files matching dependencies: {dirty_files}"
            assert name in inv1
        else:
            assert step.passed, f"Step '{name}' was unexpectedly invalidated with no matching dirty files: {dirty_files}"
            assert name not in inv1

    # 4. Idempotence
    inv3 = invalidate_dirty_step_caches(cache1, dirty_files, isolated_step=isolated_step)
    assert len(inv3) == 0, "Repeated invalidation with the same dirty files must be idempotent"


@given(
    step=step_records(),
    dirty_files=st.lists(file_paths, min_size=0, max_size=5),
)
def test_step_cache_validity_consistency(step: StepRecord, dirty_files: list[str]):
    """Property: is_step_cache_valid is strictly consistent with dependency intersection."""
    valid = is_step_cache_valid(step, dirty_files)
    if not step.passed:
        assert not valid, "Unpassed steps must always be invalid"
    else:
        has_dirty = any(
            file_matches_dependency(f, dep)
            for f in dirty_files
            for dep in (step.dependencies or get_step_dependencies(step.name, step.command))
        )
        assert valid == (not has_dirty)


@given(
    records=st.lists(step_records(), min_size=1, max_size=6),
)
def test_step_cache_save_load_roundtrip_property(tmp_path_factory, records: list[StepRecord]):
    """Property: StepCache serialization to disk and reload is an exact lossless identity function."""
    tmp = tmp_path_factory.mktemp("cache_rt")
    steps_dict = {r.name: r for r in records}
    orig_cache = StepCacheData(version=1, steps=steps_dict)

    save_step_cache(tmp, orig_cache)
    loaded = load_step_cache(tmp)

    assert loaded.version == orig_cache.version
    assert set(loaded.steps.keys()) == set(orig_cache.steps.keys())
    for k in orig_cache.steps:
        o = orig_cache.steps[k]
        l = loaded.steps[k]
        assert l.name == o.name
        assert l.command == o.command
        assert l.passed == o.passed
        assert l.exit_code == o.exit_code
        assert l.output == o.output
        assert l.dependencies == o.dependencies

    # Clear cache property
    assert clear_step_cache(tmp) is True
    assert not (tmp / ".specops" / "step_cache.json").exists()
    empty_cache = load_step_cache(tmp)
    assert len(empty_cache.steps) == 0
