# How-To: Conduct Architectural Spikes and Graduate ADRs

This guide explains how to use SpecOps spike workflows to conduct sandboxed architectural spikes, benchmark hypotheses, and graduate empirical findings into Architectural Decision Records (ADRs).

---

## 1. Start a Sandboxed Spike Worktree

To investigate an architectural uncertainty, start an isolated spike worktree:

```bash
uv run spec-ops spike start SPIKE-0038 --hypothesis "Zero-Dependency Local Web PRD Studio" --timebox 4h
```

This creates an isolated worktree at `.worktrees/spike-0038` and a dedicated spike branch (`spike/SPIKE-0038`).

Spike worktrees enforce strict write-isolation:
- Spikes cannot accidentally modify production source code or shared backlog files.
- Exploratory code lives under `spikes/spike_XXXX/`.

---

## 2. Check Spike Status and Enforce Timeboxes

To verify remaining timebox duration and ensure changes remain within the allowed spike directory:

```bash
uv run spec-ops spike check SPIKE-0038
```

To run preflight verification within the spike worktree:

```bash
uv run spec-ops spike preflight SPIKE-0038
```

---

## 3. Graduate Findings into an Accepted ADR

When the spike concludes and empirical benchmarks validate or invalidate the hypothesis, graduate the spike:

```bash
uv run spec-ops spike graduate SPIKE-0038 --result proven --title "Zero-Dependency Local Web PRD Studio Architecture" --findings "Sub-100ms latency verified across 50 operations with zero external npm dependencies."
```

Graduation automatically:
1. Synthesizes a new Architectural Decision Record under `docs/project/adrs/accepted/` (or `rejected/` if disproven).
2. Updates `docs/project/adrs/REGISTRY.md`.
3. Unblocks downstream production implementation tasks.
