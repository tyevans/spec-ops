"""Generative property test runner and verification engine.

Governed by ADR-0001, ADR-0002, ADR-0003, ADR-0007, ADR-0009; PRD-0005; US-0062.
Target Bounded Context: core. File length strictly under 400 lines.
"""

from __future__ import annotations

import argparse
import importlib.util
import inspect
import json
import re
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable

try:
    from hypothesis import HealthCheck, settings
except ImportError:
    HealthCheck = None  # type: ignore[assignment, misc]
    settings = None  # type: ignore[assignment, misc]


def is_hypothesis_available() -> bool:
    """Returns True if Hypothesis dependency is installed and available."""
    return settings is not None and HealthCheck is not None



@dataclass
class PropertyTestResult:
    """Outcome of a single generative property test execution."""

    name: str
    function_name: str
    module_name: str
    status: str  # "passed", "failed", "skipped"
    duration_seconds: float
    error_message: str = ""
    examples_tested: int = 0


@dataclass
class PropertyRunReport:
    """Aggregated execution report of generative property test verification."""

    total_count: int = 0
    passed_count: int = 0
    failed_count: int = 0
    duration_seconds: float = 0.0
    max_examples: int = 100
    results: list[PropertyTestResult] = field(default_factory=list)

    @property
    def is_success(self) -> bool:
        return self.failed_count == 0 and self.total_count > 0

    def format_output(self) -> str:
        lines = [
            "=== SpecOps Generative Property Invariant Verification ===",
            f"Configured Profile: deadline=None, suppressed timing checks, max_examples={self.max_examples}",
            f"Discovered {self.total_count} property test suite(s):",
            "",
        ]
        for r in self.results:
            icon = "✅ PASS" if r.status == "passed" else "❌ FAIL"
            lines.append(f"  {icon}: {r.name} ({r.function_name}) [{r.duration_seconds:.2f}s]")
            if r.error_message:
                lines.append(f"     Error: {r.error_message}")

        lines.append("")
        if self.is_success:
            lines.append(
                f"✨ Invariant Verification Passed: {self.passed_count}/{self.total_count} suites verified ({self.duration_seconds:.2f}s)"
            )
        else:
            lines.append(
                f"❌ Invariant Verification Failed: {self.failed_count}/{self.total_count} suites failed ({self.duration_seconds:.2f}s)"
            )
        return "\n".join(lines)

    def to_dict(self) -> dict[str, Any]:
        return {
            "is_success": self.is_success,
            "total_count": self.total_count,
            "passed_count": self.passed_count,
            "failed_count": self.failed_count,
            "duration_seconds": round(self.duration_seconds, 3),
            "max_examples": self.max_examples,
            "results": [asdict(r) for r in self.results],
        }


def configure_hypothesis_profile(max_examples: int | None = None, deadline: int | None = None) -> int:
    """Configures deterministic Hypothesis profile per ADR-0009 invariants."""
    if settings is None or HealthCheck is None:
        raise RuntimeError(
            "Hypothesis is required for property test verification. "
            "Install hypothesis or run within a project environment: uv run spec-ops verify"
        )
    resolved_examples = max_examples if (max_examples is not None and max_examples > 0) else 100
    profile_name = "specops_deterministic"
    settings.register_profile(
        profile_name,
        deadline=deadline,
        suppress_health_check=[
            HealthCheck.too_slow,
            HealthCheck.differing_executors,
        ],
        max_examples=resolved_examples,
    )
    settings.load_profile(profile_name)
    return resolved_examples


def _derive_suite_name(fn: Callable[..., Any]) -> str:
    """Derives canonical invariant name from function docstring or identifier."""
    doc = inspect.getdoc(fn) or ""
    # Check known invariant markers in docstring
    if "Parser Round-Trip" in doc or "Parser-to-Serializer" in doc:
        return "Parser Round-Trip"
    if "Graph Acyclicity" in doc or "Acyclicity" in doc:
        return "Graph Acyclicity"
    if "Boundary Classification" in doc or "Invariant Boundary" in doc:
        return "Boundary Classification"
    if "Buffer Capacity" in doc or "Buffer Health" in doc:
        return "Buffer Capacity"
    if "Graph Permutation" in doc or "Permutation Invariance" in doc:
        return "Graph Permutation Invariance"

    # Match e.g. "Review Approval Invariant: ..."
    match_prefix = re.search(r"^(.+?\bInvariant\b)\s*:", doc, re.MULTILINE | re.IGNORECASE)
    if match_prefix:
        return match_prefix.group(1).strip()

    # Match "Invariant:\s*<Name>"
    match_colon = re.search(r"\bInvariant:\s*([^.\n]+)", doc, re.IGNORECASE)
    if match_colon:
        return match_colon.group(1).strip()

    first_line = doc.splitlines()[0].strip() if doc else ""
    if first_line and ":" in first_line:
        clean = first_line.split(":")[0].strip()
        if clean:
            return clean

    # Fallback to humanized function name
    fn_name = fn.__name__
    if fn_name.startswith("test_property_"):
        return fn_name.replace("test_property_", "").replace("_", " ").title()
    if fn_name.startswith("test_"):
        return fn_name.replace("test_", "").replace("_", " ").title()
    return fn_name


def is_hypothesis_test(fn: Any, name: str = "") -> bool:
    """Returns True if the callable is recognized as a Hypothesis property test."""
    if not callable(fn):
        return False
    fn_name = name or getattr(fn, "__name__", "")
    return bool(
        getattr(fn, "is_hypothesis_test", False)
        or hasattr(fn, "hypothesis")
        or hasattr(fn, "_hypothesis_internal_use_raw_state")
        or hasattr(fn, "_hypothesis_internal_use_seed")
        or hasattr(fn, "_hypothesis_internal_use_settings")
        or hasattr(fn, "_hypothesis_internal_given_arguments")
        or "property" in fn_name.lower()
        or "properties" in fn_name.lower()
    )


def find_workspace_root(start_path: Path | str | None = None) -> Path:
    """Finds project workspace root by searching upwards for marker files."""
    current = (Path(start_path) if start_path else Path.cwd()).resolve()
    if current.is_file():
        current = current.parent
    for parent in [current, *current.parents]:
        if (parent / "pyproject.toml").is_file() or (parent / "specops.toml").is_file() or (parent / ".git").is_dir():
            return parent
    return current


def discover_property_tests(
    target_path: Path | str | None = None,
    root_dir: Path | None = None,
    filter_expr: str | None = None,
) -> list[tuple[str, Callable[..., Any], str, str]]:
    """Discovers Hypothesis property tests from target path or test suites."""
    target_p = Path(target_path) if target_path else None
    root = (root_dir or find_workspace_root(target_p)).resolve()
    for extra_dir in [root / "src", root]:
        if extra_dir.is_dir() and str(extra_dir) not in sys.path:
            sys.path.insert(0, str(extra_dir))

    files_to_scan: list[Path] = []
    if target_p:
        target = target_p if target_p.is_absolute() else (root / target_p).resolve()
        if target.is_file():
            files_to_scan.append(target)
        elif target.is_dir():
            for p in sorted(target.rglob("test_*_properties.py")):
                if p.is_file():
                    files_to_scan.append(p)
            hypo_file = target / "test_hypothesis_properties.py"
            if hypo_file.is_file() and hypo_file not in files_to_scan:
                files_to_scan.append(hypo_file)
    else:
        default_file = (root / "tests" / "test_hypothesis_properties.py").resolve()
        if default_file.is_file():
            files_to_scan.append(default_file)

    discovered: list[tuple[str, Callable[..., Any], str, str]] = []
    seen_funcs: set[str] = set()

    for file_path in files_to_scan:
        mod_name = f"spec_ops_prop_{file_path.stem}"
        spec = importlib.util.spec_from_file_location(mod_name, file_path)
        if not spec or not spec.loader:
            continue
        module = importlib.util.module_from_spec(spec)
        sys.modules[mod_name] = module
        try:
            spec.loader.exec_module(module)
        except Exception as exc:
            if target_path:
                print(f"⚠️ Warning: Failed to import property test module '{file_path}': {exc}", file=sys.stderr)
            continue

        def _record_test(suite_name: str, fn: Callable[..., Any], test_id: str) -> None:
            func_key = f"{file_path.name}:{test_id}"
            if func_key in seen_funcs:
                return
            if filter_expr:
                f_lower = filter_expr.lower()
                if f_lower not in suite_name.lower() and f_lower not in test_id.lower():
                    return
            seen_funcs.add(func_key)
            discovered.append((suite_name, fn, test_id, file_path.name))

        for attr_name in dir(module):
            obj = getattr(module, attr_name)
            if attr_name.startswith("test_") and callable(obj) and not inspect.isclass(obj):
                if is_hypothesis_test(obj, attr_name):
                    _record_test(_derive_suite_name(obj), obj, attr_name)
            elif inspect.isclass(obj) and (attr_name.startswith("Test") or "test" in attr_name.lower()):
                if getattr(obj, "__module__", None) != module.__name__:
                    continue
                instance = None
                for method_name in dir(obj):
                    if not method_name.startswith("test_"):
                        continue
                    raw_fn = getattr(obj, method_name)
                    if not callable(raw_fn) or not is_hypothesis_test(raw_fn, method_name):
                        continue
                    if instance is None:
                        try:
                            instance = obj()
                        except Exception:
                            try:
                                instance = object.__new__(obj)
                            except Exception:
                                pass
                    bound_fn = getattr(instance, method_name) if instance is not None else raw_fn
                    _record_test(_derive_suite_name(bound_fn), bound_fn, f"{attr_name}::{method_name}")

    return discovered


def run_property_tests(
    target_path: Path | str | None = None,
    root_dir: Path | None = None,
    max_examples: int | None = None,
    filter_expr: str | None = None,
) -> PropertyRunReport:
    """Executes discovered generative property tests with deterministic configuration."""
    resolved_examples = configure_hypothesis_profile(max_examples=max_examples)
    discovered = discover_property_tests(
        target_path=target_path,
        root_dir=root_dir,
        filter_expr=filter_expr,
    )

    results: list[PropertyTestResult] = []
    overall_start = time.perf_counter()

    for suite_name, fn, fn_name, mod_name in discovered:
        t_start = time.perf_counter()
        status = "passed"
        error_msg = ""
        try:
            fn()
        except Exception as exc:
            status = "failed"
            error_msg = f"{type(exc).__name__}: {exc}"
        t_duration = time.perf_counter() - t_start

        results.append(
            PropertyTestResult(
                name=suite_name,
                function_name=fn_name,
                module_name=mod_name,
                status=status,
                duration_seconds=t_duration,
                error_message=error_msg,
                examples_tested=resolved_examples,
            )
        )

    overall_duration = time.perf_counter() - overall_start
    passed_count = sum(1 for r in results if r.status == "passed")
    failed_count = sum(1 for r in results if r.status == "failed")

    return PropertyRunReport(
        total_count=len(results),
        passed_count=passed_count,
        failed_count=failed_count,
        duration_seconds=overall_duration,
        max_examples=resolved_examples,
        results=results,
    )


def handle_properties_command(args: argparse.Namespace, config: Any) -> int:
    """CLI handler for 'spec-ops test properties' and 'spec-ops verify --invariants'."""
    max_examples = getattr(args, "max_examples", None)
    target_path = getattr(args, "opt_path", None) or getattr(args, "path", None)
    as_json = getattr(args, "json", False)
    filter_expr = getattr(args, "filter_expr", None)

    if not is_hypothesis_available():
        err_msg = (
            "Hypothesis is required for property test verification.\n"
            "👉 Install hypothesis (`pip install hypothesis` or `uv add --dev hypothesis`)\n"
            "👉 Or run within your project environment: `uv run spec-ops verify`"
        )
        if as_json:
            print(json.dumps({"is_success": False, "error": err_msg}, indent=2))
        else:
            print(f"⚠️ {err_msg}", file=sys.stderr)
        return 1

    try:
        report = run_property_tests(
            target_path=target_path,
            root_dir=getattr(config, "root_dir", None),
            max_examples=max_examples,
            filter_expr=filter_expr,
        )
    except RuntimeError as err:
        if as_json:
            print(json.dumps({"is_success": False, "error": str(err)}, indent=2))
        else:
            print(f"⚠️ {err}", file=sys.stderr)
        return 1

    if as_json:
        print(json.dumps(report.to_dict(), indent=2))
        return 0 if report.is_success else 1

    output = report.format_output()
    if report.is_success:
        print(output)
        return 0

    print(output, file=sys.stderr)
    return 1
