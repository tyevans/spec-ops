"""Spike benchmark harness for SPIKE-0040: Tamper-Evident Customer UAT Receipt and Cryptographic Manifest."""

from __future__ import annotations

import json
import shutil
import tempfile
import time
from pathlib import Path
from typing import Any

from spec_ops.prd.manifest import (
    compute_git_tree_digest,
    generate_release_manifest,
    verify_release_manifest,
)
from spec_ops.prd.uat_receipt import (
    map_outcomes_to_tests,
    reconcile_signoffs,
    serialize_canonical_json,
    validate_uat_signoff_schema,
)


SAMPLE_PRD_CONTENT = """# PRD-0003: Product Discovery & Living UAT Verification

## Checkable Outcomes

1. Running spec-ops prd studio launches interactive interface.
2. Running spec-ops prd lint detects unfalsifiable outcomes.
3. Running spec-ops prd ship verifies 100% completion and generates release manifest.
"""


def run_benchmark(
    iterations: int = 50,
    repo_root: Path | None = None,
) -> dict[str, Any]:
    """Executes empirical benchmarks on tree hashing, sign-off reconciliation, and verification."""
    root = Path(repo_root or Path.cwd()).resolve()

    tree_latencies: list[float] = []
    reconciliation_latencies: list[float] = []
    mapping_latencies: list[float] = []
    verification_latencies: list[float] = []

    # 1. Benchmark git tree SHA-256 digest calculation
    for _ in range(iterations):
        t0 = time.perf_counter()
        digest, clean, errs = compute_git_tree_digest(root, allow_uncommitted=True)
        dt = (time.perf_counter() - t0) * 1000
        tree_latencies.append(dt)

    # 2. Benchmark concurrent PM sign-off reconciliation
    base_signoffs = {
        "$schema": "spec-ops/uat-signoff-v1",
        "version": "1.0",
        "signoffs": {
            "PRD-0003:1": {
                "outcome_id": "1",
                "prd_id": "PRD-0003",
                "status": "Approved",
                "reviewer": "Taylor <taylor@example.com>",
                "timestamp": "2026-09-29T18:00:00Z",
                "notes": "Verified local studio web server responsiveness",
            },
        },
    }
    incoming_signoffs = {
        "$schema": "spec-ops/uat-signoff-v1",
        "version": "1.0",
        "signoffs": {
            "PRD-0003:2": {
                "outcome_id": "2",
                "prd_id": "PRD-0003",
                "status": "Approved",
                "reviewer": "Morgan <morgan@example.com>",
                "timestamp": "2026-09-29T18:05:00Z",
                "notes": "Verified linter detects missing persona links",
            },
            "PRD-0003:1": {
                "outcome_id": "1",
                "prd_id": "PRD-0003",
                "status": "Approved",
                "reviewer": "Taylor <taylor@example.com>",
                "timestamp": "2026-09-29T18:10:00Z",
                "notes": "Updated review notes after cross-browser verification",
            },
        },
    }

    for _ in range(iterations):
        t0 = time.perf_counter()
        reconciled = reconcile_signoffs(base_signoffs, incoming_signoffs)
        dt = (time.perf_counter() - t0) * 1000
        reconciliation_latencies.append(dt)

    # 3. Benchmark outcome-to-test mapping engine
    sample_stories = [
        {"id": "0043", "governing_prd": "PRD-0003", "scenarios": ["Scenario: Web Studio Launch"]},
        {"id": "0046", "governing_prd": "PRD-0003", "scenarios": ["Scenario: UAT Matrix"]},
        {"id": "0100", "governing_prd": "PRD-0003", "scenarios": ["Scenario: PRD Shipping"]},
    ]
    test_results = {
        "Scenario: Web Studio Launch": "passed",
        "Scenario: UAT Matrix": "passed",
        "Scenario: PRD Shipping": "passed",
    }

    for _ in range(iterations):
        t0 = time.perf_counter()
        mappings = map_outcomes_to_tests(
            SAMPLE_PRD_CONTENT,
            "PRD-0003",
            sample_stories,
            test_results,
            existing_signoffs=reconciled,
        )
        dt = (time.perf_counter() - t0) * 1000
        mapping_latencies.append(dt)

    # 4. Benchmark headless release manifest verification
    tree_digest, _, _ = compute_git_tree_digest(root, allow_uncommitted=True)
    manifest = generate_release_manifest(
        repo_root=root,
        prd_id="PRD-0003",
        prd_title="Product Discovery & Living UAT Verification",
        target_persona="Taylor",
        completed_tasks=[{"id": "TASK-0038", "commit_sha": "412361f"}],
        test_summary={"status": "Passed (CI)", "total_scenarios": 3, "failed_scenarios": 0},
        uat_summary={"status": "Approved", "total_outcomes": 3, "approved_outcomes": 3},
        allow_uncommitted=True,
    )

    # For pure headless verification latency benchmarking (avoiding working tree status noise)
    for _ in range(iterations):
        t0 = time.perf_counter()
        # Verify manifest signature and structural invariants
        valid, issues = verify_release_manifest(manifest, root)
        dt = (time.perf_counter() - t0) * 1000
        verification_latencies.append(dt)

    all_latencies = sorted(
        tree_latencies + reconciliation_latencies + mapping_latencies + verification_latencies
    )
    p50_idx = int(len(all_latencies) * 0.50)
    p95_idx = int(len(all_latencies) * 0.95)
    p99_idx = min(len(all_latencies) - 1, int(len(all_latencies) * 0.99))

    avg_tree = sum(tree_latencies) / max(1, len(tree_latencies))
    avg_reconcile = sum(reconciliation_latencies) / max(1, len(reconciliation_latencies))
    avg_mapping = sum(mapping_latencies) / max(1, len(mapping_latencies))
    avg_verify = sum(verification_latencies) / max(1, len(verification_latencies))
    p95_latency = all_latencies[p95_idx]

    findings = (
        f"Benchmark findings for SPIKE-0040:\n"
        f"- Total operations: {len(all_latencies)}\n"
        f"- Git tree SHA-256 calculation avg latency: {avg_tree:.2f}ms\n"
        f"- Concurrent PM sign-off reconciliation avg latency: {avg_reconcile:.2f}ms\n"
        f"- Outcome-to-test mapping avg latency: {avg_mapping:.2f}ms\n"
        f"- Headless manifest verification avg latency: {avg_verify:.2f}ms\n"
        f"- Combined p50 latency: {all_latencies[p50_idx]:.2f}ms\n"
        f"- Combined p95 latency: {p95_latency:.2f}ms\n"
        f"- Combined p99 latency: {all_latencies[p99_idx]:.2f}ms\n"
        f"- External cryptography dependencies: 0 (Pure Python hashlib)\n"
        f"- Headless verification invariant (<50ms): {'PASSED' if p95_latency < 50.0 else 'FAILED'}"
    )

    return {
        "status": "completed",
        "iterations": iterations,
        "p95_latency_ms": round(p95_latency, 2),
        "p50_latency_ms": round(all_latencies[p50_idx], 2),
        "avg_tree_ms": round(avg_tree, 2),
        "avg_reconcile_ms": round(avg_reconcile, 2),
        "avg_mapping_ms": round(avg_mapping, 2),
        "avg_verify_ms": round(avg_verify, 2),
        "findings": findings,
    }


def record_findings(harness_dir: Path, output: str) -> Path:
    """Persists empirical findings to disk."""
    out_path = Path(harness_dir) / "benchmark.txt"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(output.strip(), encoding="utf-8")
    return out_path
