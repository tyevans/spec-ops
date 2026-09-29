# How to Monitor Project State via the Terminal UI (TUI) Dashboard

SpecOps provides an interactive terminal user interface (`spec-ops tui`) powered by [Rich](https://github.com/Textualize/rich) to monitor backlog buffers, inspect relational entity graphs, verify health invariants, and trigger JIT curation.

---

## Launching the TUI

To launch the full interactive dashboard:

```bash
uv run spec-ops tui
```

### Direct View Selection

You can launch directly into a specific view:

```bash
# Launch directly into entity tree view
uv run spec-ops tui --view tree

# Launch directly into health and invariant view
uv run spec-ops tui --view health

# Launch directly into priority backlog queue view
uv run spec-ops tui --view backlog
```

### Headless & Snapshot Mode

For CI pipelines, shell scripts, or fast terminal status inspection without an interactive event loop:

```bash
uv run spec-ops tui --once
```

---

## Interactive Keybindings

When running interactively, the following single-key shortcuts are active:

| Key | Action |
|---|---|
| `1` | Switch to **Overview** (Split Backlog & Health panels) |
| `2` | Switch to **Backlog Queue** (Buffer status and priority tasks) |
| `3` | Switch to **Entity Tree** (Hierarchical Personas, PRDs, Stories, Tasks) |
| `4` | Switch to **Health Status** (File length invariants and sync verification) |
| `c` | Trigger JIT **Curate** to replenish ready buffer |
| `h` / `r` | Refresh health check and graph state |
| `q` | Exit dashboard |
