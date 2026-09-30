# How to Export Milestone Burndown Decks and Monitor Terminal Backlog Flow

SpecOps provides multi-format executive presentation reporting and an interactive terminal flow monitor to visualize JIT buffer waterlines, detect scope creep, and claim or promote tasks with single keystrokes.

---

## 1. Exporting Executive Milestone Burndown Decks

Generate zero-dependency, self-contained HTML slide presentations displaying milestone burndown velocity, scope stability, and delivery horizons:

```bash
# Export presentation slide deck for milestone M1
uv run spec-ops report burndown --milestone M1 --format deck

# Custom output destination
uv run spec-ops report burndown --milestone M1-MVP --format deck -o dist/briefing.html
```

The exported presentation deck includes:
- **Executive Overview Slide**: Interactive SVG radial progress meters and deliverable burn velocities.
- **Delivery Horizon Gantt Slide**: Visual Gantt delivery tracks with critical path milestones.
- **Persona Value Delivered Matrix**: Customer impact mapping across Alex, Jordan, Morgan, Riley, and Taylor.
- **Codebase Health Metrics**: 0 file limit violations, 100% blackbox frontdoor test pass rate, and mutmut mutation kill score.
- **Keyboard Navigation**: Clean presentation control with Left/Right Arrow keys and Spacebar.

---

## 2. Generating Milestone Executive Briefing Digests

For text-based distribution via email, Slack, or PR descriptions:

```bash
uv run spec-ops report milestone --milestone M1-MVP --format digest
```

---

## 3. Detecting Unanchored Scope Creep

To verify that all completed tasks in the backlog remain anchored to documented milestones in `ROADMAP.md`:

```bash
uv run spec-ops report milestone --check-alignment
```

If unanchored completed tasks are identified, SpecOps outputs an alignment warning table detailing task IDs, titles, target bounded contexts, and authoring commits.

---

## 4. Monitoring Backlog Flow in the Terminal

Launch the interactive 3-column backlog Kanban and JIT buffer telemetry dashboard:

```bash
# Launch interactive terminal flow monitor
uv run spec-ops queue monitor

# Alternative alias
uv run spec-ops backlog flow

# Snapshot mode for CI scripts and non-interactive terminals
uv run spec-ops queue monitor --once
```

### Flow Monitor Keybindings

| Key | Action | Description |
|---|---|---|
| `h` / `l` / `Tab` | Switch Column | Move focus between **Proposed**, **Refined**, and **In-Flight Worktrees** |
| `j` / `k` / Arrows | Navigate | Scroll selection up or down within the active column |
| `r` | Refine Task | Single-keystroke promotion of highlighted proposed task to `refined/` (evaluates DoR) |
| `c` | Claim & Worktree | Single-keystroke provisioning of `.worktrees/task-XXXX` and branch checkout for human IC |
| `q` | Quit | Exit the flow monitor |
