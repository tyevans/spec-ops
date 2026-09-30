"""Pytest configuration and environment setup for SpecOps tests."""

import os
import re
import sys
from pathlib import Path
from typing import Any, Callable

import pytest

# Ensure the worktree src/ directory takes precedence over any installed packages
ROOT_DIR = Path(__file__).resolve().parent.parent
SRC_DIR = str(ROOT_DIR / "src")
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

# Set PYTHONPATH in os.environ so child subprocesses inherit it
current_pythonpath = os.environ.get("PYTHONPATH", "")
if SRC_DIR not in current_pythonpath.split(os.pathsep):
    os.environ["PYTHONPATH"] = (
        f"{SRC_DIR}{os.pathsep}{current_pythonpath}" if current_pythonpath else SRC_DIR
    )

# Ensure hermetic git environment for test isolation (ignore host commit.gpgsign, etc.)
os.environ.setdefault("GIT_CONFIG_GLOBAL", "/dev/null")
os.environ.setdefault("GIT_CONFIG_NOSYSTEM", "1")

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



def _discover_dynamic_marks(root_dir: Path) -> set[str]:
    """Scan feature files and user stories to discover marks dynamically."""
    marks: set[str] = set()

    # Discover tags from all .feature files in tests/
    tests_dir = root_dir / "tests"
    if tests_dir.is_dir():
        for feature_path in tests_dir.glob("**/*.feature"):
            try:
                with open(feature_path, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line.startswith("@"):
                            for token in line.split():
                                if token.startswith("@"):
                                    tag = token[1:].strip()
                                    if tag:
                                        marks.add(tag)
            except OSError:
                pass

    # Discover user stories from docs/project/user_stories/
    us_dir = root_dir / "docs" / "project" / "user_stories"
    if us_dir.is_dir():
        for path in us_dir.glob("**/*.md"):
            m = re.match(r"^(us[-_]\d+)", path.name, re.IGNORECASE)
            if m:
                raw_id = m.group(1).lower()
                marks.add(raw_id.replace("-", "_"))

    # Register standard user story sequence (us_0001 .. us_0500)
    for i in range(1, 501):
        marks.add(f"us_{i:04d}")

    return marks


def pytest_configure(config: pytest.Config) -> None:
    """Register discovered BDD marks and configure dynamic marker interception."""
    # Pre-register discovered marks
    discovered = _discover_dynamic_marks(ROOT_DIR)
    for mark in sorted(discovered):
        config.addinivalue_line("markers", f"{mark}: SpecOps BDD / User Story tag")

    # Install dynamic attribute interceptor on pytest.mark generator
    # so any on-the-fly us_*, task_*, spike_*, or custom BDD tag is registered
    mark_gen = pytest.mark
    orig_getattr = mark_gen.__class__.__getattr__

    def _dynamic_mark_getattr(self: Any, name: str) -> Any:
        if not name.startswith("_"):
            cfg = getattr(self, "_config", None)
            markers = getattr(self, "_markers", None)
            if cfg is not None and markers is not None and name not in markers:
                cfg.addinivalue_line("markers", f"{name}: dynamic SpecOps marker")
                markers.add(name)
        return orig_getattr(self, name)

    mark_gen.__class__.__getattr__ = _dynamic_mark_getattr


@pytest.hookimpl(tryfirst=True)
def pytest_bdd_apply_tag(tag: str, function: Callable[..., Any]) -> bool:
    """Hook to apply pytest-bdd tags dynamically without unknown mark warnings."""
    cfg = getattr(pytest.mark, "_config", None)
    markers = getattr(pytest.mark, "_markers", None)
    if cfg is not None and markers is not None and tag not in markers:
        cfg.addinivalue_line("markers", f"{tag}: SpecOps BDD tag")
        markers.add(tag)
    mark = getattr(pytest.mark, tag)
    mark(function)
    return True


