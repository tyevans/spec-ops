"""Customer UAT receipt schemas, deterministic serialization, and test outcome mapping."""

from __future__ import annotations

import datetime
import hashlib
import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from ..security.signing import validate_key_id


VALID_UAT_STATUSES = {"Pending", "Approved", "Rejected"}


def serialize_canonical_json(data: Any) -> str:
    """Serializes arbitrary data structure into deterministic, canonically sorted JSON."""
    return json.dumps(data, indent=2, sort_keys=True) + "\n"


def parse_iso_timestamp(ts: str) -> datetime.datetime:
    """Parses ISO 8601 timestamp string into timezone-aware datetime."""
    clean = ts.strip().replace("Z", "+00:00")
    return datetime.datetime.fromisoformat(clean)


@dataclass
class TestCorrelation:
    """Correlates a checkable outcome to executable BDD Gherkin scenarios."""

    __test__ = False

    scenario: str
    story_id: str
    passed: bool
    test_run_id: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "scenario": self.scenario,
            "story_id": self.story_id,
            "passed": self.passed,
            "test_run_id": self.test_run_id,
        }


@dataclass
class UATSignOffEntry:
    """A single human PM sign-off record for a PRD checkable outcome."""

    outcome_id: str
    prd_id: str
    status: str
    reviewer: str
    timestamp: str
    notes: str = ""
    test_correlation: TestCorrelation | None = None
    history: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        res: dict[str, Any] = {
            "outcome_id": self.outcome_id,
            "prd_id": self.prd_id,
            "status": self.status,
            "reviewer": self.reviewer,
            "timestamp": self.timestamp,
            "notes": self.notes,
        }
        if self.test_correlation:
            res["test_correlation"] = self.test_correlation.to_dict()
        if self.history:
            res["history"] = sorted(
                self.history,
                key=lambda x: (x.get("timestamp", ""), x.get("reviewer", "")),
            )
        return res


def validate_uat_signoff_schema(data: dict[str, Any]) -> tuple[bool, list[str]]:
    """Validates structure and value invariants for docs/project/product/uat-signoff.json."""
    violations: list[str] = []
    if not isinstance(data, dict):
        return False, ["Root sign-off payload must be a JSON dictionary."]

    signoffs = data.get("signoffs")
    if signoffs is None or not isinstance(signoffs, dict):
        violations.append("Missing required top-level 'signoffs' dictionary.")
        return False, violations

    for key, item in signoffs.items():
        if not isinstance(item, dict):
            violations.append(f"Sign-off entry '{key}' must be a dictionary.")
            continue

        outcome_id = item.get("outcome_id")
        if not outcome_id or not isinstance(outcome_id, str):
            violations.append(f"Entry '{key}' missing valid 'outcome_id'.")

        prd_id = item.get("prd_id")
        if not prd_id or not isinstance(prd_id, str) or not re.match(r"^PRD-\d{4}$", prd_id):
            violations.append(f"Entry '{key}' missing valid 'prd_id' (e.g. PRD-0003).")

        status = item.get("status")
        if status not in VALID_UAT_STATUSES:
            violations.append(
                f"Entry '{key}' has invalid status '{status}'; must be one of {VALID_UAT_STATUSES}."
            )

        reviewer = item.get("reviewer")
        if not reviewer or not isinstance(reviewer, str) or not validate_key_id(reviewer):
            violations.append(f"Entry '{key}' has invalid reviewer identity format: '{reviewer}'.")

        timestamp = item.get("timestamp")
        if not timestamp or not isinstance(timestamp, str):
            violations.append(f"Entry '{key}' missing valid ISO-8601 'timestamp'.")
        else:
            try:
                parse_iso_timestamp(timestamp)
            except Exception:
                violations.append(f"Entry '{key}' timestamp is not valid ISO-8601: '{timestamp}'.")

        tc = item.get("test_correlation")
        if tc is not None:
            if not isinstance(tc, dict):
                violations.append(f"Entry '{key}' test_correlation must be a dictionary.")
            else:
                if "scenario" not in tc or not isinstance(tc["scenario"], str):
                    violations.append(f"Entry '{key}' test_correlation missing 'scenario'.")
                if "story_id" not in tc or not isinstance(tc["story_id"], str):
                    violations.append(f"Entry '{key}' test_correlation missing 'story_id'.")
                if "passed" not in tc or not isinstance(tc["passed"], bool):
                    violations.append(f"Entry '{key}' test_correlation missing boolean 'passed'.")

    return len(violations) == 0, violations


def reconcile_signoffs(
    base: dict[str, Any],
    incoming: dict[str, Any],
) -> dict[str, Any]:
    """Reconciles concurrent PM sign-offs with Last-Write-Wins and history preservation."""
    valid_base, _ = validate_uat_signoff_schema(base)
    valid_inc, _ = validate_uat_signoff_schema(incoming)

    base_map: dict[str, Any] = base.get("signoffs", {}) if valid_base else {}
    inc_map: dict[str, Any] = incoming.get("signoffs", {}) if valid_inc else {}

    all_keys = sorted(set(base_map.keys()) | set(inc_map.keys()))
    merged_signoffs: dict[str, Any] = {}

    for k in all_keys:
        if k in base_map and k not in inc_map:
            merged_signoffs[k] = dict(base_map[k])
        elif k in inc_map and k not in base_map:
            merged_signoffs[k] = dict(inc_map[k])
        else:
            b_item = base_map[k]
            i_item = inc_map[k]
            b_ts = parse_iso_timestamp(b_item.get("timestamp", "1970-01-01T00:00:00Z"))
            i_ts = parse_iso_timestamp(i_item.get("timestamp", "1970-01-01T00:00:00Z"))

            # Winner is the later timestamp; ties broken deterministically by reviewer string
            if i_ts > b_ts or (i_ts == b_ts and str(i_item.get("reviewer")) >= str(b_item.get("reviewer"))):
                primary, secondary = dict(i_item), dict(b_item)
            else:
                primary, secondary = dict(b_item), dict(i_item)

            # Merge audit history
            histories: list[dict[str, Any]] = []
            seen: set[tuple[str, str, str]] = set()

            for item in [secondary, primary]:
                tup = (
                    str(item.get("timestamp", "")),
                    str(item.get("reviewer", "")),
                    str(item.get("status", "")),
                )
                if tup not in seen:
                    seen.add(tup)
                    histories.append({
                        "timestamp": tup[0],
                        "reviewer": tup[1],
                        "status": tup[2],
                        "notes": item.get("notes", ""),
                    })

                for h in item.get("history", []):
                    h_tup = (
                        str(h.get("timestamp", "")),
                        str(h.get("reviewer", "")),
                        str(h.get("status", "")),
                    )
                    if h_tup not in seen:
                        seen.add(h_tup)
                        histories.append(dict(h))

            histories.sort(key=lambda x: (x.get("timestamp", ""), x.get("reviewer", "")))
            primary["history"] = histories
            merged_signoffs[k] = primary

    return {
        "$schema": "spec-ops/uat-signoff-v1",
        "version": "1.0",
        "signoffs": merged_signoffs,
    }


@dataclass
class OutcomeTestMapping:
    """Lineage mapping between a PRD checkable outcome, user stories, and test results."""

    outcome_id: str
    outcome_text: str
    linked_stories: list[str] = field(default_factory=list)
    scenarios: list[str] = field(default_factory=list)
    test_status: str = "Pending (No Tests)"
    uat_status: str = "Pending PM"
    reviewer: str = ""
    timestamp: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def extract_prd_outcomes(prd_content: str) -> list[tuple[str, str]]:
    """Extracts numbered checkable outcomes from PRD markdown content."""
    outcomes: list[tuple[str, str]] = []
    in_outcomes = False
    for line in prd_content.splitlines():
        if line.startswith("## Checkable Outcomes"):
            in_outcomes = True
            continue
        if in_outcomes and line.startswith("## "):
            break
        if in_outcomes:
            m = re.match(r"^\s*(\d+)\.\s*(.+)$", line)
            if m:
                outcomes.append((m.group(1), m.group(2).strip()))
    return outcomes


def map_outcomes_to_tests(
    prd_content: str,
    prd_id: str,
    stories: list[dict[str, Any]],
    test_results: dict[str, str],
    existing_signoffs: dict[str, Any] | None = None,
) -> list[OutcomeTestMapping]:
    """Correlates PRD checkable outcomes with Gherkin scenarios and CI test results."""
    outcomes = extract_prd_outcomes(prd_content)
    signoff_map = existing_signoffs.get("signoffs", {}) if existing_signoffs else {}
    mappings: list[OutcomeTestMapping] = []

    for num, text in outcomes:
        outcome_key = f"{prd_id}:{num}"
        linked_stories: list[str] = []
        scenarios: list[str] = []

        for st in stories:
            if st.get("governing_prd") == prd_id:
                sid = st.get("id", "")
                if sid:
                    linked_stories.append(f"US-{sid.zfill(4)}")
                for sc in st.get("scenarios", []):
                    scenarios.append(sc)

        # Evaluate CI test status
        if not scenarios:
            test_status = "Pending (No Tests)"
        else:
            statuses = [test_results.get(sc, "pending").lower() for sc in scenarios]
            if all(s == "passed" for s in statuses):
                test_status = "Passed (CI)"
            elif any(s == "failed" for s in statuses):
                test_status = "Failed (CI)"
            else:
                test_status = "Pending (CI)"

        # Check PM UAT sign-off status
        rec = signoff_map.get(outcome_key)
        uat_status = rec.get("status", "Pending PM") if rec else "Pending PM"
        reviewer = rec.get("reviewer", "") if rec else ""
        ts = rec.get("timestamp", "") if rec else ""

        mappings.append(
            OutcomeTestMapping(
                outcome_id=num,
                outcome_text=text,
                linked_stories=sorted(set(linked_stories)),
                scenarios=scenarios,
                test_status=test_status,
                uat_status=uat_status,
                reviewer=reviewer,
                timestamp=ts,
            )
        )

    return mappings


def compute_delivery_readiness(mappings: list[OutcomeTestMapping]) -> float:
    """Calculates overall delivery readiness percentage (0.0 to 100.0)."""
    if not mappings:
        return 0.0
    approved_count = sum(
        1 for m in mappings if m.test_status == "Passed (CI)" and m.uat_status == "Approved"
    )
    return round((approved_count / len(mappings)) * 100.0, 2)
