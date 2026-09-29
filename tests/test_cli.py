import os
import subprocess
import sys
from pathlib import Path

SRC_DIR = str(Path(__file__).resolve().parent.parent / "src")
CLI_ENV = {**os.environ, "PYTHONPATH": f"{SRC_DIR}:{os.environ.get('PYTHONPATH', '')}".rstrip(":")}


def test_cli_help():
    res = subprocess.run([sys.executable, "-m", "spec_ops.cli.main", "--help"], capture_output=True, text=True)
    assert res.returncode == 0
    assert "SpecOps: Opinionated Project Management as Code" in res.stdout


def test_cli_init_and_health(tmp_path: Path):
    # Test init
    init_res = subprocess.run(
        [sys.executable, "-m", "spec_ops.cli.main", "init", "--name", "CliTest", "--dir", str(tmp_path)],
        capture_output=True,
        text=True,
    )
    assert init_res.returncode == 0
    assert "Initialized SpecOps" in init_res.stdout

    # Test health
    health_res = subprocess.run(
        [sys.executable, "-m", "spec_ops.cli.main", "health"],
        cwd=str(tmp_path),
        capture_output=True,
        text=True,
    )
    assert health_res.returncode == 0
    assert "Invariant Met: Zero source files exceed length limit" in health_res.stdout


def test_cli_visualizer_build(tmp_path: Path):
    # Initialize
    subprocess.run(
        [sys.executable, "-m", "spec_ops.cli.main", "init", "--name", "VizTest", "--dir", str(tmp_path)],
        capture_output=True,
        text=True,
        check=True,
    )
    out_html = tmp_path / "dist" / "visualizer.html"
    res = subprocess.run(
        [sys.executable, "-m", "spec_ops.cli.main", "visualizer", "--build", str(out_html)],
        cwd=str(tmp_path),
        capture_output=True,
        text=True,
    )
    assert res.returncode == 0
    assert out_html.is_file()
    assert "SpecOps Visualizer" in out_html.read_text(encoding="utf-8")


def test_cli_rescue(tmp_path: Path):
    subprocess.run(
        [sys.executable, "-m", "spec_ops.cli.main", "init", "--name", "RescueTest", "--dir", str(tmp_path)],
        capture_output=True,
        text=True,
        check=True,
    )
    # List when empty
    res_list = subprocess.run(
        [sys.executable, "-m", "spec_ops.cli.main", "rescue", "--list"],
        cwd=str(tmp_path),
        capture_output=True,
        text=True,
    )
    assert res_list.returncode == 0
    assert "Active / Stalled Worktrees" in res_list.stdout

    # Inspect non-existent
    res_inspect = subprocess.run(
        [sys.executable, "-m", "spec_ops.cli.main", "rescue", "0099"],
        cwd=str(tmp_path),
        capture_output=True,
        text=True,
    )
    assert res_inspect.returncode == 1
    assert "No worktree found" in res_inspect.stdout

    # Prune
    res_prune = subprocess.run(
        [sys.executable, "-m", "spec_ops.cli.main", "rescue", "--prune"],
        cwd=str(tmp_path),
        capture_output=True,
        text=True,
    )
    assert res_prune.returncode == 0
    assert "Pruned and cleaned up" in res_prune.stdout


def test_cli_tui_once():
    res = subprocess.run(
        [sys.executable, "-m", "spec_ops.cli.main", "tui", "--once", "--view", "overview"],
        capture_output=True,
        text=True,
    )
    assert res.returncode == 0
    assert "SpecOps TUI" in res.stdout
    assert "Backlog Management" in res.stdout


def test_cli_init_with_agent_flags(tmp_path: Path):
    target = tmp_path / "cli_agents"
    res = subprocess.run(
        [
            sys.executable,
            "-m",
            "spec_ops.cli.main",
            "init",
            "--name",
            "AgentCliApp",
            "--dir",
            str(target),
            "--agent",
            "antigravity,claude,cursor",
        ],
        capture_output=True,
        text=True,
        env=CLI_ENV,
    )
    assert res.returncode == 0
    assert "Configured Agent Adapters: antigravity, claude, cursor" in res.stdout
    assert (target / "CLAUDE.md").is_file()
    assert (target / ".cursorrules").is_file()
    assert (target / "GEMINI.md").is_file()
    assert (target / ".agents" / "skills" / "curate" / "SKILL.md").is_file()
    assert (target / ".agents" / "skills" / "health" / "SKILL.md").is_file()
    assert (target / ".agents" / "skills" / "worker" / "SKILL.md").is_file()


def test_cli_init_with_invalid_agent(tmp_path: Path):
    target = tmp_path / "cli_invalid"
    res = subprocess.run(
        [
            sys.executable,
            "-m",
            "spec_ops.cli.main",
            "init",
            "--name",
            "InvalidAgentApp",
            "--dir",
            str(target),
            "--agent",
            "unknown_agent",
        ],
        capture_output=True,
        text=True,
        env=CLI_ENV,
    )
    assert res.returncode == 1


def test_cli_worker_flags():
    res = subprocess.run(
        [sys.executable, "-m", "spec_ops.cli.main", "worker", "--help"],
        capture_output=True,
        text=True,
        env=CLI_ENV,
    )
    assert res.returncode == 0
    assert "--no-review" in res.stdout
    assert "--skip-review" in res.stdout


def test_cli_curate_flags():
    res = subprocess.run(
        [sys.executable, "-m", "spec_ops.cli.main", "curate", "--help"],
        capture_output=True,
        text=True,
        env=CLI_ENV,
    )
    assert res.returncode == 0
    assert "--infer" in res.stdout
    assert "--dry-run" in res.stdout
    assert "--model" in res.stdout


def test_cli_curate_infer_dry_run(tmp_path: Path):
    subprocess.run(
        [sys.executable, "-m", "spec_ops.cli.main", "init", "--name", "CurateTest", "--dir", str(tmp_path)],
        capture_output=True,
        text=True,
        check=True,
        env=CLI_ENV,
    )
    res = subprocess.run(
        [sys.executable, "-m", "spec_ops.cli.main", "curate", "--infer", "--dry-run"],
        cwd=str(tmp_path),
        capture_output=True,
        text=True,
        env=CLI_ENV,
    )
    assert res.returncode == 0
    assert "SpecOps Inference Curation Audit (DRY RUN)" in res.stdout
    assert "Inference curation dry-run complete" in res.stdout



def test_cli_worker_execute_syntax(tmp_path: Path):
    res = subprocess.run(
        [sys.executable, "-m", "spec_ops.cli.main", "worker", "execute", "TASK-0099"],
        cwd=str(tmp_path),
        capture_output=True,
        text=True,
        env=CLI_ENV,
    )
    assert res.returncode == 1
    assert "Task TASK-0099 not found" in res.stdout


