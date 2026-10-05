"""Definition of Ready (DoR) rules, constants, and audit report structures."""

from __future__ import annotations

from dataclasses import dataclass, field

RULE_YAML_FRONTMATTER = "Complete YAML frontmatter"
RULE_PERSONA_PRD = "Linked Persona & PRD"
RULE_GOVERNING_ADRS = "Cited Governing ADRs"
RULE_GHERKIN_SCENARIOS = "Executable Gherkin Scenarios"
RULE_BOUNDED_CONTEXT = "Defined Target Bounded Context"
RULE_FILE_LIMIT_SCOPE = "Feasible File Limit Scope"
RULE_MUTATION_SCOPE = "Mutation Testing Scope Defined"

ALL_DOR_RULES: list[str] = [
    RULE_YAML_FRONTMATTER,
    RULE_PERSONA_PRD,
    RULE_GOVERNING_ADRS,
    RULE_GHERKIN_SCENARIOS,
    RULE_BOUNDED_CONTEXT,
    RULE_FILE_LIMIT_SCOPE,
    RULE_MUTATION_SCOPE,
]

KNOWN_PERSONAS = {
    "alex",
    "jordan",
    "morgan",
    "riley",
    "taylor",
    "developer",
    "architect",
    "user",
}


@dataclass
class DoRAuditReport:
    """Report detailing Definition of Ready (DoR) audit outcomes."""

    task_id: str
    is_ready: bool
    rules: dict[str, bool] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)

    def format_report(self) -> str:
        """Renders a human-readable table of DoR rule checks."""
        lines = [f"=== Definition of Ready (DoR) Audit: {self.task_id} ==="]
        lines.append(f"{'Rule Check':<34} | Status")
        lines.append(f"{'-' * 34}-|-------")
        for rule in ALL_DOR_RULES:
            status = "Pass" if self.rules.get(rule, False) else "Fail"
            lines.append(f"{rule:<34} | {status}")
        if self.errors:
            lines.append("\nViolations:")
            for err in self.errors:
                lines.append(f"  ❌ {err}")
        if self.recommendations:
            lines.append("\nRecommendations:")
            for rec in self.recommendations:
                lines.append(f"  💡 {rec}")
        return "\n".join(lines)
