"""Spike worktree sandboxing, test harness scaffolding, and write isolation."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any

from ..core.models import Task
from ..core.parser import parse_task
from ..core.git_worktree import cleanup_worktree, create_worktree


def normalize_spike_id(spike_id: str) -> tuple[str, str]:
    """Normalizes spike identifier into canonical form and numeric string."""
    digits = re.findall(r"\d+", spike_id)
    if not digits:
        clean = spike_id.replace("SPIKE-", "").replace("TASK-", "").strip()
        num = clean.zfill(4) if clean.isdigit() else "0001"
    else:
        num = digits[-1].zfill(4)
    return f"SPIKE-{num}", num


def parse_timebox_duration(timebox_str: str) -> float:
    """Parses human timebox string (e.g., '2h', '30m', '1d', '3600s') into seconds."""
    s = str(timebox_str).strip().lower()
    m = re.match(r"^([\d.]+)\s*([a-z]+)?$", s)
    if not m:
        return 7200.0  # default 2h
    val = float(m.group(1))
    unit = m.group(2) or "h"
    if unit in ("h", "hr", "hours", "hour"):
        return val * 3600.0
    if unit in ("m", "min", "mins", "minute", "minutes"):
        return val * 60.0
    if unit in ("d", "day", "days"):
        return val * 86400.0
    if unit in ("s", "sec", "secs", "second", "seconds"):
        return val
    return val * 3600.0


class SpikeSandbox:
    """Manages the isolated git worktree sandbox and test harness for an architectural spike."""

    def __init__(self, repo_root: Path, spike_id: str, worktree_dir: Path | None = None):
        self.repo_root = Path(repo_root).resolve()
        self.canonical_id, self.num = normalize_spike_id(spike_id)
        self.worktree_dir = Path(worktree_dir).resolve() if worktree_dir else (self.repo_root / ".worktrees" / f"spike-{self.num}")
        self.branch = f"spike/{self.canonical_id}"
        self.harness_rel = Path("spikes") / f"spike_{self.num}"
        self.harness_dir = self.worktree_dir / self.harness_rel
        self.metadata_file = self.worktree_dir / ".specops" / "spike.json"

    def lookup_task(self) -> Task | None:
        """Finds the corresponding task in docs/project/backlog/ across lifecycle folders."""
        backlog_dir = self.repo_root / "docs" / "project" / "backlog"
        if not backlog_dir.exists():
            return None
        for folder_name in ["proposed", "refined", "complete"]:
            folder = backlog_dir / folder_name
            if not folder.exists():
                continue
            for p in sorted(folder.glob("*.md")):
                if p.name.startswith("."):
                    continue
                stem_digits = re.findall(r"\d+", p.stem)
                if stem_digits and stem_digits[0].zfill(4) == self.num:
                    try:
                        return parse_task(p)
                    except Exception:
                        pass
        return None

    def load_metadata(self) -> dict[str, Any]:
        """Loads cached spike metadata from disk."""
        if self.metadata_file.exists():
            try:
                return json.loads(self.metadata_file.read_text(encoding="utf-8"))
            except Exception:
                pass
        task = self.lookup_task()
        return {
            "spike_id": self.canonical_id,
            "num": self.num,
            "hypothesis": getattr(task, "hypothesis", "") or (task.title if task else f"Validate {self.canonical_id}"),
            "timebox": getattr(task, "timebox", "") or "2h",
            "started_at": time.time(),
            "branch": self.branch,
        }

    def save_metadata(self, data: dict[str, Any]) -> None:
        """Persists spike metadata inside the worktree sandbox."""
        self.metadata_file.parent.mkdir(parents=True, exist_ok=True)
        self.metadata_file.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def scaffold_harness(self, hypothesis: str, timebox: str = "2h") -> dict[str, Path]:
        """Scaffolds harness.py, test_spike.py, and README.md inside the spike worktree."""
        self.harness_dir.mkdir(parents=True, exist_ok=True)

        harness_py = self.harness_dir / "harness.py"
        harness_py.write_text(
            f'"""Spike benchmark harness for {self.canonical_id}."""\n\n'
            "from __future__ import annotations\n\n"
            "import json\nimport time\nfrom pathlib import Path\nfrom typing import Any\n\n\n"
            "def run_benchmark(iterations: int = 100) -> dict[str, Any]:\n"
            '    """Executes empirical benchmark iterations and records latency metrics."""\n'
            "    start = time.perf_counter()\n"
            "    for _ in range(iterations):\n"
            "        pass\n"
            "    elapsed_ms = (time.perf_counter() - start) * 1000\n"
            "    avg_latency = elapsed_ms / max(1, iterations)\n"
            "    return {\n"
            '        "iterations": iterations,\n'
            '        "total_time_ms": round(elapsed_ms, 3),\n'
            '        "p95_latency_ms": round(avg_latency, 3),\n'
            '        "status": "completed",\n'
            "    }\n\n\n"
            "def record_findings(harness_dir: Path, output: str) -> Path:\n"
            '    """Persists empirical findings to disk."""\n'
            '    out_path = harness_dir / "benchmark.txt"\n'
            '    out_path.write_text(output.strip(), encoding="utf-8")\n'
            "    return out_path\n",
            encoding="utf-8",
        )

        test_spike_py = self.harness_dir / "test_spike.py"
        test_spike_py.write_text(
            f'"""Executable benchmark skeleton for {self.canonical_id}.\n\n'
            f"Hypothesis: {hypothesis}\n"
            '"""\n\n'
            "from __future__ import annotations\n\n"
            "import pytest\n"
            "from .harness import run_benchmark\n\n\n"
            "def test_hypothesis_benchmark():\n"
            f'    """Empirical benchmark assertion for {self.canonical_id}.\n\n'
            f"    Hypothesis: {hypothesis}\n"
            '    """\n'
            "    results = run_benchmark()\n"
            '    assert results["status"] == "completed"\n'
            '    assert results["p95_latency_ms"] >= 0\n',
            encoding="utf-8",
        )

        readme_md = self.harness_dir / "README.md"
        readme_md.write_text(
            f"# Architectural Spike Harness: {self.canonical_id}\n\n"
            f"## Hypothesis\n{hypothesis}\n\n"
            f"## Timebox\n{timebox}\n\n"
            "## Rules & Guidelines\n"
            f"1. Implement prototype logic strictly within `spikes/spike_{self.num}/`.\n"
            "2. Modifying files under `src/` violates write isolation and will trigger preflight rejection.\n"
            f"3. Run benchmark tests via `pytest spikes/spike_{self.num}/test_spike.py`.\n"
            f"4. Conclude experiment via `spec-ops spike graduate {self.canonical_id} --result proven|disproven`.\n",
            encoding="utf-8",
        )

        return {
            "harness.py": harness_py,
            "test_spike.py": test_spike_py,
            "README.md": readme_md,
        }

    def install_preflight_hook(self) -> None:
        """Installs the write-isolation preflight hook inside the spike worktree."""
        hooks_dir = self.worktree_dir / ".specops" / "hooks"
        hooks_dir.mkdir(parents=True, exist_ok=True)
        pre_commit_script = hooks_dir / "pre-commit"
        pre_commit_script.write_text(
            "#!/bin/sh\n"
            "exec uv run spec-ops spike preflight\n",
            encoding="utf-8",
        )
        pre_commit_script.chmod(0o755)

        # Detect and preserve previous hooks path if any
        prev_hooks = ""
        chk_target = self.worktree_dir if self.worktree_dir.exists() else self.repo_root
        res = subprocess.run(
            ["git", "config", "--get", "core.hooksPath"],
            cwd=chk_target,
            capture_output=True,
            text=True,
        )
        if res.returncode == 0 and res.stdout.strip():
            prev_hooks = res.stdout.strip()

        meta = self.load_metadata()
        if "previous_hooks_path" not in meta:
            meta["previous_hooks_path"] = prev_hooks
            self.save_metadata(meta)

        # Configure git to use worktree hooks
        subprocess.run(
            ["git", "config", "core.hooksPath", ".specops/hooks"],
            cwd=self.worktree_dir,
            capture_output=True,
        )

    def uninstall_preflight_hook(self) -> None:
        """Removes the preflight hook script and restores git hooks configuration."""
        meta = self.load_metadata()
        prev_hooks = meta.get("previous_hooks_path", "")

        targets = [d for d in [self.worktree_dir, self.repo_root] if d.exists()]
        for target in targets:
            res = subprocess.run(
                ["git", "config", "--get", "core.hooksPath"],
                cwd=target,
                capture_output=True,
                text=True,
            )
            curr = res.stdout.strip()
            if curr in (
                ".specops/hooks",
                str(self.worktree_dir / ".specops" / "hooks"),
                str(self.repo_root / ".specops" / "hooks"),
            ):
                if prev_hooks and prev_hooks != curr:
                    subprocess.run(
                        ["git", "config", "core.hooksPath", prev_hooks],
                        cwd=target,
                        capture_output=True,
                    )
                else:
                    subprocess.run(
                        ["git", "config", "--unset", "core.hooksPath"],
                        cwd=target,
                        capture_output=True,
                    )

            script = target / ".specops" / "hooks" / "pre-commit"
            if script.exists():
                try:
                    script.unlink(missing_ok=True)
                except Exception:
                    pass

            h_dir = target / ".specops" / "hooks"
            if h_dir.exists():
                try:
                    if not any(h_dir.iterdir()):
                        h_dir.rmdir()
                except Exception:
                    pass

    def cleanup_metadata(self) -> None:
        """Cleans up transient spike metadata and empty .specops directories."""
        targets = [d for d in [self.worktree_dir, self.repo_root] if d.exists()]
        for target in targets:
            meta_file = target / ".specops" / "spike.json"
            if meta_file.exists():
                try:
                    try:
                        data = json.loads(meta_file.read_text(encoding="utf-8"))
                        sid = data.get("spike_id") or data.get("num")
                        if (
                            not sid
                            or sid == self.canonical_id
                            or sid == self.num
                            or str(sid).zfill(4) == self.num
                            or target == self.worktree_dir
                        ):
                            meta_file.unlink(missing_ok=True)
                    except Exception:
                        meta_file.unlink(missing_ok=True)
                except Exception:
                    pass

            specops_dir = target / ".specops"
            if specops_dir.exists():
                try:
                    if not any(specops_dir.iterdir()):
                        specops_dir.rmdir()
                except Exception:
                    pass

    def check_write_isolation(self) -> tuple[bool, str]:
        """Verifies that no source modifications occurred outside the spike harness."""
        if not self.worktree_dir.exists():
            return True, ""

        violations: list[str] = []
        res = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=self.worktree_dir,
            capture_output=True,
            text=True,
        )
        for line in res.stdout.splitlines():
            clean_line = line.strip()
            if not clean_line:
                continue
            path_part = clean_line[2:].strip().strip('"')
            if " -> " in path_part:
                path_part = path_part.split(" -> ")[-1].strip().strip('"')
            # Check if any changed/untracked file touches src/ or src/spec_ops/
            if path_part.startswith("src/"):
                violations.append(path_part)

        res_cached = subprocess.run(
            ["git", "diff", "--cached", "--name-only"],
            cwd=self.worktree_dir,
            capture_output=True,
            text=True,
        )
        for line in res_cached.stdout.splitlines():
            clean_line = line.strip()
            if clean_line and clean_line.startswith("src/"):
                violations.append(clean_line)

        violations = list(dict.fromkeys(violations))

        if violations:
            msg = (
                f"Spike Sandbox Violation: Code changes during an exploratory spike "
                f"must be contained within 'spikes/spike_{self.num}/'"
            )
            return False, msg
        return True, ""

    def has_recorded_findings(self) -> bool:
        """Returns True if empirical benchmark findings have been recorded on disk."""
        if not self.harness_dir.exists():
            return False
        for fn in ["benchmark.txt", "benchmark.json", "findings.txt", "results.txt"]:
            fp = self.harness_dir / fn
            if fp.exists() and fp.stat().st_size > 0:
                return True

        test_file = self.harness_dir / "test_spike.py"
        if test_file.exists():
            content = test_file.read_text(encoding="utf-8")
            if "p95 latency =" in content or "benchmark output:" in content:
                return True
        return False

    def check_timebox(self, simulated_elapsed: float | None = None) -> tuple[bool, str]:
        """Checks if spike timebox has expired without recorded findings."""
        meta = self.load_metadata()
        timebox_str = str(meta.get("timebox", "2h"))
        tb_seconds = parse_timebox_duration(timebox_str)

        elapsed = simulated_elapsed
        if elapsed is None:
            env_val = os.environ.get("SPECOPS_SPIKE_ELAPSED")
            if env_val:
                elapsed = parse_timebox_duration(env_val)
            else:
                started_at = float(meta.get("started_at", time.time()))
                elapsed = time.time() - started_at

        if elapsed >= tb_seconds and not self.has_recorded_findings():
            warning = (
                f"Spike {self.canonical_id} timebox expired ({timebox_str}). "
                f"Conclude experiment and run 'spec-ops spike graduate'"
            )
            return False, warning

        return True, ""


def start_spike(
    repo_root: Path,
    spike_id: str,
    hypothesis: str | None = None,
    timebox: str | None = None,
) -> SpikeSandbox:
    """Initializes and scaffolds an isolated spike worktree and test harness."""
    root = Path(repo_root).resolve()
    sandbox = SpikeSandbox(root, spike_id)
    task = sandbox.lookup_task()

    chosen_hyp = hypothesis or (getattr(task, "hypothesis", "") if task else "")
    if not chosen_hyp:
        chosen_hyp = (task.title if task else f"Empirically validate architectural hypothesis for {sandbox.canonical_id}")
    chosen_tb = timebox or (getattr(task, "timebox", "") if task else "") or "2h"

    # 1. Create worktree
    create_worktree(root, branch=sandbox.branch, worktree_dir=sandbox.worktree_dir)

    # 2. Scaffold harness
    sandbox.scaffold_harness(chosen_hyp, chosen_tb)

    # 3. Save metadata
    sandbox.save_metadata({
        "spike_id": sandbox.canonical_id,
        "num": sandbox.num,
        "hypothesis": chosen_hyp,
        "timebox": chosen_tb,
        "started_at": time.time(),
        "worktree_dir": str(sandbox.worktree_dir),
        "branch": sandbox.branch,
        "harness_dir": str(sandbox.harness_rel),
    })

    # 4. Install preflight hook
    sandbox.install_preflight_hook()

    # 5. Git commit initial scaffolding
    subprocess.run(["git", "add", "spikes"], cwd=sandbox.worktree_dir, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", f"Scaffold spike harness for {sandbox.canonical_id}"],
        cwd=sandbox.worktree_dir,
        capture_output=True,
    )

    return sandbox
