"""Web PRD Studio client-side state synchronizer and auto-save engine.

Governed by ADR-0001, ADR-0002, ADR-0003, ADR-0009, ADR-0013; PRD-0003; US-0044, US-0045.
Pure Python standard library with zero external daemons. Source strictly under 400 lines (ADR-0002).
"""

from __future__ import annotations

from dataclasses import dataclass
import difflib
import hashlib
import json
import os
from pathlib import Path
import re
import threading
import time
from typing import Any, Callable


def compute_sha256(content: str | bytes) -> str:
    """Computes SHA-256 hexadecimal digest for raw content."""
    if isinstance(content, str):
        content = content.encode("utf-8")
    return hashlib.sha256(content).hexdigest()


@dataclass
class SyncResult:
    """Outcome of a PRD draft synchronization or auto-save operation."""

    status: str  # "saved" | "conflict" | "error"
    revision_digest: str
    disk_hash: str
    client_hash: str
    diff_summary: str
    message: str
    conflict_path: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Converts SyncResult to JSON-serializable dictionary."""
        return {
            "status": self.status,
            "revision_digest": self.revision_digest,
            "disk_hash": self.disk_hash,
            "client_hash": self.client_hash,
            "diff_summary": self.diff_summary,
            "message": self.message,
            "conflict_path": self.conflict_path,
            "success": self.status == "saved",
        }


def atomic_write(target_path: Path, content: str) -> None:
    """Atomically writes content to target path using PID/timestamp tempfile."""
    target_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = target_path.with_name(f".{target_path.name}.{os.getpid()}.{time.time_ns()}.tmp")
    try:
        tmp.write_text(content, encoding="utf-8")
        tmp.replace(target_path)
    except Exception:
        if tmp.exists():
            tmp.unlink(missing_ok=True)
        raise


def resolve_prd_path(prd_path: Path | str, repo_root: Path | None = None) -> Path:
    """Resolves a PRD path relative to repo root or working directory."""
    p = Path(prd_path)
    if not p.is_absolute():
        root = Path(repo_root).resolve() if repo_root else Path.cwd()
        p = (root / p).resolve()
    return p


def find_prd_file(repo_root: Path, prd_identifier: str) -> Path | None:
    """Locates a PRD markdown file across docs/project/product/ by ID or filename."""
    product_dir = repo_root / "docs" / "project" / "product"
    if not product_dir.exists():
        return None

    norm_id = prd_identifier.strip().lower()
    clean_digits = re.findall(r"\d+", norm_id)
    target_pattern = f"prd-{int(clean_digits[-1]):04d}" if clean_digits else norm_id

    for p in product_dir.rglob("*.md"):
        if target_pattern in p.name.lower():
            return p
    return None


def save_draft(
    prd_path: Path | str,
    content: str,
    expected_hash: str | None = None,
    repo_root: Path | None = None,
) -> SyncResult:
    """Saves PRD draft with SHA-256 pre-save concurrency checks and conflict preservation."""
    try:
        target = resolve_prd_path(prd_path, repo_root=repo_root)
        client_hash = compute_sha256(content)

        if target.exists() and target.is_file():
            disk_content = target.read_text(encoding="utf-8")
            disk_hash = compute_sha256(disk_content)

            if expected_hash is not None and expected_hash != disk_hash:
                diff_lines = list(
                    difflib.unified_diff(
                        disk_content.splitlines(keepends=True),
                        content.splitlines(keepends=True),
                        fromfile=f"disk:{target.name}",
                        tofile=f"client:{target.name}",
                    )
                )
                diff_summary = "".join(diff_lines)
                conflict_path = target.with_name(f"{target.stem}.conflict{target.suffix}")
                atomic_write(conflict_path, content)

                return SyncResult(
                    status="conflict",
                    revision_digest=disk_hash,
                    disk_hash=disk_hash,
                    client_hash=client_hash,
                    diff_summary=diff_summary,
                    message=(
                        f"Conflict detected: disk hash ({disk_hash[:8]}) differs from expected hash "
                        f"({expected_hash[:8]}). Disk preserved; client draft saved to {conflict_path.name}."
                    ),
                    conflict_path=str(conflict_path),
                )

        atomic_write(target, content)
        return SyncResult(
            status="saved",
            revision_digest=client_hash,
            disk_hash=client_hash,
            client_hash=client_hash,
            diff_summary="",
            message="Draft auto-saved successfully.",
            conflict_path=None,
        )
    except Exception as exc:
        return SyncResult(
            status="error",
            revision_digest="",
            disk_hash="",
            client_hash=compute_sha256(content) if content else "",
            diff_summary="",
            message=str(exc),
            conflict_path=None,
        )


def get_draft_status(prd_path: Path | str, repo_root: Path | None = None) -> dict[str, Any]:
    """Inspects PRD draft on disk, returning content, SHA-256 digest, and timestamp."""
    target = resolve_prd_path(prd_path, repo_root=repo_root)
    if not target.exists() or not target.is_file():
        empty_hash = compute_sha256("")
        return {
            "path": str(target),
            "content": "",
            "digest": empty_hash,
            "revision_digest": empty_hash,
            "last_modified": 0.0,
            "exists": False,
            "size": 0,
        }

    content = target.read_text(encoding="utf-8")
    digest = compute_sha256(content)
    stat = target.stat()
    return {
        "path": str(target),
        "content": content,
        "digest": digest,
        "revision_digest": digest,
        "last_modified": stat.st_mtime,
        "exists": True,
        "size": stat.st_size,
    }


class PRDSyncEngine:
    """Manages draft revisions, debounce timers, and debounced writes to PRD documents."""

    def __init__(self, repo_root: Path | str | None = None, debounce_interval: float = 0.5):
        self.repo_root = Path(repo_root).resolve() if repo_root else Path.cwd()
        self.debounce_interval = max(0.01, float(debounce_interval))
        self._timers: dict[str, threading.Timer] = {}
        self._pending: dict[str, tuple[str, str | None, Callable[[SyncResult], None] | None]] = {}
        self._history: dict[str, list[str]] = {}
        self._lock = threading.Lock()

    def save_draft(
        self,
        prd_path: Path | str,
        content: str,
        expected_hash: str | None = None,
    ) -> SyncResult:
        """Immediately writes PRD draft, cancelling any pending debounce timer."""
        target = resolve_prd_path(prd_path, self.repo_root)
        key = str(target)

        with self._lock:
            timer = self._timers.pop(key, None)
            if timer:
                timer.cancel()
            self._pending.pop(key, None)

        result = save_draft(target, content, expected_hash, repo_root=self.repo_root)

        with self._lock:
            if result.status == "saved":
                hist = self._history.setdefault(key, [])
                hist.append(result.revision_digest)

        return result

    def get_draft_status(self, prd_path: Path | str) -> dict[str, Any]:
        """Returns draft status for target PRD."""
        return get_draft_status(prd_path, repo_root=self.repo_root)

    def debounce_save(
        self,
        prd_path: Path | str,
        content: str,
        expected_hash: str | None = None,
        delay: float | None = None,
        callback: Callable[[SyncResult], None] | None = None,
    ) -> None:
        """Schedules a debounced save operation, resetting existing timer."""
        target = resolve_prd_path(prd_path, self.repo_root)
        key = str(target)
        wait_sec = self.debounce_interval if delay is None else max(0.001, float(delay))

        with self._lock:
            old_timer = self._timers.pop(key, None)
            if old_timer:
                old_timer.cancel()

            self._pending[key] = (content, expected_hash, callback)

            def _flush():
                with self._lock:
                    pending_data = self._pending.pop(key, None)
                    self._timers.pop(key, None)
                if pending_data:
                    c, h, cb = pending_data
                    res = self.save_draft(key, c, h)
                    if cb:
                        try:
                            cb(res)
                        except Exception:
                            pass

            timer = threading.Timer(wait_sec, _flush)
            self._timers[key] = timer
            timer.start()

    def flush_pending(self, prd_path: Path | str | None = None) -> list[SyncResult]:
        """Immediately flushes all pending debounced writes or a specific target path."""
        keys_to_flush: list[str] = []
        with self._lock:
            if prd_path:
                target_key = str(resolve_prd_path(prd_path, self.repo_root))
                if target_key in self._pending:
                    keys_to_flush.append(target_key)
            else:
                keys_to_flush.extend(list(self._pending.keys()))

            pending_items = []
            for k in keys_to_flush:
                t = self._timers.pop(k, None)
                if t:
                    t.cancel()
                item = self._pending.pop(k, None)
                if item:
                    pending_items.append((k, item[0], item[1], item[2]))

        results: list[SyncResult] = []
        for k, c, h, cb in pending_items:
            res = self.save_draft(k, c, h)
            if cb:
                try:
                    cb(res)
                except Exception:
                    pass
            results.append(res)
        return results

    def cancel_pending(self, prd_path: Path | str | None = None) -> None:
        """Cancels active timers and pending drafts without saving."""
        with self._lock:
            if prd_path:
                target_key = str(resolve_prd_path(prd_path, self.repo_root))
                t = self._timers.pop(target_key, None)
                if t:
                    t.cancel()
                self._pending.pop(target_key, None)
            else:
                for t in self._timers.values():
                    t.cancel()
                self._timers.clear()
                self._pending.clear()

    def get_revision_history(self, prd_path: Path | str) -> list[str]:
        """Returns sequence of saved revision digests for target path."""
        key = str(resolve_prd_path(prd_path, self.repo_root))
        with self._lock:
            return list(self._history.get(key, []))


def handle_prd_draft_get(
    repo_root: Path,
    query_params: dict[str, list[str]],
    engine: PRDSyncEngine | None = None,
) -> tuple[int, dict[str, Any]]:
    """Handles GET /api/prd/draft returning current content, digest, and metadata."""
    raw_path = query_params.get("path", [None])[0] or query_params.get("file_path", [None])[0]
    prd_id = query_params.get("prd", [None])[0] or query_params.get("prd_id", [None])[0]

    target: Path | None = None
    if raw_path:
        target = resolve_prd_path(raw_path, repo_root)
    elif prd_id:
        target = find_prd_file(repo_root, prd_id)
        if not target:
            return 404, {"success": False, "error": f"PRD '{prd_id}' not found"}
    else:
        return 400, {"success": False, "error": "Missing 'path' or 'prd' parameter"}

    status = (engine or PRDSyncEngine(repo_root)).get_draft_status(target)
    if not status.get("exists"):
        return 404, {"success": False, "error": f"File not found: {status['path']}"}

    status["success"] = True
    return 200, status


def handle_prd_save_post(
    repo_root: Path,
    payload: dict[str, Any],
    engine: PRDSyncEngine | None = None,
) -> tuple[int, dict[str, Any]]:
    """Handles POST /api/prd/save for debounced auto-save with SHA-256 conflict detection."""
    raw_path = payload.get("file_path") or payload.get("path")
    content = payload.get("content")
    expected_hash = payload.get("expected_hash") or payload.get("hash")
    debounce_requested = payload.get("debounce", False)

    if not raw_path:
        return 400, {"success": False, "error": "Missing 'file_path' or 'path'"}
    if content is None:
        return 400, {"success": False, "error": "Missing 'content'"}

    target = resolve_prd_path(raw_path, repo_root)
    eng = engine or PRDSyncEngine(repo_root)

    if debounce_requested:
        eng.debounce_save(target, content, expected_hash=expected_hash)
        client_hash = compute_sha256(content)
        return 202, {
            "status": "pending",
            "message": "Draft auto-save queued (debounced).",
            "client_hash": client_hash,
            "revision_digest": client_hash,
            "success": True,
        }

    result = eng.save_draft(target, content, expected_hash=expected_hash)
    status_code = 200 if result.status == "saved" else (409 if result.status == "conflict" else 400)
    return status_code, result.to_dict()
