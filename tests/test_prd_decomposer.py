"""Tests for PRD creation, auditing, and vertical slice decomposition."""

from pathlib import Path

from spec_ops.config.loader import load_config
from spec_ops.prd.decomposer import PRDDecomposer
from spec_ops.prd.manager import PRDManager
from spec_ops.scaffold.init import init_project


def test_prd_creation_and_decomposition(tmp_path: Path):
    init_project(tmp_path, name="PRDTest")
    config = load_config(root_dir=tmp_path)

    mgr = PRDManager(config)
    prd_path = mgr.create_prd(
        title="User Registration and Identity Sync",
        persona="Developer",
        component="core",
        summary="Seamless registration with JWT verification.",
    )
    assert prd_path.is_file()
    assert "PRD-0001" in prd_path.name or "prd-0001" in prd_path.name.lower()

    # Audit PRDs
    audit_res = mgr.audit()
    assert audit_res.total_prds == 1
    assert len(audit_res.undecomposed_prds) == 1

    # Decompose PRD
    decomposer = PRDDecomposer(config)
    tasks = decomposer.decompose("PRD-0001", include_spike=True)
    assert len(tasks) >= 4  # Spike + slices

    # Check generated user stories
    stories = list((config.user_stories_dir / "accepted").glob("*.md"))
    assert len(stories) >= 1

    # Re-audit should show PRD is now decomposed
    audit_res2 = mgr.audit()
    assert len(audit_res2.undecomposed_prds) == 0
