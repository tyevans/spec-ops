"""Hypothesis property-based tests for backlog lock concurrency and transactional rollback."""

from __future__ import annotations

import concurrent.futures
import threading
import time
from pathlib import Path

from hypothesis import given, settings
from hypothesis import strategies as st

from spec_ops.backlog.lock import (
    BacklogLock,
    TwoPhaseFileTransaction,
    atomic_write,
    recover_transactions,
)


@settings(max_examples=15, deadline=None)
@given(num_workers=st.integers(min_value=2, max_value=6))
def test_property_exactly_one_worker_acquires_contested_claim(tmp_path_factory, num_workers: int):
    """Asserts that across concurrent threads, exactly one thread acquires a contested claim at a time."""
    repo = tmp_path_factory.mktemp("lock_prop")
    shared_counter = [0]
    acquired_order: list[int] = []
    lock_file = repo / "backlog.lock"

    def worker_action(worker_id: int):
        lock = BacklogLock(repo, lock_file=lock_file)
        with lock.acquire(timeout=10.0):
            # Critical section
            current = shared_counter[0]
            time.sleep(0.005)
            shared_counter[0] = current + 1
            acquired_order.append(worker_id)

    with concurrent.futures.ThreadPoolExecutor(max_workers=num_workers) as executor:
        futs = [executor.submit(worker_action, wid) for wid in range(num_workers)]
        for f in concurrent.futures.as_completed(futs):
            f.result()

    assert shared_counter[0] == num_workers
    assert len(acquired_order) == num_workers
    assert len(set(acquired_order)) == num_workers


@settings(max_examples=15, deadline=None)
@given(
    timeout=st.floats(min_value=0.02, max_value=0.1),
    num_contenders=st.integers(min_value=2, max_value=4),
)
def test_property_zero_deadlocks_under_timeout_backoff(tmp_path_factory, timeout: float, num_contenders: int):
    """Asserts that zero deadlocks occur under timeout backoff when threads contend for lock."""
    repo = tmp_path_factory.mktemp("deadlock_prop")
    lock_file = repo / "backlog.lock"
    success_count = [0]
    timeout_count = [0]
    lock = BacklogLock(repo, lock_file=lock_file)

    barrier = threading.Barrier(num_contenders)

    def contender():
        barrier.wait()
        try:
            with lock.acquire(timeout=timeout):
                time.sleep(timeout * 1.5)  # Intentionally hold longer than timeout
                success_count[0] += 1
        except TimeoutError:
            timeout_count[0] += 1

    start_time = time.monotonic()
    with concurrent.futures.ThreadPoolExecutor(max_workers=num_contenders) as executor:
        futs = [executor.submit(contender) for _ in range(num_contenders)]
        for f in concurrent.futures.as_completed(futs):
            f.result()

    duration = time.monotonic() - start_time
    # Assert zero deadlocks: all threads completed within a bounded duration
    assert duration < 5.0
    assert success_count[0] >= 1
    assert success_count[0] + timeout_count[0] == num_contenders


@settings(max_examples=10, deadline=None)
@given(
    initial_text=st.text(alphabet=st.characters(blacklist_categories=("Cs",), blacklist_characters="\r"), min_size=10, max_size=200),
    corrupted_bytes=st.binary(min_size=1, max_size=100),
)
def test_property_corrupted_index_triggers_transaction_rollback(tmp_path_factory, initial_text: str, corrupted_bytes: bytes):
    """Asserts that corrupted index states automatically trigger transaction rollbacks to restore valid state."""
    repo = tmp_path_factory.mktemp("rollback_prop")
    target_file = repo / "PRIORITY.md"
    target_file.write_text(initial_text, encoding="utf-8")

    tx = TwoPhaseFileTransaction(target_file, repo_root=repo)
    staged = tx.prepare("# New Proposed Content\n")

    # Simulate an abort / corruption mid-transaction
    target_file.write_bytes(corrupted_bytes)
    assert target_file.read_bytes() == corrupted_bytes

    # Rollback restores original state
    tx.rollback()
    assert target_file.read_text(encoding="utf-8") == initial_text
    assert not staged.exists()

    # Verify recover_transactions also restores 0-byte corrupt files
    target_file.write_text(initial_text, encoding="utf-8")
    tx2 = TwoPhaseFileTransaction(target_file, repo_root=repo)
    tx2.prepare("# Another Proposed Content\n")
    # Truncate target file to 0 bytes
    target_file.write_text("", encoding="utf-8")
    assert target_file.stat().st_size == 0

    recover_transactions(repo)
    assert target_file.read_text(encoding="utf-8") == initial_text
