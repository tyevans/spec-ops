"""Standalone HTML Customer UAT Acceptance Matrix Exporter per ADR-0014."""

from __future__ import annotations

import datetime
import hashlib
import html
import re
from pathlib import Path
from typing import Any

from ..config.models import SpecOpsConfig
from ..core.parser import SpecOpsParser
from .manifest import compute_git_tree_digest
from .uat import get_uat_signoff_path, harvest_uat_readiness, load_uat_signoffs
from .uat_cli import compute_uat_receipt_signature

UAT_MATRIX_CSS = """
    :root { --bg: #0f172a; --card: #1e293b; --border: #334155; --text: #f8fafc; --muted: #94a3b8; --accent: #38bdf8; --success: #22c55e; --warning: #eab308; --danger: #ef4444; --code-bg: #090d16; }
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background: var(--bg); color: var(--text); padding: 32px; line-height: 1.5; }
    .container { max-width: 1200px; margin: 0 auto; }
    header { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 24px; padding-bottom: 20px; border-bottom: 1px solid var(--border); }
    h1 { font-size: 1.6rem; color: var(--accent); margin-bottom: 6px; }
    .subtitle { color: var(--muted); font-size: 0.95rem; }
    .badges { display: flex; gap: 10px; margin-top: 10px; align-items: center; }
    .badge { display: inline-flex; align-items: center; gap: 6px; padding: 4px 10px; border-radius: 9999px; font-size: 0.8rem; font-weight: 600; text-transform: uppercase; }
    .badge-success { background: rgba(34, 197, 94, 0.15); color: var(--success); border: 1px solid var(--success); }
    .badge-warning { background: rgba(234, 179, 8, 0.15); color: var(--warning); border: 1px solid var(--warning); }
    .badge-danger { background: rgba(239, 68, 68, 0.15); color: var(--danger); border: 1px solid var(--danger); }
    .badge-shield { background: rgba(56, 189, 248, 0.15); color: var(--accent); border: 1px solid var(--accent); }
    .card { background: var(--card); border: 1px solid var(--border); border-radius: 8px; padding: 20px; margin-bottom: 24px; }
    .card-title { font-size: 0.95rem; font-weight: 600; margin-bottom: 12px; display: flex; align-items: center; gap: 8px; color: var(--accent); text-transform: uppercase; letter-spacing: 0.05em; }
    .proof-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 12px; }
    .proof-item { background: var(--code-bg); padding: 10px 14px; border-radius: 6px; border: 1px solid var(--border); }
    .proof-label { font-size: 0.72rem; text-transform: uppercase; color: var(--muted); margin-bottom: 4px; font-weight: 600; }
    .proof-value { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 0.78rem; color: #cbd5e1; word-break: break-all; }
    .stats-strip { display: flex; gap: 16px; margin-bottom: 24px; }
    .stat-box { flex: 1; background: var(--card); border: 1px solid var(--border); border-radius: 8px; padding: 14px; text-align: center; }
    .stat-num { font-size: 1.5rem; font-weight: 700; color: var(--accent); }
    .stat-lbl { font-size: 0.8rem; color: var(--muted); }
    .controls { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; }
    .btn-group { display: flex; gap: 8px; }
    .filter-btn { background: var(--card); border: 1px solid var(--border); color: var(--text); padding: 6px 14px; border-radius: 6px; cursor: pointer; font-size: 0.85rem; }
    .filter-btn.active { background: var(--accent); color: #000; font-weight: 600; border-color: var(--accent); }
    .btn-print { background: var(--card); border: 1px solid var(--accent); color: var(--accent); padding: 6px 14px; border-radius: 6px; cursor: pointer; font-weight: 600; font-size: 0.85rem; }
    .btn-print:hover { background: var(--accent); color: #000; }
    table { width: 100%; border-collapse: collapse; background: var(--card); border-radius: 8px; overflow: hidden; border: 1px solid var(--border); }
    th, td { padding: 12px 16px; text-align: left; border-bottom: 1px solid var(--border); vertical-align: top; }
    th { background: #0c1322; font-size: 0.75rem; text-transform: uppercase; color: var(--muted); letter-spacing: 0.05em; }
    tr:last-child td { border-bottom: none; }
    tr:hover td { background: rgba(56, 189, 248, 0.03); }
    .outcome-title { font-size: 0.95rem; font-weight: 600; color: var(--text); margin-bottom: 4px; }
    .linked-meta { font-size: 0.8rem; color: var(--muted); margin-bottom: 6px; }
    .scenarios-box { font-size: 0.8rem; color: #cbd5e1; display: flex; flex-direction: column; gap: 2px; }
    .scen-item { display: flex; align-items: center; gap: 6px; }
    .rev-name { font-weight: 600; font-size: 0.85rem; }
    .rev-ts { font-size: 0.75rem; color: var(--muted); }
    .notes-cell { font-size: 0.85rem; color: var(--muted); max-width: 250px; word-break: break-word; }
    @media print {
      body { background: #fff; color: #000; padding: 0; }
      .controls, .btn-print { display: none; }
      .card, table, .stat-box { border-color: #cbd5e1; background: #fff; }
      .proof-item { background: #f8fafc; border-color: #cbd5e1; }
      .proof-value { color: #000; }
      h1 { color: #0f172a; }
      th { background: #f1f5f9; color: #334155; }
    }
"""

UAT_FILTER_JS = """
    function filterOutcomes(status, evt) {
      document.querySelectorAll('.filter-btn').forEach(function(b) { b.classList.remove('active'); });
      if (evt && evt.target) evt.target.classList.add('active');
      document.querySelectorAll('tbody tr').forEach(function(r) {
        if (status === 'all' || r.dataset.status === status) {
          r.style.display = '';
        } else {
          r.style.display = 'none';
        }
      });
    }
"""


def compute_ledger_digest(repo_root: Path | str) -> str:
    """Computes SHA-256 digest of docs/project/product/uat-signoff.json."""
    ledger_path = get_uat_signoff_path(repo_root)
    if ledger_path.is_file():
        return hashlib.sha256(ledger_path.read_bytes()).hexdigest()
    return hashlib.sha256(b"{}").hexdigest()


def render_uat_matrix_html(
    repo_root: Path | str,
    prd_id: str,
) -> tuple[str, dict[str, Any]]:
    """Renders standalone, self-contained HTML Customer UAT matrix with zero CDN dependencies."""
    root = Path(repo_root).resolve()
    num_m = re.search(r"\d+", prd_id)
    clean_prd = f"PRD-{num_m.group(0).zfill(4)}" if num_m else prd_id.strip().upper()

    parser = SpecOpsParser(root / "docs" / "project")
    p_data = parser.parse_all()
    target_prd = next((p for p in p_data.prds if p.id.upper() == clean_prd or clean_prd in p.id.upper()), None)
    prd_title = target_prd.title if target_prd else clean_prd

    harvest = harvest_uat_readiness(root, target_prd_id=clean_prd)
    matrix = harvest.get("matrix", [])
    total_outcomes = len(matrix)
    approved_outcomes = sum(1 for m in matrix if m.get("uat_status") == "Approved")
    passed_tests = sum(1 for m in matrix if m.get("test_status") == "Passed (CI)")

    readiness = round((approved_outcomes / total_outcomes * 100.0), 1) if total_outcomes > 0 else 0.0
    test_status = "Passed (CI)" if (passed_tests == total_outcomes and total_outcomes > 0) else "Pending (CI)"
    test_summary = {"status": test_status, "total_outcomes": total_outcomes, "passed_outcomes": passed_tests}
    uat_status = "Approved" if (approved_outcomes == total_outcomes and total_outcomes > 0) else "Pending PM"
    uat_summary = {"status": uat_status, "total_outcomes": total_outcomes, "approved_outcomes": approved_outcomes}

    tree_digest, _, errs = compute_git_tree_digest(root, allow_uncommitted=True)
    if errs:
        tree_digest = "0" * 64

    ledger_digest = compute_ledger_digest(root)
    signature = compute_uat_receipt_signature(clean_prd, tree_digest, matrix, uat_summary)
    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()

    # Build rows
    rows_html = []
    for item in matrix:
        o_id = html.escape(str(item.get("outcome_id", "")), quote=True)
        o_text = html.escape(item.get("outcome_text", ""), quote=True)
        stories = ", ".join(item.get("linked_stories", [])) or "-"
        stories_esc = html.escape(stories, quote=True)
        t_status = item.get("test_status", "Pending (CI)")
        u_status = item.get("uat_status", "Pending PM")
        reviewer = html.escape(item.get("reviewer", "") or "-", quote=True)
        ts = html.escape(item.get("timestamp", "") or "-", quote=True)
        notes = html.escape(item.get("notes", "") or "-", quote=True)

        t_badge = "badge-success" if t_status == "Passed (CI)" else "badge-warning"
        u_badge = "badge-success" if u_status == "Approved" else ("badge-danger" if u_status == "Rejected" else "badge-warning")

        scenarios_html = "".join(
            f'<div class="scen-item"><svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="20 6 9 17 4 12"/></svg> {html.escape(sc, quote=True)}</div>'
            for sc in item.get("scenarios", [])
        )

        row_status_key = "approved" if u_status == "Approved" else ("rejected" if u_status == "Rejected" else "pending")
        rows_html.append(f"""
        <tr data-status="{row_status_key}">
          <td><strong>#{o_id}</strong></td>
          <td>
            <div class="outcome-title">{o_text}</div>
            <div class="linked-meta">Stories: {stories_esc}</div>
            <div class="scenarios-box">{scenarios_html}</div>
          </td>
          <td><span class="badge {t_badge}">{html.escape(t_status, quote=True)}</span></td>
          <td><span class="badge {u_badge}">{html.escape(u_status, quote=True)}</span></td>
          <td><div class="rev-name">{reviewer}</div><div class="rev-ts">{ts}</div></td>
          <td class="notes-cell">{notes}</td>
        </tr>""")

    rendered_rows = "\n".join(rows_html)
    esc_prd_title = html.escape(prd_title, quote=True)
    esc_clean_prd = html.escape(clean_prd, quote=True)
    readiness_badge = "badge-success" if readiness == 100.0 else "badge-warning"

    doc_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <meta name="spec-ops:document" content="customer-uat-acceptance-matrix">
  <meta name="spec-ops:prd-id" content="{esc_clean_prd}">
  <meta name="spec-ops:prd-title" content="{esc_prd_title}">
  <meta name="spec-ops:receipt-signature" content="{signature}">
  <meta name="spec-ops:tree-digest" content="{tree_digest}">
  <meta name="spec-ops:ledger-digest" content="{ledger_digest}">
  <meta name="spec-ops:readiness" content="{readiness}">
  <meta name="spec-ops:generated-at" content="{now_iso}">
  <title>Customer UAT Acceptance Matrix - {esc_clean_prd}</title>
  <style>
{UAT_MATRIX_CSS}
  </style>
</head>
<body>
  <div class="container">
    <header>
      <div>
        <h1>⚡ Customer UAT Acceptance Matrix</h1>
        <div class="subtitle">{esc_clean_prd}: {esc_prd_title}</div>
        <div class="badges">
          <span class="badge {readiness_badge}">{readiness:.1f}% Readiness</span>
          <span class="badge badge-shield"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg> Cryptographic Proof Sealed</span>
        </div>
      </div>
      <div>
        <button class="btn-print" onclick="window.print()">Print / Export PDF</button>
      </div>
    </header>

    <div class="stats-strip">
      <div class="stat-box"><div class="stat-num">{total_outcomes}</div><div class="stat-lbl">Checkable Outcomes</div></div>
      <div class="stat-box"><div class="stat-num">{passed_tests}</div><div class="stat-lbl">Automated BDD Passes</div></div>
      <div class="stat-box"><div class="stat-num">{approved_outcomes}</div><div class="stat-lbl">PM Approved Sign-offs</div></div>
      <div class="stat-box"><div class="stat-num">{readiness:.1f}%</div><div class="stat-lbl">Customer Readiness</div></div>
    </div>

    <div class="card">
      <div class="card-title">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>
        Tamper-Evident Cryptographic Ledger Proof (ADR-0014)
      </div>
      <div class="proof-grid">
        <div class="proof-item">
          <div class="proof-label">Receipt Signature (SHA-256)</div>
          <div class="proof-value" id="crypto-receipt-signature">{signature}</div>
        </div>
        <div class="proof-item">
          <div class="proof-label">Git Tree Digest (SHA-256)</div>
          <div class="proof-value" id="crypto-tree-digest">{tree_digest}</div>
        </div>
        <div class="proof-item">
          <div class="proof-label">Signed Ledger Digest (SHA-256)</div>
          <div class="proof-value" id="crypto-ledger-digest">{ledger_digest}</div>
        </div>
        <div class="proof-item">
          <div class="proof-label">Verification Timestamp</div>
          <div class="proof-value">{now_iso}</div>
        </div>
      </div>
    </div>

    <div class="controls">
      <div class="btn-group">
        <button class="filter-btn active" onclick="filterOutcomes('all', event)">All Outcomes ({total_outcomes})</button>
        <button class="filter-btn" onclick="filterOutcomes('approved', event)">Approved ({approved_outcomes})</button>
        <button class="filter-btn" onclick="filterOutcomes('pending', event)">Pending ({total_outcomes - approved_outcomes})</button>
      </div>
    </div>

    <table>
      <thead>
        <tr>
          <th style="width: 50px;">ID</th>
          <th>Checkable Outcome & BDD Verification</th>
          <th style="width: 130px;">Test Status</th>
          <th style="width: 140px;">UAT Status</th>
          <th style="width: 180px;">Reviewer</th>
          <th style="width: 220px;">Notes</th>
        </tr>
      </thead>
      <tbody>
{rendered_rows}
      </tbody>
    </table>
  </div>

  <script>
{UAT_FILTER_JS}
  </script>
</body>
</html>"""

    metadata = {
        "prd": {"id": clean_prd, "title": prd_title},
        "signature": signature,
        "tree_digest": tree_digest,
        "ledger_digest": ledger_digest,
        "readiness": readiness,
        "generated_at": now_iso,
        "matrix": matrix,
    }
    return doc_html, metadata


def export_uat_matrix_html(
    repo_root: Path | str,
    prd_id: str,
    output_path: Path | str | None = None,
    fmt: str = "html",
) -> tuple[Path, str, dict[str, Any]]:
    """Exports Customer UAT Acceptance Matrix as a standalone HTML document."""
    if fmt.lower() != "html":
        raise ValueError(f"Unsupported format '{fmt}'. Only 'html' is currently supported.")

    root = Path(repo_root).resolve()
    doc_html, meta = render_uat_matrix_html(root, prd_id)

    if output_path:
        out_file = Path(output_path).resolve()
    else:
        out_file = root / "dist" / "uat" / f"{meta['prd']['id']}-uat-matrix.html"

    out_file.parent.mkdir(parents=True, exist_ok=True)
    out_file.write_text(doc_html, encoding="utf-8")
    return out_file, doc_html, meta


def verify_exported_matrix_proof(
    html_content_or_path: str | Path,
    repo_root: Path | str,
) -> tuple[bool, list[str]]:
    """Validates that embedded cryptographic verification proof matches the signed ledger."""
    violations: list[str] = []
    root = Path(repo_root).resolve()

    if isinstance(html_content_or_path, Path):
        content = html_content_or_path.read_text(encoding="utf-8")
    elif isinstance(html_content_or_path, str):
        if "\n" not in html_content_or_path and len(html_content_or_path) < 4096 and Path(html_content_or_path).is_file():
            content = Path(html_content_or_path).read_text(encoding="utf-8")
        else:
            content = html_content_or_path
    else:
        return False, ["Input must be HTML string content or an existing file path."]

    def get_meta(name: str) -> str | None:
        m = re.search(rf'<meta\s+name="spec-ops:{re.escape(name)}"\s+content="([^"]*)"', content)
        return m.group(1) if m else None

    prd_id = get_meta("prd-id")
    embedded_sig = get_meta("receipt-signature")
    embedded_tree = get_meta("tree-digest")
    embedded_ledger = get_meta("ledger-digest")

    if not prd_id:
        violations.append("Missing required meta tag 'spec-ops:prd-id'.")
    if not embedded_sig:
        violations.append("Missing required meta tag 'spec-ops:receipt-signature'.")
    if not embedded_tree:
        violations.append("Missing required meta tag 'spec-ops:tree-digest'.")
    if not embedded_ledger:
        violations.append("Missing required meta tag 'spec-ops:ledger-digest'.")

    if violations:
        return False, violations

    # 1. Validate signed ledger digest
    current_ledger_digest = compute_ledger_digest(root)
    if embedded_ledger != current_ledger_digest:
        violations.append(
            f"Tampering detected: embedded ledger digest ({embedded_ledger[:12]}...) "
            f"does not match signed ledger ({current_ledger_digest[:12]}...)."
        )

    # 2. Recompute expected receipt signature
    harvest = harvest_uat_readiness(root, target_prd_id=prd_id)
    matrix = harvest.get("matrix", [])
    total_outcomes = len(matrix)
    approved_outcomes = sum(1 for m in matrix if m.get("uat_status") == "Approved")
    passed_tests = sum(1 for m in matrix if m.get("test_status") == "Passed (CI)")
    test_status = "Passed (CI)" if (passed_tests == total_outcomes and total_outcomes > 0) else "Pending (CI)"
    test_summary = {"status": test_status, "total_outcomes": total_outcomes, "passed_outcomes": passed_tests}
    uat_status = "Approved" if (approved_outcomes == total_outcomes and total_outcomes > 0) else "Pending PM"
    uat_summary = {"status": uat_status, "total_outcomes": total_outcomes, "approved_outcomes": approved_outcomes}

    expected_sig = compute_uat_receipt_signature(prd_id, embedded_tree, matrix, uat_summary)
    if embedded_sig != expected_sig:
        violations.append(
            f"Tampering detected: embedded cryptographic verification proof ({embedded_sig[:12]}...) "
            f"does not match signed ledger and test correlation ({expected_sig[:12]}...)."
        )

    return len(violations) == 0, violations


def handle_uat_export(
    config: SpecOpsConfig,
    prd: str,
    fmt: str = "html",
    output: str | None = None,
) -> int:
    """CLI handler for 'spec-ops prd uat export --prd PRD [--format html] [--output OUTPUT]'."""
    try:
        out_file, _, meta = export_uat_matrix_html(
            repo_root=config.root_dir,
            prd_id=prd,
            output_path=output,
            fmt=fmt,
        )
        print(f"✅ Exported Customer UAT Acceptance Matrix for {meta['prd']['id']}")
        print(f"   Output File: {out_file}")
        print(f"   Delivery Readiness: {meta['readiness']:.1f}%")
        print(f"   Cryptographic Signature: {meta['signature'][:16]}...")
        return 0
    except Exception as exc:
        print(f"❌ Failed to export Customer UAT matrix: {exc}")
        return 1
