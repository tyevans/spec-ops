# Tutorial 01: Getting Started with SpecOps

This tutorial guides you through creating a new project, initializing it with SpecOps, enforcing architectural invariants, and exploring the project graph.

---

## 1. Prerequisites

Ensure you have Python 3.11+ and `uv` installed:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

---

## 2. Bootstrapping a New Repository

In an empty directory, initialize a git repository and run `spec-ops init`:

```bash
git init my-app
cd my-app
spec-ops init --name MyApp --profile core,bdd,ddd
```

This generates:
- `docs/project/`: Complete PMaC directory tree.
- `docs/project/adrs/`: 7 baseline Architectural Decision Records.
- `AGENTS.md`: Agent constitution and operating instructions.
- `specops.toml`: Project configuration.

---

## 3. Verifying Invariants with Health Check

Run the health check to verify that all source files obey the <500 line limit:

```bash
spec-ops health
```

---

## 4. Visualizing the Project Graph

Launch the local interactive visualizer server:

```bash
spec-ops visualizer --serve
```

Open `http://localhost:8787` in your browser to inspect the living 2D graph!
