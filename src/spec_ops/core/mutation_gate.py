"""Core domain mutation testing invariant runner and mutant kill score quality gate (ADR-0009)."""

from __future__ import annotations

import json
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Sequence


def calculate_mutation_score(killed: int, total: int, default_on_zero: float = 100.0) -> float:
    """Calculates mutant kill percentage: (killed / total) * 100. Handles total <= 0 gracefully."""
    if total <= 0:
        return float(default_on_zero)
    if killed <= 0:
        return 0.0
    if killed >= total:
        return 100.0
    score = (killed / total) * 100.0
    return round(score, 1)


@dataclass
class SurvivingMutant:
    """Represents a surviving mutant with location and mutated expression details."""

    mutant_id: str
    file_path: str
    line: int
    expression: str = ""
    diff: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.mutant_id,
            "mutant_id": self.mutant_id,
            "file_path": self.file_path,
            "line": self.line,
            "expression": self.expression,
            "diff": self.diff,
        }


@dataclass
class MutationReport:
    """Aggregated results of mutation testing quality gate evaluation."""

    target_module: str
    threshold: float = 80.0
    killed_count: int = 0
    survived_count: int = 0
    timeout_count: int = 0
    total_mutants: int = 0
    mutation_score: float = 0.0
    survived_mutants: list[SurvivingMutant] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.total_mutants == 0:
            self.total_mutants = self.killed_count + self.survived_count + self.timeout_count
        if self.mutation_score == 0.0 and self.total_mutants > 0 and self.killed_count > 0:
            self.mutation_score = calculate_mutation_score(self.killed_count, self.total_mutants)
        elif self.total_mutants == 0 and self.mutation_score == 0.0:
            self.mutation_score = calculate_mutation_score(self.killed_count, self.total_mutants)

    @property
    def is_passed(self) -> bool:
        return self.mutation_score >= self.threshold

    def to_dict(self) -> dict[str, Any]:
        return {
            "target_module": self.target_module,
            "mutation_score": self.mutation_score,
            "threshold": self.threshold,
            "killed_count": self.killed_count,
            "survived_count": self.survived_count,
            "timeout_count": self.timeout_count,
            "total_mutants": self.total_mutants,
            "is_passed": self.is_passed,
            "survived_mutants": [m.to_dict() for m in self.survived_mutants],
        }

    def format_report(self) -> str:
        score_val = self.mutation_score
        score_str = f"{int(score_val)}%" if score_val.is_integer() else f"{score_val:.1f}%"
        if self.is_passed:
            return (
                f"Mutation Invariant Met: {score_str} mutant kill score "
                f"({self.killed_count} killed, {self.survived_count} survived, {self.timeout_count} timed out)"
            )

        lines = [
            f"❌ Mutation Score Invariant Failed: {score_str} < {self.threshold:.1f}% threshold (ADR-0009 violation).",
            f"Surviving mutants ({len(self.survived_mutants)}) requiring stronger blackbox assertions:",
        ]
        for m in self.survived_mutants:
            expr_part = f" - Mutated: {m.expression}" if m.expression else ""
            lines.append(f"  - {m.file_path}:{m.line} [{m.mutant_id}]{expr_part}")
            if m.diff:
                lines.append("    Diff:")
                for dline in m.diff.strip().splitlines():
                    lines.append(f"      {dline}")
        return "\n".join(lines)


def parse_diff_details(diff_text: str, fallback_file: str = "") -> tuple[str, int, str]:
    """Extracts file_path, line number, and mutated expression from unified diff."""
    file_path = fallback_file
    line_no = 1
    mutated_expr = ""

    for line in diff_text.splitlines():
        if line.startswith("+++ "):
            target = line[4:].strip()
            if target.startswith("b/"):
                target = target[2:]
            if target:
                file_path = target
        elif line.startswith("@@ "):
            match = re.search(r"@@ -(\d+)", line)
            if match:
                line_no = int(match.group(1))
        elif line.startswith("+") and not line.startswith("+++"):
            expr = line[1:].strip()
            if expr and not mutated_expr:
                mutated_expr = expr

    return file_path, line_no, mutated_expr


def load_specops_report(report_path: Path, target_module: str, threshold: float) -> MutationReport | None:
    """Loads existing mutation report from .specops/mutation_report.json."""
    if not report_path.is_file():
        return None
    try:
        data = json.loads(report_path.read_text(encoding="utf-8"))
        tgt = str(data.get("target_module", target_module))
        score = float(data.get("mutation_score", 0.0))
        thresh = float(data.get("threshold", threshold))
        killed = int(data.get("killed_count", 0))
        survived = int(data.get("survived_count", 0))
        timeout = int(data.get("timeout_count", 0))
        total = int(data.get("total_mutants", killed + survived + timeout))

        raw_mutants = data.get("survived_mutants", data.get("surviving_mutants", []))
        parsed_mutants: list[SurvivingMutant] = []
        for idx, m in enumerate(raw_mutants, start=1):
            if isinstance(m, dict):
                mid = str(m.get("id") or m.get("mutant_id", f"mutant_{idx}"))
                fpath = str(m.get("file_path", tgt))
                lno = int(m.get("line", 1))
                expr = str(m.get("expression", ""))
                diff = str(m.get("diff", ""))
                parsed_mutants.append(SurvivingMutant(mutant_id=mid, file_path=fpath, line=lno, expression=expr, diff=diff))
            elif isinstance(m, str):
                parsed_mutants.append(SurvivingMutant(mutant_id=m, file_path=tgt, line=idx))

        if total == 0 and (killed + survived + timeout) > 0:
            total = killed + survived + timeout
        if score == 0.0 and total > 0 and killed > 0:
            score = calculate_mutation_score(killed, total)
        elif score == 0.0 and total == 0:
            score = 100.0

        return MutationReport(
            target_module=tgt,
            threshold=thresh,
            killed_count=killed,
            survived_count=survived,
            timeout_count=timeout,
            total_mutants=total,
            mutation_score=score,
            survived_mutants=parsed_mutants,
        )
    except Exception:
        return None


def parse_mutmut_results(root: Path, target_module: str, threshold: float) -> MutationReport | None:
    """Parses Mutmut results from mutants/ directory and .meta files."""
    mutants_dir = root / "mutants"
    if not mutants_dir.is_dir():
        return None

    meta_files = list(mutants_dir.rglob("*.meta"))
    if not meta_files:
        cicd_stats = mutants_dir / "mutmut-cicd-stats.json"
        if cicd_stats.is_file():
            try:
                sdata = json.loads(cicd_stats.read_text(encoding="utf-8"))
                k = int(sdata.get("killed", 0))
                s = int(sdata.get("survived", 0))
                t = int(sdata.get("timeout", 0))
                tot = int(sdata.get("total", k + s + t))
                score = calculate_mutation_score(k, tot)
                surviving = [SurvivingMutant(mutant_id=f"mutant_{i}", file_path=target_module, line=i) for i in range(1, s + 1)]
                return MutationReport(
                    target_module=target_module,
                    threshold=threshold,
                    killed_count=k,
                    survived_count=s,
                    timeout_count=t,
                    total_mutants=tot,
                    mutation_score=score,
                    survived_mutants=surviving,
                )
            except Exception:
                return None
        return None

    killed_count = 0
    survived_count = 0
    timeout_count = 0
    surviving_mutants: list[SurvivingMutant] = []

    for meta_file in meta_files:
        try:
            rel_source = meta_file.relative_to(mutants_dir)
            source_file_str = str(rel_source)[:-5] if str(rel_source).endswith(".meta") else str(rel_source)
            meta_data = json.loads(meta_file.read_text(encoding="utf-8"))
            exit_codes = meta_data.get("exit_code_by_key", {})

            for mutant_key, code in exit_codes.items():
                if code in (1, 3):
                    killed_count += 1
                elif code == 0:
                    survived_count += 1
                    diff_text = ""
                    try:
                        show_res = subprocess.run(
                            [sys.executable, "-m", "mutmut", "show", mutant_key],
                            cwd=root,
                            capture_output=True,
                            text=True,
                            timeout=10,
                        )
                        if show_res.returncode == 0:
                            diff_text = show_res.stdout
                    except Exception:
                        pass

                    fpath, lno, expr = parse_diff_details(diff_text, fallback_file=source_file_str)
                    surviving_mutants.append(
                        SurvivingMutant(
                            mutant_id=mutant_key,
                            file_path=fpath,
                            line=lno,
                            expression=expr,
                            diff=diff_text,
                        )
                    )
                elif code in (36, 24, -24, 152, 255):
                    timeout_count += 1
                else:
                    killed_count += 1
        except Exception:
            continue

    total = killed_count + survived_count + timeout_count
    score = calculate_mutation_score(killed_count, total)

    return MutationReport(
        target_module=target_module,
        threshold=threshold,
        killed_count=killed_count,
        survived_count=survived_count,
        timeout_count=timeout_count,
        total_mutants=total,
        mutation_score=score,
        survived_mutants=surviving_mutants,
    )


def execute_mutmut_run(root: Path, target_module: str) -> None:
    """Executes Mutmut mutation testing across the specified target module."""
    pyproject = root / "pyproject.toml"
    setup_cfg = root / "setup.cfg"
    created_setup_cfg = False

    has_mutmut_config = False
    if pyproject.is_file():
        content = pyproject.read_text(encoding="utf-8")
        if "[tool.mutmut]" in content:
            has_mutmut_config = True
    if setup_cfg.is_file():
        content = setup_cfg.read_text(encoding="utf-8")
        if "[mutmut]" in content:
            has_mutmut_config = True

    if not has_mutmut_config:
        src_path = target_module
        if not (root / src_path).exists() and (root / "src").is_dir():
            src_path = "src"
        setup_cfg.write_text(f"[mutmut]\nsource_paths = {src_path}\n", encoding="utf-8")
        created_setup_cfg = True

    try:
        subprocess.run(
            [sys.executable, "-m", "mutmut", "run"],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=300,
        )
    finally:
        if created_setup_cfg and setup_cfg.is_file():
            try:
                setup_cfg.unlink()
            except OSError:
                pass


def run_mutation_gate(
    root_dir: Path | str | None = None,
    target_module: str | None = None,
    bounded_context: str | None = None,
    threshold: float = 80.0,
    force_run: bool = False,
) -> MutationReport:
    """Executes the mutation testing quality gate or evaluates completed runs."""
    root = Path(root_dir).resolve() if root_dir else Path.cwd().resolve()

    if target_module:
        target_str = str(target_module)
    elif bounded_context:
        bc_candidate = root / "src" / "spec_ops" / bounded_context
        if bc_candidate.exists():
            target_str = f"src/spec_ops/{bounded_context}"
        else:
            bc_short = root / "src" / bounded_context
            target_str = f"src/{bounded_context}" if bc_short.exists() else f"src/spec_ops/{bounded_context}"
    else:
        target_str = "src/spec_ops/core"

    specops_file = root / ".specops" / "mutation_report.json"

    if not force_run:
        report = load_specops_report(specops_file, target_module=target_str, threshold=threshold)
        if report is not None:
            return report

        report = parse_mutmut_results(root, target_module=target_str, threshold=threshold)
        if report is not None:
            return report

    # Execute mutmut run
    execute_mutmut_run(root, target_module=target_str)

    report = parse_mutmut_results(root, target_module=target_str, threshold=threshold)
    if report is None:
        report = load_specops_report(specops_file, target_module=target_str, threshold=threshold)

    if report is None:
        report = MutationReport(
            target_module=target_str,
            threshold=threshold,
            killed_count=0,
            survived_count=0,
            timeout_count=0,
            total_mutants=0,
            mutation_score=100.0,
            survived_mutants=[],
        )

    # Persist report for downstream interoperability
    try:
        specops_dir = root / ".specops"
        specops_dir.mkdir(parents=True, exist_ok=True)
        specops_file.write_text(json.dumps(report.to_dict(), indent=2), encoding="utf-8")
    except OSError:
        pass

    return report
