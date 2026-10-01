"""Dynamic Multi-Worker Fleet Concurrency and Adaptive Worktree Pool Sizing."""

from __future__ import annotations

import math
import os
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Callable


@dataclass(frozen=True)
class SystemMetrics:
    """Live host system utilization metrics sampled from standard operating system interfaces."""

    cpu_utilization_pct: float
    memory_utilization_pct: float
    disk_free_bytes: int
    disk_total_bytes: int

    @property
    def summary(self) -> str:
        """Formatted human-readable summary of metrics."""
        free_mb = self.disk_free_bytes // (1024 * 1024)
        total_mb = self.disk_total_bytes // (1024 * 1024)
        return (
            f"CPU: {self.cpu_utilization_pct:.1f}%, "
            f"Memory: {self.memory_utilization_pct:.1f}%, "
            f"Disk Free: {free_mb}MB / {total_mb}MB"
        )


@dataclass
class PoolConcurrencyConfig:
    """Configuration governing fleet worker concurrency bounds and resource thresholds."""

    min_workers: int = 1
    max_workers: int = 5
    cpu_threshold_pct: float = 85.0
    mem_threshold_pct: float = 90.0
    disk_min_free_bytes: int = 500_000_000

    def __post_init__(self) -> None:
        self.min_workers = max(1, self.min_workers)
        self.max_workers = max(self.min_workers, self.max_workers)
        self.cpu_threshold_pct = max(1.0, float(self.cpu_threshold_pct))
        self.mem_threshold_pct = max(1.0, float(self.mem_threshold_pct))
        self.disk_min_free_bytes = max(0, int(self.disk_min_free_bytes))


@dataclass(frozen=True)
class PoolEvaluation:
    """Result of evaluating dynamic capacity for new worker claims."""

    concurrency_limit: int
    available_slots: int
    is_throttled: bool
    metrics: SystemMetrics
    active_workers: int
    throttle_reason: str = ""


def sample_host_metrics(target_path: Path | str | None = None) -> SystemMetrics:
    """Samples real-time CPU, memory, and disk metrics using pure Python standard library."""
    # 1. CPU utilization via os.getloadavg() and os.cpu_count()
    cpu_utilization_pct = 0.0
    try:
        cpu_count = os.cpu_count() or 1
        if hasattr(os, "getloadavg"):
            load1, _, _ = os.getloadavg()
            cpu_utilization_pct = (load1 / max(1, cpu_count)) * 100.0
    except Exception:
        cpu_utilization_pct = 0.0

    # 2. System memory utilization via /proc/meminfo parsing
    memory_utilization_pct = 0.0
    meminfo_path = Path("/proc/meminfo")
    if meminfo_path.exists():
        try:
            mem_total_kb = 0
            mem_avail_kb = 0
            mem_free_kb = 0
            buffers_kb = 0
            cached_kb = 0
            for line in meminfo_path.read_text(encoding="utf-8").splitlines():
                if ":" in line:
                    key, rest = line.split(":", 1)
                    key = key.strip()
                    parts = rest.strip().split()
                    if parts and parts[0].isdigit():
                        val = int(parts[0])
                        if key == "MemTotal":
                            mem_total_kb = val
                        elif key == "MemAvailable":
                            mem_avail_kb = val
                        elif key == "MemFree":
                            mem_free_kb = val
                        elif key == "Buffers":
                            buffers_kb = val
                        elif key == "Cached":
                            cached_kb = val
            if mem_total_kb > 0:
                if mem_avail_kb > 0:
                    used_kb = mem_total_kb - mem_avail_kb
                else:
                    used_kb = mem_total_kb - (mem_free_kb + buffers_kb + cached_kb)
                memory_utilization_pct = max(0.0, min(100.0, (used_kb / mem_total_kb) * 100.0))
        except Exception:
            memory_utilization_pct = 0.0

    # 3. Worktree storage filesystem quota / free disk space via shutil.disk_usage()
    disk_path = Path(target_path) if target_path else Path.cwd()
    if not disk_path.exists():
        disk_path = Path.cwd()
    try:
        usage = shutil.disk_usage(disk_path)
        disk_free_bytes = usage.free
        disk_total_bytes = usage.total
    except Exception:
        disk_free_bytes = 10_000_000_000
        disk_total_bytes = 100_000_000_000

    return SystemMetrics(
        cpu_utilization_pct=max(0.0, cpu_utilization_pct),
        memory_utilization_pct=max(0.0, memory_utilization_pct),
        disk_free_bytes=max(0, disk_free_bytes),
        disk_total_bytes=max(0, disk_total_bytes),
    )


class FleetPoolController:
    """Calculates adaptive multi-worker fleet concurrency based on live host capacity."""

    def __init__(
        self,
        config: PoolConcurrencyConfig | None = None,
        metrics_sampler: Callable[[Path | str | None], SystemMetrics] | None = None,
    ) -> None:
        self.config = config or PoolConcurrencyConfig()
        self._metrics_sampler = metrics_sampler or sample_host_metrics

    def sample_metrics(self, target_path: Path | str | None = None) -> SystemMetrics:
        """Samples live system metrics using configured sampler."""
        return self._metrics_sampler(target_path)

    def calculate_concurrency(self, metrics: SystemMetrics) -> int:
        """Calculates optimal concurrent worker slots bounded between min_workers and max_workers.

        If any threshold is breached, concurrency scales down to min_workers.
        Otherwise, capacity scales up proportionally based on available resource headroom.
        """
        min_w = max(1, self.config.min_workers)
        max_w = max(min_w, self.config.max_workers)
        if min_w == max_w:
            return min_w

        # Sanitize metrics for robustness (avoid NaN, Inf)
        cpu = metrics.cpu_utilization_pct
        if math.isnan(cpu) or math.isinf(cpu) or cpu > self.config.cpu_threshold_pct:
            return min_w

        mem = metrics.memory_utilization_pct
        if math.isnan(mem) or math.isinf(mem) or mem > self.config.mem_threshold_pct:
            return min_w

        disk_free = metrics.disk_free_bytes
        disk_total = metrics.disk_total_bytes
        if math.isnan(disk_free) or math.isnan(disk_total) or disk_free < self.config.disk_min_free_bytes:
            return min_w

        cpu = max(0.0, cpu)
        mem = max(0.0, mem)
        disk_free = max(0, disk_free)
        disk_total = max(0, disk_total)

        # Compute normalized resource pressure (0.0 to 1.0)
        cpu_thresh = max(1.0, self.config.cpu_threshold_pct)
        mem_thresh = max(1.0, self.config.mem_threshold_pct)
        disk_min_free = self.config.disk_min_free_bytes

        cpu_pressure = min(1.0, cpu / cpu_thresh)
        mem_pressure = min(1.0, mem / mem_thresh)

        # Disk pressure engages when approaching minimum free quota (within 2x minimum)
        safe_disk_buffer = 2 * disk_min_free
        if disk_free < safe_disk_buffer and disk_min_free > 0:
            usable_buffer = safe_disk_buffer - disk_min_free
            free_in_buffer = max(0, disk_free - disk_min_free)
            disk_pressure = 1.0 - (free_in_buffer / usable_buffer)
        else:
            disk_pressure = 0.0

        max_pressure = max(0.0, min(1.0, max(cpu_pressure, mem_pressure, disk_pressure)))

        # Quiescent scaling: when pressure is low (<= 30%), host has full headroom for max_workers
        low_watermark = 0.30
        if max_pressure <= low_watermark:
            headroom = 1.0
        else:
            headroom = 1.0 - ((max_pressure - low_watermark) / (1.0 - low_watermark))

        headroom = max(0.0, min(1.0, headroom))
        span = max_w - min_w
        additional_slots = int(math.ceil(headroom * span))
        slots = min_w + additional_slots
        return max(min_w, min(max_w, slots))

    def evaluate_capacity(
        self,
        metrics: SystemMetrics | None = None,
        active_workers: int = 0,
        target_path: Path | str | None = None,
    ) -> PoolEvaluation:
        """Evaluates live capacity and computes available slots for newly claimed worktrees."""
        current_metrics = metrics if metrics is not None else self.sample_metrics(target_path)
        limit = self.calculate_concurrency(current_metrics)

        cpu = current_metrics.cpu_utilization_pct
        mem = current_metrics.memory_utilization_pct
        disk_free = current_metrics.disk_free_bytes

        cpu_invalid = math.isnan(cpu) or math.isinf(cpu)
        mem_invalid = math.isnan(mem) or math.isinf(mem)
        disk_invalid = math.isnan(disk_free)

        cpu_breached = cpu_invalid or (cpu > self.config.cpu_threshold_pct)
        mem_breached = mem_invalid or (mem > self.config.mem_threshold_pct)
        disk_breached = disk_invalid or (disk_free < self.config.disk_min_free_bytes)
        is_throttled = cpu_breached or mem_breached or disk_breached

        throttle_reason = ""
        if is_throttled:
            reasons: list[str] = []
            if cpu_breached:
                reasons.append(
                    f"CPU utilization {current_metrics.cpu_utilization_pct} > "
                    f"{self.config.cpu_threshold_pct:.1f}% threshold"
                )
            if mem_breached:
                reasons.append(
                    f"Memory utilization {current_metrics.memory_utilization_pct} > "
                    f"{self.config.mem_threshold_pct:.1f}% threshold"
                )
            if disk_breached:
                reasons.append(
                    f"Worktree disk free {current_metrics.disk_free_bytes}B < "
                    f"{self.config.disk_min_free_bytes}B minimum quota"
                )
            throttle_reason = "; ".join(reasons)

        # Invariant (ADR-0005): Throttling affects new claims; active workers execute unimpeded
        safe_active = max(0, active_workers)
        available_slots = max(0, limit - safe_active)

        return PoolEvaluation(
            concurrency_limit=limit,
            available_slots=available_slots,
            is_throttled=is_throttled,
            metrics=current_metrics,
            active_workers=safe_active,
            throttle_reason=throttle_reason,
        )

    def get_current_concurrency(self, target_path: Path | str | None = None) -> int:
        """Samples metrics and computes current concurrency limit."""
        return self.calculate_concurrency(self.sample_metrics(target_path))
