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

---

## Configuring Multi-Agent Platform Adapters

SpecOps supports generating platform-native configuration, rule sets, and slash commands for AI coding assistants:

```bash
spec-ops init --name "PaymentService" --agent antigravity,claude,cursor
```

Supported platform targets:
- `claude`: Generates `CLAUDE.md` with PMaC hard invariants, key verification commands, and DoR/DoD workflows.
- `cursor`: Generates `.cursorrules` with coding invariants and preflight handoff checklists.
- `antigravity`: Generates `GEMINI.md` operating manual and slash command definitions (`/curate`, `/health`, `/worker`) in `.agents/skills/`.
