---
id: '0145'
title: Interactive Persona Customer Journey Map and Pain Point Matrix Visualizer
status: Complete
dependencies:
- TASK-0043
- TASK-0131
governing_adrs:
- ADR-0001
- ADR-0002
- ADR-0003
- ADR-0013
governing_prds:
- PRD-0003
governing_stories:
- US-0043
- US-0045
target_bc: prd
---

# TASK-0145: Interactive Persona Customer Journey Map and Pain Point Matrix Visualizer

## Summary
Implement the interactive Persona Customer Journey Map and Pain Point Matrix visualizer (`spec-ops prd journey [--persona <name>] [--json]`). Governed by PRD-0003 and ADR-0013, this engine correlates user personas defined in `docs/project/user_stories/PERSONAS.md` against accepted PRDs and executable user stories, rendering an interactive visual matrix showing journey coverage, resolved pain points, and unaddressed gaps.

## Problem Statement & Context
Personas in `PERSONAS.md` represent core stakeholders (e.g. Taylor, Alex, Jordan, Riley, Sasha). Currently, verifying whether a persona's pain points are addressed requires manual cross-referencing across PRD outcomes and Gherkin user stories. Product managers need an interactive visual journey map that traces persona pain points directly to shipped capabilities and highlights unresolved gaps.

## Key Requirements & Scope
1. **Journey Mapping Engine (`src/spec_ops/prd/journey_map.py`)**:
   - Parses `docs/project/user_stories/PERSONAS.md` and correlates each persona's goals and pain points against linked user stories and PRDs.
   - Computes coverage percentages: percentage of pain points addressed by accepted or shipped stories.
2. **Visual Matrix & Studio Integration**:
   - Terminal visual matrix using rich tables and colored progress indicators.
   - Web PRD Studio integration exporting an interactive standalone HTML journey diagram.
   - Machine-readable `--json` output format.
3. **Blackbox Frontdoor Verification**:
   - 100% test pass rate with zero mock backdoors.

## Architectural Invariants & Seams
- **File Length Limit (<500 lines)**: Journey mapping module in `src/spec_ops/prd/journey_map.py` must stay strictly under 400 lines (ADR-0002).
- **Persona Traceability Invariant**: Every mapped pain point must trace to a canonical persona ID without synthetic orphans.
- **Mutation Testing Scope**: Target modules for mutmut mutation testing include `src/spec_ops/prd/journey_map.py` with target >=80% mutant kill score (ADR-0009).

## Acceptance Criteria

### Scenario 1: Auditing persona pain point resolution coverage
```gherkin
Given a project repository with persona "Taylor" having 3 defined pain points
When the product lead runs "spec-ops prd journey --persona Taylor"
Then a journey coverage report is generated
And identifies which pain points have linked accepted stories and which remain unaddressed
```

### Scenario 2: Exporting standalone HTML customer journey map
```gherkin
Given an accepted PRD with mapped persona user stories
When the user executes "spec-ops prd journey --format html"
Then a standalone HTML journey map is produced
And includes verifiable coverage metrics
```

## Hypothesis Invariant Properties

- `@given(...)`: Generative property tests asserting that for any arbitrary set of personas with randomized pain points and story linkages, journey coverage percentages are bounded strictly between 0.0% and 100.0% without numerical errors.
