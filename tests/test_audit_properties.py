"""Generative property-based tests for compliance manifest tamper detection (ADR-0009, ADR-0016)."""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from spec_ops.security.audit.exporter import (
    export_compliance_manifest,
    extract_repo_compliance_deliverables,
)
from spec_ops.security.audit.merkle import (
    ComplianceDeliverable,
    HumanSignoff,
    compile_compliance_manifest,
    hash_leaf,
)
from spec_ops.security.audit.verifier import (
    verify_audit_trail,
    verify_compliance_manifest,
)


@settings(max_examples=35, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(
    field_to_mutate=st.sampled_from([
        "task_id",
        "prd_id",
        "commit_sha",
        "prompt_sha256",
        "test_results_digest",
        "reviewer",
        "signature",
    ]),
    mutation=st.text(min_size=1, max_size=20),
)
def test_deliverable_mutation_breaks_leaf_hash(field_to_mutate: str, mutation: str):
    """Property: Mutating any field in a deliverable unconditionally alters its leaf hash."""
    signoff = HumanSignoff(
        reviewer="Sasha",
        email="sasha@specops.dev",
        signature="ed25519:valid_sig",
        timestamp="2026-09-29T18:00:00Z",
    )
    base_deliv = ComplianceDeliverable(
        task_id="TASK-0030",
        prd_id="PRD-0002",
        story_ids=["US-0056"],
        commit_sha="1111222233334444555566667777888899990000",
        prompt_sha256="aa" * 32,
        test_results_digest="bb" * 32,
        human_signoff=signoff,
    )
    original_hash = base_deliv.compute_leaf_hash()

    deliv_dict = base_deliv.to_dict()
    if field_to_mutate == "reviewer":
        deliv_dict["human_signoff"]["reviewer"] += mutation
    elif field_to_mutate == "signature":
        deliv_dict["human_signoff"]["signature"] += mutation
    else:
        deliv_dict[field_to_mutate] += mutation

    mutated_hash = hash_leaf(deliv_dict)
    assert original_hash != mutated_hash


@settings(max_examples=25, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(
    mutate_idx=st.integers(min_value=0, max_value=9999),
    replacement_byte=st.integers(min_value=33, max_value=126),
)
def test_manifest_raw_byte_mutation_fails_verification(tmp_path_factory: pytest.TempPathFactory, mutate_idx: int, replacement_byte: int):
    """Property: Mutating any single byte in an exported manifest JSON text unconditionally fails verification."""
    tmp_path = tmp_path_factory.mktemp("prop_byte_tamper")
    signoff = HumanSignoff("Sasha", "sasha@specops.dev", "sig:0030", "2026-09-29T18:00:00Z")
    deliv = ComplianceDeliverable(
        task_id="TASK-0030",
        prd_id="PRD-0002",
        story_ids=["US-0056"],
        commit_sha="1111222233334444555566667777888899990000",
        prompt_sha256="aa" * 32,
        test_results_digest="bb" * 32,
        human_signoff=signoff,
    )
    manifest = compile_compliance_manifest([deliv], standard="soc2")
    raw_json = manifest.to_json().encode("utf-8")

    idx = mutate_idx % len(raw_json)
    char_at_idx = raw_json[idx]
    rep = replacement_byte if replacement_byte != char_at_idx else (replacement_byte + 1) % 256

    mutated_bytes = raw_json[:idx] + bytes([rep]) + raw_json[idx + 1:]
    manifest_file = tmp_path / "soc2-audit-manifest.json"
    manifest_file.write_bytes(mutated_bytes)

    # Verification must fail: either JSON decode error or cryptographic mismatch
    result = verify_audit_trail(manifest_file, repo_dir=tmp_path)
    assert result.ok is False


@settings(max_examples=20, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(
    field_to_corrupt=st.sampled_from(["commit_sha", "signoff_signature", "prompt_text"]),
    tamper_text=st.text(alphabet="0123456789abcdef", min_size=1, max_size=10),
)
def test_task_file_disk_mutation_fails_verification(tmp_path_factory: pytest.TempPathFactory, field_to_corrupt: str, tamper_text: str):
    """Property: Mutating task file prompt, commit SHA, or sign-off signature causes verify_audit_trail to fail."""
    repo = tmp_path_factory.mktemp("prop_disk_tamper")
    complete_dir = repo / "docs" / "project" / "backlog" / "complete"
    complete_dir.mkdir(parents=True)

    task_file = complete_dir / "0030-task.md"
    task_file.write_text(
        "---\n"
        "id: '0030'\n"
        "title: Task Thirty\n"
        "status: Complete\n"
        "governing_prds:\n  - PRD-0002\n"
        "governing_stories:\n  - US-0056\n"
        "commit_sha: '1111222233334444555566667777888899990000'\n"
        "signed_off_by: 'Sasha <sasha@specops.dev>'\n"
        "signoff_signature: 'ed25519:valid_sig'\n"
        "---\n"
        "# TASK-0030\nOriginal content.\n",
        encoding="utf-8",
    )

    manifest_file, root_file, _ = export_compliance_manifest(repo, standard="soc2", output_dir=repo / "dist" / "compliance")

    # Baseline verification succeeds
    res_before = verify_audit_trail(manifest_file, repo_dir=repo)
    assert res_before.ok is True

    # Mutate disk state
    content = task_file.read_text(encoding="utf-8")
    if field_to_corrupt == "commit_sha":
        mutated_content = content.replace("1111222233334444555566667777888899990000", f"ffff{tamper_text}".ljust(40, "0")[:40])
    elif field_to_corrupt == "signoff_signature":
        mutated_content = content.replace("ed25519:valid_sig", f"ed25519:tampered_{tamper_text}")
    else:
        mutated_content = content + f"\nTampered comment {tamper_text}"

    task_file.write_text(mutated_content, encoding="utf-8")

    res_after = verify_audit_trail(manifest_file, repo_dir=repo)
    assert res_after.ok is False
    assert res_after.corrupted_entity_id == "TASK-0030"
    assert res_after.expected_hash is not None
    assert res_after.computed_hash is not None
    assert res_after.expected_hash != res_after.computed_hash
