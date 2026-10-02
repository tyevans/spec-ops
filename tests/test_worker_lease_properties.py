"""Hypothesis property tests for dynamic worker lease heartbeat manager.

Governed by ADR-0001, ADR-0002, ADR-0003, ADR-0005, ADR-0009, ADR-0012; PRD-0004; TASK-0166.
"""

from __future__ import annotations

import datetime
import os
from pathlib import Path
import tempfile
from hypothesis import given, settings
import hypothesis.strategies as st

from spec_ops.worker.lease_manager import (
    WorkerLease,
    WorkerLeaseManager,
    parse_utc_timestamp,
)


@settings(max_examples=100, deadline=None)
@given(
    ttl=st.integers(min_value=5, max_value=86400),
    elapsed_fraction=st.floats(min_value=0.0, max_value=0.999),
)
def test_lease_never_prematurely_invalidated_within_validity_window(
    ttl: int, elapsed_fraction: float
):
    """Asserts that lease expiry calculations are strictly monotonic and never invalidate a living process before expiry."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        mgr = WorkerLeaseManager(Path(tmp_dir), default_ttl_seconds=ttl)
        lease = mgr.create_lease("TASK-0001", pid=os.getpid(), ttl_seconds=ttl)

        created_dt = parse_utc_timestamp(lease.created_at)
        expires_dt = parse_utc_timestamp(lease.expires_at)

        # Monotonicity: expires_at is strictly greater than created_at
        assert expires_dt > created_dt
        assert (expires_dt - created_dt).total_seconds() == float(ttl)

        # Any time point within [created_at, expires_at) must evaluate as valid for a living process
        elapsed_seconds = ttl * elapsed_fraction
        test_now = created_dt + datetime.timedelta(seconds=elapsed_seconds)

        is_valid, reason = mgr.evaluate_lease(lease, now=test_now)
        assert is_valid is True, f"Premature lease invalidation at {elapsed_fraction:.3f} of TTL: {reason}"


@settings(max_examples=50, deadline=None)
@given(
    ttl=st.integers(min_value=10, max_value=3600),
    heartbeat_steps=st.lists(
        st.integers(min_value=1, max_value=5),
        min_size=1,
        max_size=5,
    ),
)
def test_heartbeat_strictly_extends_expiration_monotonically(
    ttl: int, heartbeat_steps: list[int]
):
    """Asserts that repeated heartbeats strictly advance expiration monotonically."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        mgr = WorkerLeaseManager(Path(tmp_dir), default_ttl_seconds=ttl)
        lease = mgr.create_lease("TASK-0002", pid=os.getpid(), ttl_seconds=ttl)

        last_expiry = parse_utc_timestamp(lease.expires_at)
        curr_time = parse_utc_timestamp(lease.created_at)

        for step in heartbeat_steps:
            curr_time += datetime.timedelta(seconds=step)
            updated = mgr.record_heartbeat("TASK-0002", lease_token=lease.lease_token, now=curr_time)
            assert updated is not None
            new_expiry = parse_utc_timestamp(updated.expires_at)
            assert new_expiry > last_expiry
            last_expiry = new_expiry
