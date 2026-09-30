"""SpecOps security bounded context: process sandboxing, interceptors, and guardrails."""

from __future__ import annotations

from .benchmark import run_comparative_benchmark
from .interceptor import (
    FORBIDDEN_UTILITIES,
    create_interceptor_shims,
    extract_executables,
    extract_executables_with_context,
    record_security_violation,
    resolve_audit_log_path,
    validate_command,
)
from .lockfile import (
    PROTECTED_DEPENDENCY_FILES,
    LockfileInspectionResult,
    check_diff_for_dependency_modifications,
    check_worktree_dependency_integrity,
    inspect_lockfile,
    validate_package_hashes,
    validate_package_name,
    validate_package_pinning,
    verify_lockfile,
    verify_uv_lock,
)
from .models import BenchmarkReport, BenchmarkResult, SecurityViolationEvent
from .network_guard import generate_network_isolation_sitecustomize, is_loopback_address, isolated_network
from .sandbox import ExecutionSandbox

__all__ = [
    "FORBIDDEN_UTILITIES",
    "BenchmarkReport",
    "BenchmarkResult",
    "ExecutionSandbox",
    "LockfileInspectionResult",
    "PROTECTED_DEPENDENCY_FILES",
    "SecurityViolationEvent",
    "check_diff_for_dependency_modifications",
    "check_worktree_dependency_integrity",
    "create_interceptor_shims",
    "extract_executables",
    "extract_executables_with_context",
    "generate_network_isolation_sitecustomize",
    "inspect_lockfile",
    "is_loopback_address",
    "isolated_network",
    "record_security_violation",
    "resolve_audit_log_path",
    "run_comparative_benchmark",
    "validate_command",
    "validate_package_hashes",
    "validate_package_name",
    "validate_package_pinning",
    "verify_lockfile",
    "verify_uv_lock",
]
