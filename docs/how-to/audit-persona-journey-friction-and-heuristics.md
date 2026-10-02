# How-To: Audit Persona Journey Friction and Heuristic Usability

This guide explains how to audit cognitive ceremony and CLI ergonomics across user persona touchpoints using `spec-ops prd friction` governed by [ADR-0001](../project/adrs/accepted/adr-0001-specification-as-code-pmac.md) and [ADR-0007](../project/adrs/accepted/adr-0007-domain-driven-design-bounded-contexts.md).

---

## Overview

SpecOps establishes archetypal user personas in `docs/project/user_stories/PERSONAS.md` (Alex, Jordan, Morgan, Riley, Taylor, Sasha). While unit tests and BDD scenarios verify that functionality works, the **Persona Journey Friction Auditor** evaluates the operational ergonomics of CLI workflows.

The auditor calculates a deterministic cognitive friction score between `0.0` (zero ceremony) and `10.0` (maximum friction) based on:
- Command nesting depth and subaction hierarchies
- Positional argument requirements
- Option overload and configuration flag counts
- Persona-specific ergonomics (e.g. headless `--json` availability for autonomous agents like Morgan, and visual/wizard alternatives for product managers like Taylor)

---

## Running a Full Persona Journey Friction Audit

To run a friction audit across all persona touchpoints:

```bash
uv run spec-ops prd friction
```

Example output:
```text
=== SpecOps Persona Journey Friction Audit ===
Audited Personas: Alex, Jordan, Morgan, Riley, Taylor, Sasha
Evaluated Touchpoints: 147 workflows
Average Friction Index: 5.19 / 10.0

Top Friction Touchpoints:
  • [Score 7.90] spec-ops adr supersede (Alex)
     - Introduce top-level alias (e.g. 'spec-ops supersede') to reduce nesting depth.
     - Consolidate positional arguments using smart inference or interactive selection.
  • [Score 7.90] spec-ops report milestone (Jordan)
     - Support context-aware default target when positional argument is omitted.

Status: Audit completed cleanly.
```

---

## Filtering by Target Persona Archetype

To evaluate workflows relevant to a single persona archetype:

```bash
uv run spec-ops prd friction --persona alex
uv run spec-ops prd friction --persona taylor
uv run spec-ops prd friction --persona morgan
```

---

## Enforcing Maximum Friction Thresholds in CI

You can configure friction quality gates using `--threshold <N>`. If any evaluated touchpoint exceeds the threshold, the command flags the violations with remediation hints and exits with code `1`:

```bash
uv run spec-ops prd friction --threshold 7.5
```

If any command violates the threshold:
```text
High-Friction Touchpoints (Threshold >= 7.5):
  ⚠️  [Score 7.90] spec-ops adr supersede (Persona: Alex — The Agentic Systems Architect)
     Factors: Depth 3, 2 positional(s), 2 option(s)
     Recommendations:
       - Introduce top-level alias (e.g. 'spec-ops supersede') to reduce nesting depth.
       - Consolidate positional arguments (old_id, new_id_pos) using smart inference or interactive selection.

Status: 2 workflow(s) flagged exceeding threshold (7.5).
```

---

## Exporting Structured Friction Diagnostics

For CI pipelines or automated analysis tools, pass `--json`:

```bash
uv run spec-ops prd friction --persona morgan --json
```

---

## Verifying Documentation and Drift

To ensure documentation matches CLI options and all snippets remain valid:

```bash
uv run spec-ops docs audit
uv run spec-ops docs build
```
