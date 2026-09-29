# How-To: Bootstrap a Project with Profiles

This guide shows how to initialize a project with custom architectural profiles.

---

## Listing Available Profiles

To view all built-in profiles and their bundled baseline ADRs:

```bash
spec-ops profiles list
```

Available profiles:
- `core`: Base PMaC structure, file length limits (<500 lines), blackbox testing, preflight CI, and worktree isolation.
- `bdd`: Behavior-Driven Development with Gherkin user stories and Playwright E2E.
- `ddd`: Domain-Driven Design with explicit bounded contexts and domain state boundaries.

---

## Initializing with Selected Profiles

To scaffold a project with specific profiles:

```bash
spec-ops init --name "PaymentService" --profile core,bdd
```

This generates `specops.toml` and sequentially renumbers installed baseline ADRs without ID collisions.
