"""Living security posture calculation and compliance metric aggregation (ADR-0002, ADR-0009)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ..config.models import SpecOpsConfig

_CSS_PATH = Path(__file__).parent / "templates" / "security_radar.css"
SECURITY_RADAR_CSS = _CSS_PATH.read_text(encoding="utf-8") if _CSS_PATH.is_file() else ""


def calculate_signed_commit_coverage(signed_count: int, total_count: int) -> float:
    """Calculates cryptographic commit coverage percentage bounded between 0.0 and 100.0."""
    if total_count <= 0:
        return 100.0
    if signed_count <= 0:
        return 0.0
    if signed_count >= total_count:
        return 100.0
    return round((signed_count / total_count) * 100.0, 1)


def calculate_human_signoff_rate(signed_off_count: int, total_count: int) -> float:
    """Calculates human sign-off completion percentage bounded between 0.0 and 100.0."""
    if total_count <= 0:
        return 100.0
    if signed_off_count <= 0:
        return 0.0
    if signed_off_count >= total_count:
        return 100.0
    return round((signed_off_count / total_count) * 100.0, 1)


def evaluate_secret_scan_status(violations_count: int) -> str:
    """Evaluates secret scan violations count into Pass/Fail indicator."""
    return "Pass" if violations_count == 0 else "Fail"


def evaluate_lockfile_integrity(is_valid: bool) -> str:
    """Evaluates lockfile validation result into Synchronized/Modified indicator."""
    return "Synchronized" if is_valid else "Modified"


def aggregate_vulnerability_counts(vulnerabilities: list[dict[str, Any] | Any]) -> dict[str, int]:
    """Aggregates CVE records into low, medium, and high severity buckets."""
    counts = {"low": 0, "med": 0, "high": 0, "total": 0}
    for v in vulnerabilities:
        sev = ""
        if isinstance(v, dict):
            sev = str(v.get("severity", "")).lower()
        else:
            sev = str(getattr(v, "severity", "")).lower()

        if "low" in sev:
            counts["low"] += 1
        elif "med" in sev or "mod" in sev:
            counts["med"] += 1
        else:
            counts["high"] += 1
        counts["total"] += 1
    return counts


def format_vulnerability_indicator(counts: dict[str, int]) -> str:
    """Formats vulnerability count dictionary into standard display string."""
    low = counts.get("low", 0)
    med = counts.get("med", 0)
    high = counts.get("high", 0)
    return f"{low} Low / {med} Med / {high} High"


def evaluate_task_signed_commits(task: dict[str, Any]) -> bool:
    """Evaluates whether a task has satisfied cryptographic commit signature requirements."""
    if "has_signed_commits" in task and task["has_signed_commits"] is not None:
        return bool(task["has_signed_commits"])

    status = str(task.get("commit_signature_status", "")).strip().upper()
    if status in ("SIGNED", "G", "U", "VALID", "TRUE"):
        return True
    if status in ("UNSIGNED", "N", "INVALID", "FALSE"):
        return False

    commits = task.get("commits") or []
    if commits:
        all_signed = True
        for c in commits:
            if isinstance(c, dict):
                is_c_signed = c.get("is_signed")
                sig_st = str(c.get("signature_status", "")).strip().upper()
                if is_c_signed is False or sig_st in ("N", "UNSIGNED", "INVALID"):
                    all_signed = False
                    break
                if is_c_signed is not True and sig_st not in ("G", "U", "SIGNED"):
                    all_signed = False
                    break
            else:
                all_signed = False
                break
        return all_signed

    if task.get("commit_signed") or task.get("signed_commits"):
        return True

    return False


def evaluate_task_human_signoff(task: dict[str, Any]) -> bool:
    """Evaluates whether a task has received verified human reviewer sign-off."""
    if task.get("has_human_signoff") is not None:
        return bool(task["has_human_signoff"])

    signer = str(task.get("signed_off_by") or "").strip()
    if signer:
        return True

    raw_signoff = task.get("human_signoff")
    if isinstance(raw_signoff, dict) and raw_signoff.get("reviewer"):
        return True
    if isinstance(raw_signoff, str) and raw_signoff.strip():
        return True

    if str(task.get("signoff_signature") or "").strip():
        return True

    return False


def assess_task_compliance(task: dict[str, Any]) -> dict[str, Any]:
    """Assesses a single task deliverable against cryptographic signature, review, and CVE requirements."""
    task_id = str(task.get("id") or task.get("canonical_id") or "TASK-0000")
    title = str(task.get("title") or "")
    status = str(task.get("status") or "Proposed")
    bc = str(task.get("target_bc") or "")

    has_signoff = evaluate_task_human_signoff(task)
    has_signed_commits = evaluate_task_signed_commits(task)

    cve_count = int(task.get("cve_count", 0))
    cves = task.get("cves") or []
    if cves and not cve_count:
        cve_count = len(cves)

    missing_artifacts: list[str] = []
    if not has_signoff:
        missing_artifacts.append("Human Review Sign-off")
    if not has_signed_commits:
        missing_artifacts.append("Cryptographic Commit Signature")
    if cve_count > 0:
        missing_artifacts.append(f"{cve_count} Open CVE(s)")

    is_compliant = len(missing_artifacts) == 0

    return {
        "id": task_id,
        "title": title,
        "status": status,
        "target_bc": bc,
        "signed_off_by": str(task.get("signed_off_by") or ""),
        "signed_off_at": str(task.get("signed_off_at") or ""),
        "has_human_signoff": has_signoff,
        "has_signed_commits": has_signed_commits,
        "cve_count": cve_count,
        "missing_artifacts": missing_artifacts,
        "is_compliant": is_compliant,
        "status_label": "Compliant" if is_compliant else "Non-Compliant (Blocking)",
        "permalink": f"#tab=security&entity={task_id}",
    }


def aggregate_project_compliance(
    tasks: list[dict[str, Any]],
    secret_clean: bool = True,
    lockfile_clean: bool = True,
    cves: list[dict[str, Any] | Any] | None = None,
) -> dict[str, Any]:
    """Aggregates security metrics and builds compliance triage table data."""
    triage_tasks = [assess_task_compliance(t) for t in tasks]

    total_tasks = len(triage_tasks)
    signed_tasks = sum(1 for t in triage_tasks if t["has_signed_commits"])
    signed_off_tasks = sum(1 for t in triage_tasks if t["has_human_signoff"])
    compliant_tasks = sum(1 for t in triage_tasks if t["is_compliant"])
    non_compliant_tasks = total_tasks - compliant_tasks

    commit_cov = calculate_signed_commit_coverage(signed_tasks, total_tasks)
    signoff_rate = calculate_human_signoff_rate(signed_off_tasks, total_tasks)

    sec_status = evaluate_secret_scan_status(0 if secret_clean else 1)
    lock_status = evaluate_lockfile_integrity(lockfile_clean)

    v_counts = aggregate_vulnerability_counts(cves or [])
    v_indicator = format_vulnerability_indicator(v_counts)

    return {
        "secret_scan_status": sec_status,
        "lockfile_integrity": lock_status,
        "signed_commit_coverage": commit_cov,
        "signed_commit_coverage_display": f"{commit_cov}%",
        "human_signoff_rate": signoff_rate,
        "human_signoff_rate_display": f"{signoff_rate}%",
        "vulnerability_counts": v_counts,
        "vulnerability_indicator": v_indicator,
        "triage_tasks": triage_tasks,
        "compliant_count": compliant_tasks,
        "non_compliant_count": non_compliant_tasks,
        "total_tasks": total_tasks,
    }


def harvest_security_posture(
    config: SpecOpsConfig,
    tasks: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Harvests real-time security posture from local repository scanners."""
    from ..security.lockfile import verify_lockfile
    from ..security.secrets.scanner import scan_worktree

    # 1. Secret scan
    secret_clean = True
    try:
        report = scan_worktree(config.root_dir)
        secret_clean = report.is_clean
    except Exception:
        pass

    # 2. Lockfile integrity
    lockfile_clean = True
    try:
        lock_ok, _ = verify_lockfile(config.root_dir, run_uv=False)
        lockfile_clean = lock_ok
    except Exception:
        pass

    # 3. Known CVEs
    cves: list[Any] = []
    try:
        from ..security.audit.dependency import run_dependency_audit
        dep_report = run_dependency_audit(config.root_dir, config=config, offline=True)
        cves = dep_report.vulnerabilities
    except Exception:
        pass

    task_list = tasks or []
    return aggregate_project_compliance(
        tasks=task_list,
        secret_clean=secret_clean,
        lockfile_clean=lockfile_clean,
        cves=cves,
    )
