---
id: '0097'
title: Disposable Worktree Sandboxing and Automated Spike Test Harness Scaffolding
status: Accepted
created: 2026-09-29
persona: Morgan (The Autonomous Coding Agent)
feature: FEAT-PRD-04
governing_prd: PRD-0003
---

# US-0097 — Disposable Worktree Sandboxing and Automated Spike Test Harness Scaffolding

## Governing PRD
- [`PRD-0003: Product Discovery, Web PRD Studio & Living UAT Verification`](../../product/accepted/prd-0003-product-discovery-web-prd-studio-and-living-uat-verification.md)

## User Story

**As an** autonomous coding agent,  
  - **I want** to execute `spec-ops spike start SPIKE-XXXX` to instantiate an ephemeral, sandboxed git worktree with a dedicated blackbox test harness under `spikes/`,  
  - **So that** I can rapidly test risky technical hypotheses against external libraries without polluting production source trees or violating the strict <500 line codebase invariant.

## Acceptance Criteria

```gherkin
Scenario: Scaffolding a sandboxed spike worktree and hypothesis test harness
Given a proposed spike task "SPIKE-0002" with hypothesis "DuckDB outperforms SQLite for 1M graph node queries under 200ms"
When Morgan executes "spec-ops spike start SPIKE-0002"
Then an isolated git worktree is created at ".worktrees/spike-0002" on branch "spike/SPIKE-0002"
And an isolated harness directory is generated at "spikes/spike_0002/" containing:
| spikes/spike_0002/harness.py      |
| spikes/spike_0002/test_spike.py   |
| spikes/spike_0002/README.md       |
And "spikes/spike_0002/test_spike.py" contains an executable benchmark skeleton asserting the hypothesis.
```
```gherkin
Scenario: Enforcing write isolation to prevent spike code from modifying "src/"
Given Morgan is executing spike code inside ".worktrees/spike-0002"
When Morgan attempts to edit or create files within "src/spec_ops/"
Then the in-worktree preflight hook rejects the modification
And displays "Spike Sandbox Violation: Code changes during an exploratory spike must be contained within 'spikes/spike_0002/'".
```
```gherkin
Scenario: Enforcing spike timebox expiration
Given "SPIKE-0002" specifies a frontmatter "timebox: 2h"
And the worker has spent 2 hours in the spike worktree without recording empirical findings
When the worker runs "spec-ops spike check"
Then SpecOps issues a timebox warning: "Spike SPIKE-0002 timebox expired (2h). Conclude experiment and run 'spec-ops spike graduate'".
-
```

## Rationale & Compelling Value
- *Adoption*: Removes fear of agent hallucinations and runaway dependencies during architectural prototyping. Developers and architects can safely assign high-risk spikes to autonomous agents.
  - *Regular Usage*: Used for every exploratory investigation, library evaluation, or performance feasibility spike.
  - *Compelling Value*: Enforces strict sandboxing between production code and exploratory prototypes, ensuring zero prototype "slop" pollutes `src/` while giving agents clear, localized test harnesses.

---
