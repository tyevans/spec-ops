"""Pytest configuration and environment setup for SpecOps tests."""

import os
import sys
from pathlib import Path

# Ensure the worktree src/ directory takes precedence over any installed packages
SRC_DIR = str(Path(__file__).resolve().parent.parent / "src")
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

# Set PYTHONPATH in os.environ so child subprocesses inherit it
current_pythonpath = os.environ.get("PYTHONPATH", "")
if SRC_DIR not in current_pythonpath.split(os.pathsep):
    os.environ["PYTHONPATH"] = (
        f"{SRC_DIR}{os.pathsep}{current_pythonpath}" if current_pythonpath else SRC_DIR
    )

# Isolate git commands in tests from user global ~/.gitconfig (e.g. commit.gpgsign = true)
if "GIT_CONFIG_GLOBAL" not in os.environ:
    os.environ["GIT_CONFIG_GLOBAL"] = "/dev/null"

try:
    from hypothesis import HealthCheck, settings

    settings.register_profile(
        "default",
        suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
        deadline=None,
    )
    settings.load_profile("default")
except ImportError:
    pass

