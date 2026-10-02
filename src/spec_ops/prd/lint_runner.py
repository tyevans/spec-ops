"""PRD Lint CLI frontdoor runner, remediation executor, and report formatter."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..config.models import SpecOpsConfig
from .lint_engine import PRDLintEngine, PRDLintReport


def run_prd_lint(
    config: SpecOpsConfig,
    target_path: str | None = None,
    remediate: bool = False,
    json_output: bool = False,
) -> int:
    """Runs blackbox frontdoor PRD quality and falsifiability linting."""
    root = config.root_dir
    engine = PRDLintEngine(root_dir=root)
    prd_dir = root / "docs" / "project" / "product"

    target_files: list[Path] = []
    if target_path:
        cand = Path(target_path)
        if cand.is_file():
            target_files.append(cand.resolve())
        elif (root / target_path).is_file():
            target_files.append((root / target_path).resolve())
        elif prd_dir.exists():
            clean_id = target_path.strip().lower()
            for f in prd_dir.rglob("*.md"):
                if f.name == "REGISTRY.md":
                    continue
                if clean_id in f.stem.lower():
                    target_files.append(f.resolve())
                    break
        if not target_files:
            print(f"❌ Error: PRD specification not found matching '{target_path}'.")
            return 1
    else:
        if prd_dir.exists():
            for stage in ("idea", "shaped", "accepted", "shipped"):
                s_dir = prd_dir / stage
                if not s_dir.exists():
                    continue
                for f in sorted(s_dir.glob("*.md")):
                    if f.name == "REGISTRY.md":
                        continue
                    target_files.append(f.resolve())

    if not target_files:
        if json_output:
            print(json.dumps({"success": True, "total_files": 0, "reports": []}))
        else:
            print("ℹ️ No PRD markdown specifications found under docs/project/product/.")
        return 0

    reports: list[PRDLintReport] = []
    remediated_counts: dict[str, int] = {}

    for f in target_files:
        rep = engine.lint_file(f)
        if remediate and rep.diagnostics:
            applied = 0
            lines = f.read_text(encoding="utf-8").splitlines()
            for d in rep.diagnostics:
                if d.suggestion and 1 <= d.suggestion.line <= len(lines):
                    lines[d.suggestion.line - 1] = d.suggestion.suggested_text
                    applied += 1
            if applied > 0:
                f.write_text("\n".join(lines) + "\n", encoding="utf-8")
                rep = engine.lint_file(f)
            remediated_counts[str(f)] = applied
        reports.append(rep)

    total_files = len(reports)
    valid_files = sum(1 for r in reports if r.is_valid)
    total_errors = sum(r.error_count for r in reports)
    total_warnings = sum(r.warning_count for r in reports)
    falsifiable = sum(r.falsifiable_count for r in reports)
    unfalsifiable = sum(r.unfalsifiable_count for r in reports)

    if json_output:
        payload = {
            "success": total_errors == 0,
            "total_files": total_files,
            "valid_files": valid_files,
            "total_errors": total_errors,
            "total_warnings": total_warnings,
            "falsifiable_count": falsifiable,
            "unfalsifiable_count": unfalsifiable,
            "remediated_files": remediated_counts,
            "reports": [r.to_dict() for r in reports],
        }
        print(json.dumps(payload, indent=2))
        return 0 if total_errors == 0 else 1

    # Human-readable CLI formatting
    print("=== SpecOps PRD Quality & Falsifiability Audit ===\n")
    for r in reports:
        rel_path = r.file_path
        try:
            rel_path = Path(r.file_path).relative_to(root)
        except Exception:
            pass

        remed_msg = f" (Remediated {remediated_counts.get(str(r.file_path), 0)} line(s))" if remediate else ""
        if r.outcome_checks:
            for idx, oc in enumerate(r.outcome_checks, 1):
                if oc.is_falsifiable:
                    print(f"   [Outcome {idx}] passes as a valid falsifiable frontdoor contract")
                else:
                    print(f"   [Outcome {idx}] flags Outcome {idx}: Subjective adjective '{oc.subjective_term}' is unfalsifiable")

        if r.is_valid:
            print(f"✅ {rel_path}{remed_msg}")
            print(f"   {r.falsifiable_count} checkable outcome(s) verified as falsifiable and observable.")
        else:
            print(f"❌ {rel_path}{remed_msg}")
            for d in r.diagnostics:
                print(f"   Line {d.line} [{d.rule_id}] ({d.severity.upper()}): {d.message}")
                if d.guidance:
                    print(f"      💡 Guidance: {d.guidance}")
                if d.suggestion:
                    print(f"      - {d.suggestion.original_text}")
                    print(f"      + {d.suggestion.suggested_text}")
                    print(f"      💡 Hint: {d.suggestion.remediation_hint}")
        print()

    print(f"Summary: {valid_files}/{total_files} PRDs valid | {total_errors} errors | {total_warnings} warnings")
    print(f"Outcomes: {falsifiable} falsifiable | {unfalsifiable} subjective/unfalsifiable")

    return 0 if total_errors == 0 else 1
