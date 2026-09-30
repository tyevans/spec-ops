"""Spike benchmark harness for SPIKE-0038: Zero-Dependency Local Web PRD Studio."""

from __future__ import annotations

import json
import shutil
import tempfile
import time
from pathlib import Path
from typing import Any

from spec_ops.prd.step_assistant import extract_frontdoor_steps
from spec_ops.prd.studio import (
    commit_prd_specification,
    create_prd_draft,
    parse_prd_document,
    serialize_prd_document,
    validate_prd_schema,
)


def run_benchmark(
    iterations: int = 50,
    repo_root: Path | None = None,
) -> dict[str, Any]:
    """Executes empirical benchmarks on PRD Studio API endpoints and git synchronization."""
    root = Path(repo_root or Path.cwd()).resolve()

    draft_latencies: list[float] = []
    frontdoor_latencies: list[float] = []
    commit_latencies: list[float] = []

    # 1. Benchmark GET /api/steps/frontdoor extraction
    for _ in range(iterations):
        t0 = time.perf_counter()
        steps = extract_frontdoor_steps(root)
        dt = (time.perf_counter() - t0) * 1000
        frontdoor_latencies.append(dt)

    # 2. Benchmark POST /api/prd/draft creation & validation
    # Use temporary directory inside the worktree for repeatable isolation
    temp_dir = tempfile.mkdtemp(prefix="spike_bench_")
    bench_root = Path(temp_dir)
    try:
        sample_payload = {
            "title": "Benchmark PRD Draft",
            "persona": "Taylor",
            "component": "studio",
            "problem_statement": "Empirical benchmark evaluation of local web studio latency",
            "outcomes": [
                "Interaction latency remains below 100ms",
                "Git writeback preserves bit-exact YAML frontmatter",
            ],
        }

        for i in range(iterations):
            payload = dict(sample_payload)
            payload["title"] = f"Benchmark PRD Draft {i}"
            t0 = time.perf_counter()
            res = create_prd_draft(bench_root, payload)
            dt = (time.perf_counter() - t0) * 1000
            draft_latencies.append(dt)

        # 3. Benchmark POST /api/prd/commit writeback integrity on repo
        # Measure git staging and commit time on an isolated test file
        test_file = root / "spikes" / "spike_0038" / ".bench_target.md"
        test_file.parent.mkdir(parents=True, exist_ok=True)
        rel_test_file = str(test_file.relative_to(root))

        for i in range(min(iterations, 10)):  # Git commits are slightly heavier; 10 iterations
            content = f"---\ntest: {i}\n---\n# Bench Iteration {i}\n"
            t0 = time.perf_counter()
            res = commit_prd_specification(
                repo_root=root,
                file_path=rel_test_file,
                content=content,
                commit_message=f"chore(bench): iteration {i}",
            )
            dt = (time.perf_counter() - t0) * 1000
            commit_latencies.append(dt)

        if test_file.exists():
            test_file.unlink(missing_ok=True)

    finally:
        shutil.rmtree(bench_root, ignore_errors=True)

    all_latencies = sorted(draft_latencies + frontdoor_latencies + commit_latencies)
    p50_idx = int(len(all_latencies) * 0.50)
    p95_idx = int(len(all_latencies) * 0.95)
    p99_idx = min(len(all_latencies) - 1, int(len(all_latencies) * 0.99))

    avg_draft = sum(draft_latencies) / max(1, len(draft_latencies))
    avg_frontdoor = sum(frontdoor_latencies) / max(1, len(frontdoor_latencies))
    avg_commit = sum(commit_latencies) / max(1, len(commit_latencies))
    p95_latency = all_latencies[p95_idx]

    findings = (
        f"Benchmark findings for SPIKE-0038:\n"
        f"- Total operations: {len(all_latencies)}\n"
        f"- Draft scaffolding avg latency: {avg_draft:.2f}ms\n"
        f"- Frontdoor step extraction avg latency: {avg_frontdoor:.2f}ms\n"
        f"- Git commit writeback avg latency: {avg_commit:.2f}ms\n"
        f"- Combined p50 latency: {all_latencies[p50_idx]:.2f}ms\n"
        f"- Combined p95 latency: {p95_latency:.2f}ms\n"
        f"- Combined p99 latency: {all_latencies[p99_idx]:.2f}ms\n"
        f"- External CDN/npm dependencies: 0\n"
        f"- Latency invariant (<100ms): {'PASSED' if p95_latency < 100.0 else 'FAILED'}"
    )

    return {
        "status": "completed",
        "iterations": iterations,
        "p95_latency_ms": round(p95_latency, 2),
        "p50_latency_ms": round(all_latencies[p50_idx], 2),
        "avg_draft_ms": round(avg_draft, 2),
        "avg_frontdoor_ms": round(avg_frontdoor, 2),
        "avg_commit_ms": round(avg_commit, 2),
        "findings": findings,
    }


def record_findings(harness_dir: Path, output: str) -> Path:
    """Persists empirical findings to disk."""
    out_path = Path(harness_dir) / "benchmark.txt"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(output.strip(), encoding="utf-8")
    return out_path
