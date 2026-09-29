"""SpecOps security bounded context: process sandboxing, interceptors, and guardrails."""

from __future__ import annotations

from .benchmark import run_comparative_benchmark
from .interceptor import (
    FORBIDDEN_UTILITIES,
    create_interceptor_shims,
    extract_executables,
    record_security_violation,
    resolve_audit_log_path,
    validate_command,
)
from .models import BenchmarkReport, BenchmarkResult, SecurityViolationEvent
from .network import isolated_network, is_loopback_address
from .sandbox import ExecutionSandbox

__all__ = [
    "FORBIDDEN_UTILITIES",
    "BenchmarkReport",
    "BenchmarkResult",
    "ExecutionSandbox",
    "SecurityViolationEvent",
    "create_interceptor_shims",
    "extract_executables",
    "is_loopback_address",
    "isolated_network",
    "record_security_violation",
    "resolve_audit_log_path",
    "run_comparative_benchmark",
    "validate_command",
]
