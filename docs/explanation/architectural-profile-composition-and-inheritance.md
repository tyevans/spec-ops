# Explanation: Modular Architectural Profile Inheritance and Composition

This document clarifies the design rationale, topological resolution model, and packaging architecture underlying SpecOps modular architectural profiles.

---

## The Problem: Architectural Drift Across Distributed Repositories

In modern engineering organizations, dozens of repositories share common architectural standards—such as file size limits (<500 lines per ADR-0002), blackbox frontdoor testing conventions (ADR-0003), and zero-trust supply chain guardrails (ADR-0018).

However, individual services also have unique requirements:
- A payment processing service requires stringent audit logs, mutation test gates, and cryptographic commit verification.
- A high-throughput telemetry aggregator requires custom file size thresholds and specialized dependency policies.

Historically, organizations copied and pasted ADRs and CI templates between repositories. This quickly resulted in configuration drift, outdated security postures, and divergent agent operating rules (`AGENTS.md`).

---

## Architectural Profiles as Composable Building Blocks

SpecOps treats architectural standards as composable, version-controlled building blocks called **Architectural Profiles**:

```toml
[profile]
id = "fintech-service"
name = "Fintech Microservice Profile"
version = "1.0.0"
extends = ["core", "security", "ddd"]

[overrides.architecture]
file_length_limit = 350

[overrides.quality]
require_mutation_testing = true
```

Each profile bundles:
1. **Baseline Architectural Decision Records (ADRs)**: Pre-authored specifications establishing mandatory constraints.
2. **Quality & Invariant Overrides**: Numerical thresholds, test coverage gates, and mutation testing mandates.
3. **Agent Constitution Directives**: Curated instructions automatically integrated into `AGENTS.md`.

---

## Inheritance DAG Resolution and Conflict Handling

Profiles declare dependencies using the `extends` field, forming a Directed Acyclic Graph (DAG) of architectural standards:

```
        ┌──────────────┐
        │     core     │
        └──────┬───────┘
               │
        ┌──────▼───────┐
        │   security   │
        └──────┬───────┘
               │
   ┌───────────▼───────────┐
   │    enterprise-base    │
   └───────────┬───────────┘
               │
   ┌───────────▼───────────┐
   │    fintech-service    │
   └───────────────────────┘
```

### Topological Ordering
When resolving composite profiles, SpecOps uses a topological sort to evaluate parents from base to leaf. Earlier definitions provide baseline defaults, while derived profiles override specific constraints.

### Override Monotonicity
For security and quality constraints, derived profiles may only **tighten** invariants (e.g. lowering the file length limit from 500 lines to 350 lines). If a profile attempts to loosen critical supply-chain guardrails, the composer raises an architectural drift warning.

### Cycle Detection
If a circular inheritance graph is declared (e.g. `A extends B`, `B extends A`), the profile engine aborts immediately with a clear diagnostic trace identifying the cycle before any file mutations occur.

---

## Zero-Dependency Profile Packaging (.sop)

To distribute organizational profiles across repositories without requiring central package registries or proprietary plugins, SpecOps packages profile directories into portable archive bundles:

```bash
spec-ops profiles package profiles/fintech-service --out dist/fintech-service.sop
```

The `.sop` bundle is a standard gzip-compressed tar archive containing:
- `profile.toml`: Manifest and inheritance metadata.
- `adrs/`: Canonical baseline ADR markdown files.
- `rules/`: Agent constitution rule fragments for `AGENTS.md`.
- `manifest.json`: Cryptographic SHA-256 hashes of all bundled assets for tamper detection.

This enables immediate repository bootstrapping using local bundles or HTTPS URLs:

```bash
spec-ops init --name "BillingService" --profile dist/fintech-service.sop
```
